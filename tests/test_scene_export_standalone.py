"""Standalone scene exporter: unit tests and real FFmpeg smoke tests."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_scenes.py"
spec = importlib.util.spec_from_file_location("scene_export", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TimingTests(unittest.TestCase):
    def test_time_formats(self):
        for value, expected in [(1.25, 1.25), ("1.25", 1.25), ("01:02.500", 62.5), ("01:02:03.5", 3723.5)]:
            self.assertEqual(module.seconds(value), expected)

    def test_invalid_time_formats(self):
        for value in [True, None, "NaN", "inf", -1, "00:60", "00:99:00", "00:01:02:03", "-1:05", {}]:
            with self.subTest(value=value), self.assertRaises(module.ExportError):
                module.seconds(value)

    def test_duplicate_and_unsafe_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenes.json"
            for rows in [
                [{"id": "../escape", "start": 0, "end": 1}],
                [{"id": "A", "start": 0, "end": 1}, {"id": "a", "start": 1, "end": 2}],
            ]:
                path.write_text(json.dumps(rows))
                with self.assertRaises(module.ExportError):
                    module.read_scenes(path, 6, 0)

    def test_bad_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenes.json"
            for start, end in [(2, 1), (1, 1), (0, 7), (-1, 2)]:
                path.write_text(json.dumps([{"id": "A", "start": start, "end": end}]))
                with self.assertRaises(module.ExportError):
                    module.read_scenes(path, 6, 0)

    def test_handles_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenes.json"
            path.write_text(json.dumps([{"id": "A", "start": 0.1, "end": 5.9}]))
            scene = module.read_scenes(path, 6, 1)[0]
            self.assertEqual((scene["export_start_sec"], scene["export_end_sec"]), (0, 6))

    def test_commands_no_shell_overwrite_or_ai(self):
        scene = {"export_start_sec": 1.25, "export_end_sec": 2.75}
        command = module.command_for(Path("name with spaces.mp4"), Path("out.mkv"), scene, "copy")
        self.assertIn("-n", command)
        self.assertIn("copy", command)
        self.assertEqual(command[command.index("-t") + 1], "1.500000000")
        self.assertIn("name with spaces.mp4", command)
        self.assertNotIn("-y", command)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ExportSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "synthetic input.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24:duration=6",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=6",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "24", "-c:a", "aac", "-shortest", str(cls.source)],
                       check=True, capture_output=True, timeout=30)
        cls.rows = [{"id": f"scene_{i+1:03d}", "start": a, "end": b, "description": "Synthetic test only"}
                    for i, (a, b) in enumerate([(0.25, 1.25), (2.125, 3.625), (4, 5.75)])]
        cls.timings = cls.root / "synthetic.scenes.json"
        cls.timings.write_text(json.dumps({"scenes": cls.rows}))
        cls.original_hash = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        assert hashlib.sha256(cls.source.read_bytes()).hexdigest() == cls.original_hash
        cls.temp.cleanup()

    def test_dry_run_no_files(self):
        target = self.root / "dry"
        result = module.export(self.source, self.timings, target, dry_run=True)
        self.assertEqual(result["status"], "planned")
        self.assertEqual(len(result["scenes"]), 3)
        self.assertFalse(target.exists())

    def test_precise_three_clips_and_durations(self):
        target = self.root / "precise"
        result = module.export(self.source, self.timings, target, mode="precise")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(list(target.glob("*.mp4"))), 3)
        for row, scene in zip(self.rows, result["scenes"]):
            self.assertAlmostEqual(scene["actual_duration_sec"], row["end"] - row["start"], delta=1/24 + .01)
            info = module.probe(target / scene["file"])
            self.assertEqual((info["video"]["width"], info["video"]["height"]), (160, 90))
            self.assertTrue(info["has_audio"])
        self.assertEqual(json.loads((target / "manifest.json").read_text())["status"], "complete")

    def test_copy_first_three_clips(self):
        target = self.root / "copy"
        result = module.export(self.source, self.timings, target, mode="copy", limit=3)
        self.assertEqual(len(list(target.glob("*.mkv"))), 3)
        for scene in result["scenes"]:
            self.assertEqual(scene["status"], "complete")
            self.assertNotIn("core_offset_sec", scene)
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(target / scene["file"]),
                            "-f", "null", "-"], capture_output=True, check=True, timeout=30)

    def test_existing_directory_refused(self):
        target = self.root / "existing"
        target.mkdir()
        marker = target / "do-not-touch.txt"
        marker.write_text("original")
        with self.assertRaises(FileExistsError):
            module.export(self.source, self.timings, target)
        self.assertEqual(marker.read_text(), "original")
        self.assertEqual(len(list(target.iterdir())), 1)

    def test_failure_manifest(self):
        target = self.root / "failure"
        # Probe still reads the real source; only the encoding step is made to fail.
        real_run = module.run
        def fail_encode(command, timeout):
            if command[0] == "ffmpeg":
                raise module.ExportError("Synthetic encode failure")
            return real_run(command, timeout)
        with patch.object(module, "run", side_effect=fail_encode), self.assertRaises(module.ExportError):
            module.export(self.source, self.timings, target)
        result = json.loads((target / "manifest.json").read_text())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["scenes"][0]["status"], "failed")
        self.assertFalse(list(target.glob("*.mkv")))

    def test_limit(self):
        result = module.export(self.source, self.timings, self.root / "limit", limit=1, dry_run=True)
        self.assertEqual(len(result["scenes"]), 1)


if __name__ == "__main__":
    unittest.main()
