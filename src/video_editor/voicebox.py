"""Local Voicebox pilot: bind one reference, generate versioned review audio.

No publishing, script rewriting, generic-voice fallback, or HTTP resubmission.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import quote
import wave

import httpx

UPSTREAM_COMMIT = "8af7efe62fab8d33e2a5dfbedabaa45f68a5184f"
DEFAULT_HOME = Path.home() / ".local/share/astel-voicebox"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare_reference(source: Path, output: Path, start: float, duration: float):
    if source.resolve() == output.resolve() or not source.is_file() or start < 0 or not 2 <= duration <= 30:
        raise ValueError("Choose a separate output WAV and a 2–30 second reference segment")
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicebox-reference-", dir=output.parent) as folder:
        temporary = Path(folder) / "reference.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", str(source.resolve()), "-t", str(duration), "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(temporary)], check=True)
        with wave.open(str(temporary)) as audio:
            if audio.getnframes() / audio.getframerate() < 2:
                raise ValueError("Selected reference contains less than 2 seconds of audio")
        with output.open("xb") as destination:
            destination.write(temporary.read_bytes())
    return {"reference": str(output.resolve()), "sha256": sha256(output.read_bytes()), "start": start, "duration": duration, "raw_unchanged": True}


def write_json(path: Path, value: dict):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)


class LocalVoicebox:
    def __init__(self, *, home: Path | None = None, transport=None):
        self.home = Path(home or os.environ.get("ASTEL_VOICEBOX_HOME", DEFAULT_HOME)).resolve()
        self.client = httpx.Client(base_url="http://127.0.0.1:17493", timeout=60, transport=transport)

    def close(self):
        self.client.close()

    def get(self, path):
        response = self.client.get(path)
        response.raise_for_status()
        return response.json()

    def marker(self):
        marker = self.get("/astel/health")
        if marker.get("service") != "astel-voicebox" or marker.get("required_clone") is not True or marker.get("upstream_commit") != UPSTREAM_COMMIT:
            raise ValueError("Astel's pinned required-clone runtime is not running")
        return marker

    def stored_sample(self, sample):
        data = (self.home / "data").resolve()
        path = Path(sample["audio_path"])
        path = (path if path.is_absolute() else data / path).resolve()
        if not path.is_relative_to(data) or not path.is_file():
            raise ValueError("Reference audio is missing or outside this local runtime")
        return path

    def register(self, reference: Path, transcript: str, binding: Path, name="Oleh EN"):
        marker = self.marker()
        if not reference.is_file() or reference.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("A local reference file of at most 50 MB is required")
        if not transcript.strip() or len(transcript) > 1000:
            raise ValueError("Supply the exact reference transcript, up to 1000 characters")
        with wave.open(str(reference)) as audio:
            duration = audio.getnframes() / audio.getframerate()
            if not 2 <= duration <= 30:
                raise ValueError("Prepare a 2–30 second WAV reference before creating a profile")
        # Reserve before the first mutation. An incomplete attempt remains inspectable.
        binding.parent.mkdir(parents=True, exist_ok=True)
        with binding.open("x") as stream:
            stream.write('{"status":"registering"}\n')
        binding.chmod(0o600)
        receipt = {"status": "registering", "runtime": marker, "original_reference_sha256": sha256(reference.read_bytes())}
        try:
            response = self.client.post("/profiles", json={"name": name, "language": "en", "voice_type": "cloned", "default_engine": "qwen"})
            response.raise_for_status()
            receipt["profile_id"] = response.json()["id"]
            write_json(binding, receipt)
            with reference.open("rb") as audio:
                response = self.client.post(f"/profiles/{quote(receipt['profile_id'], safe='')}/samples", data={"reference_text": transcript}, files={"file": (reference.name, audio)})
            response.raise_for_status()
            sample = response.json()
            receipt.update(status="bound", sample=sample, reference_sha256=sha256(self.stored_sample(sample).read_bytes()))
            write_json(binding, receipt)
        except Exception as exc:
            receipt.update(status="registration_incomplete", error=type(exc).__name__)
            write_json(binding, receipt)
            raise
        return receipt

    def verify_binding(self, path: Path):
        binding = json.loads(path.read_text())
        return self.verify_bound(binding)

    def verify_bound(self, binding):
        marker = self.marker()
        if binding.get("status") != "bound":
            raise ValueError("Profile registration is incomplete; inspect it before any retry")
        if marker != binding["runtime"]:
            # Model installation changes presence, but never the required-clone policy.
            stable = lambda value: {k: v for k, v in value.items() if k != "model_06b_present"}
            if stable(marker) != stable(binding["runtime"]):
                raise ValueError("Runtime changed since the reference was bound")
        key = quote(binding["profile_id"], safe="")
        profile = self.get(f"/profiles/{key}")
        samples = self.get(f"/profiles/{key}/samples")
        if profile.get("voice_type") != "cloned" or profile.get("effects_chain") or profile.get("personality"):
            raise ValueError("Pilot requires a cloned profile without effects or personality rewriting")
        if samples != [binding["sample"]]:
            raise ValueError("Reference samples or transcript changed; create a new binding")
        if sha256(self.stored_sample(samples[0]).read_bytes()) != binding["reference_sha256"]:
            raise ValueError("Reference audio changed; generation aborted")
        return binding

    def generate(self, binding_path: Path, text: str, output: Path, *, model_size="0.6B", seed=42, timeout=1800):
        binding = self.verify_binding(binding_path)
        if not text.strip() or len(text) > 5000 or model_size not in ("0.6B", "1.7B") or seed < 0:
            raise ValueError("Use nonempty pilot text up to 5000 characters, a Base model and a nonnegative seed")
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        request = {"profile_id": binding["profile_id"], "text": text, "language": "en", "engine": "qwen", "model_size": model_size, "seed": seed, "personality": False, "instruct": None, "effects_chain": [], "normalize": True}
        receipt = {"status": "submitting", "created_at": datetime.now(timezone.utc).isoformat(), "request": request, "request_sha256": sha256(json.dumps(request, sort_keys=True).encode()), "binding": binding, "qa_status": "awaiting_owner_listening"}
        (output / "script.txt").write_text(text)
        write_json(output / "manifest.json", receipt)
        try:
            # One POST only. A timeout may mean the server accepted the request.
            response = self.client.post("/generate", json=request)
            response.raise_for_status()
            receipt.update(status="submitted", generation_id=response.json()["id"])
            write_json(output / "manifest.json", receipt)
        except Exception as exc:
            receipt.update(status="submission_unconfirmed", error=type(exc).__name__)
            write_json(output / "manifest.json", receipt)
            raise
        return self.resume(output, timeout=timeout)

    def resume(self, output: Path, *, timeout=1800, poll_interval=1):
        """Read an existing generation; this method never submits a new one."""
        receipt = json.loads((output / "manifest.json").read_text())
        self.verify_bound(receipt["binding"])
        if receipt["status"] == "completed":
            if sha256((output / "narration.wav").read_bytes()) != receipt["audio_sha256"]:
                raise ValueError("Saved audio changed")
            return receipt
        key = quote(receipt["generation_id"], safe="")
        deadline = time.monotonic() + timeout
        while True:
            # /generate/{id}/status is SSE; use the JSON history endpoint here.
            result = self.get(f"/history/{key}")
            if result["status"] == "failed":
                receipt.update(status="failed", error=result.get("error"))
                write_json(output / "manifest.json", receipt)
                raise RuntimeError("Voicebox generation failed; see the saved manifest")
            if result["status"] == "completed":
                break
            if time.monotonic() >= deadline:
                receipt.update(status="pending", last_server_status=result["status"])
                write_json(output / "manifest.json", receipt)
                raise TimeoutError("Still pending; use resume for this output directory")
            time.sleep(poll_interval)
        for field in ("profile_id", "text", "engine", "model_size", "language", "seed"):
            if result.get(field) != receipt["request"][field]:
                raise ValueError(f"Generated {field} differs from the request")
        response = self.client.get(f"/audio/{key}")
        response.raise_for_status()
        self.verify_bound(receipt["binding"])
        content = response.content
        with wave.open(io.BytesIO(content), "rb") as audio:
            if audio.getnframes() == 0 or audio.getframerate() <= 0:
                raise ValueError("Generated WAV is empty")
            duration = audio.getnframes() / audio.getframerate()
            sample_rate = audio.getframerate()
        # Exclusive file creation protects an earlier downloaded result.
        destination = output / "narration.wav"
        if destination.exists():
            if destination.read_bytes() != content:
                raise ValueError("An earlier downloaded WAV differs; keep it and inspect the generation")
        else:
            with destination.open("xb") as stream:
                stream.write(content)
        receipt.update(status="completed", audio_sha256=sha256(content), duration=duration, sample_rate=sample_rate, server_result=result)
        write_json(output / "manifest.json", receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    prepare = commands.add_parser("prepare-reference")
    prepare.add_argument("--input", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--start", type=float, default=0)
    prepare.add_argument("--duration", type=float, default=20)
    register = commands.add_parser("register")
    register.add_argument("--reference", type=Path, required=True)
    register.add_argument("--transcript", type=Path, required=True)
    register.add_argument("--binding", type=Path, required=True)
    register.add_argument("--name", default="Oleh EN")
    generate = commands.add_parser("generate")
    generate.add_argument("--binding", type=Path, required=True)
    generate.add_argument("--script", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--model-size", choices=("0.6B", "1.7B"), default="0.6B")
    generate.add_argument("--seed", type=int, default=42)
    resume = commands.add_parser("resume")
    resume.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare-reference":
        print(json.dumps(prepare_reference(args.input, args.output, args.start, args.duration), indent=2))
        return
    client = LocalVoicebox()
    try:
        if args.command == "doctor":
            result = {"astel": client.marker(), "voicebox": client.get("/health"), "profiles": client.get("/profiles")}
        elif args.command == "register":
            result = client.register(args.reference, args.transcript.read_text(), args.binding, args.name)
        elif args.command == "generate":
            result = client.generate(args.binding, args.script.read_text(), args.output, model_size=args.model_size, seed=args.seed)
        else:
            result = client.resume(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
