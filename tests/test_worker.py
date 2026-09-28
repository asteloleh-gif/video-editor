from __future__ import annotations

from pathlib import Path

import pytest

from video_editor.worker import _analysis_options, safe_media_path


def test_safe_media_path_stays_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()

    inside = safe_media_path(root, "raw/input.mov")
    assert inside == (root / "raw" / "input.mov").resolve()

    with pytest.raises(ValueError):
        safe_media_path(root, "../outside.mov")


def test_safe_media_path_requires_existing_source(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()

    with pytest.raises(FileNotFoundError):
        safe_media_path(root, "missing.mov", must_exist=True)


def test_analysis_options_are_whitelisted() -> None:
    payload = {
        "vision_step": 0.5,
        "vision_model": "gpt-5.6-luna",
        "mode": "vision",
        "source_path": "raw.mov",
        "output_path": "final.mp4",
        "unexpected": "ignored",
    }

    assert _analysis_options(payload) == {
        "vision_step": 0.5,
        "vision_model": "gpt-5.6-luna",
        "mode": "vision",
    }
