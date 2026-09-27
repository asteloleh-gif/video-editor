from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from . import __version__
from .backend import (
    BackendNotConfigured,
    BackendRequestError,
    SupabaseRestClient,
)
from .final import create_short


app = FastAPI(
    title="Battle Box AutoEditor API",
    version=__version__,
    description="FastAPI control plane for AutoEditor projects, renders, presets and learning feedback.",
)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    target_duration_ms: int | None = Field(default=30_000, gt=0)
    source_provider: str | None = "google_drive"
    source_root: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceCreate(BaseModel):
    provider: str = "google_drive"
    external_id: str | None = None
    file_name: str = Field(min_length=1)
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fps: float | None = Field(default=None, gt=0)
    source_url: str | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    subject: str | None = None
    subject_color: str | None = None
    ai_model: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    source_file_id: UUID
    events: list[EventCreate] = Field(min_length=1, max_length=1000)


class RenderCreate(BaseModel):
    preset_id: UUID | None = None
    status: str = "queued"
    output_provider: str | None = None
    output_external_id: str | None = None
    output_file_name: str | None = None
    output_url: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    codec: str | None = None
    render_meta: dict[str, Any] = Field(default_factory=dict)
    error_text: str | None = None


class FeedbackCreate(BaseModel):
    render_id: UUID | None = None
    event_id: UUID | None = None
    feedback_type: str = Field(min_length=1, max_length=80)
    ai_decision: dict[str, Any] = Field(default_factory=dict)
    user_decision: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class LocalRenderRequest(BaseModel):
    source_file_id: UUID | None = None
    source_path: str
    output_path: str
    preset_id: UUID | None = None
    style_path: str | None = None
    use_whisper: bool = False
    use_remotion: bool = True
    vision_step: float = Field(default=0.5, gt=0)
    vision_model: str | None = None


def _db() -> SupabaseRestClient:
    try:
        return SupabaseRestClient.from_env()
    except BackendNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _translate_backend_error(exc: BackendRequestError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


def _local_render_enabled() -> bool:
    return os.getenv("VIDEO_EDITOR_ALLOW_LOCAL_RENDER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_media_path(value: str, *, must_exist: bool = False) -> Path:
    root_raw = os.getenv("VIDEO_EDITOR_MEDIA_ROOT", "").strip()
    if not root_raw:
        raise HTTPException(
            status_code=503,
            detail="Set VIDEO_EDITOR_MEDIA_ROOT before enabling local rendering.",
        )
    root = Path(root_raw).expanduser().resolve()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()

    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Media path must stay inside VIDEO_EDITOR_MEDIA_ROOT.",
        ) from exc

    if must_exist and not path.is_file():
        raise HTTPException(status_code=404, detail=f"Source file not found: {path.name}")
    return path


def _event_rows_from_project(project_json_path: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(project_json_path).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        source_start = float(event.get("source_start", event.get("start", 0.0)))
        source_end = float(event.get("source_end", event.get("end", source_start)))
        rows.append(
            {
                "event_type": str(event.get("label", "unknown")),
                "start_ms": max(0, round(source_start * 1000)),
                "end_ms": max(0, round(source_end * 1000)),
                "confidence": float(event.get("confidence", 1.0)),
                "payload": {
                    "output_start_sec": event.get("start"),
                    "output_end_sec": event.get("end"),
                },
            }
        )
    return rows


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "battlebox-autoeditor",
        "version": __version__,
        "supabase_configured": SupabaseRestClient.configured(),
        "local_render_enabled": _local_render_enabled(),
    }


@app.get("/v1/presets")
def list_presets(db: SupabaseRestClient = Depends(_db)) -> list[dict[str, Any]]:
    try:
        return db.list_presets()
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc


@app.post("/v1/projects", status_code=201)
def create_project(
    body: ProjectCreate,
    db: SupabaseRestClient = Depends(_db),
) -> dict[str, Any]:
    try:
        return db.create_project(body.model_dump(exclude_none=True))
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc


@app.get("/v1/projects/{project_id}")
def get_project(
    project_id: UUID,
    db: SupabaseRestClient = Depends(_db),
) -> dict[str, Any]:
    try:
        row = db.get_project(str(project_id))
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return row


@app.post("/v1/projects/{project_id}/sources", status_code=201)
def add_source(
    project_id: UUID,
    body: SourceCreate,
    db: SupabaseRestClient = Depends(_db),
) -> dict[str, Any]:
    try:
        return db.add_source(str(project_id), body.model_dump(exclude_none=True))
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc


@app.post("/v1/projects/{project_id}/events", status_code=201)
def add_events(
    project_id: UUID,
    body: EventBatch,
    db: SupabaseRestClient = Depends(_db),
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in body.events:
        if item.end_ms < item.start_ms:
            raise HTTPException(status_code=422, detail="event end_ms must be >= start_ms")
        events.append(item.model_dump(exclude_none=True))
    try:
        return db.add_events(str(project_id), str(body.source_file_id), events)
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc


@app.post("/v1/projects/{project_id}/renders", status_code=201)
def create_render(
    project_id: UUID,
    body: RenderCreate,
    db: SupabaseRestClient = Depends(_db),
) -> dict[str, Any]:
    try:
        return db.create_render(str(project_id), body.model_dump(exclude_none=True, mode="json"))
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc


@app.post("/v1/projects/{project_id}/feedback", status_code=201)
def add_feedback(
    project_id: UUID,
    body: FeedbackCreate,
    db: SupabaseRestClient = Depends(_db),
) -> dict[str, Any]:
    try:
        return db.add_feedback(str(project_id), body.model_dump(exclude_none=True, mode="json"))
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc


@app.post("/v1/projects/{project_id}/render-local", status_code=201)
async def render_local(
    project_id: UUID,
    body: LocalRenderRequest,
    db: SupabaseRestClient = Depends(_db),
) -> dict[str, Any]:
    if not _local_render_enabled():
        raise HTTPException(
            status_code=403,
            detail="Local render endpoint is disabled. Set VIDEO_EDITOR_ALLOW_LOCAL_RENDER=1.",
        )

    source = _safe_media_path(body.source_path, must_exist=True)
    output = _safe_media_path(body.output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    render_row: dict[str, Any]
    try:
        render_row = db.create_render(
            str(project_id),
            {
                "preset_id": str(body.preset_id) if body.preset_id else None,
                "status": "running",
                "output_file_name": output.name,
                "render_meta": {
                    "source_path": str(source),
                    "local_worker": True,
                    "vision_step": body.vision_step,
                },
            },
        )
    except BackendRequestError as exc:
        raise _translate_backend_error(exc) from exc

    render_id = str(render_row["id"])
    kwargs: dict[str, Any] = {
        "style_path": body.style_path,
        "use_whisper": body.use_whisper,
        "use_remotion": body.use_remotion,
        "vision_step": body.vision_step,
    }
    if body.vision_model:
        kwargs["vision_model"] = body.vision_model

    try:
        result = await run_in_threadpool(create_short, source, output, **kwargs)
        event_count = 0
        if body.source_file_id:
            events = _event_rows_from_project(result.project)
            if events:
                db.add_events(
                    str(project_id),
                    str(body.source_file_id),
                    events,
                )
                event_count = len(events)

        complete = db.update_render(
            render_id,
            {
                "status": "complete",
                "output_provider": "local",
                "output_file_name": Path(result.final).name,
                "duration_ms": round(result.duration_final_sec * 1000),
                "width": 1080 if result.graphics == "remotion" else None,
                "height": 1920 if result.graphics == "remotion" else None,
                "codec": "h264",
                "render_meta": {
                    **render_row.get("render_meta", {}),
                    "result": result.to_dict(),
                    "events_persisted": event_count,
                },
            },
        )
        return {"render": complete, "result": result.to_dict()}
    except Exception as exc:
        try:
            db.update_render(render_id, {"status": "failed", "error_text": str(exc)[:4000]})
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}") from exc


def run() -> None:
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("video_editor.api:app", host=host, port=port)


if __name__ == "__main__":
    run()
