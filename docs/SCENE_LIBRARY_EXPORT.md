# Scene library export (local, deterministic)

Export one local source into separate clips using an approved list of timings.
This is an additive standalone command, not a replacement for `create-short`.
Existing editor modules, AI analysis, Whisper, Remotion, worker, API and deployment
configuration are unchanged. No model/API calls or uploads are made by this script.

## Requirements

Python 3.11+ (matching the repository), FFmpeg and ffprobe on PATH.
The exact mode requires the `libx264` encoder. This standalone command does not
require installing the project's Python dependencies or configuring API keys.

Run from the checkout root of the feature branch, or the root of the standalone
bundle. It is also possible to run `export_scenes.py` directly using its full path.
Do not reset, stash, overwrite or switch an existing dirty Mac checkout blindly.

## Timings

JSON is an object with `schema_version: 1`, `source_id` and a nonempty `scenes`
array. Each scene has `id`, `start`, `end` and optional `description`.
The optional `source_filename` must match the selected source basename exactly.
IDs allow 1-64 ASCII letters/digits/underscores/hyphens, starting with a letter or
digit. Scene IDs must be unique ignoring case. Ranges may overlap and are not
merged. Times use seconds, MM:SS.sss or HH:MM:SS.sss, NOT SMPTE frame timecodes.
Time zero is the input's playback start; use the same source/version as the map.

`examples/scene_export.synthetic.json` is only a synthetic demonstration. Its
numbers are NOT GTA Trailer 2 timings. Do not relabel them as approved GTA scenes.
For real footage, use the existing verified timing map and correct source ID.

## First three scenes

The following paths are placeholders; use actual local input/timing file paths.
The output directory must be NEW, including for dry-run.

```bash
python3 scripts/export_scenes.py "/path/to/source.mp4" "/path/to/approved-scenes.json" \
  --output-dir "output/scenes-test-01" --mode exact --limit 3 --dry-run

# After reviewing the plan, run the same command without --dry-run:
python3 scripts/export_scenes.py "/path/to/source.mp4" "/path/to/approved-scenes.json" \
  --output-dir "output/scenes-test-01" --mode exact --limit 3
```

`--limit` defaults to 3. Only `--limit 0` explicitly selects the entire timing map.
`--handles 0.3` adds 0.3 seconds on each edge, clipped to source bounds. The
original requested bounds and padded export bounds are both kept in the manifest.
`--timeout 1800` is the per-scene process timeout, not a runtime estimate.

## Quality modes (explicit choice required)

- `--mode exact`: seek and re-encode H.264 CRF 16 / AAC 192k into MP4. No scale or
  FPS override; cuts are quantized to available frames/audio samples. This is
  NOT mathematically lossless. This first version only accepts unrotated,
  non-HDR 8-bit planar YUV. HDR, wide-gamut, high-bit-depth, other pixel formats
  and rotated sources are rejected rather than silently converted.
- `--mode copy`: copy the chosen video and first audio stream without
  re-encoding. Keeps the input container extension when supported, otherwise
  uses MKV. Arbitrary codecs/container combinations still require testing.
  Seek can retain content from an earlier keyframe and the end/duration may
  differ too. The manifest explicitly marks timing as approximate and does not
  claim the requested timestamps are measured actual clip boundaries.
  Preview each copied clip; it may require trimming at final assembly.

FFmpeg's documented seek/stream-copy behavior:
https://ffmpeg.org/ffmpeg.html (the `-ss` and `-accurate_seek` options).
This version does not provide exact lossless/HDR transcoding or smart rendering.
Copy mode is not a promise that every container retains every metadata field.
Only one video stream and the first audio stream are exported; other tracks,
subtitles, chapters and data streams are not part of this library export.

## Output and safety

Every scene produces `SOURCE_ID__SCENE_ID.mp4` (or the copy-mode extension), plus
one `manifest.json` with descriptions, requested/export ranges, source metadata,
observed output durations, file sizes and per-scene status. The source identity
uses size/mtime, not a full-file cryptographic hash. Keep the original media.

The script refuses an existing output directory; it never overwrites RAW or an
existing library. Progress is written after each scene. On handled errors/Ctrl-C,
completed clips remain, the failed partial clip is removed, and the manifest
records the failure/interruption. A hard kill or power loss can leave a partial
file; do not treat it as complete. Automatic resume is not implemented: inspect
the manifest and export remaining IDs into another new folder.

Do not upload an incomplete manifest as a finished library. After local preview,
upload the completed clips and manifest together to the intended project's Drive.
Drive upload and downstream library selection/assembly are not wired into this
script. The script does not access Drive, YouTube, cloud workers or model APIs.

## Reproducible synthetic check

```bash
ffmpeg -f lavfi -i "testsrc2=size=160x90:rate=10:duration=7" \
  -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=7" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest -n synthetic.mp4
python3 scripts/export_scenes.py synthetic.mp4 examples/scene_export.synthetic.json \
  --output-dir output/synthetic-test-01 --mode exact --limit 3
python3 -m pytest -q tests/test_scene_export.py
```

Development verification on 2026-10-02: **35 tests passed** in the assistant's
Linux container using Python 3.13.5 and FFmpeg 7.1.5. Tests exercise validation,
three-scene exact export, audio/no-audio, decoding all generated clips,
reassembly, SHA-256 source immutability, video packet-hash preservation in copy
mode, dry-run, overwrite refusal, source-name checking and simulated failure.
These are isolated tests of the new command, NOT the full existing app suite.
Mac execution, real GTA timings/media, large-source performance, HDR metadata
retention and the Drive round trip have NOT been verified in this change.
