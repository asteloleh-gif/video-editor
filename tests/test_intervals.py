from video_editor.intervals import Interval, complement, merge, pad, union


def test_merge_close_intervals():
    items = [Interval(0, 1), Interval(1.2, 2), Interval(5, 6)]
    assert merge(items, max_gap=0.25) == [Interval(0, 2), Interval(5, 6)]


def test_union():
    a = [Interval(0, 1), Interval(4, 5)]
    b = [Interval(0.5, 2)]
    assert union(a, b) == [Interval(0, 2), Interval(4, 5)]


def test_pad_clamps_to_duration():
    assert pad([Interval(0.2, 1.0)], 0.5, 1.0, 1.5) == [Interval(0.0, 1.5)]


def test_complement():
    assert complement([Interval(1, 2), Interval(3, 4)], 5) == [
        Interval(0, 1), Interval(2, 3), Interval(4, 5)
    ]
