"""Evidence-bound, editable scene proposals using the existing cloud connection."""
import math
from urllib.parse import urlparse
from .media_workspace import identifier,fingerprint

def policy(service):
    import json
    path=service.home/'planner-policy.json'
    try:
        if path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('Private policy required')
        enabled=json.loads(path.read_text()).get('enabled') is True
    except (OSError,ValueError,TypeError,AttributeError):enabled=False
    return {'enabled':enabled,'reason':'owner_enabled' if enabled else 'owner_disabled'}

def validate(service,payload):
    if not policy(service)['enabled']:raise ValueError('Облачный сценарист выключен владельцем. Поиск, ручной сценарий, озвучка и монтаж работают без него.')
    if not isinstance(payload,dict) or set(payload)!={'topic','language','facts','shots','project_id'} or not isinstance(payload['topic'],str) or not 1<=len(payload['topic'])<=200 or payload['language'] not in {'ru','en'} or not isinstance(payload['project_id'],str) or not 1<=len(payload['project_id'])<=128:raise ValueError('Invalid planning brief')
    if not isinstance(payload['facts'],list) or not 1<=len(payload['facts'])<=12 or not isinstance(payload['shots'],list) or not 1<=len(payload['shots'])<=12:raise ValueError('Supply 1–12 facts and observed shots')
    ids=set()
    import re
    for fact in payload['facts']:
        if not isinstance(fact,dict) or set(fact)!={'id','text','url'} or not isinstance(fact['id'],str) or not re.fullmatch(r'f\d{1,2}',fact['id']) or fact['id'] in ids or not isinstance(fact['text'],str) or not 1<=len(fact['text'])<=1000:raise ValueError('Invalid fact')
        u=urlparse(fact['url'])
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Source URL required')
        ids.add(fact['id'])
    for shot in payload['shots']:
        if not isinstance(shot,dict) or set(shot)!={'asset_id','start','end','evidence'}:raise ValueError('Describe the observed source range')
        asset=service.asset(identifier(shot['asset_id']));service.file_receipt(asset['id'])
        start,end=shot['start'],shot['end']
        if any(type(v) not in {float,int} or not math.isfinite(v) for v in (start,end)) or not 0<=start<end or end-start>120 or (asset['kind']=='video' and end>asset['duration']) or not isinstance(shot['evidence'],str) or not 1<=len(shot['evidence'])<=1000:raise ValueError('Invalid observed source range')
    return payload

def perform(service,job_id,payload,*,transport=None):
    from .workspace_cloud import call
    validate(service,payload)
    brief={k:v for k,v in payload.items() if k!='project_id'}
    result=(transport or call)('plan',{'brief':{'requestId':job_id,**brief}})
    # A typed remote response is revalidated against our intact local assets.
    scenes=result['proposal']['scenes']
    if not 1<=len(scenes)<=12:raise ValueError('Invalid scene count')
    for scene in scenes:
        if not isinstance(scene['text'],str) or not scene['text'].strip() or not isinstance(scene['fact_ids'],list) or not scene['fact_ids'] or any(key not in {f['id'] for f in payload['facts']} for key in scene['fact_ids']):raise ValueError('Unknown fact in proposal')
        if not any(scene['asset_id']==s['asset_id'] and s['start']<=scene['source_start']<scene['source_end']<=s['end'] for s in payload['shots']):raise ValueError('Proposal uses an unobserved source range')
    result={**result,'project_id':payload['project_id'],'profile':'oleh-ru' if payload['language']=='ru' else 'oleh-en'}
    result['digest']=fingerprint(result)
    service.update(job_id,result=result)
    return result

def choices(service,payload):
    """No modulo allocation when a scenario has explicit shot choices."""
    if 'plan_id' not in payload:return None
    job=service.status(identifier(payload['plan_id']))
    if job['kind']!='plan' or job['status']!='ready' or job['result'].get('digest')!=payload.get('plan_digest'):raise ValueError('Planning proposal changed or is not ready')
    plan=job['result'];scenes=plan['proposal']['scenes']
    if plan['project_id']!=payload['project_id'] or plan['profile']!=payload['profile']:raise ValueError('Planning project/voice differs')
    import re
    if len([p for p in re.split(r'\n\s*\n',payload['script']) if p.strip()])!=len(scenes) or not {s['asset_id'] for s in scenes}<=set(payload['asset_ids']):raise ValueError('Keep one paragraph per proposed scene and its source files')
    return plan
