import io
import json
import threading

import pytest

from video_editor.drive_authorization import DriveAuthorization


@pytest.mark.parametrize('url,expected', [
    ('http://127.0.0.1:53655/authorize', 'completed'),
    ('https://accounts.example.test/auth?token=private', 'not_completed'),
    ('http://127.0.0.1:53655/authorize?code=private', 'not_completed'),
])
def test_login_only_exposes_loopback_entry_and_never_oauth_credentials(tmp_path, monkeypatch, url, expected):
    monkeypatch.setattr('video_editor.drive_authorization.Path.home', lambda: tmp_path)
    for name in ['.local/share/astel-voicebox/venv/bin/python', 'Projects/asap-gta6-pipeline/src/video_editor/asap/google.py']:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
    calls=[]
    class Process:
        def __init__(self): self.stdout=io.StringIO(json.dumps({'url':url})+'\n'+json.dumps({'state':'completed'})+'\n')
        def poll(self): return 0
        def wait(self, **kwargs): return 0
    def popen(args, **kwargs): calls.append((args,kwargs));return Process()
    auth=DriveAuthorization(popen=popen);auth.run(threading.Event())
    assert auth.status()=={'state':expected}
    assert "oauth('drive-work'" in calls[0][0][-1]
    assert 'client_secret' not in calls[0][0][-1] and 'access_token' not in str(auth.status())
