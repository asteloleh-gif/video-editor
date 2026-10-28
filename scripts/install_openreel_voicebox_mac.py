#!/usr/bin/env python3
"""Install the local Astel speech bridge and a separate OpenReel Astel candidate.

Uses an existing Voicebox runtime and approved RU/EN bindings; never copies raw
recordings to Git or replaces /Applications/OpenReel.app. No network publishing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import tempfile
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
HOME = Path.home() / ".local/share/astel-voicebox"
PIN = "c9340465e5d37e684cc25bdbe746c4ccd45e165c"
PATCH = REPO / "integration/voicebox/patches/0002-openreel-local-speech.patch"
SEARCH_PATCH = REPO / "integration/video-search/0001-openreel-voicebox-and-search.patch"
STORY_PATCH = REPO / "integration/story-render/0001-openreel-astel-assembly.patch"
WORKSPACE_PATCH = REPO / "integration/media-workspace/0001-openreel-astel-workspace.patch"


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def private_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_suffix(target.suffix + ".install")
    shutil.copyfile(source, temporary)
    temporary.chmod(0o600)
    temporary.replace(target)


def install_bridge(ru=None, en=None):
    from video_editor.voicebox import LocalVoicebox, write_json
    root = HOME / "openreel"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (HOME / "venv/bin/python").is_file():
        raise RuntimeError("Install the pinned Voicebox runtime first; see docs/voicebox/README.md")
    for name in ("__init__.py", "voicebox.py", "voicebox_jobs.py"):
        private_copy(REPO / "src/video_editor" / name, root / "src/video_editor" / name)
    for name in ("serve.py", "runtime.py", "upstream.json"):
        private_copy(REPO / "integration/voicebox" / name, root / "server" / name)
    client = LocalVoicebox(home=HOME)
    try:
        for language, binding in (("ru", ru), ("en", en)):
            target = root / "bindings" / f"oleh-{language}.json"
            source = Path(binding).expanduser().resolve() if binding else target
            receipt = client.verify_binding(source)
            if receipt["reference_language"] != language:
                raise ValueError(f"Choose the approved {language} reference binding")
            if source != target:
                private_copy(source, target)
    finally:
        client.close()
    write_json(root / "profiles.json", {"profiles": [
        {"id": "oleh-ru", "name": "Олег — русский", "language": "ru", "binding": "bindings/oleh-ru.json", "warm": True, "speed": 1.0},
        {"id": "oleh-en", "name": "Oleh — English", "language": "en", "binding": "bindings/oleh-en.json", "warm": False, "speed": 1.02},
    ]})
    return root


def build_source(node, pnpm, patch=PATCH):
    fingerprint = hashlib.sha256(patch.read_bytes()).hexdigest()[:12]
    source = Path.home() / ".local/share/astel-openreel-voicebox" / f"source-{PIN[:8]}-{fingerprint}"
    if source.exists():
        raise FileExistsError(f"Build directory exists; use --built-source after inspecting it: {source}")
    source.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--local", REPO / "vendor/openreel", source])
    run(["git", "checkout", "--detach", PIN], cwd=source)
    run(["git", "apply", "--check", patch], cwd=source)
    run(["git", "apply", patch], cwd=source)
    env = {**os.environ, "PATH": f"{Path(node).parent}:{Path(pnpm).parent}:" + os.environ["PATH"]}
    run([pnpm, "install", "--frozen-lockfile"], cwd=source, env=env)
    for app in ("web", "desktop"):
        run([node, "node_modules/typescript/bin/tsc", "--noEmit"], cwd=source / "apps" / app, env=env)
    run([node, "node_modules/vite/bin/vite.js", "build"], cwd=source / "apps/web", env={**env, "OPENREEL_DESKTOP": "1"})
    run([node, "scripts/prepare-aurora-native.mjs"], cwd=source / "apps/desktop", env=env)
    run([node, "node_modules/tsup/dist/cli-default.js"], cwd=source / "apps/desktop", env=env)
    return source


def package(source, node, patch=PATCH, destination=None):
    original = Path("/Applications/OpenReel.app")
    destination = Path(destination) if destination else Path.home() / "Applications/OpenReel Astel.app"
    if not original.is_dir():
        raise FileNotFoundError("Install the original OpenReel desktop application first")
    if destination.exists():
        raise FileExistsError(f"Preserving existing candidate. Move it aside before reinstalling: {destination}")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() != PIN:
        raise ValueError("The build must use the pinned OpenReel revision")
    # Verify the full source patch, including added files, before packaging.
    run(["git", "apply", "--reverse", "--check", patch], cwd=source)
    required = [source / "apps/web/dist/index.html", source / "apps/desktop/dist/main/index.js"]
    if not all(p.is_file() for p in required):
        raise FileNotFoundError("Build the renderer and desktop main process before packaging")
    asar = next((source / "node_modules/.pnpm").glob("@electron+asar@*/node_modules/@electron/asar/bin/asar.js"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openreel-astel-", dir=destination.parent) as tmp:
        staged = Path(tmp) / destination.name
        shutil.copytree(original, staged, symlinks=True)
        resources = staged / "Contents/Resources"
        # Extract to preserve bundled runtime dependencies and third-party notices.
        app = Path(tmp) / "app"
        run([node, asar, "extract", resources / "app.asar", app])
        shutil.rmtree(app / "dist")
        shutil.copytree(source / "apps/desktop/dist", app / "dist")
        run([node, asar, "pack", app, resources / "app.asar", "--unpack", "dist/mcp-shim/**"])
        shutil.rmtree(resources / "renderer")
        shutil.copytree(source / "apps/web/dist", resources / "renderer")
        # Notices are preserved in original resources; include the upstream MIT
        # license alongside the local patch provenance for clarity.
        (resources / "LICENSES").mkdir(exist_ok=True)
        shutil.copyfile(source / "LICENSE", resources / "LICENSES/OpenReel-MIT.txt")
        (resources / "astel-voicebox-build.json").write_text(json.dumps({"openreel_commit": PIN, "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(), "local_only": True}, indent=2))
        info_path = staged / "Contents/Info.plist"
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
        info.update(CFBundleIdentifier="us.astel.openreel.voicebox", CFBundleDisplayName="OpenReel Astel")
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream)
        run(["codesign", "--force", "--deep", "--sign", "-", staged], stdout=subprocess.DEVNULL)
        staged.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ru-binding", type=Path)
    parser.add_argument("--en-binding", type=Path)
    parser.add_argument("--bridge-only", action="store_true")
    parser.add_argument("--with-video-search", action="store_true", help="Include the free local YouTube search panel")
    parser.add_argument("--with-story-render", action="store_true", help="Include Voicebox, search and durable prepared-package assembly")
    parser.add_argument("--with-media-workspace", action="store_true", help="Include persistent media library, topic batches and new-story assembly")
    parser.add_argument("--built-source", type=Path, help="Use an already built and reviewed patched clone")
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--pnpm", default=shutil.which("pnpm"))
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This local candidate requires Apple Silicon macOS")
    root = install_bridge(args.ru_binding, args.en_binding)
    if args.bridge_only:
        print(json.dumps({"bridge_installed": str(root)}, indent=2))
        return
    if not args.node:
        parser.error("Supply --node with a Node 22+ executable")
    major = int(subprocess.check_output([args.node, "-p", "process.versions.node.split('.')[0]"], text=True))
    if major < 22:
        parser.error("Node 22 or newer is required")
    if not args.built_source and not args.pnpm:
        parser.error("Supply --pnpm to build the pinned candidate")
    patch = WORKSPACE_PATCH if args.with_media_workspace else STORY_PATCH if args.with_story_render else SEARCH_PATCH if args.with_video_search else PATCH
    if args.with_video_search or args.with_story_render or args.with_media_workspace:
        run([sys.executable, REPO / "scripts/setup_video_search_mac.py"])
    if args.with_story_render or (args.with_media_workspace and not (Path.home() / ".local/share/astel-story-render/runtime/node_modules").exists()):
        run([sys.executable, REPO / "scripts/setup_story_render_mac.py", "--node", args.node])
    if args.with_media_workspace:
        run([sys.executable, REPO / "scripts/setup_media_workspace_mac.py", "--node", args.node])
    source = args.built_source.resolve() if args.built_source else build_source(args.node, args.pnpm, patch)
    app = package(source, args.node, patch)
    print(json.dumps({"app": str(app), "bridge": str(root), "original_preserved": "/Applications/OpenReel.app"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
