"""Private Canvas view with editorial review and simulation-only Hub handoff."""
from __future__ import annotations
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit, parse_qs

from .canvas_contract import review_card
from .media_workspace import Workspace, identifier, timestamp
from .story_jobs import digest

PORT = 17531
CANVAS_SHA = "89c0152e696fed0e836029d5c64fe5d63b0afa85e7bf7ac93751a64a53d20ada"
PACKAGE_SHA = "cca3c19768f91571d628f304c46983af41e69383a040fd15233b351d4dd6d018"


def editorial_review(service, request):
    if not isinstance(request, dict) or set(request) != {"request_id", "story_id", "digest", "decision", "note"}:
        raise ValueError("Invalid review")
    key = identifier(request["request_id"]); story_id = identifier(request["story_id"])
    if request["decision"] not in ("changes_requested", "draft_accepted") or not isinstance(request["note"], str) or len(request["note"]) > 2000:
        raise ValueError("Invalid editorial decision")
    if request["decision"] == "changes_requested" and not request["note"].strip():
        raise ValueError("Describe the requested change")
    with service.db() as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT * FROM reviews WHERE id=?", (key,)).fetchone()
        if prior:
            if (prior["story_id"], prior["digest"], prior["decision"], prior["note"]) != (story_id, request["digest"], request["decision"], request["note"]):
                raise ValueError("Review request ID conflict")
            return dict(prior)
        card = review_card(service, story_id)
        if card["digest"] != request["digest"] or card["state"] != "needs_review":
            raise ValueError("Stale story revision")
        record = (key, story_id, card["revision"], card["digest"], "editorial_only", request["decision"], request["note"], timestamp())
        db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)", record)
        return dict(zip(("id", "story_id", "revision", "digest", "kind", "decision", "note", "created_at"), record))


def snapshot(service):
    from .hub_delivery import records
    data = service.listing(); cards = []
    for story in data["stories"]:
        card = review_card(service, story["id"])
        card["editorial_reviews"] = [r for r in data["reviews"] if r["story_id"] == story["id"] and r["digest"] == story["digest"]]
        cards.append(card)
    return {"stories": cards, "assets": data["assets"], "jobs": data["jobs"], "handoffs": records(service), "publishing_enabled": False, "hub_connection": "simulation_only", "local_only": True}


def adapt_document(html):
    # Keep the original private source pinned. Only replace reviewed hooks in
    # its read-only Hub client; no owner token or approval API is introduced.
    hooks = {
        "await sdk();if(started": "if(!window.AstelMacHubReader)await sdk();if(started",
        "reader=C.createReader({getInitData:initData});": "reader=window.AstelMacHubReader||C.createReader({getInitData:initData});",
        "if(mode==='hub'&&p.full&&!error)": "if(mode==='hub'&&p.full&&!error&&!window.AstelMacHubReader)",
        "  function title(p){return seed.titles?.[p.contentId]&&mode==='demo'?seed.titles[p.contentId]:p.contentId;}": "  function title(p){return seed.titles?.[p.contentId]&&mode==='demo'?seed.titles[p.contentId]:(window.AstelMacTitles?.[p.assets?.[0]?.digest]||p.contentId);}",
        "  function makePlayer(container,a,p){": "  function makePlayer(container,a,p){\n    if(mode==='hub'&&window.AstelMacMedia?.[a.digest]){const v=el('video');v.controls=true;v.playsInline=true;v.preload='metadata';v.src=window.AstelMacMedia[a.digest];v.setAttribute('aria-label','Локальная копия точного MP4 из задания Hub');container.append(v,el('small','','Локальная копия с совпадающим SHA-256. Доступ сервера к Drive проверяется отдельно.'));return;}",
        "Данные Hub через защищённый Telegram-backend. Здесь только просмотр; согласование — отдельно.": "Подтверждённые данные Hub. Этот экран только читает очередь; публикация через него выключена.",
    }
    for old, new in hooks.items():
        if old not in html:
            # Small unit fixtures do not contain the production Canvas client.
            if 'AstelDistributionCore' in html: raise ValueError('Canvas integration hook changed')
            continue
        if html.count(old) != 1: raise ValueError('Ambiguous Canvas integration hook')
        html = html.replace(old, new)
    return html.replace('</head>', '<link rel="stylesheet" href="/workspace.css"></head>', 1).replace('</body>', '<script src="/workspace.js"></script></body>', 1)


def create_server(service, port=PORT):
    session = secrets.token_urlsafe(32)
    from .drive_authorization import DriveAuthorization
    authorization = DriveAuthorization()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # no paths, cookies or request payloads in logs

        @property
        def origin(self):
            return f"http://127.0.0.1:{self.server.server_port}"

        def boundary(self, *, authenticated=True, mutation=False):
            if self.client_address[0] != "127.0.0.1" or self.headers.get("Host") != self.origin.removeprefix("http://"):
                return False
            if self.headers.get("Sec-Fetch-Site", "none") not in {"none", "same-origin"}:
                return False
            if self.headers.get("Origin") not in (None, self.origin):
                return False
            if mutation and self.headers.get("Origin") != self.origin:
                return False
            if authenticated:
                try:
                    cookie = SimpleCookie(self.headers.get("Cookie", ""))
                    return "astel_canvas" in cookie and secrets.compare_digest(cookie["astel_canvas"].value, session)
                except Exception:
                    return False
            return True

        def write_headers(self, code, mime, size, *, cookie=False, extra=None):
            self.send_response(code)
            for key, value in {"Content-Type": mime, "Content-Length": str(size), "Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cross-Origin-Resource-Policy": "same-origin", "X-Frame-Options": "DENY", **(extra or {})}.items():
                self.send_header(key, value)
            if cookie:
                self.send_header("Set-Cookie", f"astel_canvas={session}; HttpOnly; SameSite=Strict; Path=/")
            if mime.startswith("text/html"):
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; media-src 'self' data: blob: https:; frame-src https://drive.google.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()

        def send(self, code, data, mime="application/json", *, cookie=False):
            payload = json.dumps(data, ensure_ascii=False).encode() if mime == "application/json" else data
            self.write_headers(code, mime, len(payload), cookie=cookie)
            self.wfile.write(payload)

        def do_GET(self):
            route = urlsplit(self.path).path
            try:
                if not self.boundary(authenticated=route != "/"):
                    return self.send(403, {"error": "Owner local session required"})
                if route == "/":
                    source = service.home / "canvas/document.html"
                    if digest(source) != CANVAS_SHA:
                        raise ValueError("Canvas source differs from reviewed version")
                    html = adapt_document(source.read_text())
                    return self.send(200, html.encode(), "text/html; charset=utf-8", cookie=True)
                if route in {"/workspace.js", "/workspace.css"}:
                    source = service.home / "canvas" / route[1:]
                    return self.send(200, source.read_bytes(), "text/javascript" if route.endswith(".js") else "text/css")
                if route == "/api/astel-workspace":
                    return self.send(200, {**snapshot(service), 'drive_authorization': authorization.status()})
                if route.startswith('/api/astel-workspace/hub/'):
                    from .hub_delivery import HubClient
                    hub = HubClient(readonly=True)
                    if route == '/api/astel-workspace/hub/inbox':
                        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                        if set(query) - {'cursor'} or any(len(v) != 1 for v in query.values()): raise ValueError('Invalid cursor')
                        cursor = query.get('cursor', [None])[0]
                        if cursor is not None and not re.fullmatch(r'[a-f0-9]{64}', cursor): raise ValueError('Invalid cursor')
                        return self.send(200, hub.read('inbox', limit=25, **({'cursor': cursor} if cursor else {})))
                    if route == '/api/astel-workspace/hub/metrics': return self.send(200, hub.read('metrics'))
                    plan = re.fullmatch(r'/api/astel-workspace/hub/plans/([a-f0-9]{64})', route)
                    if plan: return self.send(200, hub.read('status', planId=plan[1]))
                match = re.fullmatch(r"/api/astel-workspace/stories/([a-f0-9-]{36})/(card|video\.mp4)", route)
                if match:
                    key = identifier(match[1]); card = review_card(service, key)
                    if match[2] == "card":
                        return self.send(200, card)
                    # Immutable UUID + verified exact bytes; supports browser seek.
                    source = service.folder(key) / "video.mp4"; size = source.stat().st_size
                    start, end, status = 0, size - 1, 200
                    requested = self.headers.get("Range")
                    if requested:
                        parsed = re.fullmatch(r"bytes=(\d+)-(\d*)", requested)
                        if not parsed:
                            return self.send(416, {"error": "Invalid range"})
                        start = int(parsed[1]); end = min(int(parsed[2]) if parsed[2] else size - 1, size - 1)
                        if start > end or start >= size:
                            return self.send(416, {"error": "Invalid range"})
                        status = 206
                    extra = {"Accept-Ranges": "bytes", "ETag": '"' + card["artifact"]["sha256"] + '"'}
                    if status == 206: extra["Content-Range"] = f"bytes {start}-{end}/{size}"
                    self.write_headers(status, "video/mp4", end - start + 1, extra=extra)
                    with source.open("rb") as stream:
                        stream.seek(start); remaining = end - start + 1
                        while remaining:
                            chunk = stream.read(min(1024 * 1024, remaining))
                            if not chunk: break
                            self.wfile.write(chunk); remaining -= len(chunk)
                    return
                self.send(404, {"error": "No publication or Hub route on this service"})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (ValueError, KeyError, OSError):
                self.send(409, {"error": "The requested local revision is unavailable or changed"})

        def do_POST(self):
            if not self.boundary(mutation=True):
                return self.send(403, {"error": "Owner local session required"})
            if self.path not in {"/api/astel-workspace/review", "/api/astel-workspace/hub/submit", "/api/astel-workspace/hub/status", "/api/astel-workspace/hub/retry", "/api/astel-workspace/hub/media-access", "/api/astel-workspace/drive/reauthorize"}:
                return self.send(404, {"error": "No publication or Hub mutations"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 12000 or self.headers.get("Content-Type") != "application/json":
                    raise ValueError("Invalid request size/type")
                body = json.loads(self.rfile.read(size))
                if self.path == '/api/astel-workspace/drive/reauthorize':
                    if body != {}: raise ValueError('Unexpected login fields')
                    return self.send(200, authorization.start())
                if self.path == '/api/astel-workspace/hub/media-access':
                    from .hub_delivery import allow_media_reading
                    return self.send(200, allow_media_reading(service, body))
                if self.path == '/api/astel-workspace/hub/submit':
                    if not isinstance(body, dict) or set(body) != {'request_id','story_id','digest','account_key','text','scheduled_at'}: raise ValueError('Invalid handoff')
                    request_id = body.pop('request_id')
                    return self.send(200, service.submit({'id': request_id, 'kind': 'handoff', 'payload': body}))
                if self.path in {'/api/astel-workspace/hub/status','/api/astel-workspace/hub/retry'}:
                    from .hub_delivery import refresh, retry
                    if not isinstance(body, dict) or set(body) != {'job_id'}: raise ValueError('Invalid handoff status')
                    key = identifier(body['job_id'])
                    return self.send(200, (refresh if self.path.endswith('status') else retry)(service, key))
                result = editorial_review(service, body)
                return self.send(200, {"review": result, "publication_approved": False, "submitted": False})
            except (ValueError, KeyError):
                return self.send(409, {"error": "Review rejected: changed version, invalid fields or conflicting request ID"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    create_server(Workspace()).serve_forever()


if __name__ == "__main__":
    main()
