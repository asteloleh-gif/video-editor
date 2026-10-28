"""YouTube metadata search for Astel. No keys, paid API, cookies or media download."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
HOME = Path.home() / ".local/share/astel-video-search"
VERSION = 1
TTL = 300


def validate(request):
    if not isinstance(request, dict) or set(request) - {"query", "limit", "order"}:
        raise ValueError("Unsupported search options")
    query = request.get("query")
    limit = request.get("limit", 25)
    order = request.get("order", "relevance")
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200 or any(ord(c) < 32 for c in query):
        raise ValueError("Enter a topic of 1–200 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit not in (10, 25, 50, 100):
        raise ValueError("Select 10, 25, 50 or 100 results")
    if order not in ("relevance", "date"):
        raise ValueError("Unsupported search order")
    return {"query": query.strip(), "limit": limit, "order": order}


def number(value):
    return value if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None


def normalize(entries, limit):
    results, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get("id")
        if not isinstance(key, str) or not VIDEO_ID.fullmatch(key) or key in seen:
            continue
        seen.add(key)
        results.append({
            "id": key,
            "title": str(entry.get("title") or "Без названия")[:500],
            "channel": str(entry.get("channel") or entry.get("uploader") or "Канал не указан")[:200],
            "duration": number(entry.get("duration")),
            "views": number(entry.get("view_count")),
            "url": f"https://www.youtube.com/watch?v={key}",
            "thumbnail": f"https://i.ytimg.com/vi/{key}/hqdefault.jpg",
            "live": entry.get("live_status") == "is_live" or entry.get("is_live") is True,
        })
        if len(results) >= limit:
            break
    return results


def search(request, *, home=None, factory=None, clock=time.time):
    request = validate(request)
    cache = Path(home or HOME) / "cache"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(json.dumps({"version": VERSION, **request}, sort_keys=True).encode()).hexdigest()
    destination = cache / (key + ".json")
    try:
        previous = json.loads(destination.read_text())
        if previous.get("version") == VERSION and 0 <= clock() - previous["timestamp"] < TTL and previous.get("request") == request:
            return {**previous["response"], "from_cache": True}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    if factory is None:
        from yt_dlp import YoutubeDL
        factory = YoutubeDL
    options = {
        "quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
        "skip_download": True, "socket_timeout": 12, "retries": 1,
        "extractor_retries": 1, "cachedir": False, "playlistend": request["limit"],
        "sleep_interval_requests": .15,
    }
    target = f"ytsearch{request['limit']}:{request['query']}"
    if request["order"] == "date":
        # YouTube's upload-date + video-only filter, handled by YoutubeSearchURLIE.
        target = "https://www.youtube.com/results?" + urlencode({"search_query": request["query"], "sp": "CAISAhAB"})
    with factory(options) as extractor:
        data = extractor.extract_info(target, download=False)
        if not isinstance(data, dict):
            raise RuntimeError("YouTube did not return a search response")
        entries = normalize(data.get("entries") or [], request["limit"])
    response = {"ok": True, **request, "results": entries, "from_cache": False,
                "fetched_at": datetime.now(timezone.utc).isoformat()}
    # Empty or failed results are not cached as a successful search.
    if entries:
        with tempfile.NamedTemporaryFile(mode="w", dir=cache, prefix=".search-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"version": VERSION, "timestamp": clock(), "request": request, "response": response}, stream, ensure_ascii=False)
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    # Bound cache growth without touching source media or saved selections.
    try:
        oldest = sorted(cache.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[200:]
        for old in oldest:
            old.unlink(missing_ok=True)
    except OSError:
        pass  # Another search may expire a cache file concurrently.
    return response


def main():
    try:
        result = search(json.load(sys.stdin))
    except ValueError:
        result = {"ok": False, "code": "invalid_request", "message": "Введите тему и выберите параметры поиска."}
    except ImportError:
        result = {"ok": False, "code": "not_installed", "message": "Модуль поиска не установлен. Запустите установку Astel Video Search."}
    except Exception:
        result = {"ok": False, "code": "unavailable", "message": "YouTube не ответил на поиск. Проверьте интернет и повторите позже."}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
