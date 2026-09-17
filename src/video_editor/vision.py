from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2

from .intervals import Interval, merge, normalize


DEFAULT_MODEL = "gpt-5.6-luna"

VISION_INSTRUCTIONS = """You are the semantic rough-cut detector for Battle Box short-form challenge videos.
The camera is usually fixed on a person, a table, cups, balls, or another simple physical challenge.
Your only job is to identify the time ranges worth KEEPING in the final short.

KEEP:
- the final moment of preparation immediately before an attempt,
- the actual attempt/gameplay (throws, hits, misses, balancing, movement that is part of the challenge),
- the immediate visible result and short reaction.

CUT:
- walking into/out of position,
- waiting, empty scene, long hesitation,
- retrieving balls/items after the result,
- rebuilding/resetting props for the next round,
- adjusting camera/phone,
- unrelated talking or setup that is not immediately part of an attempt.

Prefer slightly too much footage over cutting through a real attempt. Do not invent action that is not visible.
Timestamps are supplied with each sampled frame. Returned intervals must stay inside the batch time range.
If the batch contains no clear challenge attempt, return an empty intervals array.
"""


@dataclass(frozen=True)
class VisionDetection:
    start: float
    end: float
    label: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _api_key() -> str:
    value = os.getenv("OPENAI_API_KEY", "").strip()
    if value:
        return value

    key_file = Path.home() / ".config" / "video-editor" / "openai_api_key"
    if key_file.exists():
        value = key_file.read_text(encoding="utf-8").strip()
        if value:
            return value

    raise RuntimeError(
        "Vision mode needs an OpenAI API key. Set OPENAI_API_KEY or save the key in "
        "~/.config/video-editor/openai_api_key"
    )


def _encode_frame(frame, *, max_width: int = 480, jpeg_quality: int = 72) -> str:
    height, width = frame.shape[:2]
    if width > max_width:
        scale = max_width / float(width)
        frame = cv2.resize(
            frame,
            (max_width, max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
    )
    if not ok:
        raise RuntimeError("Could not JPEG-encode sampled frame")
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _sample_batch(
    source: str | Path,
    timestamps: list[float],
    *,
    max_width: int,
) -> list[tuple[float, str]]:
    capture = cv2.VideoCapture(str(Path(source).expanduser()))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video for vision analysis: {source}")

    frames: list[tuple[float, str]] = []
    try:
        for timestamp in timestamps:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            frames.append((timestamp, _encode_frame(frame, max_width=max_width)))
    finally:
        capture.release()
    return frames


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "intervals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "label": {
                            "type": "string",
                            "enum": ["attempt", "result", "reaction"],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": ["start", "end", "label", "confidence"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["intervals", "summary"],
        "additionalProperties": False,
    }


def _analyze_batch(
    frames: list[tuple[float, str]],
    *,
    model: str,
    min_confidence: float,
) -> tuple[list[VisionDetection], str]:
    if not frames:
        return [], "No readable frames"

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Vision mode requires the 'openai' Python package. Run setup_mac.sh again.") from exc

    batch_start = frames[0][0]
    batch_end = frames[-1][0]
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                f"Analyze this chronological batch from {batch_start:.2f}s to {batch_end:.2f}s. "
                "Each image is preceded by its exact timestamp. Return only ranges that should remain in the final edit."
            ),
        }
    ]
    for timestamp, data_url in frames:
        content.append({"type": "input_text", "text": f"t={timestamp:.2f}s"})
        content.append(
            {
                "type": "input_image",
                "image_url": data_url,
                "detail": "low",
            }
        )

    client = OpenAI(api_key=_api_key())
    response = client.responses.create(
        model=model,
        instructions=VISION_INSTRUCTIONS,
        input=[{"role": "user", "content": content}],
        text={
            "format": {
                "type": "json_schema",
                "name": "battle_box_edit_ranges",
                "schema": _response_schema(),
                "strict": True,
            }
        },
    )

    try:
        payload = json.loads(response.output_text)
    except Exception as exc:
        raise RuntimeError(f"Vision model returned invalid JSON: {response.output_text!r}") from exc

    detections: list[VisionDetection] = []
    for item in payload.get("intervals", []):
        confidence = float(item.get("confidence", 0.0))
        if confidence < min_confidence:
            continue
        start = max(batch_start, float(item["start"]))
        end = min(batch_end, float(item["end"]))
        if end <= start:
            continue
        detections.append(
            VisionDetection(
                start=round(start, 3),
                end=round(end, 3),
                label=str(item.get("label", "attempt")),
                confidence=round(confidence, 3),
            )
        )

    return detections, str(payload.get("summary", ""))


def _timestamps(duration: float, step: float) -> list[float]:
    if duration <= 0:
        return []
    if step <= 0:
        raise ValueError("vision_step must be > 0")

    values: list[float] = []
    current = 0.0
    while current < duration:
        values.append(round(current, 3))
        current += step
    last = max(0.0, duration - 0.001)
    if not values or last - values[-1] > step * 0.40:
        values.append(round(last, 3))
    return values


def detect_vision_activity(
    source: str | Path,
    *,
    duration: float,
    model: str = DEFAULT_MODEL,
    step: float = 1.0,
    batch_frames: int = 20,
    overlap_frames: int = 3,
    max_width: int = 480,
    min_confidence: float = 0.45,
    merge_gap: float = 1.25,
) -> tuple[list[Interval], list[VisionDetection], list[str]]:
    """Detect semantically useful gameplay ranges using sampled video frames + vision AI."""
    if batch_frames < 4:
        raise ValueError("vision_batch_frames must be >= 4")
    if overlap_frames < 0 or overlap_frames >= batch_frames:
        raise ValueError("vision_overlap_frames must be >= 0 and smaller than batch_frames")

    points = _timestamps(duration, step)
    if not points:
        return [], [], []

    stride = batch_frames - overlap_frames
    detections: list[VisionDetection] = []
    summaries: list[str] = []

    for start_index in range(0, len(points), stride):
        batch_times = points[start_index : start_index + batch_frames]
        if not batch_times:
            break
        frames = _sample_batch(source, batch_times, max_width=max_width)
        batch_detections, summary = _analyze_batch(
            frames,
            model=model,
            min_confidence=min_confidence,
        )
        detections.extend(batch_detections)
        summaries.append(summary)
        if start_index + batch_frames >= len(points):
            break

    intervals = normalize(
        [Interval(item.start, item.end) for item in detections],
        duration=duration,
    )
    intervals = merge(intervals, max_gap=merge_gap)
    return intervals, detections, summaries
