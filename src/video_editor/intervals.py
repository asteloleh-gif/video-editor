from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, order=True)
class Interval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def normalize(intervals: Iterable[Interval], duration: float | None = None) -> list[Interval]:
    cleaned: list[Interval] = []
    for item in intervals:
        start = max(0.0, float(item.start))
        end = float(item.end)
        if duration is not None:
            end = min(float(duration), end)
        if end > start:
            cleaned.append(Interval(start, end))
    return sorted(cleaned)


def merge(intervals: Iterable[Interval], max_gap: float = 0.0) -> list[Interval]:
    items = normalize(intervals)
    if not items:
        return []
    out = [items[0]]
    for current in items[1:]:
        previous = out[-1]
        if current.start <= previous.end + max_gap:
            out[-1] = Interval(previous.start, max(previous.end, current.end))
        else:
            out.append(current)
    return out


def union(*groups: Iterable[Interval], max_gap: float = 0.0) -> list[Interval]:
    combined: list[Interval] = []
    for group in groups:
        combined.extend(group)
    return merge(combined, max_gap=max_gap)


def pad(
    intervals: Iterable[Interval],
    before: float,
    after: float,
    duration: float,
) -> list[Interval]:
    expanded = [
        Interval(max(0.0, i.start - before), min(duration, i.end + after))
        for i in intervals
    ]
    return merge(expanded)


def filter_short(intervals: Iterable[Interval], min_duration: float) -> list[Interval]:
    return [i for i in intervals if i.duration >= min_duration]


def complement(intervals: Iterable[Interval], duration: float) -> list[Interval]:
    active = merge(normalize(intervals, duration=duration))
    if not active:
        return [Interval(0.0, duration)] if duration > 0 else []
    out: list[Interval] = []
    cursor = 0.0
    for item in active:
        if item.start > cursor:
            out.append(Interval(cursor, item.start))
        cursor = max(cursor, item.end)
    if cursor < duration:
        out.append(Interval(cursor, duration))
    return out
