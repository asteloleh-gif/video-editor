"""New story preparation over catalogue assets and the existing approved voices."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
import wave

from .story_jobs import digest, write
from .media_workspace import timestamp, fingerprint


def speech(command, job_id=None, payload=None):
    home = Path.home() / ".local/share/astel-voicebox"
    result = subprocess.run([str(home / "venv/bin/python"), "-m", "video_editor.voicebox_jobs", command, *(["--id", job_id] if job_id else [])],
                            input=json.dumps(payload).encode() if payload else b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40,
                            env={**os.environ, "ASTEL_VOICEBOX_HOME": str(home), "PYTHONPATH": str(home / "openreel/src")})
    if result.returncode:
        raise RuntimeError("Voice service unavailable")
    return json.loads(result.stdout)


def build_story(service, job_id, payload, descriptors):
    folder = service.folder(job_id); public = folder / "public"; public.mkdir(exist_ok=True)
    completed = folder / "render-receipt.json"
    if completed.exists():
        receipt = json.loads(completed.read_text())
        if digest(folder / "props.json") != receipt["props_sha256"] or digest(folder / "video.mp4") != receipt["sha256"]:
            raise ValueError("Completed render receipt changed")
        commit_story(service, job_id, json.loads((folder / "props.json").read_text())["story"], payload)
        return
    parent = service.parent_story(payload) if "parent_story_id" in payload else None
    assets = [service.asset(key) for key in payload["asset_ids"]]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", payload["script"]) if p.strip()]
    scenes = []; audio_segments = []; cursor = 0; fps = 30
    for index, text in enumerate(paragraphs):
        service.cancelled(job_id)
        service.update(job_id, progress=.05 + .4 * index / len(paragraphs), phase=f"Озвучка сцены {index + 1}/{len(paragraphs)}")
        voice_id = str(uuid.uuid5(uuid.UUID(job_id), f"voice-{index}"))
        request = {"id": voice_id, "profile": payload["profile"], "text": text, "project_id": payload["project_id"]}
        value = speech("submit", payload=request)
        deadline = time.monotonic() + 1800
        while value["status"] not in {"ready", "failed", "cancelled"}:
            try:
                service.cancelled(job_id)
            except InterruptedError:
                speech("cancel", voice_id); raise
            if time.monotonic() > deadline:
                speech("cancel", voice_id); raise TimeoutError("Narration timed out")
            time.sleep(1.5); value = speech("resume", voice_id)
        if value["status"] != "ready":
            raise RuntimeError("Narration did not complete")
        receipt = speech("audio", voice_id); source = Path(receipt["path"])
        expected = Path.home() / ".local/share/astel-voicebox/openreel/jobs" / voice_id / "narration.wav"
        if source != expected or source.resolve() != expected or digest(source) != receipt["sha256"]:
            raise ValueError("Narration receipt differs")
        with wave.open(str(source)) as wav:
            params = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
            if params[1] != 2 or params[2] % fps:
                raise ValueError("Unsupported voice audio format")
            samples = wav.getnframes(); frames = math.ceil(samples / params[2] * fps)
            # Pad each scene to a video frame boundary; derive timing from actual
            # audio samples, never guessed words-per-second or fabricated ASR.
            padded_samples = frames * (params[2] // fps)
            audio_segments.append((params, wav.readframes(samples) + b"\0" * ((padded_samples - samples) * params[0] * params[1])))
        asset = assets[index % len(assets)]; media = service.file_receipt(asset["id"])
        name = f"asset-{asset['id']}" + Path(media["path"]).suffix
        target = public / name
        if not target.exists(): shutil.copyfile(media["path"], target)
        if target.is_symlink() or digest(target) != media["sha256"]:
            raise ValueError("Prepared scene media changed")
        scenes.append({"id": f"scene-{index + 1}", "title": text.split(".", 1)[0][:100], "text": text,
                       "from": cursor, "durationInFrames": frames, "src": name, "kind": asset["kind"], "sourceDuration": asset["duration"],
                       "author": asset.get("author") or "", "license": asset.get("license") or "", "sourceUrl": asset.get("source_url") or "",
                       "asset_id": asset["id"], "asset_sha256": asset["sha256"], "voice_job_id": voice_id})
        cursor += frames
    if any(params != audio_segments[0][0] for params, _ in audio_segments):
        raise ValueError("Voice scene formats differ")
    narration = public / "narration.wav"
    with wave.open(str(narration), "wb") as wav:
        channels, width, rate = audio_segments[0][0]; wav.setnchannels(channels); wav.setsampwidth(width); wav.setframerate(rate)
        for _, data in audio_segments: wav.writeframes(data)
    service.update(job_id, progress=.48, phase="Локальные субтитры")
    transcript = folder / "transcript.json"
    if not transcript.exists() or json.loads(transcript.read_text()).get("audio_sha256") != digest(narration):
        service.process(job_id, [str(service.home / "venv/bin/python"), "-m", "video_editor.media_workspace", "asr", "--id", job_id], timeout=600)
    captions = json.loads(transcript.read_text())["segments"]
    # ASR is a review draft. Store its real timestamps and bind it to this audio.
    revision = parent["revision"] + 1 if parent else 1
    story = {"schemaVersion": 1, "id": job_id, "root_id": parent.get("root_id", parent["id"]) if parent else job_id, "revision": revision, "title": payload["title"], "project_id": payload["project_id"], "profile": payload["profile"], "script": payload["script"],
             "fps": fps, "durationInFrames": cursor + 90, "audioSrc": "narration.wav", "audio_sha256": digest(narration), "scenes": scenes,
             "captions": captions, "caption_review": "asr_draft", "status": "rendering", "created_at": timestamp(), "publishing": "review_only"}
    write(folder / "props.json", {"story": story})
    service.update(job_id, progress=.55, phase="Сборка новой истории")
    service.process(job_id, [str(service.home / "bin/node"), str(service.home / "renderer/render.cjs")], timeout=3600,
                    stdin={"jobRoot": str(folder)}, pass_fds=descriptors, cwd=service.home / "renderer", render_progress=True)
    commit_story(service, job_id, story, payload)


def commit_story(service, job_id, story, payload):
    folder = service.folder(job_id)
    parent = service.parent_story(payload) if "parent_story_id" in payload else None
    output = folder / "video.mp4"; info = service.probe(output)
    if abs(info["duration"] - story["durationInFrames"] / story["fps"]) > .3 or (info["width"], info["height"]) != (1080, 1920) or info["codec"] != "h264" or not info["has_audio"]:
        raise ValueError("Rendered duration differs")
    sha = digest(output)
    story.update(status="needs_review", artifact_sha256=sha, artifact_bytes=output.stat().st_size, duration=info["duration"])
    story["digest"] = fingerprint(story)
    write(folder / "story.json", story)
    credits = "# Sources / Astel draft\n\n" + "\n\n".join(f"{s['id']}: {s['author']} · {s['license']}\n{s['sourceUrl']}\nSource SHA-256: {s['asset_sha256']}" for s in story["scenes"])
    (folder / "SOURCES.md").write_text(credits)
    with service.db() as db:
        if parent:
            service.parent_story(payload)
        db.execute("INSERT OR REPLACE INTO stories VALUES(?,?,?,?,?)", (job_id, story["revision"], story["digest"], json.dumps(story, ensure_ascii=False), timestamp()))
    service.update(job_id, result={"story_id": job_id, "revision": story["revision"], "digest": story["digest"], "artifact_sha256": sha, "duration": info["duration"], "project_id": payload["project_id"]})


def story_video(service, story_id):
    with service.db() as db:
        row = db.execute("SELECT data FROM stories WHERE id=?", (story_id,)).fetchone()
    if row is None: raise ValueError("Story not ready")
    data = json.loads(row[0]); source = service.folder(story_id) / "video.mp4"
    if source.is_symlink() or digest(source) != data["artifact_sha256"] or source.stat().st_size > 300 * 1024 * 1024:
        raise ValueError("Rendered bytes changed")
    return {"path": str(source), "sha256": data["artifact_sha256"], "kind": "video", "name": f"Astel-story-{story_id}.mp4"}
