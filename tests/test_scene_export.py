"""Isolated scene-export tests; FFmpeg tests use tiny synthetic footage only."""
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_scenes.py"
spec = importlib.util.spec_from_file_location("scene_export", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def plan(rows=None):
    return {"schema_version": 1, "source_id": "synthetic",
            "scenes": rows if rows is not None else [
                {"id": "s01", "start": "00:01.300", "end": "00:02.300", "description": "test one"},
                {"id": "s02", "start": 3, "end": 4.5, "description": "test two"},
                {"id": "s03", "start": 5, "end": 6.2, "description": "test three"},
            ]}


@pytest.mark.parametrize("value,expected", [(0, 0), (1.5, 1.5), ("12.125", 12.125),
    ("01:02.25", 62.25), ("01:02:03.5", 3723.5), ("90:00", 5400)])
def test_times(value, expected):
    assert module.seconds(value) == expected


@pytest.mark.parametrize("value", [True, None, [], -1, float("nan"), float("inf"),
    "-01:02", "00:60", "01:60:00", "01:02:03:04", "00:NaN", "bad"])
def test_invalid_times(value):
    with pytest.raises((ValueError, TypeError)):
        module.seconds(value)


def test_handles_clamped_without_merging_overlaps():
    data = plan([{"id": "a", "start": 0, "end": 2}, {"id": "b", "start": 1, "end": 4}])
    source_id, rows = module.validate_plan(data, 4, 1)
    assert source_id == "synthetic"
    assert len(rows) == 2
    assert rows[0]["export_start_sec"] == 0
    assert rows[1]["export_end_sec"] == 4


@pytest.mark.parametrize("rows", [[], [{"id": "../escape", "start": 0, "end": 1}],
    [{"id": "a", "start": 2, "end": 1}], [{"id": "a", "start": 1, "end": 8}],
    [{"id": "a", "start": 1, "end": 2}, {"id": "A", "start": 2, "end": 3}],
    [{"id": "a", "start": 1, "end": 2, "description": 3}]])
def test_bad_plans(rows):
    with pytest.raises(ValueError):
        module.validate_plan(plan(rows), 7, 0)


@pytest.mark.parametrize("video", [{"pix_fmt": "yuv420p10le"},
    {"pix_fmt": "yuv420p", "color_transfer": "smpte2084"},
    {"pix_fmt": "yuv420p", "color_primaries": "bt2020"},
    {"pix_fmt": "yuv420p", "side_data_list": [{"rotation": 90}]}])
def test_no_silent_quality_conversion(video):
    with pytest.raises(ValueError):
        module.check_exact_source({"video": video})


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/ffprobe not installed")
    source = tmp_path / "source with spaces.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=10:duration=7",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=7",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "50", "-keyint_min", "50", "-sc_threshold", "0",
        "-c:a", "aac", "-shortest", str(source)], check=True, capture_output=True, timeout=30)
    timing = tmp_path / "timings.json"
    timing.write_text(json.dumps(plan()), encoding="utf-8")
    return source, timing


def decode(path):
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
                   check=True, capture_output=True, timeout=30)


def test_exact_three_clips_audio_manifest_and_source_untouched(media, tmp_path):
    source, timing = media
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    out = tmp_path / "clips exact"
    result = module.export(source, timing, out, mode="exact")
    assert result["status"] == "complete"
    assert len(result["scenes"]) == 3
    for row, expected in zip(result["scenes"], [1, 1.5, 1.2]):
        clip = out / row["file"]
        metadata = module.probe(clip)
        assert metadata["duration_sec"] == pytest.approx(expected, abs=0.10)
        assert metadata["audio"] is not None
        assert metadata["video"]["width"] == 160
        assert metadata["video"]["height"] == 90
        decode(clip)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert json.loads((out / "manifest.json").read_text())["status"] == "complete"
    assert not list(out.glob("*.partial.*"))
    concat = tmp_path / "concat.txt"
    concat.write_text("".join(f"file '{(out / row['file']).as_posix()}'\n" for row in result["scenes"]))
    assembled = tmp_path / "assembled.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c", "copy", str(assembled)], check=True, capture_output=True, timeout=30)
    decode(assembled)
    assert module.probe(assembled)["duration_sec"] == pytest.approx(3.7, abs=0.2)


def packet_hashes(path):
    data = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_packets", "-show_data_hash", "sha256", "-show_entries", "packet=data_hash",
        "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=30).stdout)
    return [p["data_hash"] for p in data["packets"]]


def test_copy_packets_preserved_and_timing_labelled_approximate(media, tmp_path):
    source, timing = media
    out = tmp_path / "copy"
    result = module.export(source, timing, out, mode="copy", limit=1)
    assert result["timing"] == "approximate_keyframe_seek"
    clip = out / result["scenes"][0]["file"]
    assert set(packet_hashes(clip)).issubset(set(packet_hashes(source)))
    decode(clip)


def test_silent_source(media, tmp_path):
    source, timing = media
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0", "-c", "copy", str(silent)],
                   check=True, capture_output=True, timeout=30)
    out = tmp_path / "silent clips"
    result = module.export(silent, timing, out, mode="exact", limit=1)
    assert module.probe(out / result["scenes"][0]["file"])["audio"] is None
    decode(out / result["scenes"][0]["file"])


def test_dry_run_no_files_and_output_protected(media, tmp_path):
    source, timing = media
    out = tmp_path / "dry"
    result = module.export(source, timing, out, mode="exact", dry_run=True, limit=1)
    assert result["status"] == "planned"
    assert not out.exists()
    out.mkdir()
    marker = out / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="already exists"):
        module.export(source, timing, out, mode="exact")
    assert marker.read_text() == "keep"


def test_wrong_source_rejected_before_writing(media, tmp_path):
    source, timing = media
    data = plan()
    data["source_filename"] = "wrong.mp4"
    timing.write_text(json.dumps(data))
    out = tmp_path / "wrong"
    with pytest.raises(ValueError, match="does not match"):
        module.export(source, timing, out, mode="exact")
    assert not out.exists()


def test_failed_job_has_manifest_and_no_partial_file(media, tmp_path, monkeypatch):
    source, timing = media
    original = module.run
    def fail(command, timeout):
        if command[0] == "ffmpeg":
            Path(command[-1]).write_bytes(b"partial")
            raise RuntimeError("simulated encoder failure")
        return original(command, timeout)
    monkeypatch.setattr(module, "run", fail)
    out = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="simulated"):
        module.export(source, timing, out, mode="exact")
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["scenes"][0]["status"] == "failed"
    assert manifest["scenes"][1]["status"] == "pending"
    assert not list(out.glob("*.partial.*"))
