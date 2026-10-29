from datetime import datetime, timedelta, timezone
import json
import uuid
import pytest
from video_editor.media_workspace import Workspace
from video_editor import workspace_discovery as discovery, workspace_style as style

def uid():return str(uuid.uuid4())

@pytest.fixture
def service(tmp_path,monkeypatch):
    result=Workspace(tmp_path);monkeypatch.setattr(result,'spawn',lambda _:None)
    return result

def test_watch_replay_after_crash_and_no_catchup_storm(service,monkeypatch):
    value={'id':uid(),'query':'warehouse','providers':['commons'],'interval_minutes':15,'enabled':True}
    discovery.save(service,value)
    real=service.submit; seen=[]
    def crash(request):
        seen.append(request['id']);real(request);raise OSError('process died after durable intent')
    monkeypatch.setattr(service,'submit',crash)
    with pytest.raises(OSError):discovery.schedule(service)
    monkeypatch.setattr(service,'submit',real)
    assert discovery.schedule(service)==seen
    assert len(service.listing()['jobs'])==1
    assert discovery.schedule(service)==[]
    later=datetime.now(timezone.utc)+timedelta(days=90)
    assert len(discovery.schedule(service,now=later))==1
    assert discovery.schedule(service,now=later)==[]
    discovery.save(service,{**value,'enabled':False})
    assert discovery.schedule(service,now=later)==[]

def test_watch_bounds_and_backpressure(service):
    value={'id':uid(),'query':'topic','providers':['commons'],'interval_minutes':14,'enabled':True}
    with pytest.raises(ValueError):discovery.save(service,value)
    discovery.save(service,{**value,'interval_minutes':60})
    for _ in range(100):service.submit({'id':uid(),'kind':'search','payload':{'query':'x','providers':['commons']}})
    assert discovery.schedule(service)==[]
    assert discovery.listing(service)[0]['runs']
    service.cancel(service.listing()['jobs'][0]['id'])
    assert len(discovery.schedule(service))==1

def test_rank_measures_delta_not_lifetime_views_and_rejects_counter_reset(service):
    now=datetime.now(timezone.utc)
    keys=[]
    for name,views in [('old',1000000),('growing',1000),('unknown',None)]:
        key=service.save_candidate({'provider':'youtube','source_id':name,'views':views,'title':name});keys.append(key)
    with service.db() as db:
        db.execute('DELETE FROM observations')
        for key,a,b in [(keys[0],1000000,1000010),(keys[1],1000,2000),(keys[2],None,None)]:
            for when,views in [(now-timedelta(hours=1),a),(now,b)]:db.execute('INSERT INTO observations VALUES(?,?,?)',(key,when.isoformat(),views))
    ranked=discovery.ranked(service,now=now)
    assert ranked[0]['id']==keys[1] and ranked[0]['views_per_hour']==1000
    assert ranked[-1]['growth_state']=='insufficient_observations'
    with service.db() as db:db.execute('UPDATE observations SET views=500 WHERE candidate_id=? AND observed_at=?',(keys[1],now.isoformat()))
    assert next(x for x in discovery.ranked(service,now=now) if x['id']==keys[1])['views_per_hour'] is None
    assert all(x['views_per_hour'] is None for x in discovery.ranked(service,now=now+timedelta(days=3)))

def make_story(service):
    key=uid();value={'id':key,'root_id':key,'revision':1,'digest':'a'*64,'duration':10}
    with service.db() as db:db.execute('INSERT INTO stories VALUES(?,?,?,?,?)',(key,1,value['digest'],json.dumps(value),'now'))
    return value

def test_correction_candidate_activation_cas_and_frozen_story_settings(service,monkeypatch):
    story=make_story(service)
    correction={'id':uid(),'story_id':story['id'],'digest':story['digest'],'category':'motion','start':0,'end':4,'note':'Less motion','suggestion':{**style.DEFAULT,'image_motion':'static'}}
    style.correction(service,correction)
    assert style.correction(service,correction)==correction
    with pytest.raises(ValueError):style.correction(service,{**correction,'note':'different'})
    candidate=style.propose(service,{'id':uid(),'name':'Quiet scenes','correction_ids':[correction['id']],'settings':correction['suggestion']})
    assert style.current(service)['id'] is None
    monkeypatch.setattr(service,'asset',lambda _: {})
    payload={'title':'Test','script':'One paragraph','asset_ids':[uid()],'profile':'oleh-en','project_id':'project'}
    job=service.submit({'id':uid(),'kind':'story','payload':payload})
    activation={'request_id':uid(),'id':candidate['id'],'digest':candidate['digest'],'expected_active_digest':None}
    assert style.activate(service,activation)['id']==candidate['id']
    assert style.activate(service,activation)['id']==candidate['id']
    with pytest.raises(ValueError):style.activate(service,{**activation,'request_id':uid()})
    with service.db() as db:frozen=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job['id'],)).fetchone()[0])
    assert frozen['_style']['id'] is None
    job2=service.submit({'id':uid(),'kind':'story','payload':payload})
    with service.db() as db:frozen=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job2['id'],)).fetchone()[0])
    assert frozen['_style']['digest']==candidate['digest']
    assert service.submit({'id':job['id'],'kind':'story','payload':payload})['id']==job['id']

def test_stale_correction_and_unsupported_settings_rejected(service):
    story=make_story(service)
    value={'id':uid(),'story_id':story['id'],'digest':'wrong','category':'voice','start':0,'end':3,'note':'Clearer','suggestion':None}
    with pytest.raises(ValueError):style.correction(service,value)
    with pytest.raises(ValueError):style.correction(service,{**value,'digest':story['digest'],'end':11})
    with pytest.raises(ValueError):style.settings({**style.DEFAULT,'shell':'sh'})
    with pytest.raises(ValueError):style.settings({**style.DEFAULT,'caption_size':True})
