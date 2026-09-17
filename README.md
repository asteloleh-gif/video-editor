# video-editor

AI-assisted automation for Battle Box / short-form challenge video.

The project is an **orchestrator**, not another NLE. FFmpeg remains the deterministic renderer; the semantic layer decides what gameplay is worth keeping.

## V1 pipeline

```text
RAW video
  -> sample chronological frames
  -> GPT vision event detection
  -> KEEP intervals (attempt/result/reaction)
  -> deterministic padding + merge
  -> FFmpeg render
  -> MP4 + JSON edit plan
```

The old motion/audio detector is still available as a fallback, but it is no longer the default because motion and sound alone cannot understand whether a person is actually playing, resetting cups, retrieving a ball, or simply standing in frame.

## What vision mode keeps

The semantic prompt is tuned for fixed-camera physical challenge footage.

**Keep:** final preparation immediately before an attempt, gameplay/throws, immediate result, short reaction.

**Cut:** waiting, walking into position, long hesitation, retrieving items, rebuilding/resetting props, camera adjustment, empty scene and unrelated setup.

The default model is `gpt-5.6-luna`, using low-detail sampled frames. The default sample interval is 1 second. For a harder clip, use `--vision-step 0.5`.

## Setup on Mac

```bash
git pull
bash setup_mac.sh
```

`setup_mac.sh` installs the Python/OpenAI dependencies and, if needed, asks once for `OPENAI_API_KEY`. The key is stored locally at:

```text
~/.config/video-editor/openai_api_key
```

It is not stored in the repository.

Check the installation:

```bash
source .venv/bin/activate
video-editor doctor
```

## Commands

Vision is now the default:

```bash
video-editor analyze input.mov
video-editor process input.mov -o output.mp4
```

More temporal precision:

```bash
video-editor process input.mov -o output.mp4 --vision-step 0.5
```

Legacy detector for comparison:

```bash
video-editor process input.mov -o output.mp4 --mode hybrid
```

DaVinci/FCPXML remains available when an editable timeline is actually needed:

```bash
video-editor process input.mov -o output.mp4 --resolve
video-editor resolve input.mov -o output.fcpxml --open-resolve
```

## Mac app

After setup:

```bash
bash install_mac_app.sh
```

Then open `Video Editor.app` from Spotlight or drag a RAW video onto it. The app now runs the semantic AI cut directly and creates:

```text
output/<name>_rough.mp4
output/<name>_rough.plan.json
```

DaVinci is no longer part of the normal app workflow. The finished rough cut can be reviewed or sent to a mobile editor for text/music/graphics.

## Edit-plan diagnostics

Every render gets a JSON plan. Vision plans include:

- final `keep` intervals;
- raw `vision_intervals`;
- model detections with confidence;
- one short semantic summary per analyzed batch;
- total duration kept/removed.

This makes the next tuning cycle measurable: compare the AI intervals with a human edit instead of guessing at motion thresholds.

## Local stack

- Python 3.11+
- FFmpeg / ffprobe
- OpenCV for deterministic frame sampling
- OpenAI Responses API for semantic vision classification
- JSON edit plan for debugging and evaluation
- optional FCPXML 1.9 handoff to DaVinci Resolve Free

## Status

**V1 semantic detector implemented.** The next validation target is one RAW Battle Box clip plus the user's manual cut as ground truth. We compare timestamps, then tune sampling/prompt/padding before building the iPhone -> Mac -> iPhone handoff.
