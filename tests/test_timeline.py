from dataclasses import dataclass

from video_editor.intervals import Interval
from video_editor.timeline import build_timeline, map_detections, map_source_range, source_to_output_time


@dataclass(frozen=True)
class Detection:
    start: float
    end: float
    label: str
    confidence: float = 0.9


def test_build_timeline_flattens_keep_ranges():
    timeline = build_timeline([Interval(1.0, 2.0), Interval(5.0, 7.5)])
    assert timeline[0].output_start == 0.0
    assert timeline[0].output_end == 1.0
    assert timeline[1].output_start == 1.0
    assert timeline[1].output_end == 3.5


def test_source_to_output_time_returns_none_for_cut_range():
    timeline = build_timeline([Interval(1.0, 2.0), Interval(5.0, 7.5)])
    assert source_to_output_time(1.5, timeline) == 0.5
    assert source_to_output_time(4.0, timeline) is None
    assert source_to_output_time(6.0, timeline) == 2.0


def test_map_source_range_splits_across_cut():
    timeline = build_timeline([Interval(1.0, 2.0), Interval(5.0, 7.5)])
    assert map_source_range(1.5, 5.5, timeline) == [(0.5, 1.0), (1.0, 1.5)]


def test_map_detections_preserves_event_label():
    timeline = build_timeline([Interval(5.0, 7.0)])
    mapped = map_detections([Detection(5.25, 5.75, "score")], timeline)
    assert mapped == [
        {
            "start": 0.25,
            "end": 0.75,
            "label": "score",
            "confidence": 0.9,
            "source_start": 5.25,
            "source_end": 5.75,
        }
    ]


def test_map_detections_dedupes_overlapping_batches():
    from types import SimpleNamespace

    timeline = build_timeline([Interval(0.0, 10.0)])
    detections = [
        SimpleNamespace(start=2.0, end=2.8, label="score", confidence=0.8),
        SimpleNamespace(start=2.1, end=2.9, label="score", confidence=0.95),
        SimpleNamespace(start=5.0, end=5.4, label="miss", confidence=0.7),
    ]
    cues = map_detections(detections, timeline)
    assert len(cues) == 2
    assert cues[0]["label"] == "score"
    assert cues[0]["start"] == 2.0
    assert cues[0]["end"] == 2.9
    assert cues[0]["confidence"] == 0.95
