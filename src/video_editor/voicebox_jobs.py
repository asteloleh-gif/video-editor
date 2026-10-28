"""Persistent local speech jobs for OpenReel. JSON stdin/stdout; no public server."""
from __future__ import annotations

import argparse
from array import array
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
import wave

import httpx

from .voicebox import DEFAULT_HOME, LocalVoicebox, write_json

WARM = "equalizer=f=180:t=q:w=0.8:g=2.5,equalizer=f=1100:t=q:w=1:g=-2,acompressor=threshold=0.15:ratio=1.6:attack=15:release=140:knee=2.828:makeup=1"
TERMINAL = {"ready", "failed", "cancelled"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def lock(path, nonblocking=False):
    with path.open("a") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class SpeechJobs:
    def __init__(self, home=None):
        self.home = Path(home or os.environ.get("ASTEL_VOICEBOX_HOME", DEFAULT_HOME)).resolve()
        self.root = self.home / "openreel"
        self.jobs = self.root / "jobs"
        self.jobs.mkdir(parents=True, exist_ok=True, mode=0o700)

    def profiles(self):
        config = json.loads((self.root / "profiles.json").read_text())
        return config["profiles"]

    def binding(self, profile):
        path = (self.root / profile["binding"]).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("Missing approved voice binding")
        return path

    def folder(self, job_id):
        if str(uuid.UUID(job_id)) != job_id:
            raise ValueError("Invalid job ID")
        path = (self.jobs / job_id).resolve()
        if path.parent != self.jobs.resolve():
            raise ValueError("Invalid job path")
        return path

    def status(self, job_id):
        path = self.folder(job_id)
        job = json.loads((path / "job.json").read_text())
        # Never expose reference paths or backend errors/tracebacks to the renderer.
        return {k: job[k] for k in ("id", "status", "profile", "text", "speed", "warm", "project_id", "created_at", "updated_at", "duration", "error") if k in job}

    def update(self, folder, **values):
        job = json.loads((folder / "job.json").read_text())
        job.update(values, updated_at=now())
        write_json(folder / "job.json", job)

    def submit(self, request):
        if set(request) - {"id", "profile", "text", "speed", "warm", "project_id"}:
            raise ValueError("Unsupported speech settings")
        folder = self.folder(request["id"])
        profile = next((p for p in self.profiles() if p["id"] == request["profile"]), None)
        if not profile:
            raise ValueError("Select an approved voice")
        text = request.get("text", "")
        if not isinstance(text, str):
            raise ValueError("Enter 1–5000 characters")
        text = text.strip()
        speed = request.get("speed", profile.get("speed", 1))
        warm = request.get("warm", profile.get("warm", False))
        project_id = request.get("project_id", "")
        if not isinstance(text, str) or not 1 <= len(text) <= 5000:
            raise ValueError("Enter 1–5000 characters")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or not .75 <= speed <= 1.5:
            raise ValueError("Speed must be between 0.75 and 1.5")
        if not isinstance(warm, bool) or (warm and profile["language"] != "ru"):
            raise ValueError("Tone B is available for the Russian profile")
        if not isinstance(project_id, str) or len(project_id) > 128:
            raise ValueError("Invalid project")
        payload = {"profile": profile["id"], "text": text, "speed": speed, "warm": warm, "project_id": project_id}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with lock(self.root / "submit.lock"):
            if folder.exists():
                if json.loads((folder / "job.json").read_text())["request_hash"] != fingerprint:
                    raise ValueError("This job ID already belongs to another request")
                return self.status(request["id"])
            binding = json.loads(self.binding(profile).read_text())
            folder.mkdir(mode=0o700)
            write_json(folder / "binding.json", binding)
            write_json(folder / "job.json", {"id": request["id"], **payload, "language": profile["language"], "request_hash": fingerprint, "status": "queued", "created_at": now(), "updated_at": now()})
            self.spawn(folder)
        return self.status(request["id"])

    def spawn(self, folder):
        with lock(folder / "launch.lock"):
            pid_file = folder / "worker.pid"
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text()), 0)
                    return
                except (ProcessLookupError, ValueError):
                    pass
            with (folder / "worker.log").open("ab") as log:
                os.chmod(folder / "worker.log", 0o600)
                process = subprocess.Popen([sys.executable, "-m", "video_editor.voicebox_jobs", "worker", "--id", folder.name], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            pid_file.write_text(str(process.pid))
            pid_file.chmod(0o600)

    def resume(self, job_id):
        folder = self.folder(job_id)
        if self.status(job_id)["status"] not in TERMINAL:
            self.spawn(folder)
        return self.status(job_id)

    def cancel(self, job_id):
        folder = self.folder(job_id)
        if self.status(job_id)["status"] not in TERMINAL:
            (folder / "cancel").touch(mode=0o600)
        return self.status(job_id)

    def ensure_server(self, client):
        try:
            client.marker()
            return
        except httpx.ConnectError:
            pass
        with lock(self.root / "server-start.lock"):
            try:
                client.marker()
                return
            except httpx.ConnectError:
                pass
            serve = self.root / "server/serve.py"
            if not serve.is_file():
                raise RuntimeError("Local Voicebox service is not installed")
            with (self.root / "server.log").open("ab") as log:
                os.chmod(self.root / "server.log", 0o600)
                subprocess.Popen([sys.executable, str(serve)], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            for _ in range(60):
                time.sleep(.5)
                try:
                    client.marker()
                    return
                except httpx.ConnectError:
                    continue
            raise RuntimeError("Voicebox did not start")

    def worker(self, job_id):
        folder = self.folder(job_id)
        try:
            with lock(folder / "run.lock", nonblocking=True):
                self.run(folder)
        except BlockingIOError:
            return

    def run(self, folder):
        client = LocalVoicebox(home=self.home)
        try:
            if self.status(folder.name)["status"] in TERMINAL:
                return
            self.update(folder, status="starting")
            self.ensure_server(client)
            job = json.loads((folder / "job.json").read_text())
            raw = folder / "raw"
            while True:
                cancelling = (folder / "cancel").exists()
                if cancelling:
                    self.update(folder, status="cancelling")
                    if not (raw / "manifest.json").exists():
                        self.update(folder, status="cancelled")
                        return
                    receipt = json.loads((raw / "manifest.json").read_text())
                    if receipt.get("generation_id") and not (folder / "cancel-sent").exists() and receipt["status"] != "completed":
                        response = client.client.post(f"/generate/{receipt['generation_id']}/cancel")
                        response.raise_for_status()
                        (folder / "cancel-sent").touch(mode=0o600)
                else:
                    self.update(folder, status="generating")
                try:
                    if raw.exists():
                        manifest = json.loads((raw / "manifest.json").read_text())
                        if not manifest.get("generation_id"):
                            raise RuntimeError("Submission uncertain; inspect Voicebox history before retrying")
                        result = client.resume(raw, timeout=2, poll_interval=.5)
                    else:
                        result = client.generate(folder / "binding.json", job["text"], raw, language=job["language"], seed=42, timeout=2)
                    break
                except TimeoutError:
                    continue
            if (folder / "cancel").exists():
                self.update(folder, status="cancelled")
                return
            self.update(folder, status="processing")
            self.process_audio(folder, job, result)
            if (folder / "cancel").exists():
                self.update(folder, status="cancelled")
            else:
                self.update(folder, status="ready")
        except Exception as exc:
            if (folder / "cancel").exists():
                self.update(folder, status="cancelled")
            else:
                self.update(folder, status="failed", error="Озвучка не завершена. Результаты сохранены; проверьте журнал Voicebox.")
            # Diagnostics stay in the owner-only job log, never in IPC responses.
            print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        finally:
            client.close()

    def process_audio(self, folder, job, result):
        source = folder / "raw/narration.wav"
        if digest(source) != result["audio_sha256"]:
            raise ValueError("Source audio changed")
        filters = ["highpass=f=60:p=2"]
        if job["warm"]:
            filters.append(WARM)
        if job["speed"] != 1:
            filters.append(f"atempo={job['speed']}")
        ffmpeg = next((p for p in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"] if Path(p).is_file()), "ffmpeg")
        def run(args):
            return subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-nostats", *args], capture_output=True, text=True, check=True)
        def levels(path):
            r = run(["-i", str(path), "-af", "loudnorm=I=-22:TP=-2:LRA=11:print_format=json", "-f", "null", "-"])
            return json.JSONDecoder().raw_decode(r.stderr[r.stderr.rfind("{"):])[0]
        with tempfile.TemporaryDirectory(prefix="process-", dir=folder) as temporary:
            filtered = Path(temporary) / "filtered.wav"
            run(["-i", str(source), "-af", ",".join(filters), "-c:a", "pcm_f32le", "-y", str(filtered)])
            level = levels(filtered)
            gain = min(-22.07 - float(level["input_i"]), -2 - float(level["input_tp"]))
            final = Path(temporary) / "narration.wav"
            run(["-i", str(filtered), "-af", f"volume={gain}dB", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", "-y", str(final)])
            with wave.open(str(final)) as wav:
                duration = wav.getnframes() / wav.getframerate()
                samples = array("h", wav.readframes(wav.getnframes()))
                if duration <= 0 or not samples or max(abs(s) for s in samples) >= 32767:
                    raise ValueError("Invalid or clipped audio")
            destination = folder / "narration.wav"
            if destination.exists() and destination.read_bytes() != final.read_bytes():
                raise ValueError("Existing output differs; preserve it for inspection")
            if not destination.exists():
                final.rename(destination)
                destination.chmod(0o600)
            self.update(folder, duration=duration, audio_sha256=digest(destination), processing={"filters": filters, "gain_db": gain})

    def audio(self, job_id):
        folder = self.folder(job_id)
        job = json.loads((folder / "job.json").read_text())
        path = folder / "narration.wav"
        if job["status"] != "ready" or digest(path) != job["audio_sha256"]:
            raise ValueError("Audio is not ready or has changed")
        return {"path": str(path), "sha256": job["audio_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["profiles", "submit", "status", "resume", "cancel", "audio", "worker"])
    parser.add_argument("--id")
    args = parser.parse_args()
    jobs = SpeechJobs()
    if args.command == "profiles":
        result = [{k: p[k] for k in ("id", "name", "language", "warm", "speed")} for p in jobs.profiles()]
    elif args.command == "submit":
        result = jobs.submit(json.load(sys.stdin))
    else:
        result = getattr(jobs, args.command)(args.id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
