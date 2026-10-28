"""Durable, simulation-only handoff of verified stories to the existing Hub.

The Hub owns delivery plans. This module cannot approve, schedule or publish.
Existing local credentials stay in their private files, outside renderer IPC.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from .canvas_contract import canonical_hash, prepare_hub_input, review_card

HUB_ORIGIN = "https://lazy-distribution-production.up.railway.app"
READ_ACTIONS = {"capabilities", "inbox", "status", "metrics"}
ALL_ACTIONS = READ_ACTIONS | {"preview", "submit"}
ACCOUNTS = {f"{brand}:instagram" for brand in ("astel.u", "astel.us", "leoakastel")}


class DeliveryError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def private_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise DeliveryError("PRIVATE_CONNECTION_REQUIRED")
    return json.loads(path.read_text())


def request(method, url, *, data=None, headers=None, timeout=30, limit=2 * 1024 * 1024):
    """Bounded transport. Redirects never forward credentials or upload sessions."""
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json", **(headers or {})}
    req = Request(url, data=data, method=method, headers=headers or {})
    try:
        response = build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout)
    except HTTPError as error:
        response = error
    except (URLError, TimeoutError, OSError):
        raise DeliveryError("REMOTE_OUTCOME_UNCONFIRMED") from None
    with response:
        body = response.read(limit + 1)
        if len(body) > limit: raise DeliveryError("REMOTE_RESPONSE_TOO_LARGE")
        try: value = json.loads(body) if body else {}
        except (ValueError, UnicodeDecodeError): value = {}
        return response.status, dict(response.headers.items()), value


class HubClient:
    def __init__(self, *, readonly=False, transport=request, config=None):
        self.readonly, self.transport = readonly, transport
        self.config = Path(config) if config else Path.home() / ".config/astel-distribution" / ("kevin-hub-reader.json" if readonly else "editorial-hub-operator.json")

    def call(self, action, **arguments):
        if action not in (READ_ACTIONS if self.readonly else ALL_ACTIONS):
            raise DeliveryError("HUB_ACTION_DENIED")
        if arguments.get("projectId") != "copilot": raise DeliveryError("HUB_PROJECT_DENIED")
        if action in {"preview", "submit"} and arguments.get("input", {}).get("mode") != "simulation":
            raise DeliveryError("SIMULATION_ONLY")
        config = private_json(self.config)
        token = config.get("token")
        if not isinstance(token, str) or len(token) < 32: raise DeliveryError("HUB_CONNECTION_REQUIRED")
        code, _, value = self.transport("POST", HUB_ORIGIN + "/api/distribution/" + action,
                                        data=arguments, headers={"Authorization": "Bearer " + token})
        if code == 404: raise DeliveryError("HUB_PLAN_NOT_FOUND")
        if code != 200:
            error = value.get("error", "HUB_REQUEST_FAILED")
            raise DeliveryError(error if isinstance(error, str) and re.fullmatch(r"[A-Z_]{1,80}", error) else "HUB_REQUEST_FAILED")
        return value

    def read(self, action, **arguments):
        if action not in READ_ACTIONS: raise DeliveryError("HUB_READ_ONLY")
        return self.call(action, projectId="copilot", **arguments)


def initialize(service):
    with service.db() as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS hub_handoffs(job_id TEXT PRIMARY KEY,story_id TEXT,root_id TEXT,revision INTEGER,input_digest TEXT,data TEXT,request_digest TEXT UNIQUE,UNIQUE(root_id,revision));
        """)
    (service.home / "delivery").mkdir(mode=0o700, exist_ok=True)


def validate(service, payload, *, allow_elapsed=False):
    if not isinstance(payload, dict) or set(payload) != {"story_id", "digest", "account_key", "text", "scheduled_at"}:
        raise DeliveryError("INVALID_HANDOFF_FIELDS")
    card = review_card(service, payload["story_id"])
    if card["state"] != "needs_review" or card["digest"] != payload["digest"]:
        raise DeliveryError("STALE_STORY_REVISION")
    if not isinstance(payload["account_key"], str) or payload["account_key"] not in ACCOUNTS: raise DeliveryError("HUB_ACCOUNT_DENIED")
    if not isinstance(payload["text"], str) or not 1 <= len(payload["text"]) <= 2200:
        raise DeliveryError("INVALID_HANDOFF_TEXT")
    try:
        when = datetime.fromisoformat(payload["scheduled_at"].replace("Z", "+00:00"))
        if when.tzinfo is None or (not allow_elapsed and when <= datetime.now(timezone.utc)): raise ValueError()
    except (ValueError, AttributeError, TypeError): raise DeliveryError("FUTURE_TEST_TIME_REQUIRED") from None
    return card


def reserve(service, job_id, card, payload, media):
    initialize(service)
    with service.db() as db:
        db.execute("BEGIN IMMEDIATE")
        source_digest = canonical_hash(payload)
        row = db.execute("SELECT data FROM hub_handoffs WHERE job_id=? OR request_digest=?", (job_id, source_digest)).fetchone()
        if row: return json.loads(row[0])
        revision = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM hub_handoffs WHERE root_id=?", (card["id"],)).fetchone()[0]
        until = (datetime.fromisoformat(payload["scheduled_at"].replace("Z", "+00:00")) + timedelta(days=7)).isoformat()
        prepared = prepare_hub_input(card, expected_digest=payload["digest"], account_key=payload["account_key"], text=payload["text"],
                                     media_url=media["download_url"], available_until=until, scheduled_at=payload["scheduled_at"], allowed_hosts=["drive.google.com"], delivery_revision=revision)
        plan = prepared["input"]
        value = {"job_id": job_id, "story_id": card["artifact_job_id"], "story_digest": card["digest"], "artifact_sha256": card["artifact"]["sha256"], "revision": revision,
                 "input": plan, "input_digest": prepared["input_digest"], "expected_plan_id": canonical_hash(["copilot", plan["contentId"], revision]),
                 "media_id": media["file_id"], "media_ready": media["server_readable"], "submitted": False, "state": "prepared", "publication_approved": False}
        db.execute("INSERT INTO hub_handoffs VALUES(?,?,?,?,?,?,?)", (job_id, card["artifact_job_id"], card["id"], revision, prepared["input_digest"], json.dumps(value, ensure_ascii=False), source_digest))
        return value


def save(service, value):
    with service.db() as db:
        db.execute("UPDATE hub_handoffs SET data=? WHERE job_id=?", (json.dumps(value, ensure_ascii=False), value["job_id"]))


def verified_plan(value, plan):
    if plan.get("id") != value["expected_plan_id"] or plan.get("digest") != value["input_digest"] or canonical_hash(plan.get("input")) != value["input_digest"]:
        raise DeliveryError("HUB_PLAN_IDENTITY_MISMATCH")
    if plan["input"]["mode"] != "simulation" or plan.get('state') != 'DRAFT' or plan.get("approval") or any(d.get("attempts") or d.get("receipt") for d in plan.get("deliveries", [])):
        raise DeliveryError("UNEXPECTED_HUB_EXECUTION_STATE")
    return plan


def perform(service, job_id, payload, *, drive=None, hub=None):
    from .drive_delivery import DriveDelivery
    # A lost reply can be reconciled after the test slot has elapsed. Only a
    # new submission below still requires a future time.
    card = validate(service, payload, allow_elapsed=True)
    drive, hub = drive or DriveDelivery(service), hub or HubClient()
    service.cancelled(job_id)
    service.update(job_id, progress=.1, phase="Проверка копии для доставки")
    media = drive.upload(card, lambda: service.cancelled(job_id))
    value = reserve(service, job_id, card, payload, media)
    # A crashed submit is reconciled by the same deterministic plan ID before
    # resending the exact immutable input. No second revision is allocated.
    service.update(job_id, progress=.75, phase="Передача тестового черновика в Hub")
    if value["state"] in {"submitting", "received", "remote_outcome_unconfirmed"}:
        try:
            plan = verified_plan(value, hub.read("status", planId=value["expected_plan_id"]))
        except DeliveryError as error:
            if str(error) != "HUB_PLAN_NOT_FOUND": raise
        else:
            value.update(submitted=True, state="received", plan=plan, media_ready=media["server_readable"]); save(service, value)
            service.update(job_id, result=public(value)); return value
    service.cancelled(job_id)
    validate(service, payload)  # reject a new story revision after the upload
    preview = hub.call("preview", projectId="copilot", input=value["input"])
    if preview.get("mutations") != 0 or canonical_hash(preview.get("input")) != value["input_digest"]:
        raise DeliveryError("HUB_PREVIEW_MISMATCH")
    service.cancelled(job_id)
    value["state"] = "submitting"; save(service, value)
    try:
        verified_plan(value, hub.call("submit", projectId="copilot", input=value["input"]))
        plan = verified_plan(value, hub.read("status", planId=value["expected_plan_id"]))
    except DeliveryError:
        value["state"] = "remote_outcome_unconfirmed"; save(service, value); raise
    value.update(submitted=True, state="received", plan=plan); save(service, value)
    service.update(job_id, result=public(value))
    return value


def public(value):
    return {**{k: value[k] for k in ("job_id", "story_id", "story_digest", "artifact_sha256", "revision", "input_digest", "expected_plan_id", "submitted", "state", "media_ready", "publication_approved")}, "hub_state": value.get("plan", {}).get("state")}


def records(service):
    initialize(service)
    with service.db() as db: return [public(json.loads(r[0])) for r in db.execute("SELECT data FROM hub_handoffs ORDER BY rowid DESC LIMIT 30")]


def refresh(service, job_id, hub=None):
    initialize(service)
    with service.db() as db: row = db.execute("SELECT data FROM hub_handoffs WHERE job_id=?", (job_id,)).fetchone()
    if row is None: raise DeliveryError("HANDOFF_NOT_FOUND")
    value = json.loads(row[0]); plan = verified_plan(value, (hub or HubClient(readonly=True)).read("status", planId=value["expected_plan_id"]))
    value.update(submitted=True, state="received", plan=plan); save(service, value)
    return {**public(value), "plan": plan}


def retry(service, job_id):
    with service.db() as db:
        row = db.execute("SELECT kind,status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None or row["kind"] != "handoff": raise DeliveryError("HANDOFF_NOT_FOUND")
    if row["status"] == "failed": service.update(job_id, status="queued", error=None)
    return service.resume(job_id)


def allow_media_reading(service, payload, drive=None):
    """Separate exact-file consent; never approve or execute a Hub plan."""
    if not isinstance(payload, dict) or set(payload) != {'job_id', 'story_digest', 'artifact_sha256', 'consent'} or payload['consent'] != 'anyone-with-link-readonly-final-mp4':
        raise DeliveryError('EXACT_FILE_CONSENT_REQUIRED')
    from .media_workspace import identifier
    identifier(payload['job_id'])
    initialize(service)
    with service.db() as db: row = db.execute('SELECT data FROM hub_handoffs WHERE job_id=?', (payload['job_id'],)).fetchone()
    if row is None: raise DeliveryError('HANDOFF_NOT_FOUND')
    value = json.loads(row[0]); card = review_card(service, value['story_id'])
    if not value['submitted'] or card['state'] != 'needs_review' or payload['story_digest'] != card['digest'] or value['story_digest'] != card['digest'] or payload['artifact_sha256'] != card['artifact']['sha256'] or value['artifact_sha256'] != card['artifact']['sha256']:
        raise DeliveryError('STALE_STORY_REVISION')
    from .drive_delivery import DriveDelivery
    media = (drive or DriveDelivery(service)).allow_readonly_link(card, value['media_id'])
    value['media_ready'] = media['server_readable']; save(service, value)
    return public(value)
