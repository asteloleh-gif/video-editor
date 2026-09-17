from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from .pipeline import EditPlan


_COMMON_FPS = {
    23.976: Fraction(24000, 1001),
    24.0: Fraction(24, 1),
    25.0: Fraction(25, 1),
    29.97: Fraction(30000, 1001),
    30.0: Fraction(30, 1),
    50.0: Fraction(50, 1),
    59.94: Fraction(60000, 1001),
    60.0: Fraction(60, 1),
}


def _fps_fraction(value: float | None) -> Fraction:
    if not value or value <= 0:
        return Fraction(30, 1)
    for common, exact in _COMMON_FPS.items():
        if abs(value - common) < 0.02:
            return exact
    return Fraction(value).limit_denominator(1001)


def _frame_duration(fps: Fraction) -> Fraction:
    return Fraction(fps.denominator, fps.numerator)


def _frame_count(seconds: float, fps: Fraction) -> int:
    return max(0, round(float(seconds) * float(fps)))


def _fcpx_frames(frames: int, fps: Fraction) -> str:
    value = max(0, int(frames)) * _frame_duration(fps)
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def _fcpx_time(seconds: float, fps: Fraction) -> str:
    return _fcpx_frames(_frame_count(seconds, fps), fps)


def write_fcpxml(
    plan: EditPlan,
    output: str | Path,
    *,
    project_name: str | None = None,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Write a frame-aligned FCPXML timeline for DaVinci Resolve Free.

    The timeline references the original RAW and lays each keep interval
    back-to-back on the primary storyline. No Resolve Studio scripting API is
    required. FCPXML is the stable bridge; UI automation is only a convenience.
    """
    source = Path(plan.source.path).expanduser().resolve()
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    fps = _fps_fraction(plan.source.fps)
    frame_duration = _frame_duration(fps)
    frame_duration_text = (
        f"{frame_duration.numerator}/{frame_duration.denominator}s"
        if frame_duration.denominator != 1
        else f"{frame_duration.numerator}s"
    )
    name = project_name or f"{source.stem}_rough"

    clips: list[tuple[int, int, int]] = []
    timeline_frames = 0
    for interval in plan.keep:
        start_frames = _frame_count(interval.start, fps)
        duration_frames = max(1, _frame_count(interval.end - interval.start, fps))
        clips.append((timeline_frames, start_frames, duration_frames))
        timeline_frames += duration_frames

    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(
        resources,
        "format",
        {
            "id": "r1",
            "name": f"FFVideoFormat{height}x{width}p{float(fps):.3f}",
            "frameDuration": frame_duration_text,
            "width": str(width),
            "height": str(height),
        },
    )

    asset_attrs = {
        "id": "r2",
        "name": source.stem,
        "src": source.as_uri(),
        "start": "0s",
        "duration": _fcpx_time(plan.source.duration, fps),
        "hasVideo": "1",
        "format": "r1",
    }
    if plan.source.has_audio:
        asset_attrs["hasAudio"] = "1"
    ET.SubElement(resources, "asset", asset_attrs)

    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Video Editor"})
    project = ET.SubElement(event, "project", {"name": name})
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": "r1",
            "duration": _fcpx_frames(timeline_frames, fps),
            "tcStart": "0s",
            "tcFormat": "NDF",
            "audioLayout": "stereo",
            "audioRate": "48k",
        },
    )
    spine = ET.SubElement(sequence, "spine")

    for index, (offset_frames, start_frames, duration_frames) in enumerate(clips, start=1):
        ET.SubElement(
            spine,
            "asset-clip",
            {
                "name": f"keep_{index:03d}",
                "ref": "r2",
                "offset": _fcpx_frames(offset_frames, fps),
                "start": _fcpx_frames(start_frames, fps),
                "duration": _fcpx_frames(duration_frames, fps),
                "lane": "0",
            },
        )

    ET.indent(root, space="  ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + ET.tostring(root, encoding="unicode")
    target.write_text(xml, encoding="utf-8")
    return target
