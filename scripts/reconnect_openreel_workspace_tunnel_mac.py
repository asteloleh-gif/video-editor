#!/usr/bin/env python3
"""Reconnect only the already authorized Astel tunnel with an existing local key."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ALIAS = 'astel-openreel'
TUNNEL = 'tunnel_6ac566f1fac08191b548240633db227d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credential-file', required=True, type=Path)
    args = parser.parse_args()
    credential = args.credential_file.expanduser()
    if credential.is_symlink() or not credential.is_file() or credential.stat().st_mode & 0o077:
        raise ValueError('Existing owner-only credential file required')
    if subprocess.run(['git', 'check-ignore', '-q', credential.name], cwd=credential.parent).returncode:
        raise ValueError('Credential file must remain ignored')
    if subprocess.check_output(['git', 'ls-files', '--', credential.name], cwd=credential.parent).strip():
        raise ValueError('Credential file must remain untracked')
    match = re.search(r'(?m)^OPENAI_API_KEY=(sk-[A-Za-z0-9_-]+)$', credential.read_text())
    if not match:
        raise ValueError('Existing credential unavailable; no key was created')
    profile = Path.home() / '.config/tunnel-client/astel-openreel.yaml'
    if profile.is_symlink() or not profile.is_file():
        raise ValueError('Existing native profile required')
    config = json.loads(profile.read_text())
    if config.get('control_plane', {}).get('tunnel_id') != TUNNEL:
        raise ValueError('Existing profile points at another tunnel')
    wrapper = Path.home() / '.local/share/astel-media-workspace/bin/mcp'
    if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
        raise ValueError('Install the candidate-specific MCP wrapper first')
    env = os.environ.copy()
    env['CONTROL_PLANE_API_KEY'] = match.group(1)
    env['HEALTH_LISTEN_ADDR'] = '127.0.0.1:0'

    def cli(*arguments):
        result = subprocess.run(['/opt/homebrew/bin/tunnel-client', *arguments], env=env,
                                capture_output=True, text=True, timeout=55)
        if result.returncode:
            raise RuntimeError('Existing tunnel command failed; private diagnostics were withheld')
        return result.stdout

    status = json.loads(cli('runtimes', 'status', ALIAS, '--json'))
    if status.get('tunnel_id') != TUNNEL:
        raise ValueError('Alias identity mismatch')
    if status.get('process_running'):
        if status.get('process', {}).get('target_value') != str(wrapper):
            raise ValueError('Another MCP command is running; preserve it and review the profile')
    else:
        backup = profile.with_name(profile.name + '.before-workspace-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        shutil.copyfile(profile, backup); backup.chmod(0o600)
        cli('runtimes', 'connect', '--alias', ALIAS, '--profile', ALIAS,
            '--tunnel-id', TUNNEL, '--runtime-api-key', 'env:CONTROL_PLANE_API_KEY',
            '--mcp-command', str(wrapper))
    status = json.loads(cli('runtimes', 'status', ALIAS, '--json'))
    proof = {name: status.get(name) for name in ('process_running', 'healthy', 'ready')}
    print(json.dumps(proof))
    if not all(proof.values()):
        raise RuntimeError('Tunnel has not reached healthy/ready; no external readiness claim')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        sys.exit('Existing tunnel reconnect did not complete. No key or private diagnostic was printed.')
