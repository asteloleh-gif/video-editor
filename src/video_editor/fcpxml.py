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


def _fcpx_time(seconds: float, fps: Fraction) -> str:
    frame = _frame_duration(fps)
    frames = max(0, round(float(seconds) / float(frame)))
    value = frames * frame
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def write_fcpxml(
    plan: EditPlan,
    output: str | Path,
    *,
    project_name: str | None = None,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Write a simple, frame-aligned FCPXML rough-cut timeline for Resolve Free.

    The timeline references the original source media and lays each keep interval
    back-to-back on the primary storyline. No Resolve scripting API is needed.
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

    root = ET.Element("fcpxml", {"version": "1.9"})
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
            "colorSpace": "1-1-1 (Rec. 709)",
        },
    )

    asset_attrs = {
        "id": "r2",
        "name": source.name,
        "start": "0s",
        "duration": _fcpx_time(plan.source.duration, fps),
        "hasVideo": "1",
        "format": "r1",
    }
    if plan.source.has_audio:
        asset_attrs["hasAudio"] = "1"
        asset_attrs["audioSources"] = "1"
        asset_attrs["audioChannels"] = "2"
        asset_attrs["audioRate"] = "48k"
    asset = ET.SubElement(resources, "asset", asset_attrs)
    ET.SubElement(asset, "media-rep", {"kind": "original-media", "src": source.as_uri()})

    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Video Editor"})
    project = ET.SubElement(event, "project", {"name": name})
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": "r1",
            "duration": _fcpx_time(plan.duration_kept, fps),
            "tcStart": "0s",
            "tcFormat": "NDF",
            "audioLayout": "stereo",
            "audioRate": "48k",
        },
    )
    spine = ET.SubElement(sequence, "spine")

    timeline_offset = 0.0
    for index, interval in enumerate(plan.keep, start=1):
        duration = max(0.0, interval.end - interval.start)
        attrs = {
            "name": f"keep_{index:03d}",
            "ref": "r2",
            "offset": _fcpx_time(timeline_offset, fps),
            "start": _fcpx_time(interval.start, fps),
            "duration": _fcpx_time(duration, fps),
            "format": "r1",
        }
        ET.SubElement(spine, "asset-clip", attrs)
        timeline_offset += duration

    ET.indent(root, space="  ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + ET.tostring(root, encoding="unicode")
    target.write_text(xml, encoding="utf-8")
    return target
