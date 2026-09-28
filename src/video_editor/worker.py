from __future__ import annotations

import argparse
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .final import create_short
from .pipeline import analyze, save_plan


@dataclass(frozen=True)
class WorkerSettings:
    api_base_url: str
    api_token: str
    media_root: Path
    worker_id: str
    poll_seconds: float = 5.0
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        base = os.getenv("AUTOEDITOR_API_BASE_URL", "").strip().rstrip("/")
        token = os.getenv("AUTOEDITOR_API_TOKEN", "").strip()
        media_root_raw = os.getenv("VIDEO_EDITOR_MEDIA_ROOT", "").strip()
        if not base:
            raise RuntimeError("Set AUTOEDITOR_API_BASE_URL for the worker.")
        if not token:
            raise RuntimeError("Set AUTOEDITOR_API_TOKEN for the worker.")
        if not media_root_raw:
            raise RuntimeError("Set VIDEO_EDITOR_MEDIA_ROOT for the worker.")
        media_root = Path(media_root_raw).expanduser().resolve()
        media_root.mkdir(parents=True, exist_ok=True)
        return cls(
            api_base_url=base,
            api_token=token,
            media_root=media_root,
            worker_id=os.getenv("AUTOEDITOR_WORKER_ID", "").strip()
            or socket.gethostname(),
            poll_seconds=float(os.getenv("AUTOEDITOR_WORKER_POLL_SEC", "5")),
            timeout_seconds=float(os.getenv("AUTOEDITOR_WORKER_TIMEOUT_SEC", "60")),
        )


def safe_media_path(
    root: Path,
    value: str,
    *,
    must_exist: bool = False,
) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Worker media paths must stay inside VIDEO_EDITOR_MEDIA_ROOT.") from exc
    if must_exist and not path.is_file():
        raise FileNotFoundError(path)
    return path


def _request(
    settings: WorkerSettings,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {"Authorization": f"Bearer {settings.api_token}"}
    url = f"{settings.api_base_url}{path}"
    with httpx.Client(timeout=settings.timeout_seconds) as client:
        response = client.request(method, url, json=payload, headers=headers)
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def claim_next_job(settings: WorkerSettings) -> dict[str, Any] | None:
    payload = _request(
        settings,
        "POST",
        "/v1/jobs/claim",
        payload={"worker_id": settings.worker_id},
    )
    if not payload:
        return None
    return payload.get("job")


def _analysis_options(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "mode",
        "motion_threshold",
        "sample_fps",
        "audio_noise_db",
        "min_silence",
        "merge_gap",
        "margin_before",
        "margin_after",
        "min_segment",
        "vision_model",
        "vision_step",
        "vision_batch_frames",
        "vision_overlap_frames",
        "vision_max_width",
        "vision_min_confidence",
        "vision_merge_gap",
    }
    return {key: payload[key] for key in allowed if key in payload}


def execute_job(job: dict[str, Any], settings: WorkerSettings) -> dict[str, Any]:
    payload = dict(job.get("payload") or {})
    source_value = str(payload.get("source_path") or "").strip()
    if not source_value:
        raise ValueError("Job payload needs source_path.")
    source = safe_media_path(settings.media_root, source_value, must_exist=True)
    analysis_options = _analysis_options(payload)

    job_type = str(job.get("job_type") or "")
    if job_type == "analyze":
        plan = analyze(source, **analysis_options)
        plan_file = None
        if payload.get("plan_path"):
            plan_file = safe_media_path(
                settings.media_root,
                str(payload["plan_path"]),
            )
            plan_file.parent.mkdir(parents=True, exist_ok=True)
            save_plan(plan, plan_file)
        return {
            "job_type": "analyze",
            "source": str(source),
            "plan_file": str(plan_file) if plan_file else None,
            "plan": plan.to_dict(),
        }

    if job_type == "create_short":
        output_value = str(payload.get("output_path") or "").strip()
        if not output_value:
            raise ValueError("create_short job payload needs output_path.")
        output = safe_media_path(settings.media_root, output_value)
        output.parent.mkdir(parents=True, exist_ok=True)

        style_path = None
        if payload.get("style_path"):
            style_path = safe_media_path(
                settings.media_root,
                str(payload["style_path"]),
                must_exist=True,
            )

        result = create_short(
            source,
            output,
            style_path=style_path,
            use_whisper=bool(payload.get("use_whisper", False)),
            require_whisper=bool(payload.get("require_whisper", False)),
            use_remotion=bool(payload.get("use_remotion", True)),
            require_remotion=bool(payload.get("require_remotion", False)),
            whisper_model=payload.get("whisper_model"),
            whisper_language=str(payload.get("whisper_language", "auto")),
            **analysis_options,
        )
        return {
            "job_type": "create_short",
            "source": str(source),
            "result": result.to_dict(),
        }

    raise ValueError(f"Unsupported job_type: {job_type!r}")


def finish_job(
    settings: WorkerSettings,
    job_id: str,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    endpoint = "fail" if error else "complete"
    payload: dict[str, Any] = {
        "worker_id": settings.worker_id,
        "result": result or {},
    }
    if error:
        payload["error_text"] = error[:4000]
    return _request(
        settings,
        "POST",
        f"/v1/jobs/{job_id}/{endpoint}",
        payload=payload,
    )


def run_once(settings: WorkerSettings) -> bool:
    job = claim_next_job(settings)
    if not job:
        return False

    job_id = str(job["id"])
    try:
        result = execute_job(job, settings)
        finish_job(settings, job_id, result=result)
        print(f"[autoeditor-worker] completed {job_id}")
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        try:
            finish_job(settings, job_id, error=message)
        finally:
            print(f"[autoeditor-worker] failed {job_id}: {message}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="video-editor-worker",
        description="Local Astel AutoEditor worker for Supabase/Railway queued jobs.",
    )
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit.")
    args = parser.parse_args()

    settings = WorkerSettings.from_env()
    if args.once:
        run_once(settings)
        return

    print(
        f"[autoeditor-worker] worker={settings.worker_id} "
        f"root={settings.media_root} poll={settings.poll_seconds}s"
    )
    while True:
        worked = run_once(settings)
        if not worked:
            time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
