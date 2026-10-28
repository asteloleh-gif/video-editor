"""Recover the existing drive-work login from Canvas, with unchanged scopes.

Only the loopback entry URL is returned to the owner UI. OAuth codes, tokens,
Google callback URLs and credentials never enter the Canvas API or its logs.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import threading

from .hub_delivery import DeliveryError

CODE = '''
import json
from video_editor.asap.google import oauth
try:
    oauth('drive-work', on_ready=lambda url: print(json.dumps({'url':url}),flush=True))
    print(json.dumps({'state':'completed'}),flush=True)
except Exception:
    print(json.dumps({'state':'not_completed'}),flush=True)
'''


class DriveAuthorization:
    def __init__(self, *, popen=subprocess.Popen):
        self.popen = popen
        self.guard = threading.Lock()
        self.value = {'state': 'idle'}

    def status(self):
        with self.guard: return dict(self.value)

    def start(self):
        with self.guard:
            if self.value['state'] in {'starting', 'authorizing'}: return dict(self.value)
            self.value = {'state': 'starting'}
        ready = threading.Event()
        threading.Thread(target=self.run, args=(ready,), daemon=True).start()
        ready.wait(3)
        return self.status()

    def run(self, ready):
        python = Path.home() / '.local/share/astel-voicebox/venv/bin/python'
        source = Path.home() / 'Projects/asap-gta6-pipeline/src'
        process = None
        try:
            if not python.is_file() or not (source / 'video_editor/asap/google.py').is_file():
                raise DeliveryError('EXISTING_DRIVE_LOGIN_HELPER_REQUIRED')
            process = self.popen([str(python), '-u', '-c', CODE], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                 env={**os.environ, 'PYTHONPATH': str(source)})
            first = json.loads(process.stdout.readline(1024))
            url = first.get('url', '')
            if not isinstance(url, str) or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/authorize', url):
                raise DeliveryError('DRIVE_LOGIN_URL_REQUIRED')
            with self.guard: self.value = {'state': 'authorizing', 'url': url}
            ready.set()
            result = json.loads(process.stdout.readline(1024))
            with self.guard: self.value = {'state': 'completed' if result.get('state') == 'completed' else 'not_completed'}
        except Exception:
            with self.guard: self.value = {'state': 'not_completed'}
        finally:
            ready.set()
            if process:
                if process.poll() is None: process.terminate()
                process.wait(timeout=10)
                if process.stdout: process.stdout.close()
