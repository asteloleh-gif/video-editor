#!/usr/bin/env python3
"""Export an existing timing map into separate clips; Python stdlib + FFmpeg only.

Run from any checkout (no pip install or AI key required):
  python3 scripts/export_scenes.py input.mp4 --timings scenes.json -o output/scenes --dry-run
  python3 scripts/export_scenes.py input.mp4 --timings scenes.json -o output/scenes

JSON: {"scenes": [{"id": "scene_001", "start": "00:01.000", "end": 3.0,
                     "description": "Approved description"}]}
Times are seconds from the beginning of the file, NOT SMPTE frame timecode.
The default copy mode preserves encoded media but NOT exact cut boundaries.
Use --mode precise for re-encoded SDR H.264/AAC, with frame-level cut accuracy.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExportError(ValueError):
    """An invalid plan, unsupported source, or failed export."""


def seconds(value: Any) -> float:
    """Accept numeric seconds, MM:SS.mmm or HH:MM:SS.mmm, never frame notation."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ExportError(f"Invalid timestamp: {value!r}")
    try:
        if isinstance(value, str) and ":" in value:
            parts = value.strip().split(":")
            if len(parts) not in (2, 3) or not all(re.fullmatch(r"\d+", p) for p in parts[:-1]):
                raise ValueError
            if not re.fullmatch(r"\d+(?:\.\d+)?", parts[-1]):
                raise ValueError
            fields = [float(p) for p in parts]
            if not 0 <= fields[-1] < 60 or (len(fields) == 3 and not 0 <= fields[1] < 60):
                raise ValueError
            result = 0.0
            for field in fields:
                result = result * 60 + field
        else:
            result = float(value)
    except (ValueError, OverflowError):
        raise ExportError(f"Invalid timestamp: {value!r}") from None
    if not math.isfinite(result) or result < 0:
        raise ExportError(f"Timestamp must be finite and non-negative: {value!r}")
    return result


def run(command: list[str], timeout: float) -> str:
    try:
        completed = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                   text=True, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ExportError(f"Timed out after {timeout:g}s: {command[0]}") from None
    except subprocess.CalledProcessError as exc:
        raise ExportError(f"{command[0]} failed:\n{exc.stderr[-3000:]}") from None
    return completed.stdout


def probe(source: Path) -> dict[str, Any]:
    info = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", str(source)], 60))
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ExportError("Source has no video stream.")
    duration = seconds(video.get("duration") or info.get("format", {}).get("duration"))
    if duration <= 0:
        raise ExportError("Source duration must be positive.")
    return {"duration": duration, "video": video,
            "has_audio": any(s.get("codec_type") == "audio" for s in info.get("streams", []))}


def read_scenes(path: Path, duration: float, handle: float) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("scenes") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ExportError("Timing JSON must contain a non-empty scenes array.")
    if not math.isfinite(handle) or handle < 0:
        raise ExportError("Handle must be finite and non-negative.")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ExportError("Every scene must be an object.")
        scene_id = row.get("id")
        if not isinstance(scene_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", scene_id):
            raise ExportError("Scene ID must be 1-80 ASCII letters, digits, '-' or '_'.")
        if scene_id.casefold() in seen:
            raise ExportError(f"Duplicate scene ID (case-insensitive): {scene_id}")
        seen.add(scene_id.casefold())
        start, end = seconds(row.get("start")), seconds(row.get("end"))
        if not start < end <= duration:
            raise ExportError(f"{scene_id}: require 0 <= start < end <= source duration ({duration:g}s).")
        description = row.get("description", "")
        if not isinstance(description, str):
            raise ExportError(f"{scene_id}: description must be a string.")
        cut_start, cut_end = max(0.0, start - handle), min(duration, end + handle)
        result.append({"id": scene_id, "description": description,
                       "requested_start_sec": start, "requested_end_sec": end,
                       "export_start_sec": cut_start, "export_end_sec": cut_end})
    return result


def command_for(source: Path, target: Path, scene: dict[str, Any], mode: str,
                video_index: int = 0) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
               "-ss", f"{scene['export_start_sec']:.9f}", "-i", str(source),
               "-t", f"{scene['export_end_sec'] - scene['export_start_sec']:.9f}",
               "-map", f"0:{video_index}", "-map", "0:a:0?", "-sn", "-dn", "-map_chapters", "-1"]
    if mode == "copy":
        command += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    else:
        command += ["-c:v", "libx264", "-crf", "16", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    return command + [str(target)]


def write_manifest(target: Path, payload: dict[str, Any]) -> None:
    # Output directory is exclusively owned by this run; publish JSON atomically.
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(target)


def export(source: Path, timings: Path, output: Path, *, mode: str = "copy",
           handle: float = 0.0, limit: int | None = None, dry_run: bool = False,
           timeout: float = 1800.0) -> dict[str, Any]:
    source, timings, output = (p.expanduser().resolve() for p in (source, timings, output))
    if not source.is_file() or not timings.is_file():
        raise ExportError("Both a local source video and a timing JSON file are required.")
    if mode not in ("copy", "precise"):
        raise ExportError("Mode must be copy or precise.")
    if limit is not None and (isinstance(limit, bool) or limit < 1):
        raise ExportError("Limit must be at least 1.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ExportError("Timeout must be finite and positive.")
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise ExportError(f"Missing {binary}; install FFmpeg on the execution computer.")
    media = probe(source)
    scenes = read_scenes(timings, media["duration"], handle)
    if limit is not None:
        scenes = scenes[:limit]
    video = media["video"]
    # Never silently turn HDR/10-bit into 8-bit SDR. Copy remains available.
    if mode == "precise" and (video.get("pix_fmt") not in {"yuv420p", "yuvj420p"}
                              or video.get("color_transfer") in {"smpte2084", "arib-std-b67"}):
        raise ExportError("Precise mode supports 8-bit SDR yuv420p only; use copy for this source.")
    suffix = ".mkv" if mode == "copy" else ".mp4"
    for scene in scenes:
        scene.update({"file": scene["id"] + suffix, "status": "planned"})
    warning = ("Stream copy does not re-encode media, but cut boundaries and core offset are "
               "NOT frame-accurate; inspect clips before use." if mode == "copy" else
               "Video/audio are re-encoded (H.264 CRF 16 / AAC 192k); this is NOT lossless.")
    stat = source.stat()
    manifest = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                "status": "planned", "source": {"file": source.name, "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns, "duration_sec": media["duration"],
                "video_codec": video.get("codec_name"), "width": video.get("width"),
                "height": video.get("height"), "pix_fmt": video.get("pix_fmt")},
                "mode": mode, "handle_sec": handle, "warning": warning, "scenes": scenes}
    if dry_run:
        return manifest
    # Require a NEW directory. No deletion, overwrites, AI calls, or Drive uploads.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    manifest_path = output / "manifest.json"
    manifest["status"] = "running"
    write_manifest(manifest_path, manifest)
    for index, scene in enumerate(scenes, 1):
        temp = output / ("." + scene["id"] + ".partial" + suffix)
        try:
            scene["status"] = "running"
            write_manifest(manifest_path, manifest)
            print(f"[{index}/{len(scenes)}] {scene['id']}", file=sys.stderr, flush=True)
            run(command_for(source, temp, scene, mode, int(video["index"])), timeout)
            actual = probe(temp)
            scene["actual_duration_sec"] = actual["duration"]
            if mode == "precise":
                scene["core_offset_sec"] = scene["requested_start_sec"] - scene["export_start_sec"]
            temp.rename(output / scene["file"])
            scene["status"] = "complete"
            write_manifest(manifest_path, manifest)
        except (Exception, KeyboardInterrupt) as exc:
            temp.unlink(missing_ok=True)
            scene["status"] = "failed"
            scene["error"] = str(exc) or "Interrupted"
            manifest["status"] = "failed"
            write_manifest(manifest_path, manifest)
            raise
    manifest["status"] = "complete"
    write_manifest(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--timings", type=Path, required=True)
    parser.add_argument("-o", "--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("copy", "precise"), default="copy")
    parser.add_argument("--handle", type=float, default=0.0, help="Extra seconds on EACH side; may cross a scene boundary")
    parser.add_argument("--limit", type=int, help="Export only the first N approved scenes")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print plan without creating files")
    parser.add_argument("--timeout", type=float, default=1800, help="Maximum seconds PER clip")
    args = parser.parse_args(argv)
    try:
        result = export(args.video, args.timings, args.output_dir, mode=args.mode,
                        handle=args.handle, limit=args.limit, dry_run=args.dry_run, timeout=args.timeout)
    except KeyboardInterrupt:
        print("Interrupted; inspect the partial manifest before retrying with a NEW output directory.", file=sys.stderr)
        return 130
    except (ExportError, OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
