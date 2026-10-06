"""Astel's independent OpenReel layer. No publishing or implicit live mutations."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("MCP endpoint redirects are not allowed")


class DesktopMcp:
    """Read-only Stage 1 probe; endpoint token never enters snapshot artifacts."""

    def __init__(self, endpoint_file: str | Path | None = None):
        path = Path(endpoint_file or os.environ.get("OPENREEL_MCP_ENDPOINT_FILE", "~/.openreel/mcp-endpoint.json")).expanduser()
        endpoint = json.loads(path.read_text())
        url = urlparse(endpoint["url"])
        if url.scheme != "http" or url.hostname != "127.0.0.1" or url.path != "/mcp" or url.username or url.password or url.query or url.fragment:
            raise ValueError("Expected loopback OpenReel HTTP /mcp endpoint")
        self.url, self.token = endpoint["url"], endpoint["token"]
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.request_id = 0

    def rpc(self, method: str, params: dict | None = None):
        if method not in {"initialize", "tools/list", "tools/call"}:
            raise ValueError("Unsupported probe method")
        if method == "tools/call" and (params or {}).get("name") not in {"get_editor_state", "list_tracks", "list_clips", "list_media", "get_clip"}:
            raise ValueError("Probe only permits read tools")
        self.request_id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}}).encode()
        request = Request(self.url, body, {"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"})
        with self.opener.open(request, timeout=60) as response:
            reply = json.load(response)
        if reply.get("error"):
            raise RuntimeError(reply["error"].get("message", "MCP error"))
        return reply["result"]

    def read(self, name: str, **arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(f"OpenReel read failed: {name}")
        text = next(item["text"] for item in result["content"] if item["type"] == "text")
        # Upstream core.ts emits summary + blank line + JSON data.
        return json.loads(text.split("\n\n", 1)[1])

    def snapshot(self):
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "astel-probe", "version": "0.1"}})
        tools = self.rpc("tools/list")["tools"]
        before = self.read("get_editor_state")
        clips, offset = [], 0
        while True:
            page = self.read("list_clips", offset=offset, limit=100)
            clips.extend(page)
            if len(page) < 100:
                break
            offset += len(page)
        details = [self.read("get_clip", clipId=clip["id"]) for clip in clips]
        tracks, media = self.read("list_tracks"), self.read("list_media")
        after = self.read("get_editor_state")
        if before["project"]["id"] != after["project"]["id"]:
            raise RuntimeError("Active project changed while reading; retry")
        return {"format": "astel.openreel.snapshot.v1", "state": after, "tracks": tracks, "media": media, "clips": clips, "clip_details": details, "tools": tools,
                "consistency": "non-atomic; keep editor idle during capture"}


def plan_keep_ranges(plan: dict, *, media_id: str, track_id: str, style: dict | None = None):
    """Compile Astel source KEEP ranges to a reviewable tool recipe.

    $clip:N is a response binding for a future executor, not an OpenReel ID.
    Live import of local RAW is deliberately manual; no fabricated media IDs.
    """
    if not media_id or not track_id:
        raise ValueError("Existing OpenReel media and empty target track IDs required")
    duration = float(plan["source"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid source duration")
    calls, mapping, cursor, previous_end = [], [], 0.0, 0.0
    if not plan["keep"]:
        raise ValueError("No KEEP ranges")
    for index, interval in enumerate(plan["keep"]):
        start, end = float(interval["start"]), float(interval["end"])
        if not all(math.isfinite(x) for x in (start, end)) or start < previous_end or end <= start or end > duration:
            raise ValueError("KEEP ranges must be ordered, disjoint and inside source duration")
        binding = f"$clip:{index}"
        calls.extend([
            {"name": "add_clip", "arguments": {"trackId": track_id, "mediaId": media_id, "startTime": cursor}, "bind": binding},
            {"name": "trim_clip", "arguments": {"clipId": binding, "inPoint": start, "outPoint": end}},
            {"name": "move_clip", "arguments": {"clipId": binding, "startTime": cursor}},
        ])
        mapping.append({"binding": binding, "source_start": start, "source_end": end, "output_start": cursor, "output_end": cursor + end - start})
        cursor += end - start
        previous_end = end
    return {"format": "astel.openreel.recipe.v1", "status": "review-only", "preconditions": {"empty_track_id": track_id, "source_media_id": media_id, "source_duration": duration},
            "calls": calls, "source_mapping": mapping, "style_sidecar": style or {},
            "unsupported": ["AstelFam Remotion graphics remain external assets; style_sidecar is not applied by this recipe"]}


def correction_diff(before: dict, after: dict):
    if before["state"]["project"]["id"] != after["state"]["project"]["id"]:
        raise ValueError("Cannot compare different projects")
    old = {item["id"]: item for item in before["clip_details"]}
    new = {item["id"]: item for item in after["clip_details"]}
    changes = []
    for clip_id in sorted(old.keys() | new.keys()):
        if old.get(clip_id) != new.get(clip_id):
            changes.append({"clip_id": clip_id, "before": old.get(clip_id), "after": new.get(clip_id)})
    return {"format": "astel.openreel.corrections.v1", "project_id": before["state"]["project"]["id"], "changes": changes,
            "status": "human-review-required", "learning_promoted": False,
            "scope": "clip details only; motion/text/subtitle full snapshots require a future adapter"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--endpoint-file")
    snap.add_argument("--out", required=True)
    recipe = sub.add_parser("plan")
    recipe.add_argument("plan")
    recipe.add_argument("--media-id", required=True)
    recipe.add_argument("--track-id", required=True)
    recipe.add_argument("--style")
    recipe.add_argument("--out", required=True)
    diff = sub.add_parser("diff")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--out", required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    if args.command == "snapshot":
        result = DesktopMcp(args.endpoint_file).snapshot()
    elif args.command == "plan":
        result = plan_keep_ranges(load(args.plan), media_id=args.media_id, track_id=args.track_id, style=load(args.style) if args.style else None)
    else:
        result = correction_diff(load(args.before), load(args.after))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Artifacts are append-only by filename: never overwrite evidence or RAW.
    with out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
