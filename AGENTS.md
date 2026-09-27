# Battle Box AutoEditor — agent instructions

This repository is the deterministic editing engine for Battle Box short-form challenge videos.

## Goal

Turn RAW challenge footage into a reviewable vertical Short without manually opening an NLE:

`RAW -> semantic vision events -> keep ranges -> FFmpeg rough cut -> local Whisper -> Remotion graphics -> final MP4`

The AI model decides **what happened**. FFmpeg and Remotion perform deterministic media operations.

## Default command

```bash
source .venv/bin/activate
video-editor doctor --full
video-editor create-short /path/to/raw.mov -o output/final.mp4 --open
```

For action that happens between the 1-second samples, retry with:

```bash
video-editor create-short raw.mov -o output/final.mp4 --vision-step 0.5
```

## Important editing rules

- Never modify or overwrite RAW media.
- Keep the attempt, visible result, and immediate reaction.
- Cut waiting, retrieving items, rebuilding/resetting props, camera adjustment, and unrelated setup.
- Do not invent a `score` or `miss` when the result is not visibly clear.
- `*.plan.json` is the semantic cut record; `*.project.json` is the flattened final-timeline record.
- Tune analysis parameters before adding hard-coded per-video timestamps.
- Prefer reusable rules over one-off edits.

## Event grammar

`ready -> attempt -> score/miss -> reaction -> reset -> next attempt`

`ready`, `attempt`, `score`, `miss`, and short `reaction` events are keep-worthy.
`reset` and `dead` are diagnostics and should normally be cut.

## Tools

- OpenAI vision: event semantics and result classification.
- FFmpeg/ffprobe: trim, concat, encode, metadata and audio extraction.
- whisper.cpp: local transcription; no source audio is uploaded for captions.
- Remotion: deterministic vertical graphics, counters, badges, captions and reaction zoom.
- FCPXML: optional DaVinci Resolve Free handoff.

## Debugging order

1. `video-editor doctor --full`
2. `video-editor analyze RAW -o output/debug.plan.json --vision-step 0.5`
3. Inspect `vision_detections` and `keep` before changing renderer code.
4. If cuts are right but graphics are wrong, inspect `*.project.json`.
5. If Remotion fails, rerun with `--no-remotion`; this isolates semantic/FFmpeg problems.
6. If Whisper fails, rerun with `--no-whisper`; captions are not allowed to block the core edit.

## Cost discipline

Use 1.0-second vision sampling by default. Use 0.5 seconds only for fast action or failed detections. Local Whisper and local rendering do not consume model API tokens.
