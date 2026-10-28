import json
from unittest.mock import Mock
import pytest
from video_editor.video_search import normalize, search, validate


def entry(key="QdBZY2fkU-0", **kw):
    return {"id": key, "title": "Example", "channel": "Channel", "duration": 91, "view_count": 123, **kw}


@pytest.mark.parametrize("bad", [{"query": ""}, {"query": 123}, {"query": "a"*201}, {"query": "x\ny"}, {"query": "x", "limit": True}, {"query": "x", "limit": 1000}, {"query": "x", "order": "random"}, {"query": "x", "url": "https://example.org"}])
def test_invalid_requests(bad):
    with pytest.raises(ValueError): validate(bad)


def test_normalization_deduplicates_and_builds_canonical_urls():
    rows = normalize([None, {}, entry(url="file:///private", thumbnail="javascript:bad"), entry(), entry("../x"), entry("tJbzMqJGH4k", duration=float("nan"), view_count=True)], 100)
    assert len(rows) == 2
    assert rows[0]["url"] == "https://www.youtube.com/watch?v=QdBZY2fkU-0"
    assert rows[0]["thumbnail"].startswith("https://i.ytimg.com/")
    assert rows[1]["duration"] is None and rows[1]["views"] is None


def fake(entries):
    context = Mock()
    context.__enter__ = Mock(return_value=context)
    context.__exit__ = Mock(return_value=False)
    context.extract_info.return_value = {"entries": entries}
    return Mock(return_value=context), context


def test_cache_avoids_another_network_search(tmp_path):
    factory, engine = fake([entry()])
    req = {"query": "GTA", "limit": 10}
    first = search(req, home=tmp_path, factory=factory, clock=lambda: 1000)
    second = search(req, home=tmp_path, factory=factory, clock=lambda: 1001)
    assert first["results"] == second["results"]
    assert not first["from_cache"] and second["from_cache"]
    factory.assert_called_once()
    engine.extract_info.assert_called_once_with("ytsearch10:GTA", download=False)
    assert factory.call_args.args[0]["skip_download"] is True
    assert factory.call_args.args[0]["extract_flat"] == "in_playlist"


def test_expiry_and_order_have_independent_searches(tmp_path):
    factory, engine = fake([entry()])
    search({"query": "GTA", "limit": 10}, home=tmp_path, factory=factory, clock=lambda: 1000)
    search({"query": "GTA", "limit": 10}, home=tmp_path, factory=factory, clock=lambda: 1400)
    search({"query": "GTA", "limit": 10, "order": "date"}, home=tmp_path, factory=factory, clock=lambda: 1401)
    assert factory.call_count == 3
    engine.extract_info.assert_called_with("https://www.youtube.com/results?search_query=GTA&sp=CAISAhAB", download=False)


def test_empty_results_not_cached_and_limits_enforced(tmp_path):
    factory, _ = fake([])
    for _ in range(2):search({"query": "GTA", "limit": 10}, home=tmp_path, factory=factory)
    assert factory.call_count == 2
    assert len(normalize([entry(f"abcdefgh{i:03}") for i in range(100)],10)) == 10
