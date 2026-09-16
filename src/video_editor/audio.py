from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .intervals import Interval, complement

_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")


def detect_audio_activity(
    path: str | Path,
    *,
    duration: float,
    noise_db: float = -35.0,
    min_silence: float = 0.35,
) -> list[Interval]:
    """Return non-silent intervals using FFmpeg silencedetect."""
    source = str(Path(path).expanduser().resolve())
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", source,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    log = proc.stderr or ""

    silence: list[Interval] = []
    pending_start: float | None = None
    for line in log.splitlines():
        start_match = _SILENCE_START.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = _SILENCE_END.search(line)
        if end_match and pending_start is not None:
            end = float(end_match.group(1))
            if end > pending_start:
                silence.append(Interval(pending_start, min(duration, end)))
            pending_start = None

    if pending_start is not None and pending_start < duration:
        silence.append(Interval(pending_start, duration))

    return complement(silence, duration)
