"""Fixed cloud review/planner endpoints; never approve, schedule or publish."""
from .hub_delivery import HubClient,HUB_ORIGIN,private_json,DeliveryError,records
from .canvas_contract import review_card
from .media_workspace import identifier
from .story_jobs import write

def call(action,arguments,*,readonly=False,client=None):
    allowed={'inbox','status'} if readonly else {'inbox','status','register','preflight','review','plan'}
    if action not in allowed:raise DeliveryError('VIDEO_ACTION_DENIED')
    client=client or HubClient(readonly=readonly);config=private_json(client.config);token=config.get('token')
    if not isinstance(token,str) or len(token)<32:raise DeliveryError('PRIVATE_CONNECTION_REQUIRED')
    status,_,value=client.transport('POST',HUB_ORIGIN+'/api/video-workspace/'+action,data={**arguments,'projectId':'copilot'},headers={'Authorization':'Bearer '+token},timeout=120)
    if status!=200:
        import re
        error=value.get('error','VIDEO_REQUEST_FAILED')
        raise DeliveryError(error if isinstance(error,str) and re.fullmatch('[A-Z_]{1,80}',error) else 'VIDEO_REQUEST_FAILED')
    return value

def prepare(service,job_id,*,transport=call):
    job_id=identifier(job_id)
    handoff=next((r for r in records(service) if r['job_id']==job_id),None)
    if not handoff or not handoff.get('submitted') or not handoff.get('media_ready'):raise ValueError('Allow reading the final MP4 before server preflight')
    card=review_card(service,handoff['story_id'])
    if card['digest']!=handoff['story_digest'] or card['state']!='needs_review':raise ValueError('Story revision is stale')
    args={'planId':handoff['expected_plan_id'],'digest':card['digest']}
    transport('register',{**args,'inputDigest':handoff['input_digest'],'card':card})
    proof=transport('preflight',args)
    value={**args,'proof':proof,'publishing_enabled':False}
    write(service.folder(job_id)/'cloud-review.json',value)
    import json
    from .hub_delivery import save,public
    with service.db() as db:row=db.execute('SELECT data FROM hub_handoffs WHERE job_id=?',(job_id,)).fetchone()
    record=json.loads(row[0]);record['server_preflight']=proof;save(service,record)
    service.update(job_id,result=public(record))
    return value

def request_review(service,job_id,*,transport=call):
    job_id=identifier(job_id)
    import json
    value=json.loads((service.folder(job_id)/'cloud-review.json').read_text())
    handoff=next(r for r in records(service) if r['job_id']==job_id)
    card=review_card(service,handoff['story_id'])
    if card['digest']!=value['digest'] or card['state']!='needs_review':raise ValueError('Story revision is stale')
    result=transport('review',{'planId':value['planId'],'digest':value['digest']})
    from .hub_delivery import refresh
    refresh(service,job_id)
    return {**result,'publishing_enabled':False,'approval_required':True}
