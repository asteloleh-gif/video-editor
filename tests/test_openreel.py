import json
from copy import deepcopy

import pytest

from video_editor.openreel import DesktopMcp, correction_diff, plan_keep_ranges


def test_recipe_timing_and_rejects_invalid_ranges():
    plan = {"source": {"duration": 10}, "keep": [{"start": 1, "end": 3}, {"start": 5, "end": 8}]}
    recipe = plan_keep_ranges(plan, media_id="m", track_id="t", style={"brand": "ASTEL FAM"})
    assert recipe["source_mapping"][-1]["output_end"] == 5
    assert recipe["calls"][4]["arguments"] == {"clipId": "$clip:1", "inPoint": 5, "outPoint": 8}
    assert recipe["status"] == "review-only"
    for ranges in ([], [{"start": 3, "end": 2}], [{"start": 0, "end": 11}], [{"start": 0, "end": float('nan')}], [{"start": 1, "end": 4}, {"start": 3, "end": 5}]):
        with pytest.raises(ValueError):
            plan_keep_ranges({"source": {"duration": 10}, "keep": ranges}, media_id="m", track_id="t")


def test_correction_keeps_evidence_without_promoting_style():
    before = {"state": {"project": {"id": "p"}}, "clip_details": [{"id": "c", "startTime": 1, "inPoint": 0}]}
    after = deepcopy(before)
    after["clip_details"][0]["inPoint"] = 0.5
    diff = correction_diff(before, after)
    assert len(diff["changes"]) == 1
    assert diff["learning_promoted"] is False
    after["state"]["project"]["id"] = "different"
    with pytest.raises(ValueError):
        correction_diff(before, after)


def test_probe_rejects_remote_endpoint_and_mutations(tmp_path):
    endpoint = tmp_path / 'endpoint.json'
    endpoint.write_text(json.dumps({"url": "http://example.org/mcp", "token": "test"}))
    with pytest.raises(ValueError):
        DesktopMcp(endpoint)
    endpoint.write_text(json.dumps({"url": "http://127.0.0.1:1234/mcp", "token": "test"}))
    probe = DesktopMcp(endpoint)
    with pytest.raises(ValueError):
        probe.rpc("tools/call", {"name": "delete_clip"})


def test_snapshot_paginates_and_omits_token(tmp_path):
    endpoint = tmp_path / 'endpoint.json'
    endpoint.write_text(json.dumps({"url": "http://127.0.0.1:1234/mcp", "token": "never-save-me"}))
    probe = DesktopMcp(endpoint)
    state = {"project": {"id": "p"}}
    def rpc(method, params=None):
        if method == 'tools/list':
            return {"tools": []}
        return {}
    def read(name, **args):
        if name == 'get_editor_state':
            return state
        if name == 'list_clips':
            return [{"id": str(i)} for i in range(100)] if args['offset'] == 0 else [{"id": '100'}]
        if name == 'get_clip':
            return {"id": args['clipId']}
        return []
    probe.rpc, probe.read = rpc, read
    snapshot = probe.snapshot()
    assert len(snapshot['clip_details']) == 101
    assert 'never-save-me' not in json.dumps(snapshot)
