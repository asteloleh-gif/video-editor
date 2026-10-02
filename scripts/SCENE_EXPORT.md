# Manual scene library export — no Codex required

Standalone helper: `scripts/export_scenes.py`.
It does not change the existing Battle Box CLI, worker queue, semantic analysis, captions, Remotion, or deployments. There is no new `video-editor export-scenes` subcommand yet: use the Python command below.

## Requirements

Python 3.11+ and FFmpeg/ffprobe on the computer that holds the local video. No model API, API key, Codex, pip dependencies, Whisper, Remotion, or network service is required for this helper. It does not download or upload Drive files.

Use this feature branch in a separate checkout/worktree so an unfinished Mac setup stays untouched. From the existing repository directory:

```bash
git fetch origin feat/manual-scene-export-20261002
git worktree add ../video-editor-scene-export origin/feat/manual-scene-export-20261002
cd ../video-editor-scene-export
```

Do not run the full setup script merely to use this helper. First check `python3 --version`, `ffmpeg -version`, and `ffprobe -version`.

## Input timing map

Use the actual approved timing map. These are SYNTHETIC EXAMPLES, NOT Trailer 2 timings:

```json
{
  "scenes": [
    {"id": "scene_001", "start": "00:00.250", "end": "00:01.250", "description": "Synthetic example only"},
    {"id": "scene_002", "start": 2.125, "end": 3.625, "description": "Synthetic example only"},
    {"id": "scene_003", "start": 4.0, "end": 5.75, "description": "Synthetic example only"}
  ]
}
```

Times are seconds from the beginning of this exact source file, not SMPTE frame notation. Accepted forms: numeric seconds, `MM:SS.mmm`, `HH:MM:SS.mmm`. All scenes are validated even when using `--limit`.

## First run: plan only, no output created

Replace the three example paths with verified paths on the execution computer:

```bash
python3 scripts/export_scenes.py "/path/to/Trailer2.mp4" \
  --timings "/path/to/approved-scenes.json" \
  -o "/path/to/gta-scenes-test" \
  --mode copy --limit 3 --dry-run
```

Remove `--dry-run` to export. The output directory MUST NOT already exist. The helper never overwrites RAW media or an existing export directory. For retry after a failed/interrupted run, inspect `manifest.json` and choose a NEW directory; automatic resume is not implemented.

`--handle 0.25` adds up to 0.25 seconds on each side, clamped to the source boundaries. Default is zero; handles can include neighboring shots, so inspect them before final use.

## Quality and timing

- `--mode copy` (default): separate MKV clips; copies the first real video stream and optional first audio stream without re-encoding. Cut boundaries are not frame-accurate and may include extra material. The manifest does NOT claim an exact core offset. Inspect/decode the output before use. Not all codecs/container combinations or downstream assemblers support MKV: compatibility needs a real-source test.
- `--mode precise`: separate MP4 clips; H.264 CRF 16 + AAC 192k with accurate seek. This IS re-encoding, NOT mathematically lossless. Limited to 8-bit SDR yuv420p/yuvj420p; rejects HDR/other pixel formats rather than silently converting them. No resize/crop filter or forced frame rate is added. Container/frame timestamps still limit timing precision.

Reference: https://ffmpeg.org/ffmpeg.html (stream copy and `-ss` / accurate seeking).

Output includes one clip per scene and `manifest.json` with source identity metadata, requested and export intervals, descriptions, measured clip duration and status. This is a local export manifest, not a synced Drive catalog. Source filename, size and mtime are recorded; no full 14 GB hash scan is performed by the exporter.

## Validation performed

```bash
python3 -m unittest discover -s tests -p test_scene_export_standalone.py -v
```

12 tests passed in the assistant's Linux environment with Python 3.13.5 and FFmpeg 7.1.5. Tests actually exported three synthetic clips in each mode, checked precise-mode durations and dimensions, decoded copy-mode output, checked audio presence, dry-run/no-overwrite behavior, timestamp validation, case-insensitive duplicate IDs, failure reporting, and unchanged synthetic source SHA-256.

NOT yet validated: the user's Mac installation, actual Trailer 2 file/timing map, large-file runtime, Drive upload, or the downstream GTA assembler. No real GTA source was rendered or published as part of this patch.
