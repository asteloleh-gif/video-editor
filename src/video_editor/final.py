from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .pipeline import EditPlan, process
from .probe import probe
from .remotion_bridge import remotion_ready, render_with_remotion
from .style import load_style
from .timeline import build_timeline, map_detections, map_transcript_segments
from .transcript import TranscriptResult, transcribe_video, whisper_ready


@dataclass(frozen=True)
class ShortResult:
    input: str
    rough: str
    final: str
    plan: str
    project: str
    graphics: str
    transcript_engine: str | None
    transcript_segments: int
    event_cues: int
    duration_original_sec: float
    duration_final_sec: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RestyleResult:
    input: str
    final: str
    project: str
    graphics: str
    transcript_engine: str | None
    transcript_segments: int
    duration_sec: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _derive_paths(source: Path, output: Path) -> tuple[Path, Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    stem = output.stem
    rough = output.with_name(f"{stem}_rough.mp4")
    plan = rough.with_suffix(".plan.json")
    project = output.with_suffix(".project.json")
    return rough, plan, project


def _build_payload(
    plan: EditPlan,
    transcript: TranscriptResult | None,
    style: dict[str, Any],
) -> dict[str, Any]:
    timeline = build_timeline(plan.keep)
    events = map_detections(plan.vision_detections, timeline)
    captions = map_transcript_segments(transcript.segments, timeline) if transcript else []
    return {
        "version": 1,
        "style": style,
        "events": events,
        "captions": captions,
        "timeline": [segment.to_dict() for segment in timeline],
        "source": {
            "duration": plan.source.duration,
            "width": plan.source.width,
            "height": plan.source.height,
            "fps": plan.source.fps,
            "has_audio": plan.source.has_audio,
        },
        "analysis": {
            "mode": plan.mode,
            "duration_kept": plan.duration_kept,
            "duration_removed": plan.duration_removed,
            "percent_removed": plan.percent_removed,
            "vision_summaries": plan.vision_summaries,
        },
        "transcript": transcript.to_dict() if transcript else None,
    }


def restyle_video(
    source: str | Path,
    output: str | Path,
    *,
    style_path: str | Path | None = None,
    use_whisper: bool = True,
    require_whisper: bool = False,
    use_remotion: bool = True,
    require_remotion: bool = True,
    whisper_model: str | Path | None = None,
    whisper_language: str = "auto",
) -> RestyleResult:
    """Keep the existing edit/audio intact and apply only the visual layer."""
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    final_path = Path(output).expanduser().resolve()
    final_path.parent.mkdir(parents=True, exist_ok=True)
    project_path = final_path.with_suffix(".project.json")

    info = probe(source_path)
    style = load_style(style_path)

    transcript: TranscriptResult | None = None
    if use_whisper and info.has_audio:
        if whisper_ready(whisper_model):
            transcript = transcribe_video(
                source_path,
                model_path=whisper_model,
                language=whisper_language,
                max_len=int(style.get("caption", {}).get("max_chars", 34)),
            )
        elif require_whisper:
            raise RuntimeError("Whisper is required but whisper-cli/model is not ready. Run setup_mac.sh.")
        else:
            print("[video-editor] Whisper unavailable; continuing without captions.", file=sys.stderr)

    captions = [segment.to_dict() for segment in transcript.segments] if transcript else []
    payload = {
        "version": 1,
        "style": style,
        "events": [],
        "captions": captions,
        "timeline": [],
        "source": {
            "duration": info.duration,
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "has_audio": info.has_audio,
        },
        "analysis": {
            "mode": "restyle-existing",
            "cuts_changed": False,
            "audio_changed": False,
        },
        "transcript": transcript.to_dict() if transcript else None,
    }
    project_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if use_remotion:
        if remotion_ready():
            render_with_remotion(
                source_path,
                final_path,
                payload=payload,
                width=1080,
                height=1920,
                fps=info.fps or 30.0,
            )
            graphics_mode = "remotion"
        elif require_remotion:
            raise RuntimeError("Remotion is required but is not installed. Run setup_mac.sh.")
        else:
            shutil.copy2(source_path, final_path)
            graphics_mode = "copy-only"
    else:
        shutil.copy2(source_path, final_path)
        graphics_mode = "copy-only"

    return RestyleResult(
        input=str(source_path),
        final=str(final_path),
        project=str(project_path),
        graphics=graphics_mode,
        transcript_engine=transcript.engine if transcript else None,
        transcript_segments=len(captions),
        duration_sec=info.duration,
    )


def create_short(
    source: str | Path,
    output: str | Path,
    *,
    style_path: str | Path | None = None,
    use_whisper: bool = True,
    require_whisper: bool = False,
    use_remotion: bool = True,
    require_remotion: bool = False,
    whisper_model: str | Path | None = None,
    whisper_language: str = "auto",
    **analysis_options: Any,
) -> ShortResult:
    """End-to-end Battle Box short creation."""
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    final_path = Path(output).expanduser().resolve()
    rough_path, plan_path, project_path = _derive_paths(source_path, final_path)

    plan = process(source_path, rough_path, report=plan_path, **analysis_options)
    style = load_style(style_path)

    transcript: TranscriptResult | None = None
    if use_whisper and plan.source.has_audio:
        if whisper_ready(whisper_model):
            transcript = transcribe_video(
                source_path,
                model_path=whisper_model,
                language=whisper_language,
                max_len=int(style.get("caption", {}).get("max_chars", 42)),
            )
        elif require_whisper:
            raise RuntimeError("Whisper is required but whisper-cli/model is not ready. Run setup_mac.sh.")
        else:
            print("[video-editor] Whisper unavailable; continuing without captions.", file=sys.stderr)

    payload = _build_payload(plan, transcript, style)
    project_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if use_remotion:
        if remotion_ready():
            render_with_remotion(
                rough_path,
                final_path,
                payload=payload,
                width=1080,
                height=1920,
                fps=plan.source.fps or 30.0,
            )
            graphics_mode = "remotion"
        elif require_remotion:
            raise RuntimeError("Remotion is required but is not installed. Run setup_mac.sh.")
        else:
            print("[video-editor] Remotion unavailable; final is the clean FFmpeg rough cut.", file=sys.stderr)
            shutil.copy2(rough_path, final_path)
            graphics_mode = "ffmpeg-only"
    else:
        shutil.copy2(rough_path, final_path)
        graphics_mode = "ffmpeg-only"

    return ShortResult(
        input=str(source_path),
        rough=str(rough_path),
        final=str(final_path),
        plan=str(plan_path),
        project=str(project_path),
        graphics=graphics_mode,
        transcript_engine=transcript.engine if transcript else None,
        transcript_segments=len(transcript.segments) if transcript else 0,
        event_cues=len(payload["events"]),
        duration_original_sec=plan.source.duration,
        duration_final_sec=plan.duration_kept,
    )
