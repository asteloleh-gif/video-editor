import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

from video_editor.media_workspace import Workspace, fingerprint


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    service = Workspace(tmp_path)
    monkeypatch.setattr(service, "spawn", lambda _: None)
    return service


def request(kind="search", **payload):
    return {"id": str(uuid.uuid4()), "kind": kind, "payload": payload or {"query": "warehouse", "providers": ["commons"]}}


def test_job_idempotency_persistence_and_conflict(workspace):
    value = request()
    first = workspace.submit(value)
    assert workspace.submit(value)["id"] == first["id"]
    with pytest.raises(ValueError, match="already belongs"):
        workspace.submit({**value, "payload": {"query": "different", "providers": ["commons"]}})
    reopened = Workspace(workspace.home)
    assert reopened.listing()["jobs"][0]["id"] == first["id"]


@pytest.mark.parametrize("payload", [{"query": "a", "providers": ["shell"]}, {"query": "", "providers": ["commons"]}, {"query": "a\nb", "providers": ["commons"]}, {"query": "x", "providers": ["commons"], "command": "sh"}])
def test_search_boundary(workspace, payload):
    with pytest.raises(ValueError): workspace.submit(request(**payload))


def test_batch_limit_and_duplicate_topics(workspace, monkeypatch):
    with pytest.raises(ValueError): workspace.submit(request("batch", topics=["x"] * 101, providers=["commons"]))
    calls = []
    monkeypatch.setattr("video_editor.media_workspace.commons_search", lambda query: calls.append(query) or [])
    job = workspace.submit(request("batch", topics=["one", "two", "one"], providers=["commons"]))
    workspace.run_search(job["id"], {"topics": ["one", "two", "one"], "providers": ["commons"]})
    assert calls == ["one", "two"]
    workspace.run_search(job["id"], {"topics": ["one", "two", "one"], "providers": ["commons"]})
    assert calls == ["one", "two"]  # durable checkpoint prevents repeating work


def test_provider_failure_keeps_other_results(workspace, monkeypatch):
    def fail(_): raise OSError("network")
    monkeypatch.setattr("video_editor.media_workspace.commons_search", fail)
    monkeypatch.setattr("video_editor.video_search.search", lambda *a, **k: {"results": [{"id": "abcdef12345", "title": "Found", "channel": "Owner", "views": None, "url": "https://www.youtube.com/watch?v=abcdef12345"}]})
    data = {"query": "topic", "providers": ["commons", "youtube"]}
    job = workspace.submit(request(**data));workspace.run_search(job["id"], data)
    result = workspace.listing()["searches"][0]
    assert len(result["candidates"]) == 1
    assert result["errors"][0]["provider"] == "commons"
    assert result["candidates"][0]["downloadable"] is False


def test_source_identity_dedup_and_no_private_paths(workspace):
    data = {"provider": "local", "source_id": "hash", "title": "File", "local_path": "/private/owner.mov", "file_url": "https://example.com/file", "views": None}
    first = workspace.save_candidate(data)
    assert workspace.save_candidate(data) == first
    public = workspace.candidate(first, public=True)
    assert "local_path" not in public and "file_url" not in public


def test_reference_cannot_be_downloaded(workspace):
    key = workspace.save_candidate({"provider": "youtube", "source_id": "abcdef12345", "title": "Reference", "downloadable": False})
    job = workspace.submit(request("acquire", candidate_id=key))
    with pytest.raises(ValueError, match="reference"):
        workspace.acquire(key, job["id"])


def test_cancellation_survives_reopen(workspace):
    job = workspace.submit(request())
    workspace.cancel(job["id"])
    with pytest.raises(InterruptedError): Workspace(workspace.home).cancelled(job["id"])


def test_real_local_file_acquisition_receipt_and_reuse(workspace, tmp_path):
    source = tmp_path / "owner.jpg"
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=green:s=320x180", "-frames:v", "1", str(source)], check=True)
    original = source.read_bytes()
    job = workspace.import_local(source)
    with workspace.db() as db:
        payload = json.loads(db.execute("SELECT payload FROM jobs WHERE id=?", (job["id"],)).fetchone()[0])
    asset = workspace.acquire(payload["candidate_id"], job["id"])
    assert source.read_bytes() == original
    assert asset["width"] == 320 and asset["kind"] == "image"
    receipt = workspace.file_receipt(asset["id"])
    assert Path(receipt["path"]).is_file()
    assert workspace.acquire(payload["candidate_id"], job["id"])["id"] == asset["id"]
    Path(receipt["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"): workspace.file_receipt(asset["id"])


def test_download_origin_guard(workspace):
    candidate = workspace.save_candidate({"provider": "commons", "source_id": "1", "title": "File", "downloadable": True, "file_url": "http://127.0.0.1/private"})
    job = workspace.submit(request("acquire", candidate_id=candidate))
    with pytest.raises(ValueError, match="origin denied"): workspace.acquire(candidate, job["id"])


def test_interrupted_normalization_reuses_original(workspace, tmp_path, monkeypatch):
    source = tmp_path / "owner.jpg"
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=green:s=320x180", "-frames:v", "1", str(source)], check=True)
    job = workspace.import_local(source)
    with workspace.db() as db:
        candidate_id = json.loads(db.execute("SELECT payload FROM jobs WHERE id=?", (job["id"],)).fetchone()[0])["candidate_id"]
    real_process = workspace.process
    def interrupted(*args, **kwargs): raise InterruptedError()
    monkeypatch.setattr(workspace, "process", interrupted)
    with pytest.raises(InterruptedError): workspace.acquire(candidate_id, job["id"])
    source.unlink()  # Recovery must use the durable original, not the picker path.
    monkeypatch.setattr(workspace, "process", real_process)
    asset = workspace.acquire(candidate_id, job["id"])
    assert Path(asset["original_path"]).is_file()
    assert len(list(workspace.assets.iterdir())) == 1


def test_stale_parent_cannot_create_new_revision(workspace):
    root, newer = str(uuid.uuid4()), str(uuid.uuid4())
    def save(key, revision, digest):
        data = {"id": key, "root_id": root, "revision": revision, "digest": digest}
        with workspace.db() as db:
            db.execute("INSERT INTO stories VALUES(?,?,?,?,?)", (key, revision, digest, json.dumps(data), "now"))
    save(root, 1, "one")
    assert workspace.parent_story({"parent_story_id": root, "parent_digest": "one"})["revision"] == 1
    save(newer, 2, "two")
    with pytest.raises(ValueError, match="stale"):
        workspace.parent_story({"parent_story_id": root, "parent_digest": "one"})


def test_completed_render_recovery_does_not_generate_voice(workspace, monkeypatch):
    from video_editor import story_workspace
    from video_editor.story_jobs import digest
    job = workspace.submit(request()); folder = workspace.folder(job["id"])
    (folder / "video.mp4").write_bytes(b"verified-final")
    (folder / "props.json").write_text(json.dumps({"story": {"id": job["id"]}}))
    (folder / "render-receipt.json").write_text(json.dumps({"sha256": digest(folder / "video.mp4"), "props_sha256": digest(folder / "props.json")}))
    committed = []
    monkeypatch.setattr(story_workspace, "commit_story", lambda *args: committed.append(args[2]))
    monkeypatch.setattr(story_workspace, "speech", lambda *args: pytest.fail("completed render must not regenerate speech"))
    story_workspace.build_story(workspace, job["id"], {}, ())
    assert committed == [{"id": job["id"]}]
    (folder / "video.mp4").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        story_workspace.build_story(workspace, job["id"], {}, ())


def test_installer_refuses_update_while_worker_active(tmp_path, monkeypatch):
    import fcntl
    import importlib.util
    import sys
    file = Path(__file__).parents[1] / "scripts/setup_media_workspace_mac.py"
    spec = importlib.util.spec_from_file_location("workspace_installer", file)
    installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
    monkeypatch.setattr(installer, "HOME", tmp_path)
    monkeypatch.setattr(sys, "argv", [str(file), "--node", "/unused"])
    with (tmp_path / "worker.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(SystemExit, match="active"):
            installer.main()
