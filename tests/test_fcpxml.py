from xml.etree import ElementTree as ET

from video_editor.fcpxml import write_fcpxml
from video_editor.intervals import Interval
from video_editor.pipeline import EditPlan
from video_editor.probe import MediaInfo


def _plan(tmp_path):
    source = tmp_path / "raw.mov"
    source.write_bytes(b"")
    info = MediaInfo(
        path=str(source),
        duration=12.0,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=True,
    )
    keep = [Interval(1.0, 2.0), Interval(5.0, 7.5)]
    return EditPlan(
        source=info,
        mode="hybrid",
        keep=keep,
        motion_intervals=keep,
        audio_intervals=[],
        motion_samples=[],
        duration_kept=3.5,
        duration_removed=8.5,
        percent_removed=70.83,
    )


def test_write_fcpxml_creates_resolve_timeline(tmp_path):
    output = tmp_path / "rough.fcpxml"
    write_fcpxml(_plan(tmp_path), output)

    text = output.read_text(encoding="utf-8")
    assert '<!DOCTYPE fcpxml>' in text
    root = ET.fromstring(text.split("<!DOCTYPE fcpxml>\n", 1)[1])
    assert root.tag == "fcpxml"
    assert root.attrib["version"] == "1.9"

    format_node = root.find("./resources/format")
    assert format_node is not None
    assert format_node.attrib["width"] == "1080"
    assert format_node.attrib["height"] == "1920"
    assert format_node.attrib["frameDuration"] == "1/30s"

    clips = root.findall("./library/event/project/sequence/spine/asset-clip")
    assert len(clips) == 2
    assert clips[0].attrib["offset"] == "0s"
    assert clips[0].attrib["start"] == "1s"
    assert clips[0].attrib["duration"] == "1s"
    assert clips[1].attrib["offset"] == "1s"
    assert clips[1].attrib["start"] == "5s"
    assert clips[1].attrib["duration"] == "5/2s"
