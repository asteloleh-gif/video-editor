"""Private, durable local Remotion jobs. Fixed installed renderer; JSON IPC only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

TERMINAL = {"ready", "failed", "cancelled"}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write(path, value):
    temporary = path.with_name(f".{path.name}.{uuid.uuid4()}.tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def lock(path, nonblocking=False):
    with path.open("a") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        try:
            yield handle
        finally:
            # Do not explicitly LOCK_UN: a renderer that inherited this FD must
            # retain the lock if its Python parent dies during an encode.
            pass


class StoryJobs:
    def __init__(self, home=None):
        self.home = Path(home or os.environ.get("ASTEL_STORY_HOME", Path.home() / ".local/share/astel-story-render")).resolve()
        self.jobs = self.home / "jobs"
        self.jobs.mkdir(parents=True, exist_ok=True, mode=0o700)

    def folder(self, job_id):
        if str(uuid.UUID(job_id)) != job_id:
            raise ValueError("Invalid job ID")
        folder = self.jobs / job_id
        if folder.resolve().parent != self.jobs or folder.is_symlink():
            raise ValueError("Invalid job path")
        return folder

    def manifest(self, package_id):
        if not isinstance(package_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", package_id):
            raise ValueError("Invalid package")
        root = self.home / "packages" / package_id
        if root.is_symlink() or not root.resolve().is_relative_to(self.home / "packages"):
            raise ValueError("Invalid package path")
        data = json.loads((root / "manifest.json").read_text())
        if data["id"] != package_id or data["composition"] != "AstelStoryPilot-3D":
            raise ValueError("Unsupported composition")
        return root, data

    def packages(self):
        values = []
        for path in sorted((self.home / "packages").glob("*/manifest.json")):
            _, data = self.manifest(path.parent.name)
            values.append({key: data[key] for key in ("id", "name", "description", "duration", "revision")})
        return values

    def verify(self, root, manifest):
        for relative, expected in manifest["files"].items():
            path = root / relative
            if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or digest(path) != expected:
                raise ValueError("Prepared package changed; reinstall it")

    def update(self, folder, **values):
        with lock(folder / "state.lock"):
            data = json.loads((folder / "job.json").read_text())
            data.update(values, updated_at=datetime.now(timezone.utc).isoformat())
            write(folder / "job.json", data)
        return data

    def submit(self, request):
        if set(request) != {"id", "package_id", "project_id"}:
            raise ValueError("Unsupported settings")
        folder = self.folder(request["id"])
        _, package = self.manifest(request["package_id"])
        if not isinstance(request["project_id"], str) or not 1 <= len(request["project_id"]) <= 128:
            raise ValueError("Open a project first")
        payload = {"package_id": package["id"], "project_id": request["project_id"], "revision": package["revision"]}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with lock(self.home / "submit.lock"):
            if folder.exists():
                if json.loads((folder / "job.json").read_text())["request_hash"] != fingerprint:
                    raise ValueError("Job ID belongs to a different request")
            else:
                folder.mkdir(mode=0o700)
                now = datetime.now(timezone.utc).isoformat()
                write(folder / "job.json", {"id": folder.name, **payload, "request_hash": fingerprint, "status": "queued", "progress": 0, "created_at": now, "updated_at": now})
        return self.resume(folder.name)

    def spawn(self, folder):
        # The lock is acquired before spawning, eliminating PID reuse checks and
        # duplicate workers on rapid polling/reopen. Node inherits it as well.
        try:
            with lock(folder / "run.lock", True) as handle:
                with (folder / "worker.log").open("ab") as log:
                    os.chmod(folder / "worker.log", 0o600)
                    subprocess.Popen([sys.executable, "-m", "video_editor.story_jobs", "worker", "--id", folder.name, "--lock-fd", str(handle.fileno())],
                                     pass_fds=(handle.fileno(),), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                                     env={**os.environ, "ASTEL_STORY_HOME": str(self.home)})
        except BlockingIOError:
            pass

    def status(self, job_id):
        folder = self.folder(job_id)
        data = json.loads((folder / "job.json").read_text())
        if data["status"] not in TERMINAL and (folder / "result.json").is_file():
            try:
                self.finish(folder)
            except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
                self.update(folder, status="failed", phase="Ошибка проверки", error="MP4 не прошёл проверку. Создайте новую задачу.")
            data = json.loads((folder / "job.json").read_text())
        if data["status"] not in TERMINAL:
            try:
                progress = json.loads((folder / "progress.json").read_text())
                data["progress"] = max(0, min(.99, float(progress["progress"])))
                data["phase"] = progress["phase"]
            except (FileNotFoundError, ValueError, KeyError):
                pass
        return {key: data[key] for key in ("id", "package_id", "project_id", "revision", "status", "progress", "phase", "duration", "created_at", "updated_at", "error") if key in data}

    def recent(self):
        folders = sorted(self.jobs.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
        return [self.status(p.parent.name) for p in folders]

    def resume(self, job_id):
        result = self.status(job_id)
        if result["status"] not in TERMINAL:
            self.spawn(self.folder(job_id))
        return result

    def cancel(self, job_id):
        folder = self.folder(job_id)
        with lock(folder / "state.lock"):
            data = json.loads((folder / "job.json").read_text())
            if data["status"] not in TERMINAL:
                (folder / "cancel").touch(mode=0o600)
        self.spawn(folder) if data["status"] not in TERMINAL else None
        return self.status(job_id)

    def finish(self, folder):
        with lock(folder / "state.lock"):
            data = json.loads((folder / "job.json").read_text())
            if data["status"] in TERMINAL:
                return
            if (folder / "cancel").exists():
                data.update(status="cancelled", phase="Остановлено")
            else:
                receipt = json.loads((folder / "result.json").read_text())
                output = folder / "video.mp4"
                if output.is_symlink() or digest(output) != receipt["sha256"] or output.stat().st_size > 300 * 1024 * 1024:
                    raise ValueError("Render output changed")
                probe = subprocess.check_output([str(self.home / "bin/ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)], timeout=20)
                info = json.loads(probe)
                video = next(s for s in info["streams"] if s["codec_type"] == "video")
                audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
                _, package = self.manifest(data["package_id"])
                duration = float(info["format"]["duration"])
                if video["width"] != 1080 or video["height"] != 1920 or audio["codec_name"] != "aac" or abs(duration - package["duration"]) > .3:
                    raise ValueError("Unexpected render format or duration")
                data.update(status="ready", progress=1, phase="Готово", duration=duration, sha256=receipt["sha256"])
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            write(folder / "job.json", data)

    def video(self, job_id):
        status = self.status(job_id)
        if status["status"] != "ready":
            raise ValueError("Video is not ready")
        folder = self.folder(job_id)
        data = json.loads((folder / "job.json").read_text())
        output = folder / "video.mp4"
        if output.is_symlink() or digest(output) != data["sha256"]:
            raise ValueError("Video changed")
        return {"path": str(output), "sha256": data["sha256"]}

    def worker(self, job_id, inherited_fd):
        folder = self.folder(job_id)
        # The inherited file description owns run.lock until Python and Node exit.
        with os.fdopen(inherited_fd, "a") as run_handle:
            try:
                while True:
                    if (folder / "cancel").exists():
                        self.update(folder, status="cancelled", phase="Остановлено")
                        return
                    try:
                        global_handle = (self.home / "render.lock").open("a")
                        fcntl.flock(global_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        global_handle.close()
                        self.update(folder, status="queued", phase="Ожидание другого рендера")
                        time.sleep(.5)
                with global_handle:
                    self.run(folder, (run_handle.fileno(), global_handle.fileno()))
            except Exception:
                # Details remain in the private worker log, never renderer IPC.
                import traceback
                traceback.print_exc()
                self.update(folder, status="failed", phase="Ошибка", error="Сборка не завершена. Проверьте установку пакета и создайте новую задачу.")

    def run(self, folder, descriptors):
        if (folder / "result.json").exists():
            self.finish(folder)
            return
        data = json.loads((folder / "job.json").read_text())
        root, package = self.manifest(data["package_id"])
        if data["revision"] != package["revision"]:
            raise ValueError("Package revision changed")
        self.update(folder, status="rendering", phase="Проверка материалов")
        self.verify(root, package)
        receipt = json.loads((self.home / "install.json").read_text())
        if receipt.get("runtime_files"):
            self.verify(self.home / "runtime", {"files": receipt["runtime_files"]})
        if (folder / "cancel").exists():
            self.update(folder, status="cancelled", phase="Остановлено")
            return
        process = subprocess.Popen([str(self.home / "bin/node"), str(self.home / "runtime/render.cjs")],
                                   stdin=subprocess.PIPE, pass_fds=descriptors, start_new_session=True, cwd=self.home / "runtime")
        process.stdin.write(json.dumps({"packageRoot": str(root), "jobRoot": str(folder)}).encode())
        process.stdin.close()
        deadline = time.monotonic() + 3600
        while process.poll() is None:
            if (folder / "cancel").exists() or time.monotonic() > deadline:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                if (folder / "cancel").exists():
                    self.update(folder, status="cancelled", phase="Остановлено")
                    return
                raise TimeoutError("Render timeout")
            time.sleep(.4)
        if (folder / "cancel").exists():
            self.update(folder, status="cancelled", phase="Остановлено")
            return
        if process.returncode:
            raise RuntimeError("Renderer failed")
        self.finish(folder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["packages", "recent", "submit", "status", "resume", "cancel", "video", "worker"])
    parser.add_argument("--id")
    parser.add_argument("--lock-fd", type=int)
    args = parser.parse_args()
    jobs = StoryJobs()
    if args.command == "worker":
        jobs.worker(args.id, args.lock_fd)
        return
    if args.command == "submit":
        value = jobs.submit(json.loads(sys.stdin.read(4096)))
    elif args.command in {"packages", "recent"}:
        value = getattr(jobs, args.command)()
    else:
        value = getattr(jobs, args.command)(args.id)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    main()
