import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from video_editor.story_jobs import StoryJobs, digest, lock, write


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    service = StoryJobs(tmp_path)
    root = tmp_path / "packages/amazon"
    root.mkdir(parents=True)
    (root / "asset").write_bytes(b"approved")
    write(root / "manifest.json", {"id": "amazon", "composition": "AstelStoryPilot-3D", "revision": "frozen", "name": "Amazon", "description": "Test", "duration": 2, "files": {"asset": digest(root / "asset")}})
    monkeypatch.setattr(service, "spawn", lambda folder: None)
    return service


def request():
    return {"id": str(uuid.uuid4()), "package_id": "amazon", "project_id": "project-a"}


def test_retry_is_idempotent_and_rejects_conflicting_uuid(jobs):
    payload = request()
    assert jobs.submit(payload)["status"] == "queued"
    assert jobs.submit(payload)["id"] == payload["id"]
    assert len(list(jobs.jobs.iterdir())) == 1
    with pytest.raises(ValueError, match="different request"):
        jobs.submit({**payload, "project_id": "b"})


@pytest.mark.parametrize("change", [{"package_id": "../secret"}, {"id": "../../x"}, {"project_id": ""}, {"command": "rm"}])
def test_rejects_paths_code_and_invalid_identity(jobs, change):
    with pytest.raises(ValueError):
        jobs.submit({**request(), **change})


def test_persistent_recent_and_safe_recovery(jobs):
    payload = request()
    jobs.submit(payload)
    restarted = StoryJobs(jobs.home)
    assert restarted.recent()[0]["id"] == payload["id"]
    calls = []
    restarted.spawn = calls.append
    restarted.resume(payload["id"])
    assert calls == [jobs.folder(payload["id"])]


def test_cancel_before_render_does_not_run_renderer(jobs):
    payload = request()
    jobs.submit(payload)
    jobs.cancel(payload["id"])
    folder = jobs.folder(payload["id"])
    with lock(folder / "run.lock") as handle:
        # worker owns and closes the duplicated descriptor.
        jobs.worker(payload["id"], os.dup(handle.fileno()))
    assert jobs.status(payload["id"])["status"] == "cancelled"
    assert not (folder / "video.mp4").exists()


def test_package_tamper_and_escape_fail_before_execution(jobs):
    root, manifest = jobs.manifest("amazon")
    jobs.verify(root, manifest)
    (root / "asset").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        jobs.verify(root, manifest)
    with pytest.raises(ValueError):
        jobs.verify(root, {"files": {"../manifest.json": "x"}})


def test_output_tamper_is_rejected(jobs):
    payload = request()
    jobs.submit(payload)
    folder = jobs.folder(payload["id"])
    (folder / "video.mp4").write_bytes(b"changed")
    write(folder / "result.json", {"sha256": "0" * 64})
    assert jobs.status(payload["id"])["status"] == "failed"
    assert jobs.recent()[0]["status"] == "failed"
    with pytest.raises(ValueError, match="not ready"):
        jobs.video(payload["id"])


def test_inherited_lock_survives_parent_handle_close(tmp_path):
    path = tmp_path / "worker.lock"
    with lock(path) as handle:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"], pass_fds=(handle.fileno(),))
    try:
        with pytest.raises(BlockingIOError):
            with lock(path, True):
                pass
    finally:
        child.wait()
    with lock(path, True):
        pass


def test_ready_output_requires_audio_geometry_duration_and_hash(jobs, monkeypatch):
    payload = request()
    jobs.submit(payload)
    folder = jobs.folder(payload["id"])
    (folder / "video.mp4").write_bytes(b"video")
    write(folder / "result.json", {"sha256": digest(folder / "video.mp4")})
    probe = {"streams": [{"codec_type": "video", "width": 1080, "height": 1920}, {"codec_type": "audio", "codec_name": "aac"}], "format": {"duration": "2.0"}}
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: json.dumps(probe).encode())
    assert jobs.status(payload["id"])["status"] == "ready"
    assert jobs.video(payload["id"])["path"] == str(folder / "video.mp4")
    restarted = StoryJobs(jobs.home)
    restarted.spawn = lambda _: pytest.fail("Completed output must not rerender")
    restarted.resume(payload["id"])
    jobs.cancel(payload["id"])
    assert jobs.status(payload["id"])["status"] == "ready"
