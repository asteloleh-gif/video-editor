#!/usr/bin/env python3
"""Inspect the installed worker, optionally testing KeepAlive while it is idle.

No model, download, publishing or Mac reboot is invoked. A previous report lets
the same read-only command distinguish a physical boot from a process restart.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import sqlite3
import subprocess
import sys
import time

LABEL = 'us.astel.media-workspace.worker'
HOME = Path.home() / '.local/share/astel-media-workspace'


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def snapshot():
    result = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'],
                            capture_output=True, text=True, check=True)
    pid = re.search(r'^\s*pid = (\d+)\s*$', result.stdout, re.MULTILINE)
    state = re.search(r'^\s*state = (\w+)\s*$', result.stdout, re.MULTILINE)
    heartbeat = json.loads((HOME / 'supervisor.json').read_text())
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat['at'])).total_seconds()
    with sqlite3.connect('file:' + str(HOME / 'catalogue.sqlite') + '?mode=ro', uri=True) as db:
        jobs = db.execute('SELECT id,status,updated_at FROM jobs ORDER BY id').fetchall()
        pending = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
        watches = db.execute('SELECT COUNT(*) FROM topic_watches WHERE enabled=1').fetchone()[0]
    return {'pid': int(pid[1]) if pid else None, 'state': state[1] if state else None,
            'heartbeat_at': heartbeat['at'], 'heartbeat_age_seconds': round(age, 2),
            'healthy': heartbeat.get('state') == 'running' and 0 <= age <= 90,
            'pending_jobs': pending, 'enabled_watches': watches, 'job_count': len(jobs),
            'jobs_sha256': hashlib.sha256(json.dumps(jobs).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restart-idle-worker', action='store_true')
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit('Use the installed ~/.local/share/astel-media-workspace/venv/bin/python (Python 3.11+)')
    if args.out.exists():
        raise ValueError('Choose a new report filename; existing evidence is preserved')
    plist = plistlib.loads((Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')).read_bytes())
    expected = [str(HOME / 'venv/bin/python'), '-m', 'video_editor.workspace_runtime', 'serve']
    if plist.get('Label') != LABEL or plist.get('ProgramArguments') != expected:
        raise ValueError('Installed worker identity differs; preserving it')
    boot = subprocess.check_output(['sysctl', '-n', 'kern.bootsessionuuid'], text=True).strip()
    boot_hash = hashlib.sha256(boot.encode()).hexdigest()
    before = snapshot()
    media = [Path.home() / 'Movies/Astel-Pilots/Amazon-02-3D-2026-10-28/amazon-pilot-v2-openreel-20261028.mp4',
             HOME / 'jobs/4448432b-a128-4602-9bce-60f015a3c815/video.mp4']
    hashes = [sha(path) for path in media]
    after = before
    if args.restart_idle_worker:
        if before['pending_jobs'] or before['enabled_watches'] or not before['healthy'] or not before['pid']:
            raise ValueError('Restart acceptance requires an idle healthy worker and paused watches')
        if plist.get('KeepAlive') is not True or plist.get('RunAtLoad') is not True:
            raise ValueError('Automatic user service recovery is not configured')
        # Only this exact existing user job is signalled; launchd must restart it.
        subprocess.run(['launchctl', 'kill', 'SIGTERM', f'gui/{os.getuid()}/{LABEL}'], check=True)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            time.sleep(1)
            try:
                after = snapshot()
            except (subprocess.CalledProcessError, OSError, ValueError):
                continue
            if after['pid'] and after['pid'] != before['pid'] and after['healthy'] and after['heartbeat_at'] > before['heartbeat_at']:
                break
        else:
            raise RuntimeError('KeepAlive restart was not confirmed within 45 seconds')
        if after['jobs_sha256'] != before['jobs_sha256'] or [sha(path) for path in media] != hashes:
            raise RuntimeError('Persistent job or accepted media snapshot changed during acceptance')
    previous = json.loads(args.previous.read_text()) if args.previous else None
    report = {'at': datetime.now(timezone.utc).isoformat(), 'boot_session_sha256': boot_hash,
              'run_at_load': plist.get('RunAtLoad') is True, 'keep_alive': plist.get('KeepAlive') is True,
              'before': before, 'after': after, 'keep_alive_restart_tested': args.restart_idle_worker,
              'physical_boot_changed_from_previous': boot_hash != previous['boot_session_sha256'] if previous else None,
              'previous_jobs_match': before['jobs_sha256'] == previous['after']['jobs_sha256'] if previous else None,
              'previous_media_match': hashes == previous['accepted_media_sha256'] if previous else None,
              'accepted_media_sha256': hashes, 'publishing_called': False, 'model_called': False}
    args.out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with args.out.open('x') as target:
        target.write(json.dumps(report, indent=2) + '\n')
    args.out.chmod(0o600)
    print(json.dumps({'healthy': after['healthy'], 'keep_alive_restart_tested': args.restart_idle_worker,
                      'pid_changed': after['pid'] != before['pid'], 'job_count': after['job_count'],
                      'jobs_preserved': after['jobs_sha256'] == before['jobs_sha256'],
                      'physical_boot_changed_from_previous': report['physical_boot_changed_from_previous']}))


if __name__ == '__main__':
    main()
