import http.client
import json
import threading
import uuid

import pytest

from video_editor.media_workspace import Workspace
from video_editor.story_jobs import digest
from video_editor import workspace_canvas as canvas


@pytest.fixture
def local(tmp_path, monkeypatch):
    service = Workspace(tmp_path); folder = tmp_path / 'canvas'; folder.mkdir()
    (folder / 'document.html').write_text('<html><head></head><body>Owner Canvas</body></html>')
    monkeypatch.setattr(canvas, 'CANVAS_SHA', digest(folder / 'document.html'))
    key = str(uuid.uuid4()); service.folder(key).mkdir(); video = service.folder(key) / 'video.mp4'; video.write_bytes(b'0123456789')
    story = {'id': key, 'root_id': key, 'revision': 1, 'digest': 'c' * 64, 'title': '<script>untrusted</script>', 'script': 'Owner script', 'profile': 'oleh-ru', 'audio_sha256': 'b' * 64, 'captions': [], 'caption_review': 'asr_draft', 'scenes': [], 'artifact_sha256': digest(video), 'artifact_bytes': 10, 'duration': 12}
    with service.db() as db: db.execute('INSERT INTO stories VALUES(?,?,?,?,?)', (key, 1, story['digest'], json.dumps(story), 'now'))
    server = canvas.create_server(service, port=0); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    def request(path='/', method='GET', data=None, cookie=None, **extra):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        headers = {'Content-Type': 'application/json', **extra}
        if cookie: headers['Cookie'] = cookie
        conn.request(method, path, json.dumps(data).encode() if data is not None else None, headers=headers)
        res = conn.getresponse(); body = res.read(); result = (res.status, dict(res.getheaders()), body); conn.close(); return result
    status, headers, _ = request(); assert status == 200
    cookie = headers['Set-Cookie'].split(';')[0]
    yield service, key, story, origin, cookie, request
    server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_private_document_and_session_boundary(local):
    service, key, story, origin, cookie, request = local
    assert request('/api/astel-workspace')[0] == 403
    assert request('/api/astel-workspace', cookie=cookie, Origin='https://other.example')[0] == 403
    assert request('/api/astel-workspace', cookie=cookie, Host='attacker.example')[0] == 403
    assert request('/api/astel-workspace', cookie=cookie, **{'Sec-Fetch-Site': 'cross-site'})[0] == 403
    status, headers, body = request(cookie=cookie)
    assert status == 200 and b'/workspace.js' in body
    assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
    assert 'HttpOnly' in headers['Set-Cookie'] and 'SameSite=Strict' in headers['Set-Cookie']


def test_exact_bytes_range_and_tamper(local):
    service, key, story, origin, cookie, request = local
    route=f'/api/astel-workspace/stories/{key}/video.mp4'
    status, headers, body = request(route, cookie=cookie, Range='bytes=2-5')
    assert status == 206 and body == b'2345' and headers['Content-Range'] == 'bytes 2-5/10'
    assert request(route, cookie=cookie, Range='bytes=20-')[0] == 416
    (service.folder(key) / 'video.mp4').write_bytes(b'changed')
    assert request(route, cookie=cookie)[0] == 409


def test_snapshot_is_preparation_only_and_has_no_paths(local):
    service, key, story, origin, cookie, request = local
    status, headers, body = request('/api/astel-workspace', cookie=cookie)
    value = json.loads(body)
    assert status == 200 and not value['publishing_enabled'] and value['hub_connection']=='not_submitted'
    assert value['stories'][0]['title'] == story['title']
    assert str(service.home).encode() not in body
    assert value['stories'][0]['publication']['approved'] is False


def test_editorial_review_idempotence_conflict_stale_and_no_publication(local):
    service, key, story, origin, cookie, request = local
    data={'request_id':str(uuid.uuid4()),'story_id':key,'digest':story['digest'],'decision':'changes_requested','note':'QA remark'}
    def post(data, **headers): return request('/api/astel-workspace/review', method='POST', data=data, cookie=cookie, **headers)
    assert post(data)[0] == 403
    first=post(data, Origin=origin); second=post(data, Origin=origin)
    assert first[0]==second[0]==200 and first[2]==second[2]
    assert json.loads(first[2])['publication_approved'] is False
    assert post({**data,'note':'different'}, Origin=origin)[0]==409
    assert post({**data,'request_id':str(uuid.uuid4()),'digest':'old'}, Origin=origin)[0]==409
    assert post({**data,'request_id':str(uuid.uuid4()),'decision':['invalid']}, Origin=origin)[0]==409
    for route in ['/api/distribution/approve','/api/distribution/schedule','/api/publish']:
        assert request(route, method='POST', data={}, cookie=cookie, Origin=origin)[0]==404


def test_changed_owner_canvas_does_not_execute(local):
    service, key, story, origin, cookie, request = local
    (service.home / 'canvas/document.html').write_text('unreviewed change')
    assert request(cookie=cookie)[0]==409
