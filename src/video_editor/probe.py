from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaInfo:
    path: str
    duration: float
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool


def executable(name: str) -> bool:
    return shutil.which(name) is not None


def _parse_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" in value:
        a, b = value.split("/", 1)
        try:
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(value)
    except ValueError:
        return None


def probe(path: str | Path) -> MediaInfo:
    if not executable("ffprobe"):
        raise RuntimeError("ffprobe not found in PATH")
    source = Path(path).expanduser().resolve()
    cmd = [
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(source),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    if duration <= 0 and video and video.get("duration"):
        duration = float(video["duration"])
    return MediaInfo(
        path=str(source),
        duration=duration,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        fps=_parse_rate(video.get("avg_frame_rate") if video else None),
        has_audio=audio,
    )
