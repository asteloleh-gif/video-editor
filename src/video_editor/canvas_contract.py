"""Version-bound review cards and existing Hub PlanInput adapter. Never publishes."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from urllib.parse import urlparse


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def review_card(service, story_id):
    from .story_workspace import story_video
    from .media_workspace import identifier
    story_video(service, identifier(story_id))  # prove the exact bytes still exist
    with service.db() as db:
        data = json.loads(db.execute("SELECT data FROM stories WHERE id=?", (story_id,)).fetchone()[0])
    root = data.get("root_id", data["id"])
    with service.db() as db:
        versions = [json.loads(row[0]) for row in db.execute("SELECT data FROM stories")]
    latest = max((v for v in versions if v.get("root_id", v["id"]) == root), key=lambda v: v["revision"])
    return {"schemaVersion": 1, "type": "astel.video.review", "id": root, "artifact_job_id": data["id"], "revision": data["revision"], "digest": data["digest"],
            "title": data["title"], "script": data["script"], "state": "needs_review" if latest["id"] == data["id"] else "superseded", "voice": {"profile": data["profile"], "audio_sha256": data["audio_sha256"]},
            "captions": {"review": data["caption_review"], "items": data["captions"]},
            "sources": [{k: s[k] for k in ("id", "title", "asset_id", "asset_sha256", "sourceUrl", "author", "license")} for s in data["scenes"]],
            "artifact": {"sha256": data["artifact_sha256"], "bytes": data["artifact_bytes"], "duration": data["duration"], "mime": "video/mp4"},
            "preview": {"state": "local_only", "message": "Remote preview requires a verified media delivery URL"},
            "publication": {"state": "not_approved", "approved": False, "handoff_status": "see_canvas_handoffs"}}


def prepare_hub_input(card, *, expected_digest, account_key, text, media_url, available_until, scheduled_at, allowed_hosts, delivery_revision=None):
    if card["digest"] != expected_digest or card["state"] != "needs_review":
        raise ValueError("Review revision is stale")
    if account_key not in {f"{brand}:instagram" for brand in ("astel.us", "astel.u", "leoakastel")}:
        raise ValueError("Choose an existing certified Instagram route")
    parsed = urlparse(media_url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError("A verified delivery URL on an operator-approved origin is required")
    if any(term in parsed.hostname for term in ("localhost", ".local", ".internal")):
        raise ValueError("Local delivery URL denied")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Literal delivery IP denied")
    if not isinstance(text, str) or len(text) > 2200:
        raise ValueError("Invalid publication text")
    def date(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None: raise ValueError("Timezone required")
        return parsed
    if date(available_until) <= date(scheduled_at) or date(scheduled_at) <= datetime.now(timezone.utc):
        raise ValueError("Delivery must remain available after the scheduled time")
    brand = account_key.split(":", 1)[0]
    revision = card["revision"] if delivery_revision is None else delivery_revision
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1: raise ValueError("Invalid delivery revision")
    identity = f"astel-video:{card['id']}:simulation:{revision}"
    # Simulation is an explicit rehearsal. The existing owner approval and
    # publisher remain responsible for any subsequent live plan.
    plan = {"contractVersion": 1, "projectId": "copilot", "brandId": brand, "contentId": f"astel-video:{card['id']}:simulation", "revision": revision,
            "source": {"producer": "astel-video-workspace", "reference": card["id"]},
            "variants": {"reel": {"text": text, "asset": 0, "instagram": {"type": "reel"}}},
            "assets": [{"url": media_url, "kind": "reel", "digest": "sha256:" + card["artifact"]["sha256"], "revision": str(card["revision"]), "availableUntil": available_until}],
            "destinations": [{"platform": "instagram", "accountKey": account_key, "variant": "reel", "scheduledAt": scheduled_at, "timezone": "America/Chicago"}],
            "requestId": identity, "idempotencyKey": identity, "mode": "simulation"}
    return {"input": plan, "input_digest": canonical_hash(plan), "story_digest": expected_digest, "state": "prepared_for_hub_validation", "submitted": False}
