from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .intervals import Interval, merge


def _prepare(frame: np.ndarray, analysis_width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w > analysis_width:
        scale = analysis_width / float(w)
        frame = cv2.resize(frame, (analysis_width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (5, 5), 0)


def detect_motion(
    path: str | Path,
    *,
    sample_fps: float = 4.0,
    threshold: float = 0.018,
    analysis_width: int = 320,
) -> tuple[list[Interval], list[tuple[float, float]]]:
    """Return active motion intervals and (timestamp, score) samples.

    Score is mean absolute grayscale frame difference normalized to 0..1.
    Analysis is intentionally downscaled for speed; source resolution is untouched.
    """
    source = str(Path(path).expanduser().resolve())
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {source}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        cap.release()
        raise RuntimeError("Could not determine source FPS")

    step = max(1, int(round(fps / max(0.1, sample_fps))))
    effective_sample_fps = fps / step
    prev: np.ndarray | None = None
    prev_t: float | None = None
    intervals: list[Interval] = []
    samples: list[tuple[float, float]] = []

    frame_index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index % step != 0:
            frame_index += 1
            continue

        t = frame_index / fps
        current = _prepare(frame, analysis_width)
        if prev is not None and prev_t is not None:
            diff = cv2.absdiff(current, prev)
            score = float(np.mean(diff) / 255.0)
            samples.append((round(t, 4), round(score, 6)))
            if score >= threshold:
                intervals.append(Interval(prev_t, t + (1.0 / effective_sample_fps)))
        prev = current
        prev_t = t
        frame_index += 1

    cap.release()
    return merge(intervals, max_gap=1.0 / effective_sample_fps), samples
