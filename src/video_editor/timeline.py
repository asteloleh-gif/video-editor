from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from .intervals import Interval


@dataclass(frozen=True)
class TimelineSegment:
    source_start: float
    source_end: float
    output_start: float
    output_end: float

    @property
    def source_duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    @property
    def output_duration(self) -> float:
        return max(0.0, self.output_end - self.output_start)

    def to_dict(self) -> dict:
        return asdict(self)


def build_timeline(keep: Iterable[Interval]) -> list[TimelineSegment]:
    """Map source keep-ranges onto the flattened rough-cut timeline."""
    out: list[TimelineSegment] = []
    cursor = 0.0
    for interval in sorted(keep):
        duration = max(0.0, interval.end - interval.start)
        if duration <= 0:
            continue
        out.append(
            TimelineSegment(
                source_start=round(interval.start, 6),
                source_end=round(interval.end, 6),
                output_start=round(cursor, 6),
                output_end=round(cursor + duration, 6),
            )
        )
        cursor += duration
    return out


def source_to_output_time(timestamp: float, timeline: Sequence[TimelineSegment]) -> float | None:
    """Return flattened timeline time for a source timestamp, or None if it was cut."""
    value = float(timestamp)
    for segment in timeline:
        if segment.source_start <= value <= segment.source_end:
            mapped = segment.output_start + (value - segment.source_start)
            return round(min(segment.output_end, max(segment.output_start, mapped)), 6)
    return None


def map_source_range(
    start: float,
    end: float,
    timeline: Sequence[TimelineSegment],
) -> list[tuple[float, float]]:
    """Map a source range across all kept overlaps."""
    start = float(start)
    end = float(end)
    if end <= start:
        return []

    mapped: list[tuple[float, float]] = []
    for segment in timeline:
        overlap_start = max(start, segment.source_start)
        overlap_end = min(end, segment.source_end)
        if overlap_end <= overlap_start:
            continue
        out_start = segment.output_start + (overlap_start - segment.source_start)
        out_end = segment.output_start + (overlap_end - segment.source_start)
        if out_end > out_start:
            mapped.append((round(out_start, 6), round(out_end, 6)))
    return mapped


def _dedupe_event_cues(cues: list[dict], *, max_gap: float = 0.15) -> list[dict]:
    """Merge duplicate same-label cues produced by overlapping vision batches."""
    if not cues:
        return []

    merged: list[dict] = []
    for cue in sorted(cues, key=lambda item: (item["label"], item["start"], item["end"])):
        if merged:
            previous = merged[-1]
            if (
                previous["label"] == cue["label"]
                and cue["start"] <= previous["end"] + max_gap
            ):
                previous["start"] = min(previous["start"], cue["start"])
                previous["end"] = max(previous["end"], cue["end"])
                previous["confidence"] = max(previous["confidence"], cue["confidence"])
                previous["source_start"] = min(previous["source_start"], cue["source_start"])
                previous["source_end"] = max(previous["source_end"], cue["source_end"])
                continue
        merged.append(dict(cue))

    return sorted(merged, key=lambda item: (item["start"], item["end"], item["label"]))


def map_detections(detections: Iterable[object], timeline: Sequence[TimelineSegment]) -> list[dict]:
    """Map VisionDetection-like objects onto output time."""
    out: list[dict] = []
    for item in detections:
        start = float(getattr(item, "start"))
        end = float(getattr(item, "end"))
        label = str(getattr(item, "label"))
        confidence = float(getattr(item, "confidence", 1.0))
        for out_start, out_end in map_source_range(start, end, timeline):
            out.append(
                {
                    "start": out_start,
                    "end": out_end,
                    "label": label,
                    "confidence": round(confidence, 3),
                    "source_start": round(start, 6),
                    "source_end": round(end, 6),
                }
            )
    return _dedupe_event_cues(out)


def map_transcript_segments(segments: Iterable[object], timeline: Sequence[TimelineSegment]) -> list[dict]:
    """Map TranscriptSegment-like objects from RAW time to final-cut time."""
    out: list[dict] = []
    for segment in segments:
        start = float(getattr(segment, "start"))
        end = float(getattr(segment, "end"))
        text = str(getattr(segment, "text", "")).strip()
        if not text:
            continue
        for out_start, out_end in map_source_range(start, end, timeline):
            if out_end - out_start < 0.08:
                continue
            out.append(
                {
                    "start": out_start,
                    "end": out_end,
                    "text": text,
                    "source_start": round(start, 6),
                    "source_end": round(end, 6),
                }
            )
    return sorted(out, key=lambda item: (item["start"], item["end"]))
