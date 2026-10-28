#!/usr/bin/env python3
"""Install fixed local assembly runtime and the frozen Amazon package. No downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from video_editor.story_jobs import StoryJobs, digest, lock, write


def stage_package(stage, archive=None):
    public = stage / "public/jobs/amazon-pilot-20261028"
    public.parent.mkdir(parents=True)
    if archive:
        checkpoint = json.loads((REPO / "docs/story-pilot/PILOT_CHECKPOINT_2026-10-28.json").read_text())
        if digest(archive) != checkpoint["archive"]["sha256"]:
            raise ValueError("Pilot archive checksum differs from the frozen checkpoint")
        public.mkdir()
        # Fixed members only. Never extract code or arbitrary archive paths.
        with zipfile.ZipFile(archive) as source:
            for name in ("bezos.jpg", "narration.wav", "props.json", "warehouse-1.mp4", "warehouse-2.mp4", "warehouse-photo.jpg"):
                (public / name).write_bytes(source.read(f"remotion/public/jobs/amazon-pilot-20261028/{name}"))
            for name in ("props.json", "SOURCES.md"):
                (stage / name).write_bytes(source.read(f"output/amazon-pilot-20261028/{name}"))
    else:
        shutil.copytree(REPO / "remotion/public/jobs/amazon-pilot-20261028", public)
        shutil.copy2(REPO / "output/amazon-pilot-20261028/props.json", stage / "props.json")
        shutil.copy2(REPO / "output/amazon-pilot-20261028/SOURCES.md", stage / "SOURCES.md")


def install(node, home=None, archive=None):
    home = Path(home or Path.home() / ".local/share/astel-story-render")
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    with lock(home / "render.lock", True):
        sources = {f"src/{p.relative_to(REPO / 'remotion/src')}": p for p in (REPO / "remotion/src").rglob("*") if p.is_file()}
        sources.update({"render.cjs": REPO / "integration/story-render/render.cjs", "package-lock.json": REPO / "remotion/package-lock.json"})
        runtime_files = {name: digest(path) for name, path in sources.items()}
        runtime = home / "runtime"
        # A future source/dependency upgrade must use a separately versioned home.
        # Never silently change the renderer underneath persisted prepared jobs.
        if runtime.exists():
            for name, expected in runtime_files.items():
                if not (runtime / name).is_file() or digest(runtime / name) != expected:
                    raise RuntimeError("Installed renderer differs; preserve this runtime and install a new version separately")
        for name, source in {"node": node, "ffprobe": shutil.which("ffprobe")}.items():
            if not source:
                raise RuntimeError(f"Missing {name}")
            target = home / "bin" / name
            target.parent.mkdir(exist_ok=True)
            # ffprobe retains Homebrew's dylib paths; Node is a standalone binary.
            shutil.copy2(Path(source).resolve(), target)
            target.chmod(0o700)
            if name == "ffprobe":
                notices = home / "LICENSES/FFmpeg"
                notices.mkdir(parents=True, exist_ok=True)
                prefix = Path(source).resolve().parent.parent
                for license_file in [*prefix.glob("COPYING*"), *prefix.glob("LICENSE*")]:
                    if license_file.is_file():
                        shutil.copy2(license_file, notices / license_file.name)
        python = home / "venv/bin/python"
        if not python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(home / "venv")], check=True)
        module = home / "src/video_editor"
        module.mkdir(parents=True, exist_ok=True)
        (module / "__init__.py").touch()
        shutil.copy2(REPO / "src/video_editor/story_jobs.py", module / "story_jobs.py")
        runtime.mkdir(exist_ok=True)
        shutil.copytree(REPO / "remotion/src", runtime / "src", dirs_exist_ok=True)
        for name in ("package.json", "package-lock.json", "tsconfig.json"):
            shutil.copy2(REPO / "remotion" / name, runtime / name)
        shutil.copy2(REPO / "integration/story-render/render.cjs", runtime / "render.cjs")
        dependencies = runtime / "node_modules"
        if not dependencies.exists():
            # Exclude only disposable webpack cache, preserving the pinned browser,
            # FFmpeg binaries and all third-party licenses. No repo symlink.
            shutil.copytree(REPO / "remotion/node_modules", dependencies, ignore=shutil.ignore_patterns(".cache"), symlinks=True)
        if not (dependencies / "@remotion/renderer/package.json").is_file():
            raise RuntimeError("Install pinned Remotion dependencies first: npm ci")
        if not any(p.is_file() for p in (dependencies / ".remotion").rglob("chrome-headless-shell")):
            raise RuntimeError("Provision the pinned browser in remotion first: npx remotion browser ensure")
        package_id = "amazon-3d-9589ee7"
        package = home / "packages" / package_id
        with tempfile.TemporaryDirectory(dir=home, prefix="package-") as temporary:
            stage = Path(temporary)
            if archive is None and package.exists() and not (REPO / "output/amazon-pilot-20261028/props.json").is_file():
                service = StoryJobs(home)
                root, manifest = service.manifest(package_id)
                service.verify(root, manifest)
                shutil.copytree(root / "public", stage / "public")
                for name in ("props.json", "SOURCES.md"):
                    shutil.copy2(root / name, stage / name)
            else:
                stage_package(stage, archive)
            files = {str(p.relative_to(stage)): digest(p) for p in stage.rglob("*") if p.is_file()}
            revision = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
            write(stage / "manifest.json", {"id": package_id, "name": "Amazon · озвучка + видео + 3D", "description": "Согласованный пилот v2 · 1080×1920 · исходная озвучка и субтитры", "composition": "AstelStoryPilot-3D", "duration": 1868 / 30, "revision": revision, "files": files})
            if package.exists():
                if json.loads((package / "manifest.json").read_text())["revision"] != revision:
                    raise RuntimeError("Installed package differs; preserve it and use a new package ID")
            else:
                package.parent.mkdir(exist_ok=True)
                shutil.copytree(stage, package)
        receipt = {"package": package_id, "revision": revision, "remotion": "4.0.529", "renderer_sha256": digest(runtime / "render.cjs"), "runtime_files": runtime_files, "publishing": False}
        write(home / "install.json", receipt)
        return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=shutil.which("node"), required=not shutil.which("node"))
    parser.add_argument("--pilot-archive", type=Path, help="Frozen local snapshot ZIP; checksum verified before reading fixed media members")
    args = parser.parse_args()
    print(json.dumps({k: v for k, v in install(args.node, archive=args.pilot_archive).items() if k != "runtime_files"}, ensure_ascii=False, indent=2))
