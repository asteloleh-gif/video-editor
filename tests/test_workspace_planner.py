import json
import uuid
import pytest
from video_editor.media_workspace import Workspace
from video_editor import workspace_planner as planner,workspace_control as control

def uid():return str(uuid.uuid4())
@pytest.fixture
def setup(tmp_path,monkeypatch):
    service=Workspace(tmp_path);monkeypatch.setattr(service,'spawn',lambda _:None)
    flag=tmp_path/'planner-policy.json';flag.write_text('{"enabled":true}');flag.chmod(0o600)
    asset=uid();monkeypatch.setattr(service,'asset',lambda key:{'id':key,'kind':'video','duration':20})
    monkeypatch.setattr(service,'file_receipt',lambda key:{'path':'not-used','sha256':'a'*64})
    payload={'topic':'Parcel','language':'en','project_id':'p','facts':[{'id':'f1','text':'A parcel moves on a belt.','url':'https://example.com/source'}],'shots':[{'asset_id':asset,'start':2,'end':8,'evidence':'Box and belt visible.'}]}
    return service,asset,payload

def test_plan_is_durable_editable_and_binds_explicit_source_ranges(setup):
    service,asset,payload=setup;job=service.submit({'id':uid(),'kind':'plan','payload':payload});calls=[]
    def remote(action,args):
        calls.append((action,args));return {'id':job['id'],'facts':payload['facts'],'proposal':{'title':'A parcel','scenes':[{'asset_id':asset,'text':'Parcel moves.','source_start':3,'source_end':6,'evidence':'Box on belt','fact_ids':['f1']}]}}
    result=planner.perform(service,job['id'],payload,transport=remote);service.update(job['id'],status='ready')
    assert calls[0][1]['brief']['requestId']==job['id']
    assert result['profile']=='oleh-en' and len(result['digest'])==64
    request={'title':'Edited title','script':'Edited owner narration.','asset_ids':[asset],'profile':'oleh-en','project_id':'p','plan_id':job['id'],'plan_digest':result['digest']}
    service.validate('story',request);assert planner.choices(service,request)['proposal']['scenes'][0]['source_start']==3
    for changed in [{'plan_digest':'old'},{'script':'One\n\nTwo'},{'project_id':'other'},{'asset_ids':[uid()]}]:
        with pytest.raises(ValueError):service.validate('story',{**request,**changed})

def test_unobserved_shots_missing_facts_and_extra_transport_actions_are_rejected(setup):
    service,asset,payload=setup
    for change in [{'shots':[{**payload['shots'][0],'end':30}]},{'facts':[]},{'shots':[{**payload['shots'][0],'evidence':''}]}]:
        with pytest.raises(ValueError):planner.validate(service,{**payload,**change})
    for action in ['publish','shell','style_activate','approve']:
        with pytest.raises(ValueError):control.execute(service,{'action':action,'args':{}})

def test_planner_revalidates_cloud_output_before_story_can_use_it(setup):
    service,asset,payload=setup;job=service.submit({'id':uid(),'kind':'plan','payload':payload})
    def remote(*_):return {'proposal':{'scenes':[{'asset_id':asset,'text':'Claim','source_start':0,'source_end':19,'fact_ids':['f1']}]}}
    with pytest.raises(ValueError):planner.perform(service,job['id'],payload,transport=remote)
    assert service.status(job['id'])['result']=={}

def test_owner_disabled_policy_prevents_new_billing_intents(setup):
    service,asset,payload=setup;(service.home/'planner-policy.json').write_text('{"enabled":false}')
    with pytest.raises(ValueError,match='выключен'):service.submit({'id':uid(),'kind':'plan','payload':payload})
    with service.db() as db:assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0
