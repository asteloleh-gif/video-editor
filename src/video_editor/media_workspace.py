"""Astel media catalogue, durable acquisition and new-story jobs. Private JSON IPC."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
import uuid
import wave

from .story_jobs import digest, lock, write

HOME = Path.home() / ".local/share/astel-media-workspace"
END = {"ready", "failed", "cancelled"}
MAX_FILE = 100 * 1024 * 1024
MAX_PENDING_JOBS = 100
MAX_WORKER_PROCESSES = 4
UA = "AstelMediaWorkspace/1.0 (https://github.com/asteloleh-gif/video-editor; local review)"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError("Invalid ID")
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))[:2000].strip()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("Redirect refused")


def get_json(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "commons.wikimedia.org" or parsed.path != "/w/api.php":
        raise ValueError("Source API denied")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(Request(url, headers={"User-Agent": UA}), timeout=20) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Source response too large")
    result = json.loads(data)
    if "error" in result:
        raise RuntimeError("Source API unavailable")
    return result


def commons_search(query, limit=10):
    params = {"action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
              "gsrlimit": limit, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
              "iiurlwidth": 480, "format": "json", "formatversion": 2}
    data = get_json("https://commons.wikimedia.org/w/api.php?" + urlencode(params))
    results = []
    for page in data.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime not in {"image/jpeg", "image/png", "image/webp", "video/webm", "video/mp4", "application/ogg", "video/ogg"}:
            continue
        url = info.get("url", "")
        if urlparse(url).hostname != "upload.wikimedia.org":
            continue
        meta = info.get("extmetadata", {})
        field = lambda key: plain(meta.get(key, {}).get("value"))
        results.append({"provider": "commons", "source_id": str(page["pageid"]), "title": plain(page["title"].removeprefix("File:")),
                        "url": info.get("descriptionurl", ""), "thumbnail": info.get("thumburl", ""), "file_url": url,
                        "kind": "video" if mime.startswith("video/") or mime.endswith("ogg") else "image", "mime": mime,
                        "author": field("Artist"), "license": field("LicenseShortName"), "license_url": field("LicenseUrl"),
                        "size": info.get("size"), "views": None, "downloadable": bool(field("LicenseShortName") and info.get("size", MAX_FILE + 1) <= MAX_FILE)})
    return results


class Workspace:
    def __init__(self, home=None):
        self.home = Path(home or os.environ.get("ASTEL_MEDIA_HOME", HOME)).resolve()
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.jobs = self.home / "jobs"; self.jobs.mkdir(exist_ok=True, mode=0o700)
        self.assets = self.home / "assets"; self.assets.mkdir(exist_ok=True, mode=0o700)
        self.database = self.home / "catalogue.sqlite"
        with self.db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,provider TEXT,source_id TEXT,data TEXT,UNIQUE(provider,source_id));
              CREATE TABLE IF NOT EXISTS searches(id TEXT PRIMARY KEY,query TEXT,created_at TEXT,results TEXT,errors TEXT);
              CREATE TABLE IF NOT EXISTS observations(candidate_id TEXT,observed_at TEXT,views REAL,PRIMARY KEY(candidate_id,observed_at));
              CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,candidate_id TEXT UNIQUE,sha256 TEXT,data TEXT,created_at TEXT);
              CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,request_hash TEXT,payload TEXT,status TEXT,progress REAL,phase TEXT,error TEXT,result TEXT,created_at TEXT,updated_at TEXT);
              CREATE TABLE IF NOT EXISTS stories(id TEXT PRIMARY KEY,revision INTEGER,digest TEXT,data TEXT,created_at TEXT);
              CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,story_id TEXT,revision INTEGER,digest TEXT,kind TEXT,decision TEXT,note TEXT,created_at TEXT);
            """)
        self.database.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def folder(self, job_id):
        folder = self.jobs / identifier(job_id)
        if folder.is_symlink() or folder.resolve().parent != self.jobs:
            raise ValueError("Invalid job folder")
        return folder

    def status(self, job_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier(job_id),)).fetchone()
        if row is None:
            raise ValueError("Job not found")
        return {**{k: row[k] for k in ("id", "kind", "status", "progress", "phase", "error", "created_at", "updated_at")}, "result": json.loads(row["result"] or "{}"),
                **({"story_id": json.loads(row["payload"])["story_id"]} if row["kind"] == "handoff" else {})}

    def update(self, job_id, **values):
        allowed = {"status", "progress", "phase", "error", "result"}
        if not set(values) <= allowed:
            raise ValueError("Invalid update")
        values["updated_at"] = timestamp()
        if "result" in values:
            values["result"] = json.dumps(values["result"], ensure_ascii=False)
        with self.db() as db:
            db.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in values) + " WHERE id=?", (*values.values(), job_id))

    def submit(self, request):
        if not isinstance(request, dict) or set(request) != {"id", "kind", "payload"}:
            raise ValueError("Invalid request")
        job_id = identifier(request["id"]); kind = request["kind"]; payload = request["payload"]
        if kind not in {"search", "batch", "acquire", "story", "handoff"} or not isinstance(payload, dict):
            raise ValueError("Invalid job kind")
        expected = fingerprint({"kind": kind, "payload": payload})
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT request_hash FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row and row[0] != expected:
                raise ValueError("Request ID already belongs to other settings")
            if not row:
                if db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= MAX_PENDING_JOBS:
                    raise ValueError("Queue contains 100 unfinished jobs; finish or cancel one before adding more")
                self.validate(kind, payload)
                self.folder(job_id).mkdir(mode=0o700)
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (job_id, kind, expected, json.dumps(payload, ensure_ascii=False), "queued", 0, "В очереди", None, "{}", timestamp(), timestamp()))
        self.spawn(job_id)
        return self.status(job_id)

    def validate(self, kind, payload):
        if kind in {"search", "batch"}:
            expected = {"query", "providers"} if kind == "search" else {"topics", "providers"}
            if set(payload) != expected or not isinstance(payload["providers"], list) or not 1 <= len(payload["providers"]) <= 2 or any(p not in ("youtube", "commons") for p in payload["providers"]):
                raise ValueError("Choose supported sources")
            topics = [payload["query"]] if kind == "search" else payload["topics"]
            if not isinstance(topics, list) or not 1 <= len(topics) <= 100 or any(not isinstance(q, str) or not 1 <= len(q.strip()) <= 200 or any(ord(c) < 32 for c in q) for q in topics):
                raise ValueError("Enter 1–100 topics, up to 200 characters each")
        elif kind == "acquire":
            if set(payload) != {"candidate_id"}:
                raise ValueError("Select a candidate")
            self.candidate(payload["candidate_id"])
        elif kind == "handoff":
            from .hub_delivery import validate
            validate(self, payload)
        else:
            required = {"title", "script", "asset_ids", "profile", "project_id"}
            if not required <= set(payload) or set(payload) - required - {"parent_story_id", "parent_digest"}:
                raise ValueError("Invalid story settings")
            if ("parent_story_id" in payload) != ("parent_digest" in payload):
                raise ValueError("Revision identity is incomplete")
            if "parent_story_id" in payload:
                self.parent_story(payload)
            if not isinstance(payload["title"], str) or not 1 <= len(payload["title"].strip()) <= 160 or not isinstance(payload["script"], str) or not 1 <= len(payload["script"].strip()) <= 3000:
                raise ValueError("Enter a title and up to 3000 characters of script")
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", payload["script"]) if p.strip()]
            if not 1 <= len(paragraphs) <= 12 or payload["profile"] not in {"oleh-ru", "oleh-en"}:
                raise ValueError("Use 1–12 paragraphs and an approved voice")
            if not isinstance(payload["project_id"], str) or not 1 <= len(payload["project_id"]) <= 128 or not isinstance(payload["asset_ids"], list) or not 1 <= len(payload["asset_ids"]) <= 12:
                raise ValueError("Select 1–12 library files and open a project")
            for asset_id in payload["asset_ids"]:
                self.asset(asset_id)

    def story(self, story_id):
        with self.db() as db:
            row = db.execute("SELECT data FROM stories WHERE id=?", (identifier(story_id),)).fetchone()
        if row is None:
            raise ValueError("Story not found")
        return json.loads(row[0])

    def parent_story(self, payload):
        parent = self.story(payload["parent_story_id"])
        root = parent.get("root_id", parent["id"])
        with self.db() as db:
            versions = [json.loads(r[0]) for r in db.execute("SELECT data FROM stories")]
        latest = max((v for v in versions if v.get("root_id", v["id"]) == root), key=lambda v: v["revision"])
        if parent["digest"] != payload["parent_digest"] or latest["id"] != parent["id"]:
            raise ValueError("Story revision is stale; open the latest version")
        return parent

    def spawn(self, job_id):
        if self.status(job_id)["status"] in END:
            return
        with self.db() as db:
            eligible = {row[0] for row in db.execute("SELECT id FROM jobs WHERE status IN ('queued','running') ORDER BY created_at,rowid LIMIT ?", (MAX_WORKER_PROCESSES,))}
        if job_id not in eligible:
            return  # The persistent supervisor advances the bounded backlog.
        try:
            with lock(self.folder(job_id) / "run.lock", True) as handle:
                current = self.status(job_id)
                if current['kind'] in {'story','acquire'} and shutil.disk_usage(self.home).free < 8 * 1024**3:
                    self.update(job_id, status='queued', phase='Ожидает свободного места на диске')
                    return
                with (self.folder(job_id) / "worker.log").open("ab") as log:
                    os.chmod(log.name, 0o600)
                    subprocess.Popen([sys.executable, "-m", "video_editor.media_workspace", "worker", "--id", job_id, "--lock-fd", str(handle.fileno())],
                                     pass_fds=(handle.fileno(),), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                                     env={**os.environ, "ASTEL_MEDIA_HOME": str(self.home), "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"})
        except BlockingIOError:
            pass

    def resume(self, job_id):
        self.spawn(job_id)
        return self.status(job_id)

    def cancelled(self, job_id):
        if (self.folder(job_id) / "cancel").exists():
            raise InterruptedError("Cancelled")

    def cancel(self, job_id):
        status = self.status(job_id)['status']
        if status not in END:
            (self.folder(job_id) / "cancel").touch(mode=0o600)
            if status == 'queued':
                self.update(job_id, status='cancelled', phase='Остановлено')
            else:
                self.spawn(job_id)
        return self.status(job_id)

    def worker(self, job_id, inherited_fd):
        kind = None
        with os.fdopen(inherited_fd, "a") as handle:
            try:
                while True:
                    self.cancelled(job_id)
                    try:
                        gate = (self.home / "worker.lock").open("a")
                        import fcntl
                        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        gate.close(); time.sleep(.5)
                with gate:
                    with self.db() as db:
                        row = db.execute("SELECT kind,payload FROM jobs WHERE id=?", (job_id,)).fetchone()
                    kind, payload = row["kind"], json.loads(row["payload"])
                    self.update(job_id, status="running", phase="Подготовка")
                    if kind in {"search", "batch"}:
                        self.run_search(job_id, payload)
                    elif kind == "acquire":
                        asset = self.acquire(payload["candidate_id"], job_id)
                        self.update(job_id, result={"asset_id": asset["id"]})
                    elif kind == "handoff":
                        from .hub_delivery import perform
                        perform(self, job_id, payload)
                    else:
                        from .story_workspace import build_story
                        build_story(self, job_id, payload, (handle.fileno(), gate.fileno()))
                    # A received Hub draft remains received if cancellation was
                    # requested during the submit. This never cancels/publishes
                    # a remote plan or hides an accepted request as "cancelled".
                    if kind != "handoff": self.cancelled(job_id)
                    self.update(job_id, status="ready", progress=1, phase="Готово")
            except InterruptedError:
                self.update(job_id, status="cancelled", phase="Остановлено")
            except Exception as error:
                import traceback
                traceback.print_exc()
                message = "Задача не завершена. Данные сохранены; проверьте источники и локальные сервисы."
                if kind == "handoff":
                    from .hub_delivery import DeliveryError
                    if isinstance(error, DeliveryError):
                        message = {"DRIVE_REAUTHORIZE_LOCALLY_REQUIRED": "Нужно повторно войти в Google Drive на этом Mac. После входа нажмите «Продолжить передачу».",
                                   "REMOTE_OUTCOME_UNCONFIRMED": "Ответ не подтверждён. Продолжение проверит тот же файл и ID Hub; новый черновик автоматически не создаётся.",
                                   "PRIVATE_CONNECTION_REQUIRED": "Локальное подключение Hub или Drive ещё не настроено.",
                                   "STALE_STORY_REVISION": "История изменилась. Выберите новую версию перед передачей."}.get(str(error), "Передача остановлена: " + str(error))
                self.update(job_id, status="failed", phase="Ошибка", error=message)

    def save_candidate(self, data):
        key = str(uuid.uuid5(uuid.NAMESPACE_URL, data["provider"] + ":" + data["source_id"]))
        data = {**data, "id": key, "captured_at": timestamp()}
        with self.db() as db:
            db.execute("INSERT INTO candidates VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (key, data["provider"], data["source_id"], json.dumps(data, ensure_ascii=False)))
            db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?)", (key, data["captured_at"], data.get("views")))
        return key

    def candidate(self, candidate_id, public=False):
        with self.db() as db:
            row = db.execute("SELECT data FROM candidates WHERE id=?", (identifier(candidate_id),)).fetchone()
        if not row:
            raise ValueError("Candidate not found")
        data = json.loads(row[0])
        if public:
            data.pop("file_url", None)
            data.pop("local_path", None)
        return data

    def run_search(self, job_id, payload):
        from .video_search import search
        topics = [payload["query"]] if "query" in payload else list(dict.fromkeys(q.strip() for q in payload["topics"]))
        result = self.status(job_id)["result"]
        runs = result.get("search_ids", [])
        for index in range(len(runs), len(topics)):
            self.cancelled(job_id)
            query = topics[index]; found = []; errors = []
            self.update(job_id, progress=index / len(topics), phase=f"Поиск {index + 1}/{len(topics)}: {query[:80]}")
            for provider in payload["providers"]:
                self.cancelled(job_id)
                try:
                    if provider == "commons":
                        entries = commons_search(query)
                    else:
                        response = search({"query": query, "limit": 10, "order": "relevance"}, home=self.home / "youtube")
                        entries = [{**entry, "provider": "youtube", "source_id": entry["id"], "kind": "reference", "author": entry["channel"], "license": None, "downloadable": False} for entry in response["results"]]
                    found.extend(self.save_candidate(entry) for entry in entries)
                except Exception:
                    errors.append({"provider": provider, "message": "Источник временно недоступен; другие результаты сохранены"})
                time.sleep(.25)
            run_id = str(uuid.uuid5(uuid.UUID(job_id), str(index)))
            with self.db() as db:
                db.execute("INSERT OR REPLACE INTO searches VALUES(?,?,?,?,?)", (run_id, query, timestamp(), json.dumps(list(dict.fromkeys(found))), json.dumps(errors, ensure_ascii=False)))
            runs.append(run_id)
            self.update(job_id, result={"search_ids": runs, "completed_topics": len(runs), "total_topics": len(topics)})

    def listing(self):
        with self.db() as db:
            job_ids = [r[0] for r in db.execute("SELECT id FROM jobs ORDER BY created_at DESC LIMIT 30")]
            search_rows = db.execute("SELECT * FROM searches ORDER BY created_at DESC LIMIT 20").fetchall()
            assets = [json.loads(r[0]) for r in db.execute("SELECT data FROM assets ORDER BY created_at DESC LIMIT 100")]
            stories = [json.loads(r[0]) for r in db.execute("SELECT data FROM stories ORDER BY created_at DESC LIMIT 30")]
            reviews = [dict(r) for r in db.execute("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 50")]
        return {"jobs": [self.status(key) for key in job_ids], "searches": [{"id": r["id"], "query": r["query"], "created_at": r["created_at"], "errors": json.loads(r["errors"]), "candidates": [self.candidate(key, True) for key in json.loads(r["results"])]} for r in search_rows],
                "assets": [self.public_asset(a) for a in assets], "stories": stories, "reviews": reviews,
                "disk_free_bytes": shutil.disk_usage(self.home).free, "publishing_enabled": False}

    def public_asset(self, asset):
        return {k: v for k, v in asset.items() if k not in {"original_path", "media_path"}}

    def asset(self, asset_id):
        with self.db() as db:
            row = db.execute("SELECT data FROM assets WHERE id=?", (identifier(asset_id),)).fetchone()
        if row is None:
            raise ValueError("Asset not found")
        return json.loads(row[0])

    def storage_check(self, size=MAX_FILE):
        # Keep a reserve on the owner's disk and a bounded managed originals cache.
        total = sum(p.stat().st_size for p in self.assets.rglob("*") if p.is_file())
        if total + size > 2 * 1024**3 or shutil.disk_usage(self.home).free - size < 8 * 1024**3:
            raise ValueError("Library storage limit reached")

    def probe(self, source):
        info = json.loads(subprocess.check_output(["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)], timeout=20))
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        duration = float(info["format"].get("duration") or 0)
        if not 0 < video["width"] <= 20000 or not 0 < video["height"] <= 20000 or duration > 7200:
            raise ValueError("Unsupported media dimensions/duration")
        return {"kind": "video" if duration > 0 else "image", "width": video["width"], "height": video["height"], "duration": duration, "codec": video["codec_name"], "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}

    def acquire(self, candidate_id, job_id):
        with lock(self.home / "acquire.lock"):
            with self.db() as db:
                previous = db.execute("SELECT id FROM assets WHERE candidate_id=?", (candidate_id,)).fetchone()
            if previous:
                self.file_receipt(previous[0])
                return self.asset(previous[0])
            candidate = self.candidate(candidate_id)
            if not candidate.get("downloadable"):
                raise ValueError("This candidate is a reference link, not an available file")
            self.storage_check(); asset_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "astel-asset:" + candidate_id)); folder = self.assets / asset_id; folder.mkdir(mode=0o700, exist_ok=True)
            source = folder / "original"
            source_receipt = folder / "source-receipt.json"
            partial = folder / "original.part"
            if source_receipt.exists():
                if digest(source) != json.loads(source_receipt.read_text())["sha256"]:
                    raise ValueError("Acquired original changed")
            elif source.exists():
                # A crash between the atomic rename and receipt write leaves a
                # completed original. Validate it and repair only the receipt.
                self.probe(source)
                write(source_receipt, {"sha256": digest(source), "candidate_id": candidate_id})
            elif candidate["provider"] == "local":
                original = Path(candidate["local_path"]).resolve()
                if not original.is_file() or original.stat().st_size > MAX_FILE or digest(original) != candidate["expected_sha256"]:
                    raise ValueError("Selected local file changed")
                shutil.copyfile(original, partial)
            else:
                parsed = urlparse(candidate["file_url"])
                if parsed.scheme != "https" or parsed.hostname != "upload.wikimedia.org" or parsed.username or parsed.password or parsed.port or not parsed.path.startswith("/wikipedia/commons/"):
                    raise ValueError("Media origin denied")
                opener = build_opener(ProxyHandler({}), NoRedirect())
                with opener.open(Request(candidate["file_url"], headers={"User-Agent": UA}), timeout=25) as response, partial.open("wb") as output:
                    received = 0
                    while chunk := response.read(256 * 1024):
                        self.cancelled(job_id); received += len(chunk)
                        if received > MAX_FILE:
                            raise ValueError("File too large")
                        output.write(chunk)
            self.cancelled(job_id)
            if not source.exists():
                original_hash = digest(partial)
                partial.replace(source)
                write(source_receipt, {"sha256": original_hash, "candidate_id": candidate_id})
            info = self.probe(source); original_hash = digest(source)
            target = folder / ("media.mp4" if info["kind"] == "video" else "media.jpg")
            prepared = target.with_name("preparing-" + target.name)
            command = ["/opt/homebrew/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vf", "scale='min(1920,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"]
            command += ["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart"] if info["kind"] == "video" else ["-frames:v", "1"]
            command += [str(prepared)]
            self.process(job_id, command, timeout=600)
            if prepared.stat().st_size > MAX_FILE:
                raise ValueError("Prepared file too large")
            prepared.replace(target)
            asset = {"id": asset_id, "candidate_id": candidate_id, **info, "title": candidate["title"], "provider": candidate["provider"], "source_url": candidate.get("url"), "author": candidate.get("author"), "license": candidate.get("license"), "license_url": candidate.get("license_url"),
                     "original_path": str(source), "media_path": str(target), "sha256": original_hash, "media_sha256": digest(target), "bytes": source.stat().st_size, "created_at": timestamp()}
            write(folder / "provenance.json", self.public_asset(asset))
            with self.db() as db:
                db.execute("INSERT INTO assets VALUES(?,?,?,?,?)", (asset_id, candidate_id, original_hash, json.dumps(asset, ensure_ascii=False), timestamp()))
            return asset

    def import_local(self, source):
        # Only called by the native main process after its own file picker.
        source = Path(source).expanduser().resolve()
        if not source.is_file() or source.stat().st_size > MAX_FILE:
            raise ValueError("Choose a media file under 100 MiB")
        sha = digest(source)
        key = self.save_candidate({"provider": "local", "source_id": sha, "title": source.name, "url": None, "author": "Owner-provided", "license": "Owner review required", "downloadable": True, "local_path": str(source), "expected_sha256": sha})
        return self.submit({"id": str(uuid.uuid4()), "kind": "acquire", "payload": {"candidate_id": key}})

    def file_receipt(self, asset_id):
        asset = self.asset(asset_id); source = Path(asset["media_path"])
        if source.is_symlink() or not source.resolve().is_relative_to(self.assets / asset["id"]) or digest(source) != asset["media_sha256"]:
            raise ValueError("Library media changed")
        return {"path": str(source), "sha256": asset["media_sha256"], "kind": asset["kind"], "name": f"Astel-{asset['id']}" + source.suffix}

    def process(self, job_id, command, *, timeout=600, stdin=None, pass_fds=(), cwd=None, render_progress=False):
        self.cancelled(job_id)
        process = subprocess.Popen(command, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL, start_new_session=True, pass_fds=pass_fds, cwd=cwd)
        if stdin is not None:
            process.stdin.write(json.dumps(stdin).encode()); process.stdin.close()
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                self.cancelled(job_id)
                if time.monotonic() > deadline:
                    raise TimeoutError("Local operation timed out")
                if render_progress:
                    try:
                        value = json.loads((self.folder(job_id) / "progress.json").read_text())["progress"]
                        self.update(job_id, progress=.55 + max(0, min(1, float(value))) * .4, phase="Рендер видео и звука")
                    except (OSError, ValueError, KeyError):
                        pass
                time.sleep(.3)
        except BaseException:
            try:
                process.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait()
            raise
        self.cancelled(job_id)
        if process.returncode:
            raise RuntimeError("Local media operation failed")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list", "submit", "resume", "cancel", "file", "video", "card", "import", "worker", "asr"])
    parser.add_argument("--id"); parser.add_argument("--lock-fd", type=int)
    args = parser.parse_args(); service = Workspace()
    if args.command == "worker":
        service.worker(args.id, args.lock_fd); return
    if args.command == "asr":
        from .transcript import transcribe_video
        folder = service.folder(args.id)
        with service.db() as db:
            request = json.loads(db.execute("SELECT payload FROM jobs WHERE id=?", (args.id,)).fetchone()[0])
        result = transcribe_video(folder / "public/narration.wav", language="ru" if request["profile"] == "oleh-ru" else "en", max_len=38)
        write(folder / "transcript.json", {**result.to_dict(), "audio_sha256": digest(folder / "public/narration.wav")}); return
    if args.command == "list": result = service.listing()
    elif args.command == "submit": result = service.submit(json.loads(sys.stdin.read(50000)))
    elif args.command == "import": result = service.import_local(json.loads(sys.stdin.read(8192))["path"])
    elif args.command == "file": result = service.file_receipt(args.id)
    elif args.command == "video":
        from .story_workspace import story_video
        result = story_video(service, identifier(args.id))
    elif args.command == "card":
        from .canvas_contract import review_card
        result = review_card(service, identifier(args.id))
    else: result = getattr(service, args.command)(args.id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(json.dumps({"error": "invalid_request", "message": str(error)}, ensure_ascii=False))
