from video_editor.vision import _timestamps


def test_timestamps_cover_start_and_end():
    points = _timestamps(3.2, 1.0)
    assert points[0] == 0.0
    assert points[-1] == 3.0
    assert all(a < b for a, b in zip(points, points[1:]))


def test_timestamps_short_clip():
    points = _timestamps(0.4, 1.0)
    assert points == [0.0]


def test_timestamps_reject_bad_step():
    try:
        _timestamps(10.0, 0.0)
    except ValueError as exc:
        assert "vision_step" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
