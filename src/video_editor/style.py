from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_STYLE: dict[str, Any] = {
    "name": "battle-box",
    "accent": "#D7FF35",
    "danger": "#FF5D5D",
    "text": "#FFFFFF",
    "panel": "rgba(8, 12, 10, 0.88)",
    "shadow": "rgba(0, 0, 0, 0.55)",
    "brand": "BATTLE BOX",
    "show_brand": True,
    "show_attempt_counter": True,
    "show_score_counter": True,
    "caption": {
        "enabled": True,
        "max_chars": 42,
        "font_size": 64,
        "bottom": 150,
    },
    "event_badge": {
        "enabled": True,
        "font_size": 90,
        "top": 180,
    },
    "reaction_zoom": 1.045,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def default_style_path() -> Path:
    return Path(__file__).resolve().parents[2] / "styles" / "battle_box.json"


def load_style(path: str | Path | None = None) -> dict[str, Any]:
    """Load a style preset while keeping sensible defaults for missing fields."""
    candidate = Path(path).expanduser() if path else default_style_path()
    if not candidate.is_file():
        return deepcopy(DEFAULT_STYLE)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Style file must contain a JSON object: {candidate}")
    return _deep_merge(DEFAULT_STYLE, payload)
