"""Regression tests against the actual patched upstream backend, without weights."""

import asyncio
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from runtime import SOURCE, verify_source

os.environ["HF_HUB_OFFLINE"] = "1"
verify_source()
sys.path.insert(0, str(SOURCE))
from backend.backends.mlx_backend import MLXTTSBackend  # noqa: E402


class CloningModel:
    config = SimpleNamespace(tts_model_type="base")
    speech_tokenizer = SimpleNamespace(has_encoder=True)
    speaker_encoder = object()


@pytest.fixture
def clone(tmp_path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"test fixture, never decoded by fake model")
    backend = MLXTTSBackend("0.6B")
    backend._current_model_size = "0.6B"
    calls = []

    class Model(CloningModel):
        def generate(self, text, ref_audio, ref_text, lang_code):
            calls.append((text, ref_audio, ref_text, lang_code))
            yield SimpleNamespace(audio=np.array([0.1, 0.2]), sample_rate=24000)

    backend.model = Model()
    return backend, {"ref_audio": str(reference), "ref_text": "Exact reference."}, calls


def test_clone_always_receives_audio_and_exact_transcript(clone):
    backend, prompt, calls = clone
    audio, rate = asyncio.run(backend.generate("Hello.", prompt))
    assert rate == 24000 and audio.size == 2
    assert calls == [("Hello.", prompt["ref_audio"], prompt["ref_text"], "english")]


@pytest.mark.parametrize("problem", ["missing", "none", "empty_transcript", "instruct", "language"])
def test_invalid_reference_fails_before_inference(clone, problem):
    backend, prompt, calls = clone
    kwargs = {}
    if problem == "missing":
        prompt["ref_audio"] += ".deleted"
    elif problem == "none":
        prompt = None
    elif problem == "empty_transcript":
        prompt["ref_text"] = " "
    elif problem == "instruct":
        kwargs["instruct"] = "Slavic accent"
    else:
        kwargs["language"] = "unknown"
    with pytest.raises(ValueError):
        asyncio.run(backend.generate("Hello.", prompt, **kwargs))
    assert not calls


def test_incompatible_model_is_not_called_without_reference(clone):
    backend, prompt, calls = clone

    class Incompatible(CloningModel):
        def generate(self, text, lang_code):
            calls.append("unconditioned")
            return iter(())

    backend.model = Incompatible()
    with pytest.raises(RuntimeError, match="cloning API"):
        asyncio.run(backend.generate("Hello.", prompt))
    assert not calls


def test_exception_after_partial_audio_does_not_retry_or_return_partial(clone):
    backend, prompt, calls = clone

    class Broken(CloningModel):
        def generate(self, text, ref_audio, ref_text, lang_code):
            calls.append("one attempt")
            yield SimpleNamespace(audio=np.array([0.2]), sample_rate=24000)
            raise RuntimeError("Clone failed after first chunk")

    backend.model = Broken()
    with pytest.raises(RuntimeError, match="after first chunk"):
        asyncio.run(backend.generate("Hello.", prompt))
    assert calls == ["one attempt"]


@pytest.mark.parametrize("samples,rate", [([], 24000), ([float("nan")], 24000), ([0, 0], 24000), ([0.1], 0)])
def test_invalid_audio_is_rejected(clone, samples, rate):
    backend, prompt, _ = clone

    class Invalid(CloningModel):
        def generate(self, text, ref_audio, ref_text, lang_code):
            yield SimpleNamespace(audio=np.array(samples), sample_rate=rate)

    backend.model = Invalid()
    with pytest.raises(RuntimeError):
        asyncio.run(backend.generate("Hello.", prompt))


@pytest.mark.parametrize("problem", ["preset_model", "reference_encoder", "speaker_encoder"])
def test_matching_signature_cannot_hide_a_non_cloning_model(clone, problem):
    backend, prompt, calls = clone
    if problem == "preset_model":
        backend.model.config = SimpleNamespace(tts_model_type="custom_voice")
    elif problem == "reference_encoder":
        backend.model.speech_tokenizer = SimpleNamespace(has_encoder=False)
    else:
        backend.model.speaker_encoder = None
    with pytest.raises(RuntimeError):
        asyncio.run(backend.generate("Hello.", prompt))
    assert not calls
