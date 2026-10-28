#!/usr/bin/env python3
"""Install the private media workspace; preserve accepted Voicebox/pilot runtimes."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home() / '.local/share/astel-media-workspace'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--canvas-html', type=Path, help='Owner-supplied Canvas 2026-10-27 HTML; kept private')
    parser.add_argument('--canvas-package', type=Path, help='Owner-supplied integration ZIP; provenance only, never executed')
    parser.add_argument('--start-canvas', action='store_true', help='Install/start the private local Canvas LaunchAgent')
    args = parser.parse_args()
    for source, expected in ((args.canvas_html, '89c0152e696fed0e836029d5c64fe5d63b0afa85e7bf7ac93751a64a53d20ada'), (args.canvas_package, 'cca3c19768f91571d628f304c46983af41e69383a040fd15233b351d4dd6d018')):
        if source and hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise SystemExit('Canvas source differs from reviewed version; no update applied')
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    gate = (HOME / 'worker.lock').open('a')
    try:
        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('A workspace job is active; finish or cancel it before updating the runtime')
    python = HOME / 'venv/bin/python'
    if not python.exists(): subprocess.run([sys.executable, '-m', 'venv', str(HOME / 'venv')], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '--require-hashes', '--no-deps', '-r', str(REPO / 'integration/video-search/requirements-mac.txt')], check=True, stdout=subprocess.DEVNULL)
    module = HOME / 'src/video_editor'; module.mkdir(parents=True, exist_ok=True)
    for name in ('__init__.py', 'media_workspace.py', 'story_workspace.py', 'canvas_contract.py', 'workspace_canvas.py', 'story_jobs.py', 'video_search.py', 'transcript.py'):
        source = REPO / 'src/video_editor' / name
        temporary = module / (name + '.install'); shutil.copyfile(source, temporary); temporary.chmod(0o600); temporary.replace(module / name)
    binary = HOME / 'bin/node'; binary.parent.mkdir(exist_ok=True)
    shutil.copy2(Path(args.node).resolve(), binary); binary.chmod(0o700)
    renderer = HOME / 'renderer'; (renderer / 'src').mkdir(parents=True, exist_ok=True)
    for name in ('StoryShortV1.tsx', 'workspace-entry.tsx'):
        shutil.copy2(REPO / 'remotion/src' / name, renderer / 'src' / name)
    shutil.copy2(REPO / 'integration/media-workspace/render.cjs', renderer / 'render.cjs')
    # Reuse installed, pinned dependencies/browser; no symlink into the repo/cache.
    deps = Path.home() / '.local/share/astel-story-render/runtime/node_modules'
    if not (deps / '@remotion/renderer/package.json').is_file(): raise RuntimeError('Install the existing pinned local renderer first')
    target = renderer / 'node_modules'
    if not target.exists(): target.symlink_to(deps, target_is_directory=True)
    canvas = HOME / 'canvas'; canvas.mkdir(exist_ok=True, mode=0o700)
    for name in ('workspace.js', 'workspace.css'):
        shutil.copyfile(REPO / 'integration/media-workspace' / name, canvas / name)
    for source, name, expected in ((args.canvas_html, 'document.html', '89c0152e696fed0e836029d5c64fe5d63b0afa85e7bf7ac93751a64a53d20ada'), (args.canvas_package, 'upstream-integration.zip', 'cca3c19768f91571d628f304c46983af41e69383a040fd15233b351d4dd6d018')):
        if source:
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected: raise SystemExit('Canvas source differs from reviewed version; preserving existing private copy')
            shutil.copyfile(source, canvas / name); (canvas / name).chmod(0o600)
    if args.start_canvas and not (canvas / 'document.html').is_file(): raise SystemExit('Provide the owner Canvas HTML before starting its local view')
    files = [*module.glob('*.py'), renderer / 'render.cjs', *(renderer / 'src').glob('*.tsx'), canvas / 'workspace.js', canvas / 'workspace.css']
    hashes = {str(file.relative_to(HOME)): hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(files)}
    (HOME / 'install.json').write_text(json.dumps({'version': 1, 'remotion': '4.0.529', 'files': hashes, 'local_only': True, 'publishing_enabled': False}, indent=2))
    label = 'us.astel.media-workspace.canvas'; domain = f'gui/{os.getuid()}'
    agent = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
    if args.start_canvas or agent.exists():
        agent.parent.mkdir(parents=True, exist_ok=True)
        config = {'Label': label, 'ProgramArguments': [str(python), '-m', 'video_editor.workspace_canvas'], 'RunAtLoad': True, 'KeepAlive': True,
                  'EnvironmentVariables': {'PYTHONPATH': str(HOME / 'src'), 'ASTEL_MEDIA_HOME': str(HOME), 'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'},
                  'StandardOutPath': str(HOME / 'canvas-service.log'), 'StandardErrorPath': str(HOME / 'canvas-service.log')}
        subprocess.run(['launchctl', 'bootout', domain + '/' + label], capture_output=True)
        agent.write_bytes(plistlib.dumps(config)); agent.chmod(0o600)
        subprocess.run(['launchctl', 'bootstrap', domain, str(agent)], check=True)
        print('Local Canvas: http://127.0.0.1:17531/ (private Mac preparation; no Hub submission)')
    print('Astel media workspace installed; publishing disabled')


if __name__ == '__main__': main()
