from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptResult:
    language: str
    segments: list[TranscriptSegment]
    engine: str = "whisper.cpp"

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "engine": self.engine,
            "segments": [segment.to_dict() for segment in self.segments],
        }


def whisper_binary() -> str | None:
    """Return the installed whisper.cpp CLI binary path, if available."""
    return shutil.which("whisper-cli") or shutil.which("whisper-cpp")


def default_model_path() -> Path:
    override = os.getenv("WHISPER_MODEL_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "video-editor" / "whisper" / "ggml-base.bin"


def whisper_ready(model_path: str | Path | None = None) -> bool:
    model = Path(model_path).expanduser() if model_path else default_model_path()
    return bool(whisper_binary()) and model.is_file() and model.stat().st_size > 0


def _extract_audio(source: str | Path, output: str | Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for transcription")
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(Path(source).expanduser().resolve()),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(Path(output).resolve()),
    ]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"Could not extract audio for Whisper (ffmpeg exit {proc.returncode})")


def _parse_whisper_json(payload: dict[str, Any]) -> TranscriptResult:
    language = str((payload.get("result") or {}).get("language") or "unknown")
    segments: list[TranscriptSegment] = []
    for item in payload.get("transcription") or []:
        offsets = item.get("offsets") or {}
        try:
            start_ms = float(offsets.get("from", 0))
            end_ms = float(offsets.get("to", 0))
        except (TypeError, ValueError):
            continue
        text = str(item.get("text") or "").strip()
        start = max(0.0, start_ms / 1000.0)
        end = max(start, end_ms / 1000.0)
        if not text or end <= start:
            continue
        segments.append(
            TranscriptSegment(
                start=round(start, 3),
                end=round(end, 3),
                text=text,
            )
        )
    return TranscriptResult(language=language, segments=segments)


def transcribe_video(
    source: str | Path,
    *,
    model_path: str | Path | None = None,
    language: str = "auto",
    max_len: int = 42,
) -> TranscriptResult:
    """Transcribe a video locally using Homebrew whisper.cpp."""
    binary = whisper_binary()
    if not binary:
        raise RuntimeError("whisper-cli not found. Run setup_mac.sh to install whisper.cpp.")

    model = Path(model_path).expanduser() if model_path else default_model_path()
    if not model.is_file():
        raise RuntimeError(
            f"Whisper model not found: {model}. Run setup_mac.sh or set WHISPER_MODEL_PATH."
        )

    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    with tempfile.TemporaryDirectory(prefix="video-editor-whisper-") as temp_dir:
        temp = Path(temp_dir)
        wav = temp / "audio.wav"
        output_prefix = temp / "transcript"
        _extract_audio(source_path, wav)

        cmd = [
            binary,
            "-m",
            str(model.resolve()),
            "-f",
            str(wav),
            "-l",
            language,
            "-ojf",
            "-of",
            str(output_prefix),
            "-np",
            "-ml",
            str(max(8, int(max_len))),
            "-sow",
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"whisper-cli failed with exit {proc.returncode}: {stderr[-1200:]}")

        json_path = output_prefix.with_suffix(".json")
        if not json_path.is_file():
            raise RuntimeError("whisper-cli completed but did not create JSON output")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return _parse_whisper_json(payload)
