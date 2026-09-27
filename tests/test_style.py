import json

from video_editor.style import load_style


def test_load_style_deep_merges_defaults(tmp_path):
    path = tmp_path / "style.json"
    path.write_text(json.dumps({"accent": "#123456", "caption": {"font_size": 70}}), encoding="utf-8")
    style = load_style(path)
    assert style["accent"] == "#123456"
    assert style["caption"]["font_size"] == 70
    assert style["caption"]["enabled"] is True
