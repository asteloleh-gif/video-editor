from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audio import detect_audio_activity
from .intervals import Interval, filter_short, merge, pad, union
from .motion import detect_motion
from .probe import MediaInfo, probe
from .render import render_intervals
from .vision import DEFAULT_MODEL, VisionDetection, detect_vision_activity


@dataclass
class EditPlan:
    source: MediaInfo
    mode: str
    keep: list[Interval]
    motion_intervals: list[Interval]
    audio_intervals: list[Interval]
    vision_intervals: list[Interval]
    vision_detections: list[VisionDetection]
    vision_summaries: list[str]
    motion_samples: list[tuple[float, float]]
    duration_kept: float
    duration_removed: float
    percent_removed: float

    def to_dict(self) -> dict:
        return {
            "source": asdict(self.source),
            "mode": self.mode,
            "keep": [asdict(i) for i in self.keep],
            "motion_intervals": [asdict(i) for i in self.motion_intervals],
            "audio_intervals": [asdict(i) for i in self.audio_intervals],
            "vision_intervals": [asdict(i) for i in self.vision_intervals],
            "vision_detections": [i.to_dict() for i in self.vision_detections],
            "vision_summaries": self.vision_summaries,
            "motion_samples": self.motion_samples,
            "duration_kept": self.duration_kept,
            "duration_removed": self.duration_removed,
            "percent_removed": self.percent_removed,
        }


def analyze(
    source: str | Path,
    *,
    mode: str = "vision",
    motion_threshold: float = 0.018,
    sample_fps: float = 4.0,
    audio_noise_db: float = -35.0,
    min_silence: float = 0.35,
    merge_gap: float = 0.70,
    margin_before: float = 0.35,
    margin_after: float = 0.90,
    min_segment: float = 0.15,
    vision_model: str = DEFAULT_MODEL,
    vision_step: float = 1.0,
    vision_batch_frames: int = 20,
    vision_overlap_frames: int = 3,
    vision_max_width: int = 480,
    vision_min_confidence: float = 0.45,
    vision_merge_gap: float = 1.25,
) -> EditPlan:
    info = probe(source)
    if info.duration <= 0:
        raise RuntimeError("Could not determine media duration")

    motion_intervals: list[Interval] = []
    motion_samples: list[tuple[float, float]] = []
    audio_intervals: list[Interval] = []
    vision_intervals: list[Interval] = []
    vision_detections: list[VisionDetection] = []
    vision_summaries: list[str] = []

    if mode in {"motion", "hybrid"}:
        motion_intervals, motion_samples = detect_motion(
            source,
            sample_fps=sample_fps,
            threshold=motion_threshold,
        )

    if mode in {"audio", "hybrid"} and info.has_audio:
        audio_intervals = detect_audio_activity(
            source,
            duration=info.duration,
            noise_db=audio_noise_db,
            min_silence=min_silence,
        )

    if mode == "vision":
        vision_intervals, vision_detections, vision_summaries = detect_vision_activity(
            source,
            duration=info.duration,
            model=vision_model,
            step=vision_step,
            batch_frames=vision_batch_frames,
            overlap_frames=vision_overlap_frames,
            max_width=vision_max_width,
            min_confidence=vision_min_confidence,
            merge_gap=vision_merge_gap,
        )

    if mode == "motion":
        keep = motion_intervals
    elif mode == "audio":
        keep = audio_intervals
    elif mode == "hybrid":
        keep = union(motion_intervals, audio_intervals)
    elif mode == "vision":
        keep = vision_intervals
    else:
        raise ValueError(f"Unknown mode: {mode}")

    keep = merge(keep, max_gap=merge_gap)
    keep = filter_short(keep, min_segment)
    keep = pad(keep, margin_before, margin_after, info.duration)

    # Vision should fail loudly rather than silently returning the whole source.
    # That makes a bad semantic detection visible during testing instead of hiding it.
    if not keep and mode == "vision":
        raise RuntimeError(
            "Vision AI found no gameplay ranges. No render was created. "
            "Inspect the sampled scene or retry with --vision-step 0.5."
        )

    # Legacy detector fallback: never silently produce an empty edit.
    if not keep:
        keep = [Interval(0.0, info.duration)]

    kept = round(sum(i.duration for i in keep), 3)
    removed = round(max(0.0, info.duration - kept), 3)
    percent = round((removed / info.duration) * 100.0, 2) if info.duration else 0.0

    return EditPlan(
        source=info,
        mode=mode,
        keep=keep,
        motion_intervals=motion_intervals,
        audio_intervals=audio_intervals,
        vision_intervals=vision_intervals,
        vision_detections=vision_detections,
        vision_summaries=vision_summaries,
        motion_samples=motion_samples,
        duration_kept=kept,
        duration_removed=removed,
        percent_removed=percent,
    )


def save_plan(plan: EditPlan, path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    return target


def process(
    source: str | Path,
    output: str | Path,
    *,
    report: str | Path | None = None,
    **analysis_options,
) -> EditPlan:
    plan = analyze(source, **analysis_options)
    render_intervals(source, output, plan.keep, has_audio=plan.source.has_audio)
    report_path = Path(report) if report else Path(output).with_suffix(".plan.json")
    save_plan(plan, report_path)
    return plan
