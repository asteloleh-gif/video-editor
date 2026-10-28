from datetime import datetime, timedelta, timezone
import copy
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlparse
import uuid

import pytest

from video_editor.canvas_contract import canonical_hash, review_card
from video_editor.drive_delivery import DriveDelivery
from video_editor.hub_delivery import DeliveryError, HubClient, allow_media_reading, perform, records, validate, verified_plan
from video_editor.media_workspace import Workspace
from video_editor.story_jobs import digest


@pytest.fixture
def sample(tmp_path, monkeypatch):
    service = Workspace(tmp_path / 'workspace'); monkeypatch.setattr(service, 'spawn', lambda _: None)
    key = str(uuid.uuid4()); service.folder(key).mkdir(); source = service.folder(key) / 'video.mp4'; source.write_bytes(b'Astel verified MP4 fixture')
    story = {'id': key, 'root_id': key, 'revision': 1, 'digest': 'c'*64, 'title': 'QA', 'script': 'Owner text', 'profile': 'oleh-ru', 'audio_sha256': 'b'*64, 'captions': [], 'caption_review': 'asr_draft', 'scenes': [], 'artifact_sha256': digest(source), 'artifact_bytes': source.stat().st_size, 'duration': 12}
    with service.db() as db: db.execute('INSERT INTO stories VALUES(?,?,?,?,?)',(key,1,story['digest'],json.dumps(story),'now'))
    payload={'story_id':key,'digest':story['digest'],'account_key':'astel.u:instagram','text':'Technical draft only','scheduled_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    config=tmp_path/'credentials';config.mkdir(mode=0o700)
    token=config/'drive-work-token.json';token.write_text(json.dumps({'scope':'https://www.googleapis.com/auth/drive.file','verified_email':'owner@example.test','access_token':'dummy-token','expires_at':time.time()+3600}));token.chmod(0o600)
    return service, review_card(service,key), payload, config


class GoogleFixture:
    def __init__(self):
        self.files={};self.ids=iter(['folder_1234567890','media_1234567890','extra_1234567890']);self.sessions={};self.calls=[];self.lose_final=False
    def __call__(self, method, url, *, data=None, headers=None, **kwargs):
        u=urlparse(url);q=parse_qs(u.query);self.calls.append((method,u.path))
        assert u.hostname=='www.googleapis.com'
        if u.path=='/drive/v3/about':return 200,{}, {'user':{'emailAddress':'owner@example.test'}}
        if u.path.endswith('/generateIds'):return 200,{}, {'ids':[next(self.ids)]}
        if u.path=='/drive/v3/files' and method=='GET':return 200,{}, {'files':[{'id':k} for k,v in self.files.items() if v['mimeType'].endswith('folder')]}
        if u.path=='/drive/v3/files' and method=='POST':
            self.files[data['id']]={**copy.deepcopy(data),'permissions':[{'type':'user','role':'owner'}]};return 200,{}, {'id':data['id']}
        if u.path.endswith('/permissions') and method=='POST':
            key=u.path.split('/')[-2];self.files[key]['permissions'].append(copy.deepcopy(data));return 200,{}, {'id':'anyoneWithLink'}
        if u.path.startswith('/drive/v3/files/'):
            key=u.path.rsplit('/',1)[1];return (200,{},copy.deepcopy(self.files[key])) if key in self.files else (404,{}, {})
        if u.path=='/upload/drive/v3/files' and method=='POST':
            self.sessions[data['id']]={'metadata':copy.deepcopy(data),'bytes':b''};return 200,{'Location':'https://www.googleapis.com/upload/drive/v3/files?upload_id='+data['id']},{}
        if u.path=='/upload/drive/v3/files' and method=='PUT':
            key=q['upload_id'][0];session=self.sessions[key];span=headers['Content-Range']
            if span.startswith('bytes */'):return 308,({'Range':'bytes=0-'+str(len(session['bytes'])-1)} if session['bytes'] else {}),{}
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',span);start,end,size=map(int,match.groups());assert start==len(session['bytes']);session['bytes']+=data
            if end+1==size:
                import hashlib
                self.files[key]={**session['metadata'],'size':str(size),'sha256Checksum':hashlib.sha256(session['bytes']).hexdigest(),'permissions':[{'type':'user','role':'owner'}]}
                if self.lose_final:self.lose_final=False;raise DeliveryError('REMOTE_OUTCOME_UNCONFIRMED')
                return 200,{}, {'id':key}
            return 308,{'Range':'bytes=0-'+str(len(session['bytes'])-1)},{}
        raise AssertionError((method,url))


def test_private_upload_reuses_exact_file_and_survives_lost_final_response(sample):
    service,card,payload,config=sample;google=GoogleFixture();drive=DriveDelivery(service,transport=google,config=config)
    google.lose_final=True
    with pytest.raises(DeliveryError,match='UNCONFIRMED'):drive.upload(card)
    result=drive.upload(card)
    assert not result['server_readable']
    assert drive.upload(card)==result
    assert len(google.files)==2 # one private folder, one verified MP4
    assert sum(method=='POST' and path=='/upload/drive/v3/files' for method,path in google.calls)==1
    assert not any('permissions' in path for _,path in google.calls)
    private=json.loads(drive.receipt(card['artifact']['sha256']).read_text());assert 'session' not in private


def test_upload_rejects_mutated_cloud_file_and_broad_permissions(sample):
    service,card,payload,config=sample;google=GoogleFixture();drive=DriveDelivery(service,transport=google,config=config);result=drive.upload(card)
    remote=google.files[result['file_id']];remote['permissions'].append({'type':'anyone','role':'writer'})
    with pytest.raises(DeliveryError,match='PERMISSION_DRIFT'):drive.upload(card)
    remote['permissions']=[{'type':'user','role':'owner'}];remote['sha256Checksum']='a'*64
    with pytest.raises(DeliveryError,match='HASH_MISMATCH'):drive.upload(card)


def test_link_permission_requires_exact_consent_and_only_shares_output_file(sample):
    service,card,payload,config=sample;google=GoogleFixture();drive=DriveDelivery(service,transport=google,config=config);hub=FakeHub()
    job=service.submit({'id':str(uuid.uuid4()),'kind':'handoff','payload':payload});value=perform(service,job['id'],payload,drive=drive,hub=hub)
    consent={'job_id':job['id'],'story_digest':card['digest'],'artifact_sha256':card['artifact']['sha256'],'consent':'anyone-with-link-readonly-final-mp4'}
    for change in [{'consent':True},{'artifact_sha256':'wrong'},{'story_digest':'old'},{'extra':'approve'}]:
        with pytest.raises(DeliveryError):allow_media_reading(service,{**consent,**change},drive=drive)
    assert not any(p.endswith('/permissions') for _,p in google.calls)
    result=allow_media_reading(service,consent,drive=drive)
    assert result['media_ready'] and not result['publication_approved']
    assert allow_media_reading(service,consent,drive=drive)['media_ready']
    changes=[p for method,p in google.calls if method=='POST' and p.endswith('/permissions')]
    assert changes==['/drive/v3/files/media_1234567890/permissions']
    assert google.files['folder_1234567890']['permissions']==[{'type':'user','role':'owner'}]
    assert set(hub.calls)=={'preview','submit','status'}


@pytest.mark.parametrize('url',['http://www.googleapis.com/upload/drive/v3/files?x=1','https://attacker.example/upload/drive/v3/files','https://www.googleapis.com/private/path','https://www.googleapis.com:443/upload/drive/v3/files'])
def test_upload_session_cannot_forward_credentials(url):
    with pytest.raises(DeliveryError):DriveDelivery.session_path(url)


class FakeHub:
    def __init__(self):self.plans={};self.calls=[];self.lose_submit=False
    def call(self,action,**args):
        self.calls.append(action);assert action in {'preview','submit'}
        plan=args['input'];assert plan['mode']=='simulation'
        if action=='preview':return {'input':plan,'mutations':0,'aiCalls':0}
        key=canonical_hash(['copilot',plan['contentId'],plan['revision']]);value={'id':key,'digest':canonical_hash(plan),'input':copy.deepcopy(plan),'state':'DRAFT','deliveries':[{'attempts':0,'state':'DRAFT'}]};self.plans[key]=value
        if self.lose_submit:self.lose_submit=False;raise DeliveryError('REMOTE_OUTCOME_UNCONFIRMED')
        return value
    def read(self,action,**args):
        self.calls.append(action);assert action=='status'
        if args['planId'] not in self.plans:raise DeliveryError('HUB_PLAN_NOT_FOUND')
        return copy.deepcopy(self.plans[args['planId']])


def test_handoff_reconciles_lost_submit_and_allocates_delivery_versions(sample):
    service,card,payload,config=sample;google=GoogleFixture();drive=DriveDelivery(service,transport=google,config=config);hub=FakeHub();hub.lose_submit=True
    job=service.submit({'id':str(uuid.uuid4()),'kind':'handoff','payload':payload})
    with pytest.raises(DeliveryError,match='UNCONFIRMED'):perform(service,job['id'],payload,drive=drive,hub=hub)
    recovered=perform(service,job['id'],payload,drive=drive,hub=hub)
    assert recovered['submitted'] and not recovered['publication_approved'] and not recovered['media_ready']
    assert hub.calls.count('submit')==1 and len(hub.plans)==1
    repeat=service.submit({'id':str(uuid.uuid4()),'kind':'handoff','payload':payload});assert perform(service,repeat['id'],payload,drive=drive,hub=hub)['expected_plan_id']==recovered['expected_plan_id']
    changed={**payload,'text':'New caption, same video'};another=service.submit({'id':str(uuid.uuid4()),'kind':'handoff','payload':changed});new=perform(service,another['id'],changed,drive=drive,hub=hub)
    assert new['revision']==2 and len(hub.plans)==2 and len(google.files)==2
    assert all(item['state']=='received' for item in records(service))
    assert set(hub.calls)=={'preview','submit','status'}


def test_handoff_validation_rejects_stale_or_privilege_fields(sample):
    service,card,payload,_=sample
    for change in [{'mode':'live'},{'account_key':[]},{'account_key':'asapleo.ai:instagram'},{'digest':'old'},{'scheduled_at':'2020-01-01T00:00:00Z'},{'scheduled_at':'2030-01-01T00:00:00'}]:
        with pytest.raises(ValueError):validate(service,{**payload,**change})


def test_lost_submit_can_be_reconciled_after_test_slot(sample, monkeypatch):
    service,card,payload,config=sample;google=GoogleFixture();drive=DriveDelivery(service,transport=google,config=config);hub=FakeHub();hub.lose_submit=True
    job=service.submit({'id':str(uuid.uuid4()),'kind':'handoff','payload':payload})
    with pytest.raises(DeliveryError): perform(service,job['id'],payload,drive=drive,hub=hub)
    class Later(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.fromisoformat(payload['scheduled_at'])+timedelta(days=2)
    monkeypatch.setattr('video_editor.hub_delivery.datetime', Later)
    assert perform(service,job['id'],payload,drive=drive,hub=hub)['submitted']
    assert hub.calls.count('submit')==1


def test_remote_execution_or_identity_drift_is_not_claimed_as_safe_draft(sample):
    service,card,payload,config=sample;drive=DriveDelivery(service,transport=GoogleFixture(),config=config);hub=FakeHub()
    job=service.submit({'id':str(uuid.uuid4()),'kind':'handoff','payload':payload});value=perform(service,job['id'],payload,drive=drive,hub=hub)
    for change in [{'state':'APPROVED'},{'approval':{'actor':'someone'}},{'deliveries':[{'attempts':1}]},{'deliveries':[{'receipt':{'platformPostId':'unexpected'}}]},{'digest':'wrong'}]:
        with pytest.raises(DeliveryError): verified_plan(value,{**value['plan'],**change})


def test_backend_client_cannot_approve_schedule_or_publish(tmp_path):
    p=tmp_path/'key.json';p.write_text(json.dumps({'token':'fake_'+'a'*40}));p.chmod(0o600)
    client=HubClient(config=p,transport=lambda *a,**k:pytest.fail('forbidden action reached network'))
    for action in ['approve','schedule','cancel','pause','resume','publish']:
        with pytest.raises(DeliveryError,match='DENIED'):client.call(action,projectId='copilot')
    with pytest.raises(DeliveryError,match='SIMULATION_ONLY'):client.call('submit',projectId='copilot',input={'mode':'live'})
    with pytest.raises(DeliveryError,match='PROJECT_DENIED'):client.call('capabilities',projectId='other')
