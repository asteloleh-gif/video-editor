import io
import json
from pathlib import Path
import wave

import httpx
import pytest

from video_editor.voicebox import LocalVoicebox, UPSTREAM_COMMIT, sha256


def wav_bytes():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x01\x00" * 2400)
    return stream.getvalue()


@pytest.fixture
def local(tmp_path):
    reference = tmp_path / "data/profiles/ref.wav"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(wav_bytes())
    marker = {"service": "astel-voicebox", "required_clone": True, "upstream_commit": UPSTREAM_COMMIT, "patched_backend_sha256": "tested", "model_06b_present": True}
    sample = {"id": "s1", "profile_id": "p1", "audio_path": "profiles/ref.wav", "reference_text": "My reference."}
    binding = {"status": "bound", "runtime": marker, "profile_id": "p1", "sample": sample, "reference_sha256": sha256(reference.read_bytes())}
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(binding))
    state = {"posts": [], "sample": sample, "result_status": "completed", "profile": {"voice_type": "cloned"}, "audio": wav_bytes()}

    def handle(request):
        path = request.url.path
        if path == "/astel/health":
            return httpx.Response(200, json=marker)
        if path == "/profiles/p1":
            return httpx.Response(200, json=state["profile"])
        if path == "/profiles/p1/samples":
            return httpx.Response(200, json=[state["sample"]])
        if path == "/generate":
            state["posts"].append(json.loads(request.content))
            if state.get("ambiguous"):
                raise httpx.ReadTimeout("Accepted, then connection lost", request=request)
            return httpx.Response(200, json={"id": "g1"})
        if path == "/history/g1":
            result = {**state["posts"][0], "id": "g1", "status": state["result_status"]}
            result.update(state.get("result_override", {}))
            return httpx.Response(200, json=result)
        if path == "/audio/g1":
            return httpx.Response(200, content=state["audio"])
        raise AssertionError(f"Unexpected request: {request.method} {path}")

    client = LocalVoicebox(home=tmp_path, transport=httpx.MockTransport(handle))
    yield client, binding_path, reference, state
    client.close()


def test_complete_review_artifact_and_explicit_resume(local, tmp_path):
    client, binding, _, state = local
    output = tmp_path / "v1"
    result = client.generate(binding, "Hello Oleh.", output)
    assert result["qa_status"] == "awaiting_owner_listening"
    assert result["duration"] == 0.1
    assert result["audio_sha256"] == sha256((output / "narration.wav").read_bytes())
    assert state["posts"][0]["personality"] is False
    assert state["posts"][0]["engine"] == "qwen"
    assert client.resume(output) == result
    assert len(state["posts"]) == 1
    assert (output / "manifest.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        client.generate(binding, "Hello again.", output)
    assert len(state["posts"]) == 1


@pytest.mark.parametrize("change", ["missing", "bytes", "transcript", "preset", "effects", "runtime"])
def test_reference_or_runtime_change_never_submits(local, tmp_path, change):
    client, binding, reference, state = local
    if change == "missing":
        reference.unlink()
    elif change == "bytes":
        reference.write_bytes(b"changed")
    elif change == "transcript":
        state["sample"] = {**state["sample"], "reference_text": "Other voice."}
    elif change == "preset":
        state["profile"]["voice_type"] = "preset"
    elif change == "effects":
        state["profile"]["effects_chain"] = [{"type": "pitch"}]
    else:
        contents = json.loads(binding.read_text())
        contents["runtime"]["patched_backend_sha256"] = "other"
        binding.write_text(json.dumps(contents))
    with pytest.raises(ValueError):
        client.generate(binding, "Hello.", tmp_path / "v1")
    assert not state["posts"]


def test_unknown_post_outcome_is_saved_without_retry(local, tmp_path):
    client, binding, _, state = local
    state["ambiguous"] = True
    output = tmp_path / "ambiguous"
    with pytest.raises(httpx.ReadTimeout):
        client.generate(binding, "Hello.", output)
    assert len(state["posts"]) == 1
    receipt = json.loads((output / "manifest.json").read_text())
    assert receipt["status"] == "submission_unconfirmed"
    assert "generation_id" not in receipt
    assert not (output / "narration.wav").exists()


def test_pending_resume_never_posts_again(local, tmp_path):
    client, binding, _, state = local
    state["result_status"] = "generating"
    output = tmp_path / "pending"
    with pytest.raises(TimeoutError):
        client.generate(binding, "Hello.", output, timeout=0)
    state["result_status"] = "completed"
    assert client.resume(output)["status"] == "completed"
    assert len(state["posts"]) == 1


@pytest.mark.parametrize("problem", ["failed", "wrong_text", "empty_audio"])
def test_invalid_generation_is_not_a_completed_artifact(local, tmp_path, problem):
    client, binding, _, state = local
    if problem == "failed":
        state["result_status"] = "failed"
    elif problem == "wrong_text":
        state["result_override"] = {"text": "Unexpected rewritten script."}
    else:
        state["audio"] = b""
    output = tmp_path / "invalid"
    with pytest.raises((RuntimeError, ValueError, EOFError)):
        client.generate(binding, "Hello.", output)
    assert not (output / "narration.wav").exists()
    assert len(state["posts"]) == 1
