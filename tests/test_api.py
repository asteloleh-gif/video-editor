from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from video_editor.api import _event_rows_from_project, _safe_media_path, app


def test_health_without_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("VIDEO_EDITOR_ALLOW_LOCAL_RENDER", raising=False)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["supabase_configured"] is False
    assert payload["local_render_enabled"] is False


def test_db_route_returns_503_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    client = TestClient(app)
    response = client.get("/v1/presets")

    assert response.status_code == 503
    assert "SUPABASE_URL" in response.json()["detail"]


def test_safe_media_path_rejects_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "media"
    root.mkdir()
    monkeypatch.setenv("VIDEO_EDITOR_MEDIA_ROOT", str(root))

    with pytest.raises(HTTPException) as exc:
        _safe_media_path("../outside.mp4")

    assert exc.value.status_code == 400


def test_event_rows_from_project(tmp_path: Path) -> None:
    project = tmp_path / "render.project.json"
    project.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "label": "score",
                        "confidence": 0.91,
                        "start": 2.0,
                        "end": 2.5,
                        "source_start": 8.25,
                        "source_end": 8.8,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = _event_rows_from_project(str(project))

    assert rows == [
        {
            "event_type": "score",
            "start_ms": 8250,
            "end_ms": 8800,
            "confidence": 0.91,
            "payload": {
                "output_start_sec": 2.0,
                "output_end_sec": 2.5,
            },
        }
    ]
