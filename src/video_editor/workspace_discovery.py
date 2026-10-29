"""Owner-controlled topic watches and timestamped growth observations.

Adapters remain self-owned. Search hits are references until a supported,
provenanced acquisition is explicitly selected. Missing views are never zero.
"""
from datetime import datetime, timedelta, timezone
import json
import math
import uuid

from .media_workspace import identifier, timestamp, fingerprint


def initialize(service):
    with service.db() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS topic_watches(id TEXT PRIMARY KEY,data TEXT,next_at TEXT,enabled INTEGER);
          CREATE TABLE IF NOT EXISTS watch_runs(watch_id TEXT,job_id TEXT UNIQUE,due_at TEXT,PRIMARY KEY(watch_id,due_at));
        ''')


def save(service, value):
    initialize(service)
    if not isinstance(value, dict) or set(value) != {'id','query','providers','interval_minutes','enabled'}:
        raise ValueError('Invalid topic watch')
    key = identifier(value['id'])
    service.validate('search', {'query': value['query'], 'providers': value['providers']})
    interval = value['interval_minutes']
    if type(interval) is not int or not 15 <= interval <= 10080 or type(value['enabled']) is not bool:
        raise ValueError('Watch interval must be 15 minutes to 7 days')
    value = {**value, 'query': value['query'].strip(), 'providers': list(dict.fromkeys(value['providers']))}
    with service.db() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT data,next_at FROM topic_watches WHERE id=?',(key,)).fetchone()
        if not old and db.execute('SELECT COUNT(*) FROM topic_watches').fetchone()[0] >= 100:
            raise ValueError('At most 100 topic watches')
        # Editing settings invalidates any reserved old run, but does not cancel it.
        same = old and json.loads(old['data']) == value
        due = old['next_at'] if same else timestamp()
        db.execute('INSERT OR REPLACE INTO topic_watches VALUES(?,?,?,?)',(key,json.dumps(value,ensure_ascii=False),due,int(value['enabled'])))
    return value


def listing(service):
    initialize(service)
    with service.db() as db:
        rows = db.execute('SELECT * FROM topic_watches ORDER BY next_at,id').fetchall()
        return [{**json.loads(r['data']), 'next_at':r['next_at'],
                 'runs':[dict(x) for x in db.execute('SELECT job_id,due_at FROM watch_runs WHERE watch_id=? ORDER BY due_at DESC LIMIT 5',(r['id'],))]} for r in rows]


def schedule(service, *, now=None):
    """At most two new search jobs per tick, replaying the same reserved UUID.

    Reservation precedes submit; a crash at either side retries the same ID.
    There is no catch-up storm after a long sleep and no automatic download.
    """
    initialize(service); now = now or datetime.now(timezone.utc); made = []
    with service.db() as db:
        rows = db.execute('SELECT * FROM topic_watches WHERE enabled=1 AND next_at<=? ORDER BY next_at,id LIMIT 2',(now.isoformat(),)).fetchall()
    for row in rows:
        value = json.loads(row['data']); due = row['next_at']
        key = str(uuid.uuid5(uuid.UUID(row['id']), due + fingerprint(value)))
        with service.db() as db:
            db.execute('INSERT OR IGNORE INTO watch_runs VALUES(?,?,?)',(row['id'],key,due))
        try:
            service.submit({'id':key,'kind':'search','payload':{'query':value['query'],'providers':value['providers']}})
        except ValueError:
            continue  # Bounded queue is full: keep the reserved intent pending.
        with service.db() as db:
            db.execute('UPDATE topic_watches SET next_at=? WHERE id=? AND next_at=?',((now+timedelta(minutes=value['interval_minutes'])).isoformat(),row['id'],due))
        made.append(key)
    return made


def ranked(service, *, search_id=None, limit=50, now=None):
    if type(limit) is not int or not 1 <= limit <= 100: raise ValueError('Invalid ranking limit')
    now = now or datetime.now(timezone.utc)
    with service.db() as db:
        if search_id:
            row = db.execute('SELECT results FROM searches WHERE id=?',(identifier(search_id),)).fetchone()
            if not row: raise ValueError('Search not found')
            keys = json.loads(row[0])
        else:
            keys = [r[0] for r in db.execute('SELECT id FROM candidates ORDER BY rowid DESC LIMIT 500')]
        result = []
        for key in keys:
            observations = db.execute('SELECT observed_at,views FROM observations WHERE candidate_id=? AND views IS NOT NULL ORDER BY observed_at DESC LIMIT 200',(key,)).fetchall()
            growth = None; evidence = None
            if observations:
                latest = observations[0]; end = datetime.fromisoformat(latest['observed_at'])
                for previous in observations[1:]:
                    start = datetime.fromisoformat(previous['observed_at']); hours = (end-start).total_seconds()/3600
                    if hours < .25: continue
                    if now-end > timedelta(days=2) or hours > 168: break
                    if all(isinstance(x,(float,int)) and math.isfinite(x) and x>=0 for x in (latest['views'],previous['views'])) and latest['views'] >= previous['views']:
                        growth = (latest['views']-previous['views'])/hours
                        evidence = {'from':previous['observed_at'],'to':latest['observed_at'],'view_delta':latest['views']-previous['views'],'hours':hours}
                    break
            item = service.candidate(key,True)
            result.append({**item,'views_per_hour':growth,'growth_evidence':evidence,'growth_state':'measured' if growth is not None else 'insufficient_observations'})
    result.sort(key=lambda x:(x['views_per_hour'] is not None,x['views_per_hour'] or 0),reverse=True)
    return result[:limit]
