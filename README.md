# Battle Box AutoEditor

AI-assisted short-form editing for Battle Box challenge footage.

This is an **agentic editing stack**, not a single magic editor. The semantic layer decides what is happening in the game; deterministic media tools execute the edit.

```text
RAW video
  -> OpenAI vision event grammar
       ready / attempt / score / miss / reaction / reset / dead
  -> KEEP planner
  -> FFmpeg clean rough cut
  -> whisper.cpp local transcript
  -> flattened timeline + project JSON
  -> Remotion graphics / captions / reaction zoom
  -> final vertical H.264 MP4
```

Codex / Claude Code can operate the stack through the CLI. See `AGENTS.md` for the editing contract.

## What V0.3 does

- semantic action detection instead of naive sound/motion cuts;
- classifies visible challenge phases and results;
- removes waiting, retrieving items and resets;
- renders a deterministic FFmpeg rough cut;
- transcribes locally with `whisper.cpp`;
- remaps captions and game events through all cuts;
- renders a 1080x1920 Remotion final with:
  - Battle Box brand badge,
  - attempt counter,
  - score counter from clearly detected score events,
  - `GO!`, `SCORE!`, and `MISS` event badges,
  - subtitles,
  - reaction zoom;
- keeps JSON diagnostics for every edit;
- still supports FCPXML handoff to DaVinci Resolve Free.

## One-time Mac setup

From the repository folder:

```bash
bash setup_mac.sh
```

The full setup installs/configures:

- Python 3.11 virtualenv;
- FFmpeg / ffprobe;
- OpenCV + OpenAI Python SDK;
- `whisper.cpp` via Homebrew;
- multilingual Whisper `base` model in `~/.cache/video-editor/whisper/`;
- Node.js;
- the bundled Remotion project.

The OpenAI API key is stored locally at:

```text
~/.config/video-editor/openai_api_key
```

It is never committed to GitHub.

Verify the whole stack:

```bash
source .venv/bin/activate
video-editor doctor --full
```

Low-disk / partial installation options:

```bash
VIDEO_EDITOR_SKIP_WHISPER=1 bash setup_mac.sh
VIDEO_EDITOR_SKIP_REMOTION=1 bash setup_mac.sh
```

The core semantic rough cutter still works without those optional layers.

## Normal use

### Full automatic short

```bash
video-editor create-short RAW.mov -o output/RAW_final.mp4 --open
```

Artifacts:

```text
output/RAW_final.mp4          final styled Short
output/RAW_final_rough.mp4    deterministic clean cut
output/RAW_final_rough.plan.json
output/RAW_final.project.json
```

The two JSON files make the pipeline debuggable instead of opaque.

### Fast action: sample vision more frequently

```bash
video-editor create-short RAW.mov -o output/final.mp4 --vision-step 0.5
```

Default is 1 second to keep API usage controlled.

### Disable layers while debugging

```bash
video-editor create-short RAW.mov -o output/final.mp4 --no-whisper
video-editor create-short RAW.mov -o output/final.mp4 --no-remotion
```

### Analyze without rendering

```bash
video-editor analyze RAW.mov -o output/debug.plan.json
```

### Local Whisper only

```bash
video-editor transcribe RAW.mov -o output/transcript.json
```

### Folder batch

Clean rough cuts:

```bash
video-editor batch input --output-dir output
```

Full styled shorts:

```bash
video-editor batch input --output-dir output --final
```

## Mac drag-and-drop app

After setup:

```bash
bash install_mac_app.sh
```

This creates:

```text
~/Applications/Battle Box AutoEditor.app
```

Open it from Spotlight or drag a RAW video onto the app icon. It runs the same `create-short` pipeline and puts results in the repository `output/` folder.

## How the edit is decided

The vision model receives chronological low-resolution samples and labels ranges with a reusable game grammar:

```text
ready -> attempt -> score/miss -> reaction -> reset -> next attempt
```

Keep-worthy labels:

- `ready`
- `attempt`
- `score`
- `miss`
- `reaction`

Normally removed:

- `reset`
- `dead`

The model is explicitly told not to invent a score or miss when the visible result is ambiguous.

## Final-timeline mapping

After FFmpeg removes source ranges, timestamps change. `timeline.py` maps source time to flattened output time so that:

- semantic event badges land on the correct frame;
- reaction zoom happens after the cut, not at the RAW timestamp;
- Whisper captions remain synchronized after multiple removed sections.

The mapped data is saved in `*.project.json` and passed to Remotion via `--props`.

## Styling

Default preset:

```text
styles/battle_box.json
```

Change colors, caption size, counters, brand text and reaction zoom without changing Python or TypeScript.

Remotion project:

```text
remotion/
  src/Root.tsx
  src/Short.tsx
```

Open Remotion Studio for visual tuning:

```bash
cd remotion
npm run studio
```

## DaVinci Resolve Free bridge

The old editable-timeline path is preserved:

```bash
video-editor process RAW.mov -o output/rough.mp4 --resolve
video-editor resolve RAW.mov -o output/rough.fcpxml --open-resolve
```

The core product does not depend on DaVinci scripting.

## Repo architecture

```text
src/video_editor/
  vision.py             semantic event detection
  pipeline.py           keep planner + JSON edit plan
  render.py             FFmpeg deterministic cut
  transcript.py         local whisper.cpp bridge
  timeline.py           RAW -> flattened timeline mapping
  style.py              style presets
  remotion_bridge.py    Python -> Remotion handoff
  final.py              end-to-end create-short orchestration
  fcpxml.py             optional Resolve Free bridge
  cli.py                user + agent interface

remotion/                programmatic graphics renderer
styles/                  visual presets
assets/                  future SFX / PNG overlays
AGENTS.md                 Codex / Claude Code operating rules
```

## What is intentionally not automated yet

Player-specific scoring is not guessed from appearance. V0.3 only increments the generic score counter when the semantic detector sees a clearly successful result. Named-player/team scores and challenge-specific rules belong in the next Battle Box game-logic layer.

Likewise, viral music selection and copyrighted tracks are not automatically downloaded or embedded.

## Next validation step

Use one real pair:

```text
RAW challenge clip + your manual final cut
```

Compare the AI `keep` intervals against the human edit. Once cuts are consistently correct, tune graphics/SFX rather than changing the semantic core per video.
