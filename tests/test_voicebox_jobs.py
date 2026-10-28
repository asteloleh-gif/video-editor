"""Persistent desktop jobs: recovery, isolation, immutability and real audio processing."""
import json
import math
from pathlib import Path
import struct
from unittest.mock import Mock
import uuid
import wave

import pytest

from video_editor.voicebox import write_json
from video_editor.voicebox_jobs import SpeechJobs, digest


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    service = SpeechJobs(tmp_path)
    (service.root / "bindings").mkdir()
    write_json(service.root / "bindings/ru.json", {"status": "bound", "profile_id": "private-reference"})
    write_json(service.root / "profiles.json", {"profiles": [{"id": "oleh-ru", "name": "Олег", "language": "ru", "binding": "bindings/ru.json", "warm": True, "speed": 1}]})
    monkeypatch.setattr(service, "spawn", Mock())
    return service


def request(**kw):
    return {"id": str(uuid.uuid4()), "profile": "oleh-ru", "text": "Привет, это тест!", "project_id": "project-a", **kw}


def test_exact_retry_reuses_job_without_spawning(jobs):
    req = request()
    first = jobs.submit(req)
    assert jobs.submit(req) == first
    jobs.spawn.assert_called_once()
    with pytest.raises(ValueError, match="another request"):
        jobs.submit({**req, "text": "Другой текст"})
    assert jobs.status(req["id"])["text"] == req["text"]
    assert "private-reference" not in json.dumps(jobs.status(req["id"]))


@pytest.mark.parametrize("kw", [{"text": 5}, {"text": " "}, {"text": "a"*5001}, {"speed": float("nan")}, {"speed": True}, {"speed": 2}, {"warm": "yes"}, {"profile": "other"}, {"path": "/etc/passwd"}, {"id": "../x"}])
def test_rejects_invalid_payload_before_work(jobs, kw):
    with pytest.raises((ValueError, AttributeError)):
        jobs.submit(request(**kw))
    jobs.spawn.assert_not_called()


def test_resume_never_resubmits_and_cancel_is_persistent(jobs):
    req = request()
    jobs.submit(req)
    jobs.resume(req["id"])
    assert jobs.spawn.call_count == 2
    jobs.cancel(req["id"])
    assert (jobs.folder(req["id"]) / "cancel").exists()
    jobs.update(jobs.folder(req["id"]), status="cancelled")
    jobs.resume(req["id"])
    assert jobs.spawn.call_count == 2


def test_processing_keeps_source_and_protects_ready_output(jobs):
    req = request(speed=1.2)
    jobs.submit(req)
    folder = jobs.folder(req["id"])
    (folder / "raw").mkdir()
    source = folder / "raw/narration.wav"
    with wave.open(str(source), "wb") as stream:
        stream.setparams((1, 2, 24000, 0, "NONE", "NONE"))
        stream.writeframes(b"".join(struct.pack("<h", int(7000*math.sin(2*math.pi*180*i/24000))) for i in range(48000)))
    before = source.read_bytes()
    jobs.process_audio(folder, {"warm": True, "speed": 1.2}, {"audio_sha256": digest(source)})
    job = json.loads((folder / "job.json").read_text())
    assert 1.6 < job["duration"] < 1.8
    assert source.read_bytes() == before
    jobs.update(folder, status="ready")
    assert jobs.audio(req["id"])["sha256"] == digest(folder / "narration.wav")
    (folder / "narration.wav").write_bytes(b"changed")
    with pytest.raises(ValueError):
        jobs.audio(req["id"])


def test_worker_recovers_existing_generation_without_post(jobs, monkeypatch):
    req = request()
    jobs.submit(req)
    folder = jobs.folder(req["id"])
    (folder / "raw").mkdir()
    write_json(folder / "raw/manifest.json", {"generation_id": "existing", "status": "pending"})
    client = Mock()
    client.resume.side_effect = [TimeoutError(), {"audio_sha256": "hash"}]
    monkeypatch.setattr("video_editor.voicebox_jobs.LocalVoicebox", lambda **kw: client)
    monkeypatch.setattr(jobs, "ensure_server", lambda _: None)
    monkeypatch.setattr(jobs, "process_audio", Mock())
    jobs.run(folder)
    client.generate.assert_not_called()
    assert client.resume.call_count == 2
    assert jobs.status(req["id"])["status"] == "ready"


def test_worker_refuses_uncertain_submission(jobs, monkeypatch):
    req = request()
    jobs.submit(req)
    folder = jobs.folder(req["id"])
    (folder / "raw").mkdir()
    write_json(folder / "raw/manifest.json", {"status": "submitting"})
    client = Mock()
    monkeypatch.setattr("video_editor.voicebox_jobs.LocalVoicebox", lambda **kw: client)
    monkeypatch.setattr(jobs, "ensure_server", lambda _: None)
    jobs.run(folder)
    client.generate.assert_not_called()
    client.resume.assert_not_called()
    assert jobs.status(req["id"])["status"] == "failed"


def test_cancel_existing_generation_sends_one_cancel_and_preserves_source(jobs, monkeypatch):
    req = request()
    jobs.submit(req)
    folder = jobs.folder(req["id"])
    (folder / "raw").mkdir()
    write_json(folder / "raw/manifest.json", {"generation_id": "existing", "status": "pending"})
    jobs.cancel(req["id"])
    client = Mock()
    client.resume.side_effect = [TimeoutError(), RuntimeError("Generation cancelled")]
    monkeypatch.setattr("video_editor.voicebox_jobs.LocalVoicebox", lambda **kw: client)
    monkeypatch.setattr(jobs, "ensure_server", lambda _: None)
    jobs.run(folder)
    client.client.post.assert_called_once_with("/generate/existing/cancel")
    client.generate.assert_not_called()
    assert jobs.status(req["id"])["status"] == "cancelled"
    assert "error" not in jobs.status(req["id"])
    assert (folder / "raw/manifest.json").exists()
