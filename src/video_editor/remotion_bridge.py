from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .probe import probe


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def remotion_dir() -> Path:
    override = os.getenv("VIDEO_EDITOR_REMOTION_DIR", "").strip()
    return Path(override).expanduser().resolve() if override else project_root() / "remotion"


def remotion_binary() -> Path | None:
    candidate = remotion_dir() / "node_modules" / ".bin" / "remotion"
    if candidate.is_file():
        return candidate
    return None


def remotion_ready() -> bool:
    return bool(shutil.which("node")) and remotion_binary() is not None


def _link_media(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
        return
    except OSError:
        pass
    try:
        target.symlink_to(source)
        return
    except OSError:
        pass
    shutil.copy2(source, target)


def render_with_remotion(
    rough_video: str | Path,
    output: str | Path,
    *,
    payload: dict[str, Any],
    width: int = 1080,
    height: int = 1920,
    fps: float | None = None,
) -> Path:
    """Render the styled short with the bundled Remotion composition."""
    binary = remotion_binary()
    if not binary:
        raise RuntimeError("Remotion is not installed. Run setup_mac.sh.")

    rough = Path(rough_video).expanduser().resolve()
    if not rough.is_file():
        raise FileNotFoundError(rough)
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    info = probe(rough)
    render_fps = float(fps or info.fps or 30.0)
    duration_frames = max(1, int(round(info.duration * render_fps)))

    root = remotion_dir()
    token = uuid.uuid4().hex[:12]
    job_dir = root / "public" / "jobs" / token
    media_path = job_dir / "source.mp4"
    props_path = job_dir / "props.json"
    _link_media(rough, media_path)

    props = dict(payload)
    props.update(
        {
            "videoSrc": f"jobs/{token}/source.mp4",
            "durationInFrames": duration_frames,
            "fps": render_fps,
        }
    )
    props_path.write_text(json.dumps(props, indent=2), encoding="utf-8")

    cmd = [
        str(binary),
        "render",
        "src/index.ts",
        "BattleBoxShort",
        str(target),
        "--props",
        str(props_path),
        "--duration",
        str(duration_frames),
        "--fps",
        f"{render_fps:g}",
        "--width",
        str(width),
        "--height",
        str(height),
        "--codec",
        "h264",
        "--crf",
        "18",
        "--log",
        "warn",
    ]

    try:
        proc = subprocess.run(cmd, cwd=root)
        if proc.returncode != 0:
            raise RuntimeError(f"Remotion render failed with exit code {proc.returncode}")
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    if not target.is_file():
        raise RuntimeError("Remotion reported success but output file is missing")
    return target
