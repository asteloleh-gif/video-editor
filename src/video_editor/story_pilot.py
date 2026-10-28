"""Reviewable topic-to-video pilot: receipts, ASR scene anchors and local render props.

Source discovery/selection is an agent review step. This module does not publish,
select licenses automatically, or send voice/audio to a network service.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import wave


def normalized(text):
    return " ".join(re.sub(r"[^a-zа-я0-9 ]", " ", text.lower().replace("ё", "е")).split())


def contained(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Asset path leaves the raw media folder")
    return path


def acquire_reviewed_assets(brief, raw):
    """Download only named Commons files with pre-reviewed licenses and pinned bytes.

    No cookies, keys, provider switching or automatic retry after rate limiting.
    """
    import os
    import tempfile
    from urllib.error import HTTPError
    from urllib.parse import quote
    from urllib.request import Request, build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("Media redirects require a new source review")
    if not 1 <= len(brief["assets"]) <= 16:
        raise ValueError("Pilot source count must be between 1 and 16")
    raw.mkdir(parents=True, exist_ok=True)
    receipts = []
    for asset in brief["assets"]:
        if asset["license"] not in ("CC-BY-2.0", "CC-BY-4.0", "CC0-1.0", "PUBLIC-DOMAIN"):
            raise ValueError("A reviewed license is required before acquisition")
        name = asset["title"].replace(" ", "_")
        if "/" in name or "\\" in name or not name.lower().endswith((".jpg", ".png", ".webm", ".mp4")):
            raise ValueError("Expected a reviewed Commons filename")
        target = contained(raw, asset["raw"])
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != asset["sha256"]:
                raise ValueError("Preserving existing source with different bytes")
            receipts.append({"id":asset["id"], "reused":True})
            continue
        key = hashlib.md5(name.encode()).hexdigest()
        url = f"https://upload.wikimedia.org/wikipedia/commons/{key[0]}/{key[:2]}/{quote(name)}"
        request = Request(url, headers={"User-Agent":"AstelStoryPilot/0.1 (https://github.com/asteloleh-gif/video-editor)"})
        temporary = None
        try:
            with build_opener(NoRedirect()).open(request, timeout=45) as response, tempfile.NamedTemporaryFile(dir=raw, delete=False) as stream:
                temporary = Path(stream.name)
                total = 0
                while chunk := response.read(128*1024):
                    total += len(chunk)
                    if total > 40*1024*1024:
                        raise ValueError("Source exceeds the 40 MiB pilot limit")
                    stream.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != asset["sha256"]:
                raise ValueError("Downloaded bytes differ from the reviewed source")
            os.replace(temporary, target)
            receipts.append({"id":asset["id"], "reused":False, "bytes":total, "sha256":asset["sha256"]})
        except HTTPError as error:
            if error.code == 429:
                raise RuntimeError("Source rate limited; stop and respect Retry-After: " + str(error.headers.get("Retry-After", "not specified"))) from None
            raise
        finally:
            if temporary and temporary.exists(): temporary.unlink()
    return receipts


def validate_assets(brief, raw):
    seen = set()
    for asset in brief["assets"]:
        if asset["id"] in seen or not re.fullmatch(r"[a-z0-9-]+", asset["id"]):
            raise ValueError("Asset IDs must be unique safe names")
        seen.add(asset["id"])
        if asset["kind"] not in ("video", "image"):
            raise ValueError("Unsupported source media kind")
        if asset["license"] not in ("CC-BY-2.0", "CC-BY-4.0", "CC0-1.0", "PUBLIC-DOMAIN"):
            raise ValueError("This pilot requires reviewed attribution-only or public-domain media")
        if not asset.get("source", "").startswith("https://") or not asset.get("author") or not asset.get("reason"):
            raise ValueError("Missing reviewed source, author or selection reason")
        path = contained(raw, asset["raw"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError(f"Source bytes changed: {asset['id']}")
    if len(brief["scenes"]) != 7:
        raise ValueError("The current pilot template has seven authored scenes")
    for scene in brief["scenes"]:
        if scene.get("asset") and scene["asset"] not in seen:
            raise ValueError("Scene references an unknown asset")


def align_scenes(scenes, segments, duration):
    """Use reviewed textual anchors in real ASR; no proportional timing fallback."""
    starts, after = [0.0], 0
    for scene in scenes[1:]:
        match = None
        for index in range(after, len(segments)):
            text = normalized(" ".join(s["text"] for s in segments[index:index+2]))
            if any(normalized(anchor) in text for anchor in scene["anchor"]):
                # Prefer the segment containing the start of the anchor itself.
                current = normalized(segments[index]["text"])
                anchor_first = [normalized(a).split()[0] for a in scene["anchor"]]
                if not any(first in current.split() for first in anchor_first):
                    continue
                match = index
                break
        if match is None:
            raise ValueError(f"No verified spoken anchor for scene {scene['id']}")
        start = float(segments[match]["start"])
        if not math.isfinite(start) or start <= starts[-1] or start >= duration:
            raise ValueError("Spoken scene boundaries overlap or leave narration")
        starts.append(start)
        after = match + 1
    return [{**scene, "start": start, "end": (starts[i+1] if i+1 < len(starts) else duration),
             "timing_source": "local_whisper_anchor"} for i, (scene, start) in enumerate(zip(scenes, starts))]


def prepare(brief_path, output, public):
    brief = json.loads(brief_path.read_text())
    raw = output / "raw"
    validate_assets(brief, raw)
    narration = output / "narration.wav"
    with wave.open(str(narration)) as audio:
        duration = audio.getnframes() / audio.getframerate()
    transcript = json.loads((output / "transcript.json").read_text())
    scenes = align_scenes(brief["scenes"], transcript["segments"], duration)
    reviewed = output / "captions-reviewed.json"
    captions = transcript["segments"]
    if reviewed.exists():
        correction = json.loads(reviewed.read_text())
        if correction["audio_sha256"] != hashlib.sha256(narration.read_bytes()).hexdigest():
            raise ValueError("Caption corrections belong to a different narration")
        captions = correction["segments"]
    previous_end = 0.0
    for caption in captions:
        a, b = caption["start"], caption["end"]
        if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (a,b)) or not previous_end <= a < b <= duration or not caption["text"].strip():
            raise ValueError("Invalid caption timing")
        previous_end = b
    public.mkdir(parents=True, exist_ok=True)
    prefix = f"jobs/{brief['id']}"
    shutil.copyfile(narration, public / "narration.wav")
    for asset in brief["assets"]:
        source = contained(raw, asset["raw"])
        target = public / (asset["id"] + "-" + asset["sha256"][:12] + (".mp4" if asset["kind"] == "video" else ".jpg"))
        if asset["kind"] == "video":
            if not target.exists():
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source), "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)], check=True)
            metadata = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(target)], text=True))
            asset["media_duration"] = float(metadata["format"]["duration"])
        else:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", "scale=1920:-2:force_original_aspect_ratio=decrease", "-frames:v", "1", str(target)], check=True)
        asset["local_src"] = f"{prefix}/{target.name}"
    asset_by_id = {a["id"]: a for a in brief["assets"]}
    for scene in scenes:
        if scene.get("asset"):
            asset = asset_by_id[scene["asset"]]
            scene["media"] = asset
            trim = scene.get("trim_start", 0)
            if not isinstance(trim, (int,float)) or not math.isfinite(trim) or trim < 0:
                raise ValueError("Invalid source trim")
            if asset["kind"] == "video" and trim + scene["end"] - scene["start"] > asset["media_duration"]:
                raise ValueError(f"Selected source range is too short: {scene['id']}")
    story = {"title": brief["topic"], "id": brief["id"], "duration": duration + 3, "narrationDuration": duration,
             "audioSrc": f"{prefix}/narration.wav", "scenes": scenes, "captions": captions,
             "assets": brief["assets"], "facts": brief["facts"], "publishing": "review_only"}
    payload = {"story": story}
    (output / "props.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (public / "props.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    credits = ["# Sources and attribution", "", "Local review draft. Narration: owner's authorized Voicebox profile.", ""]
    for asset in brief["assets"]:
        credits += [f"## {asset['title']}", f"Author: {asset['author']}", f"Source: {asset['source']}",
                    f"License: {asset['license']} — {asset.get('license_url', '')}", f"Changes: {asset['changes']}",
                    f"Selection: {asset['reason']}", f"SHA-256: {asset['sha256']}", ""]
    credits += ["## Factual sources", *[f"- {f['claim']}: {f['url']}" for f in brief["facts"]]]
    (output / "SOURCES.md").write_text("\n".join(credits) + "\n")
    def stamp(seconds):
        ms = round(seconds * 1000); return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
    srt = "\n\n".join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(story["captions"]))
    (output / "captions.srt").write_text(srt + "\n")
    return story


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--brief", type=Path, required=True)
    p.add_argument("--acquire-only", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--public", type=Path, required=True)
    args = p.parse_args()
    if args.acquire_only:
        print(json.dumps(acquire_reviewed_assets(json.loads(args.brief.read_text()), args.output / "raw")))
        return
    story = prepare(args.brief, args.output, args.public)
    print(json.dumps({"duration": story["duration"], "scenes": len(story["scenes"]), "captions": len(story["captions"])}))


if __name__ == "__main__":
    main()
