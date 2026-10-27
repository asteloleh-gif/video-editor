"""Prepare an isolated, pinned Voicebox API runtime. Does not download models."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
HOME = Path(os.environ.get("ASTEL_VOICEBOX_HOME", Path.home() / ".local/share/astel-voicebox")).resolve()
UPSTREAM = json.loads((HERE / "upstream.json").read_text())
SOURCE = HOME / ("source-" + UPSTREAM["commit"][:12] + "-" + UPSTREAM["patch_sha256"][:12])


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_source():
    receipt = json.loads((SOURCE / "astel-runtime.json").read_text())
    if receipt["upstream"] != UPSTREAM or digest(SOURCE / "backend/backends/mlx_backend.py") != receipt["patched_backend_sha256"]:
        raise RuntimeError("Runtime source has changed; prepare a fresh pinned runtime")
    return receipt


def prepare():
    vendor = REPO / "vendor/voicebox"
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=vendor, text=True).strip()
    if revision != UPSTREAM["commit"] or digest(vendor / "backend/backends/mlx_backend.py") != UPSTREAM["backend_sha256"]:
        raise RuntimeError("Unexpected upstream checkout; initialize the pinned submodule")
    patch = HERE / "patches/0001-required-clone.patch"
    if digest(patch) != UPSTREAM["patch_sha256"]:
        raise RuntimeError("Patch fingerprint does not match upstream.json")
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    if SOURCE.exists():
        return verify_source()
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=HOME) as tmp:
        staging = Path(tmp) / "source"
        archive = subprocess.check_output(["git", "archive", UPSTREAM["commit"]], cwd=vendor)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(staging, filter="data")
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=staging, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=staging, check=True)
        receipt = {"upstream": UPSTREAM, "patched_backend_sha256": digest(staging / "backend/backends/mlx_backend.py")}
        (staging / "astel-runtime.json").write_text(json.dumps(receipt, indent=2) + "\n")
        staging.rename(SOURCE)
    return verify_source()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install isolated API dependencies, without model weights")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64" or sys.version_info[:2] != (3, 12):
        parser.error("This pilot requires Apple Silicon and Python 3.12")
    prepare()
    if args.install:
        python = HOME / "venv/bin/python"
        if not python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(HOME / "venv")], check=True)
        version = subprocess.check_output([str(python), "-c", "import sys; print(sys.version_info[:2])"], text=True).strip()
        if version != "(3, 12)":
            raise RuntimeError("Existing isolated venv is not Python 3.12; choose another ASTEL_VOICEBOX_HOME")
        lock = HERE / "requirements-mac.lock.txt"
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(lock if lock.exists() else HERE / "requirements-mac.in")], check=True)
        # Upstream deliberately bypasses these declared transformers>=5 requirements.
        # Only our Qwen MLX path is validated; other engines are not installed.
        subprocess.run([str(python), "-m", "pip", "install", "--no-deps", "mlx-lm==0.31.1", "mlx-audio==0.4.1"], check=True)
        frozen = subprocess.check_output([str(python), "-m", "pip", "freeze"], text=True)
        (HOME / "installed-requirements.txt").write_text(frozen)
    print(json.dumps({"runtime": str(HOME), "source": str(SOURCE), "models_downloaded_by_setup": False}, indent=2))


if __name__ == "__main__":
    main()
