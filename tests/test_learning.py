from __future__ import annotations

from video_editor.learning import build_learning_candidate


def test_learning_candidate_uses_review_feedback() -> None:
    base = {
        "goal_weight": 2.0,
        "attempt_weight": 1.0,
        "collision_weight": 1.2,
        "reaction_weight": 0.9,
        "dead_time_weight": 0.0,
        "clip_target_ms": 1300,
        "orange_priority": 1.4,
    }
    events = {
        "score-1": {
            "id": "score-1",
            "event_type": "score",
            "subject_color": "orange",
        },
        "collision-1": {
            "id": "collision-1",
            "event_type": "collision",
            "subject_color": "green",
        },
        "reaction-1": {
            "id": "reaction-1",
            "event_type": "reaction",
        },
        "miss-1": {
            "id": "miss-1",
            "event_type": "miss",
            "subject_color": "orange",
        },
    }
    feedback = [
        {"feedback_type": "keep", "event_id": "score-1"},
        {"feedback_type": "more_like_this", "event_id": "collision-1"},
        {"feedback_type": "cut", "event_id": "reaction-1"},
        {"feedback_type": "shorter", "event_id": "score-1"},
        {"feedback_type": "goal", "event_id": "miss-1"},
    ]

    result = build_learning_candidate(base, feedback, events)
    candidate = result["candidate_config"]

    assert result["sample_count"] == 5
    assert result["confidence"] == "cold_start"
    assert candidate["goal_weight"] > base["goal_weight"]
    assert candidate["collision_weight"] > base["collision_weight"]
    assert candidate["reaction_weight"] < base["reaction_weight"]
    assert candidate["clip_target_ms"] < base["clip_target_ms"]
    assert candidate["orange_priority"] > base["orange_priority"]
    assert result["relabel_counts"]["goal"] == 1


def test_learning_candidate_becomes_grounded_after_fifty_examples() -> None:
    feedback = [{"feedback_type": "keep", "event_id": None} for _ in range(50)]

    result = build_learning_candidate({}, feedback, {})

    assert result["sample_count"] == 50
    assert result["confidence"] == "grounded"
    assert result["candidate_config"] == {}
