"""Real upstream HTTP/queue/WAV flow with a deterministic fake inference model.

This verifies integration, not voice quality. No real speaker is synthesized.
"""

import os
import sys
from types import SimpleNamespace

import httpx
import numpy as np
import soundfile as sf

from runtime import SOURCE, verify_source

os.environ["HF_HUB_OFFLINE"] = "1"
verify_source()
sys.path.insert(0, str(SOURCE))

from video_editor.voicebox import LocalVoicebox, UPSTREAM_COMMIT  # noqa: E402
from backend import backends, config  # noqa: E402
from backend.backends.mlx_backend import MLXTTSBackend  # noqa: E402


def test_profile_upload_queue_generation_and_artifact(tmp_path, monkeypatch):
    config.set_data_dir(tmp_path / "data")
    from backend.app import create_app
    from fastapi.testclient import TestClient

    calls = []

    class FixtureModel:
        config = SimpleNamespace(tts_model_type="base")
        speech_tokenizer = SimpleNamespace(has_encoder=True)
        speaker_encoder = object()

        def generate(self, text, ref_audio, ref_text, lang_code):
            calls.append({"text": text, "ref_audio": ref_audio, "ref_text": ref_text})
            yield SimpleNamespace(audio=0.15 * np.sin(np.arange(24000) * 0.1), sample_rate=24000)

    backend = MLXTTSBackend("0.6B")
    backend.model = FixtureModel()
    backend._current_model_size = "0.6B"
    monkeypatch.setitem(backends._tts_backends, "qwen", backend)
    app = create_app()

    @app.get("/astel/health")
    async def astel_marker():
        return {"service": "astel-voicebox", "required_clone": True, "upstream_commit": UPSTREAM_COMMIT}

    with TestClient(app) as server:
        def dispatch(request):
            response = server.request(request.method, request.url.raw_path.decode(), headers=dict(request.headers), content=request.content)
            return httpx.Response(response.status_code, headers=response.headers, content=response.content)

        client = LocalVoicebox(home=tmp_path, transport=httpx.MockTransport(dispatch))
        try:
            reference = tmp_path / "reference.wav"
            sf.write(reference, 0.15 * np.sin(np.arange(72000) * 0.1), 24000)
            binding = tmp_path / "binding.json"
            client.register(reference, "Exact fixture reference.", binding, "QA fixture")
            result = client.generate(binding, "Fixture integration test.", tmp_path / "v1", timeout=30)
            assert result["status"] == "completed"
            assert result["qa_status"] == "awaiting_owner_listening"
            assert calls[0]["ref_text"] == "Exact fixture reference."
            assert calls[0]["text"] == "Fixture integration test."
            assert len(calls) == 1
            # A changed upstream sample is detected before another job is sent.
            sample_id = result["binding"]["sample"]["id"]
            response = server.put(f"/profiles/samples/{sample_id}", json={"reference_text": "Changed."})
            response.raise_for_status()
            import pytest
            with pytest.raises(ValueError, match="transcript changed"):
                client.generate(binding, "Another test.", tmp_path / "v2")
            assert len(calls) == 1
        finally:
            client.close()
