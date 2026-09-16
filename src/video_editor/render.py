from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .intervals import Interval


def _has_encoder(name: str) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        text=True,
        capture_output=True,
    )
    return name in (proc.stdout or "")


def preferred_h264_encoder() -> str:
    return "h264_videotoolbox" if _has_encoder("h264_videotoolbox") else "libx264"


def render_intervals(
    source: str | Path,
    output: str | Path,
    intervals: list[Interval],
    *,
    has_audio: bool,
) -> None:
    if not intervals:
        raise ValueError("No intervals to render")

    src = str(Path(source).expanduser().resolve())
    dst = Path(output).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)

    filters: list[str] = []
    concat_inputs: list[str] = []
    for index, interval in enumerate(intervals):
        filters.append(
            f"[0:v]trim=start={interval.start:.6f}:end={interval.end:.6f},"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        concat_inputs.append(f"[v{index}]")
        if has_audio:
            filters.append(
                f"[0:a]atrim=start={interval.start:.6f}:end={interval.end:.6f},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
            concat_inputs.append(f"[a{index}]")

    if has_audio:
        filters.append(
            "".join(concat_inputs)
            + f"concat=n={len(intervals)}:v=1:a=1[outv][outa]"
        )
    else:
        filters.append(
            "".join(concat_inputs)
            + f"concat=n={len(intervals)}:v=1:a=0[outv]"
        )

    encoder = preferred_h264_encoder()
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-i", src,
        "-filter_complex", ";".join(filters),
        "-map", "[outv]",
    ]
    if has_audio:
        cmd += ["-map", "[outa]"]

    if encoder == "h264_videotoolbox":
        cmd += ["-c:v", encoder, "-b:v", "16M"]
    else:
        cmd += ["-c:v", encoder, "-preset", "veryfast", "-crf", "20"]

    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(dst)]

    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg render failed with exit code {proc.returncode}")
