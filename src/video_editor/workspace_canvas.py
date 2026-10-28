"""Private loopback preparation view inside the owner's existing Canvas.

No Hub credentials, plan submission, publication approval or scheduler.
"""
from __future__ import annotations
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

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
    data = service.listing(); cards = []
    for story in data["stories"]:
        card = review_card(service, story["id"])
        card["editorial_reviews"] = [r for r in data["reviews"] if r["story_id"] == story["id"] and r["digest"] == story["digest"]]
        cards.append(card)
    return {"stories": cards, "assets": data["assets"], "jobs": data["jobs"], "publishing_enabled": False, "hub_connection": "not_submitted", "local_only": True}


def create_server(service, port=PORT):
    session = secrets.token_urlsafe(32)

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
                    html = source.read_text().replace("</head>", '<link rel="stylesheet" href="/workspace.css"></head>', 1)
                    html = html.replace("</body>", '<script src="/workspace.js"></script></body>', 1)
                    return self.send(200, html.encode(), "text/html; charset=utf-8", cookie=True)
                if route in {"/workspace.js", "/workspace.css"}:
                    source = service.home / "canvas" / route[1:]
                    return self.send(200, source.read_bytes(), "text/javascript" if route.endswith(".js") else "text/css")
                if route == "/api/astel-workspace":
                    return self.send(200, snapshot(service))
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
            if self.path != "/api/astel-workspace/review":
                return self.send(404, {"error": "No publication or Hub mutations"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 12000 or self.headers.get("Content-Type") != "application/json":
                    raise ValueError("Invalid request size/type")
                result = editorial_review(service, json.loads(self.rfile.read(size)))
                return self.send(200, {"review": result, "publication_approved": False, "submitted": False})
            except (ValueError, KeyError):
                return self.send(409, {"error": "Review rejected: changed version, invalid fields or conflicting request ID"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    create_server(Workspace()).serve_forever()


if __name__ == "__main__":
    main()
