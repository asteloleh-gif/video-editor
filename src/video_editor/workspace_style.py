"""Version-bound corrections and explicitly activated story style snapshots."""
import json
from .media_workspace import identifier, timestamp, fingerprint

DEFAULT = {'image_motion':'gentle','title_mode':'scene','caption_size':52}


def initialize(service):
    with service.db() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS corrections(id TEXT PRIMARY KEY,story_id TEXT,digest TEXT,data TEXT,created_at TEXT);
          CREATE TABLE IF NOT EXISTS style_versions(id TEXT PRIMARY KEY,digest TEXT,data TEXT,created_at TEXT);
          CREATE TABLE IF NOT EXISTS style_active(singleton INTEGER PRIMARY KEY CHECK(singleton=1),id TEXT,digest TEXT);
          CREATE TABLE IF NOT EXISTS style_events(id TEXT PRIMARY KEY,data TEXT);
        ''')


def settings(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULT) or value['image_motion'] not in {'gentle','static'} or value['title_mode'] not in {'scene','none'} or type(value['caption_size']) is not int or not 44<=value['caption_size']<=76:
        raise ValueError('Unsupported style settings')
    return value


def correction(service, request):
    initialize(service)
    if not isinstance(request,dict) or set(request)!={'id','story_id','digest','category','start','end','note','suggestion'}:
        raise ValueError('Invalid correction')
    key=identifier(request['id']); story=service.story(identifier(request['story_id']))
    service.parent_story({'parent_story_id':story['id'],'parent_digest':request['digest']})
    if request['category'] not in {'voice','editing','captions','sources','motion'} or not isinstance(request['note'],str) or not 1<=len(request['note'].strip())<=2000:
        raise ValueError('Describe the correction')
    start,end=request['start'],request['end']
    if any(type(x) not in {int,float} for x in (start,end)) or not 0<=start<=end<=story['duration']:
        raise ValueError('Correction time range is outside this artifact')
    if request['suggestion'] is not None: settings(request['suggestion'])
    with service.db() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT data FROM corrections WHERE id=?',(key,)).fetchone()
        if old:
            if json.loads(old[0])!=request:raise ValueError('Correction ID conflict')
            return request
        service.parent_story({'parent_story_id':story['id'],'parent_digest':request['digest']})
        db.execute('INSERT INTO corrections VALUES(?,?,?,?,?)',(key,story['id'],story['digest'],json.dumps(request,ensure_ascii=False),timestamp()))
    return request


def propose(service, request):
    initialize(service)
    if not isinstance(request,dict) or set(request)!={'id','name','correction_ids','settings'} or not isinstance(request['name'],str) or not 1<=len(request['name'].strip())<=100:
        raise ValueError('Invalid style proposal')
    identifier(request['id']); settings(request['settings']); ids=request['correction_ids']
    if not isinstance(ids,list) or not 1<=len(ids)<=30 or len(set(ids))!=len(ids): raise ValueError('Select 1–30 corrections')
    with service.db() as db:
        for key in ids:
            if not db.execute('SELECT 1 FROM corrections WHERE id=?',(identifier(key),)).fetchone():raise ValueError('Correction not found')
        sha=fingerprint(request); old=db.execute('SELECT digest,data FROM style_versions WHERE id=?',(request['id'],)).fetchone()
        if old and old['digest']!=sha:raise ValueError('Style version is immutable')
        db.execute('INSERT OR IGNORE INTO style_versions VALUES(?,?,?,?)',(request['id'],sha,json.dumps(request,ensure_ascii=False),timestamp()))
    return {**request,'digest':sha,'state':'candidate'}


def activate(service, request):
    """Only the owner UI exposes activation; agent tools can propose only."""
    initialize(service)
    if not isinstance(request,dict) or set(request)!={'request_id','id','digest','expected_active_digest'}:raise ValueError('Invalid style activation')
    key=identifier(request['request_id']); identifier(request['id'])
    with service.db() as db:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT data FROM style_events WHERE id=?',(key,)).fetchone()
        if prior:
            if json.loads(prior[0])!=request:raise ValueError('Activation ID conflict')
            return current(service)
        row=db.execute('SELECT digest FROM style_versions WHERE id=?',(request['id'],)).fetchone()
        active=db.execute('SELECT digest FROM style_active WHERE singleton=1').fetchone()
        if not row or row[0]!=request['digest'] or request['expected_active_digest']!=(active[0] if active else None):raise ValueError('Style selection is stale')
        db.execute('INSERT OR REPLACE INTO style_active VALUES(1,?,?)',(request['id'],request['digest']))
        db.execute('INSERT INTO style_events VALUES(?,?)',(key,json.dumps(request)))
    return current(service)


def current(service):
    initialize(service)
    with service.db() as db:
        row=db.execute('SELECT v.data,v.digest FROM style_active a JOIN style_versions v ON a.id=v.id AND a.digest=v.digest WHERE singleton=1').fetchone()
    return {**json.loads(row['data']),'digest':row['digest']} if row else {'id':None,'name':'Astel default','digest':None,'settings':dict(DEFAULT),'correction_ids':[]}


def listing(service):
    initialize(service)
    with service.db() as db:
        corrections=[json.loads(r[0]) for r in db.execute('SELECT data FROM corrections ORDER BY created_at DESC LIMIT 100')]
        versions=[{**json.loads(r['data']),'digest':r['digest']} for r in db.execute('SELECT * FROM style_versions ORDER BY created_at DESC LIMIT 30')]
    return {'active':current(service),'corrections':corrections,'versions':versions}
