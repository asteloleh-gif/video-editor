"""Persistent supervisor and recoverable cache maintenance for the Mac workspace.

The supervisor resumes only unfinished local jobs. It never retries a failed
publication request, launches a browser login, or invokes a publisher.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import time

from .media_workspace import Workspace, timestamp, identifier, MAX_PENDING_JOBS, MAX_WORKER_PROCESSES
from .story_jobs import digest, lock, write

RESERVE_BYTES = 8 * 1024**3
RETENTION_DAYS = 7


def health(service):
    target = service.home / 'supervisor.json'
    try:
        value = json.loads(target.read_text())
        when = datetime.fromisoformat(value['at'])
        age = (datetime.now(timezone.utc) - when).total_seconds()
        return {**value, 'healthy': value.get('state') == 'running' and 0 <= age <= 90}
    except (OSError, ValueError, KeyError, TypeError):
        return {'healthy': False, 'state': 'not_running', 'at': None}


def cache_plan(service, *, now=None):
    """Only verified per-job duplicates with an intact library source qualify.

    Final MP4, narration, references, original assets, receipts and active jobs
    are excluded. Removed duplicates have an immutable restore map.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    result = []
    with service.db() as db:
        jobs = db.execute("SELECT id,updated_at FROM jobs WHERE status='ready' AND kind='story'").fetchall()
    for row in jobs:
        try:
            if datetime.fromisoformat(row['updated_at']) > cutoff: continue
            folder = service.folder(row['id'])
            if (folder / 'public').is_symlink(): continue
            props = json.loads((folder / 'props.json').read_text())
            scenes = props['story']['scenes']
            unique = set()
            for scene in scenes:
                asset_id = identifier(scene['asset_id'])
                source = service.file_receipt(asset_id)
                expected = 'asset-' + asset_id + Path(source['path']).suffix
                if scene['src'] != expected or expected in unique: continue
                unique.add(expected)
                copy = folder / 'public' / expected
                if copy.is_symlink() or not copy.is_file(): continue
                if source['sha256'] != scene['asset_sha256'] or digest(copy) != source['sha256']: continue
                result.append({'job_id': row['id'], 'name': expected, 'asset_id': asset_id,
                               'sha256': source['sha256'], 'bytes': copy.stat().st_size})
        except (OSError, KeyError, TypeError, ValueError):
            continue  # An unclear cache entry is preserved, not guessed.
    return result


def prune_cache(service, *, now=None):
    """Reclaim reconstructible copies, under the same global rendering lock."""
    removed = []
    try:
        with lock(service.home / 'worker.lock', True):
            for item in cache_plan(service, now=now):
                folder = service.folder(item['job_id'])
                path = folder / 'public' / item['name']
                # Revalidate immediately before unlink; the library original is
                # still checked by file_receipt, and the restore map is fsynced.
                source = service.file_receipt(item['asset_id'])
                if digest(path) != item['sha256'] or source['sha256'] != item['sha256']: continue
                receipt = folder / 'cache-restore.json'
                if receipt.is_symlink(): continue
                saved = json.loads(receipt.read_text()) if receipt.exists() else {'entries': {}}
                saved['entries'][item['name']] = item
                write(receipt, saved)
                path.unlink()
                removed.append(item)
    except BlockingIOError:
        return {'busy': True, 'removed': 0, 'reclaimed_bytes': 0}
    return {'busy': False, 'removed': len(removed), 'reclaimed_bytes': sum(i['bytes'] for i in removed)}


def restore_cache(service, job_id):
    folder = service.folder(identifier(job_id))
    if (folder / 'public').is_symlink(): raise ValueError('Cache directory changed')
    with lock(service.home / 'worker.lock', True):
        receipt = folder / 'cache-restore.json'
        if receipt.is_symlink(): raise ValueError('Cache receipt changed')
        if not receipt.exists(): return {'restored': 0}
        saved = json.loads(receipt.read_text()); restored = 0
        for name, item in saved['entries'].items():
            asset_id = identifier(item['asset_id']); source = service.file_receipt(asset_id)
            if name != 'asset-' + asset_id + Path(source['path']).suffix or item['sha256'] != source['sha256']:
                raise ValueError('Cache restore identity changed')
            target = folder / 'public' / name
            if target.is_symlink(): raise ValueError('Cache target changed')
            if target.exists():
                if digest(target) != item['sha256']: raise ValueError('Cache target changed')
                continue
            temporary = target.with_name('.' + name + '.restore')
            if temporary.is_symlink(): raise ValueError('Cache staging changed')
            shutil.copyfile(source['path'], temporary)
            temporary.chmod(0o600)
            if digest(temporary) != item['sha256']: raise ValueError('Cache source changed')
            temporary.replace(target); restored += 1
        return {'restored': restored}


def tick(service, *, maintenance=False):
    free = shutil.disk_usage(service.home).free
    with service.db() as db:
        rows = db.execute("SELECT id,kind FROM jobs WHERE status IN ('queued','running') ORDER BY created_at,rowid LIMIT ?", (MAX_PENDING_JOBS + 1,)).fetchall()
        failed = db.execute("SELECT COUNT(*) FROM jobs WHERE status='failed'").fetchone()[0]
    resumed = []; warnings = []
    if free < RESERVE_BYTES: warnings.append('LOW_DISK')
    if len(rows) > MAX_PENDING_JOBS: warnings.append('BACKLOG_LIMIT')
    for row in rows[:MAX_WORKER_PROCESSES]:
        # Network/status jobs can still run during low disk; rendering and
        # acquisition wait instead of filling the remaining reserve.
        if free < RESERVE_BYTES and row['kind'] in {'story', 'acquire'}: continue
        try:
            service.resume(row['id']); resumed.append(row['id'])
        except (OSError, ValueError): warnings.append('JOB_RECOVERY_REQUIRES_ATTENTION')
    cache = prune_cache(service) if maintenance else {'checked': False}
    value = {'at': timestamp(), 'state': 'running', 'unfinished': len(rows), 'failed': failed,
             'recovery_checks': len(resumed), 'disk_free_bytes': free, 'warnings': sorted(set(warnings)),
             'cache': cache, 'publishing_enabled': False}
    write(service.home / 'supervisor.json', value)
    return value


def serve(service, interval=20):
    # A second LaunchAgent/CLI invocation never creates a second supervisor.
    with lock(service.home / 'supervisor.lock', True):
        last_maintenance = None
        while True:
            try:
                due = last_maintenance is None or time.monotonic() - last_maintenance >= 3600
                result = tick(service, maintenance=due)
                if due and not result['cache'].get('busy'): last_maintenance = time.monotonic()
            except Exception:
                write(service.home / 'supervisor.json', {'at': timestamp(), 'state': 'attention',
                      'warnings': ['SUPERVISOR_CHECK_FAILED'], 'publishing_enabled': False})
            time.sleep(interval)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['serve', 'status', 'cache-plan', 'cache-prune', 'cache-restore'])
    p.add_argument('--id')
    args = p.parse_args(); service = Workspace()
    if args.command == 'serve': serve(service)
    elif args.command == 'status': print(json.dumps(health(service)))
    elif args.command == 'cache-plan': print(json.dumps(cache_plan(service)))
    elif args.command == 'cache-prune': print(json.dumps(prune_cache(service)))
    elif args.command == 'cache-restore': print(json.dumps(restore_cache(service, args.id)))


if __name__ == '__main__': main()
