from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any


POSITIVE_FEEDBACK = {
    "keep": 1.0,
    "more_like_this": 1.5,
}
NEGATIVE_FEEDBACK = {
    "cut": -1.0,
    "bad": -1.5,
}
EVENT_WEIGHT_KEYS = {
    "goal": "goal_weight",
    "score": "goal_weight",
    "attempt": "attempt_weight",
    "collision": "collision_weight",
    "reaction": "reaction_weight",
    "dead": "dead_time_weight",
    "dead_time": "dead_time_weight",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _event_type(event: dict[str, Any] | None) -> str:
    if not event:
        return "unknown"
    return str(event.get("event_type") or "unknown").strip().lower()


def _subject_color(event: dict[str, Any] | None) -> str:
    if not event:
        return ""
    return str(event.get("subject_color") or "").strip().lower()


def build_learning_candidate(
    base_config: dict[str, Any],
    feedback_rows: list[dict[str, Any]],
    events_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic candidate style from human review feedback.

    This deliberately creates a candidate only. It never promotes or activates a preset.
    The first stage is lightweight online adaptation; a learned ranking model belongs after
    enough RAW -> FINAL / keep-cut examples exist.
    """

    candidate = deepcopy(base_config)
    feedback_counts: Counter[str] = Counter()
    event_feedback_counts: dict[str, Counter[str]] = defaultdict(Counter)
    event_scores: dict[str, float] = defaultdict(float)
    orange_score = 0.0
    shorter_count = 0
    longer_count = 0
    relabel_counts: Counter[str] = Counter()

    for row in feedback_rows:
        feedback_type = str(row.get("feedback_type") or "").strip().lower()
        if not feedback_type:
            continue

        feedback_counts[feedback_type] += 1
        event_id = row.get("event_id")
        event = events_by_id.get(str(event_id)) if event_id else None
        kind = _event_type(event)
        event_feedback_counts[kind][feedback_type] += 1

        score = POSITIVE_FEEDBACK.get(feedback_type, 0.0)
        score += NEGATIVE_FEEDBACK.get(feedback_type, 0.0)

        if feedback_type == "goal":
            relabel_counts["goal"] += 1
            kind = "goal"
            score += 1.0
        elif feedback_type == "reaction":
            relabel_counts["reaction"] += 1
            kind = "reaction"
            score += 0.75
        elif feedback_type == "shorter":
            shorter_count += 1
        elif feedback_type == "longer":
            longer_count += 1

        if score:
            event_scores[kind] += score
            if _subject_color(event) == "orange":
                orange_score += score

    weight_changes: dict[str, dict[str, float]] = {}
    for event_type, weight_key in EVENT_WEIGHT_KEYS.items():
        if event_type not in event_scores:
            continue
        old_value = float(candidate.get(weight_key, 1.0))
        factor = _clamp(1.0 + event_scores[event_type] * 0.08, 0.50, 1.75)
        new_value = round(_clamp(old_value * factor, 0.0, 4.0), 4)
        candidate[weight_key] = new_value
        weight_changes[weight_key] = {
            "from": round(old_value, 4),
            "to": new_value,
            "signal": round(event_scores[event_type], 4),
        }

    old_clip_target = int(candidate.get("clip_target_ms", 1300))
    duration_signal = longer_count - shorter_count
    if duration_signal:
        factor = _clamp(1.0 + duration_signal * 0.05, 0.70, 1.30)
        candidate["clip_target_ms"] = int(
            round(_clamp(old_clip_target * factor, 500.0, 3500.0))
        )

    old_orange_priority = float(candidate.get("orange_priority", 1.0))
    if orange_score:
        orange_factor = _clamp(1.0 + orange_score * 0.06, 0.70, 1.50)
        candidate["orange_priority"] = round(
            _clamp(old_orange_priority * orange_factor, 0.5, 3.0),
            4,
        )

    sample_count = len(feedback_rows)
    if sample_count < 20:
        confidence = "cold_start"
    elif sample_count < 50:
        confidence = "learning"
    else:
        confidence = "grounded"

    return {
        "sample_count": sample_count,
        "confidence": confidence,
        "feedback_counts": dict(feedback_counts),
        "event_feedback_counts": {
            event_type: dict(counts)
            for event_type, counts in sorted(event_feedback_counts.items())
        },
        "event_scores": {
            event_type: round(score, 4)
            for event_type, score in sorted(event_scores.items())
        },
        "relabel_counts": dict(relabel_counts),
        "duration_signal": duration_signal,
        "orange_signal": round(orange_score, 4),
        "weight_changes": weight_changes,
        "base_config": deepcopy(base_config),
        "candidate_config": candidate,
    }
