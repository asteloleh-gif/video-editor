from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from video_editor.media_workspace import Workspace, MAX_PENDING_JOBS
from video_editor import workspace_runtime as runtime

def test_cancel_does_not_hide_a_remote_unknown_handoff_or_an_owned_child(tmp_path,monkeypatch):
    import json,uuid
    from video_editor.media_workspace import Workspace
    from video_editor.hub_delivery import initialize
    from video_editor.story_jobs import lock
    service=Workspace(tmp_path);monkeypatch.setattr(service,'spawn',lambda _:None)
    key=str(uuid.uuid4());service.submit({'id':key,'kind':'search','payload':{'query':'test','providers':['commons']}})
    with lock(service.folder(key)/'run.lock',True):
        assert service.cancel(key)['status']=='queued'
        assert (service.folder(key)/'cancel').exists()
    (service.folder(key)/'cancel').unlink()
    initialize(service)
    with service.db() as db:
        db.execute('UPDATE jobs SET kind=?,payload=? WHERE id=?',('handoff',json.dumps({'story_id':key}),key))
        db.execute('INSERT INTO hub_handoffs VALUES(?,?,?,?,?,?,?)',(key,key,key,1,'a'*64,json.dumps({'state':'remote_outcome_unconfirmed'}),'b'*64))
    import pytest
    with pytest.raises(ValueError,match='already have accepted'):service.cancel(key)
    assert not (service.folder(key)/'cancel').exists() and service.status(key)['status']=='queued'
from video_editor.story_jobs import digest, lock, write


def search():
    return {'id':str(uuid.uuid4()),'kind':'search','payload':{'query':'warehouse','providers':['commons']}}


@pytest.fixture
def service(tmp_path, monkeypatch):
    value=Workspace(tmp_path)
    monkeypatch.setattr(value,'spawn',lambda _:None)
    return value


def test_admission_is_bounded_but_exact_replay_is_still_idempotent(service):
    first=search();service.submit(first)
    for _ in range(MAX_PENDING_JOBS-1):service.submit(search())
    assert service.submit(first)['id']==first['id']
    with pytest.raises(ValueError,match='100 unfinished'):service.submit(search())
    service.cancel(first['id'])
    assert service.status(first['id'])['status']=='cancelled'
    assert service.submit(search())['status']=='queued'


def test_restart_recovery_keeps_worker_locks_and_bounds_processes(service, monkeypatch):
    ids=[service.submit(search())['id'] for _ in range(7)]
    reopened=Workspace(service.home);inherited=[];calls=[]
    def popen(args, **kwargs):
        # Retain the exact inherited lock as a child/renderer would do.
        inherited.extend(os.dup(fd) for fd in kwargs['pass_fds']);calls.append(args)
        return SimpleNamespace(pid=1)
    monkeypatch.setattr('video_editor.media_workspace.subprocess.Popen',popen)
    try:
        runtime.tick(reopened)
        assert len(calls)==4
        runtime.tick(reopened)
        assert len(calls)==4  # no second child for a still-held job lock
        assert set(args[args.index('--id')+1] for args in calls)==set(ids[:4])
        for fd in inherited:os.close(fd)
        inherited.clear();calls.clear()
        reopened.update(ids[0],status='ready');reopened.update(ids[1],status='failed')
        runtime.tick(reopened)
        assert len(calls)==4 and ids[4] in {args[args.index('--id')+1] for args in calls}
        assert ids[1] not in {args[args.index('--id')+1] for args in calls}
    finally:
        for fd in inherited:os.close(fd)


def test_low_disk_waits_for_render_but_keeps_network_work_and_health(service,monkeypatch):
    network=service.submit(search())['id'];render=service.submit(search())['id']
    with service.db() as db:db.execute("UPDATE jobs SET kind='story' WHERE id=?",(render,))
    attempted=[];monkeypatch.setattr(service,'resume',lambda key:attempted.append(key))
    monkeypatch.setattr(runtime.shutil,'disk_usage',lambda _:SimpleNamespace(free=1024))
    result=runtime.tick(service)
    assert attempted==[network] and result['warnings']==['LOW_DISK']
    assert runtime.health(service)['healthy']
    write(service.home/'supervisor.json',{'at':(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(),'state':'running'})
    assert not runtime.health(service)['healthy']
    write(service.home/'supervisor.json',{'at':datetime.now(timezone.utc).isoformat(),'state':'attention'})
    assert not runtime.health(service)['healthy']


def cached_story(service,monkeypatch):
    job=service.submit(search())['id'];asset=str(uuid.uuid4());public=service.folder(job)/'public';public.mkdir()
    original=service.assets/asset;original.mkdir();source=original/'montage.mp4';source.write_bytes(b'preserved library montage')
    filename='asset-'+asset+'.mp4';copy=public/filename;copy.write_bytes(source.read_bytes())
    (public/'narration.wav').write_bytes(b'keep voice');(public/'unknown.bin').write_bytes(b'keep unknown')
    (service.folder(job)/'video.mp4').write_bytes(b'keep final')
    write(service.folder(job)/'props.json',{'story':{'scenes':[{'asset_id':asset,'asset_sha256':digest(source),'src':filename}]}})
    with service.db() as db:db.execute("UPDATE jobs SET kind='story',status='ready',updated_at=? WHERE id=?",((datetime.now(timezone.utc)-timedelta(days=8)).isoformat(),job))
    monkeypatch.setattr(service,'file_receipt',lambda key:{'path':str(source),'sha256':digest(source)})
    return job,asset,source,copy


def test_retention_only_removes_reconstructible_duplicates_and_restores_them(service,monkeypatch):
    job,asset,source,copy=cached_story(service,monkeypatch)
    plan=runtime.cache_plan(service);assert len(plan)==1
    result=runtime.prune_cache(service);assert result['removed']==1 and not copy.exists()
    assert source.read_bytes()==b'preserved library montage'
    assert (service.folder(job)/'video.mp4').read_bytes()==b'keep final'
    assert (copy.parent/'narration.wav').read_bytes()==b'keep voice'
    assert (copy.parent/'unknown.bin').read_bytes()==b'keep unknown'
    assert runtime.restore_cache(service,job)['restored']==1 and copy.read_bytes()==source.read_bytes()
    assert runtime.restore_cache(service,job)['restored']==0


def test_retention_preserves_active_changed_or_linked_paths(service,monkeypatch,tmp_path):
    job,asset,source,copy=cached_story(service,monkeypatch)
    with lock(service.home/'worker.lock',True):assert runtime.prune_cache(service)['busy']
    assert copy.exists()
    copy.write_bytes(b'changed copy');assert runtime.cache_plan(service)==[]
    copy.unlink();copy.symlink_to(source);assert runtime.cache_plan(service)==[]
    copy.unlink();copy.write_bytes(source.read_bytes())
    with service.db() as db:db.execute("UPDATE jobs SET status='running' WHERE id=?",(job,))
    assert runtime.cache_plan(service)==[]


def test_installer_handles_launchd_bootout_registration_race(tmp_path,monkeypatch):
    import importlib.util
    path=Path(__file__).parents[1]/'scripts/setup_media_workspace_mac.py'
    spec=importlib.util.spec_from_file_location('runtime_installer',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    calls=[];codes=iter([5,5,0])
    def run(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=next(codes))
    monkeypatch.setattr(module.subprocess,'run',run);monkeypatch.setattr(module.time,'sleep',lambda _:None)
    agent=tmp_path/'exact-agent.plist';module.bootstrap_agent('gui/502',agent)
    assert calls==[['launchctl','bootstrap','gui/502',str(agent)]]*3
