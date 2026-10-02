#!/usr/bin/env python3
"""Export a local source into separate scenes using approved JSON time ranges.

Standard library only. Does not import the AI/Whisper/Remotion pipeline or upload
anything. Requires ffprobe and (unless --dry-run) ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
COPY_NOTE = ("Stream copy does not re-encode, but cuts can include material from an "
             "earlier seek/keyframe. Requested bounds are NOT measured actual bounds; "
             "preview each clip before using it.")
EXACT_NOTE = ("Accurate seek with H.264 CRF 16 and AAC 192k re-encoding; NOT lossless. "
              "Cuts are quantized to available frames/audio samples. No scaling or FPS override.")


def seconds(value: Any) -> float:
    """Accept numeric seconds, MM:SS.sss or HH:MM:SS.sss (not frame timecode)."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"Invalid time: {value!r}")
    if isinstance(value, str) and ":" in value:
        parts = value.strip().split(":")
        if len(parts) not in (2, 3) or not all(re.fullmatch(r"\d+", p) for p in parts[:-1]):
            raise ValueError(f"Invalid timecode: {value!r}")
        if not re.fullmatch(r"\d+(?:\.\d+)?", parts[-1]):
            raise ValueError(f"Invalid seconds field: {value!r}")
        values = [float(p) for p in parts]
        if any(v >= 60 for v in values[1:]):
            raise ValueError(f"Timecode field out of range: {value!r}")
        result = sum(v * 60 ** i for i, v in enumerate(reversed(values)))
    else:
        result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Time must be finite and nonnegative: {value!r}")
    return result


def run(command: list[str], timeout: float) -> str:
    proc = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError(f"{Path(command[0]).name} failed ({proc.returncode}): {proc.stderr[-3000:]}")
    return proc.stdout


def probe(path: Path) -> dict[str, Any]:
    raw = json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ], 60))
    streams = raw.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ValueError(f"No video stream: {path.name}")
    duration = seconds(video.get("duration") or raw.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise ValueError(f"No usable video duration: {path.name}")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {"duration_sec": duration, "video": video, "audio": audio}


def validate_plan(data: Any, duration: float, handles: float) -> tuple[str, list[dict]]:
    if not isinstance(data, dict) or data.get("schema_version", 1) != 1:
        raise ValueError("Expected a version-1 JSON object")
    source_id = data.get("source_id")
    if not isinstance(source_id, str) or not SAFE_ID.fullmatch(source_id):
        raise ValueError("source_id must use 1-64 ASCII letters, digits, underscores or hyphens")
    rows = data.get("scenes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("scenes must be a nonempty list")
    if not math.isfinite(handles) or handles < 0:
        raise ValueError("handles must be finite and nonnegative")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each scene must be an object")
        scene_id = row.get("id")
        if not isinstance(scene_id, str) or not SAFE_ID.fullmatch(scene_id):
            raise ValueError(f"Invalid scene id: {scene_id!r}")
        if scene_id.casefold() in seen:
            raise ValueError(f"Duplicate scene id: {scene_id}")
        seen.add(scene_id.casefold())
        start, end = seconds(row.get("start")), seconds(row.get("end"))
        if not 0 <= start < end <= duration:
            raise ValueError(f"{scene_id}: require 0 <= start < end <= {duration:.6f}")
        description = row.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"{scene_id}: description must be text")
        result.append({"id": scene_id, "description": description,
                       "requested_start_sec": start, "requested_end_sec": end,
                       "export_start_sec": max(0, start - handles),
                       "export_end_sec": min(duration, end + handles), "status": "pending"})
    return source_id, result


def check_exact_source(info: dict) -> None:
    video = info["video"]
    if video.get("pix_fmt") not in {"yuv420p", "yuv422p", "yuv444p"}:
        raise ValueError("Exact mode currently supports only 8-bit planar YUV; use copy for other formats")
    if video.get("color_transfer") in {"smpte2084", "arib-std-b67"} or video.get("color_primaries") == "bt2020":
        raise ValueError("HDR/wide-gamut source: use copy; no automatic SDR conversion is allowed")
    rotations = [video.get("tags", {}).get("rotate", 0)]
    rotations += [s.get("rotation", 0) for s in video.get("side_data_list", [])]
    if any(float(r) % 360 for r in rotations):
        raise ValueError("Rotated source: use copy; automatic orientation conversion is not supported")


def command_for(source: Path, target: Path, scene: dict, info: dict, mode: str) -> list[str]:
    start = scene["export_start_sec"]
    duration = scene["export_end_sec"] - start
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-xerror",
           "-ss", f"{start:.9f}", "-noautorotate", "-i", str(source),
           "-t", f"{duration:.9f}", "-map", f"0:{info['video']['index']}"]
    if info["audio"] is not None:
        cmd += ["-map", f"0:{info['audio']['index']}"]
    cmd += ["-map_chapters", "-1"]
    if mode == "copy":
        cmd += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    else:
        cmd += ["-c:v", "libx264", "-crf", "16", "-preset", "medium",
                "-pix_fmt", "+" + info["video"]["pix_fmt"], "-fps_mode", "passthrough"]
        if info["audio"] is not None:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
    if target.suffix.lower() in {".mp4", ".mov", ".m4v"}:
        cmd += ["-movflags", "+faststart"]
    return cmd + [str(target)]


def write_manifest(path: Path, manifest: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def export(source: Path, plan_path: Path, output: Path, *, mode: str,
           handles: float = 0, limit: int = 3, dry_run: bool = False,
           timeout: float = 1800) -> dict:
    if mode not in {"exact", "copy"}:
        raise ValueError("Mode must be exact or copy")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be an integer >= 0 (0 means all)")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    for tool in (["ffprobe"] if dry_run else ["ffprobe", "ffmpeg"]):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} not found on PATH")
    source, plan_path = source.expanduser().resolve(), plan_path.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file() or not plan_path.is_file():
        raise ValueError("Both source video and timing JSON must be existing local files")
    if output.exists():
        raise ValueError("Output directory already exists; choose a NEW directory (no overwrites)")
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    info = probe(source)
    source_id, scenes = validate_plan(data, info["duration_sec"], handles)
    if data.get("source_filename") and data["source_filename"] != source.name:
        raise ValueError("source_filename in timing JSON does not match the selected video")
    if mode == "exact":
        check_exact_source(info)
    total = len(scenes)
    if limit:
        scenes = scenes[:limit]
    suffix = ".mp4" if mode == "exact" else source.suffix.lower()
    if suffix not in {".mp4", ".mov", ".m4v", ".mkv", ".webm"}:
        suffix = ".mkv"
    for scene in scenes:
        scene["file"] = f"{source_id}__{scene['id']}{suffix}"
    stat = source.stat()
    manifest = {"schema_version": 1, "status": "planned" if dry_run else "in_progress",
                "source_id": source_id, "source_file": source.name,
                "source_identity": {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns},
                "source_media": info, "mode": mode,
                "timing": "frame_quantized" if mode == "exact" else "approximate_keyframe_seek",
                "quality_note": EXACT_NOTE if mode == "exact" else COPY_NOTE,
                "handles_sec": handles, "total_in_plan": total,
                "selected_count": len(scenes), "scenes": scenes}
    if dry_run:
        return manifest
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = output / "manifest.json"
    write_manifest(manifest_path, manifest)
    try:
        for i, scene in enumerate(scenes, 1):
            target = output / scene["file"]
            partial = target.with_name(target.stem + ".partial" + target.suffix)
            print(f"[{i}/{len(scenes)}] {scene['id']}", file=sys.stderr, flush=True)
            scene["status"] = "rendering"
            write_manifest(manifest_path, manifest)
            try:
                run(command_for(source, partial, scene, info, mode), timeout)
                rendered = probe(partial)
                expected = scene["export_end_sec"] - scene["export_start_sec"]
                if mode == "exact":
                    fps = info["video"].get("avg_frame_rate", "0/1").split("/")
                    rate = float(fps[0]) / float(fps[1]) if len(fps) == 2 and float(fps[1]) else 0
                    tolerance = max(0.10, 2 / rate) if rate > 0 else 0.25
                    if abs(rendered["duration_sec"] - expected) > tolerance:
                        raise RuntimeError("Output duration differs from requested duration beyond frame tolerance")
                if (rendered["video"].get("width"), rendered["video"].get("height")) != (
                        info["video"].get("width"), info["video"].get("height")):
                    raise RuntimeError("Output video dimensions changed unexpectedly")
                if info["audio"] is not None and rendered["audio"] is None:
                    raise RuntimeError("Output audio stream is missing")
                partial.replace(target)
                scene.update(status="complete", actual_duration_sec=rendered["duration_sec"],
                             size_bytes=target.stat().st_size)
            except BaseException:
                partial.unlink(missing_ok=True)
                scene["status"] = "failed"
                raise
            write_manifest(manifest_path, manifest)
        if (source.stat().st_size, source.stat().st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise RuntimeError("Source changed during export; verify clips before using them")
        manifest["status"] = "complete"
    except BaseException as exc:
        manifest.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed", error=str(exc))
        write_manifest(manifest_path, manifest)
        raise
    write_manifest(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("timings", type=Path)
    parser.add_argument("-o", "--output-dir", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=["exact", "copy"],
                        help="exact: high-quality re-encode; copy: no re-encode, approximate cuts")
    parser.add_argument("--handles", type=float, default=0, help="Extra seconds at each edge")
    parser.add_argument("--limit", type=int, default=3, help="First N scenes; default 3; 0 explicitly selects all")
    parser.add_argument("--timeout", type=float, default=1800, help="Timeout per scene in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Probe and validate only; create no files")
    args = parser.parse_args(argv)
    try:
        result = export(args.source, args.timings, args.output_dir, mode=args.mode,
                        handles=args.handles, limit=args.limit, dry_run=args.dry_run, timeout=args.timeout)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        print("Interrupted. Completed clips are kept; inspect manifest.json.", file=sys.stderr)
        return 130
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
