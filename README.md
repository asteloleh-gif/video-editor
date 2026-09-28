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


## V0.4 FastAPI + Supabase learning backend

The editor now has an optional API/control-plane layer. The media engine still runs locally or on a worker, while Supabase stores projects, source metadata, semantic events, render history, presets and user feedback.

Install the API extras:

```bash
pip install -e ".[api]"
```

Configure environment variables from `.env.example`:

```text
SUPABASE_URL=https://jlmenuqcxtiwwjfnoupn.supabase.co
SUPABASE_SECRET_KEY=<server-side secret only>
HOST=0.0.0.0
PORT=8000
```

Never expose a Supabase secret/service-role key to a browser or mobile client. It belongs only on the trusted backend/worker.

Run the API:

```bash
video-editor-api
```

Health check:

```text
GET /health
```

Core endpoints:

```text
GET  /v1/presets
POST /v1/projects
GET  /v1/projects/{project_id}
POST /v1/projects/{project_id}/sources
POST /v1/projects/{project_id}/events
POST /v1/projects/{project_id}/renders
POST /v1/projects/{project_id}/feedback
```

A trusted render worker can also expose:

```text
POST /v1/projects/{project_id}/render-local
```

That endpoint is disabled by default. Enable it only on a trusted machine:

```text
VIDEO_EDITOR_ALLOW_LOCAL_RENDER=1
VIDEO_EDITOR_MEDIA_ROOT=/data/battlebox
```

The API rejects render paths outside `VIDEO_EDITOR_MEDIA_ROOT`.

### Learning loop

The intended loop is now:

```text
RAW
 -> Vision events
 -> OLEH_STYLE preset
 -> render
 -> user KEEP/CUT/SHORTER/LONGER feedback
 -> Supabase feedback table
 -> future ranking model: P(user keeps this clip)
```

The initial Supabase schema contains:

```text
projects
source_files
events
presets
renders
edits
feedback
```

The first stored preset is `OLEH_STYLE v1`: 30-second target, speech removed, stronger goal/orange weighting, short reactions, preserved ball travel, impact transitions, goal SFX, and no "ORANGE GOAL" text.

### Railway

`railway.json` is included for the API service. The API itself can deploy before the heavy media worker. FFmpeg/Remotion/Whisper rendering should be deployed as a separate worker or kept on a trusted local machine until the media-runtime image is finalized.

## V0.6 secure worker queue

All `/v1/*` API routes require `Authorization: Bearer $AUTOEDITOR_API_TOKEN`. The public `/health` route remains unauthenticated.

Heavy media work stays off the Railway API container. Queue jobs in Supabase and let a local/remote worker claim them atomically:

- `POST /v1/projects/{project_id}/jobs` — enqueue `analyze` or `create_short`
- `GET /v1/projects/{project_id}/jobs` — inspect queue/history
- `POST /v1/jobs/claim` — atomically claim the next queued job
- `POST /v1/jobs/{job_id}/complete` — complete only as the claiming worker
- `POST /v1/jobs/{job_id}/fail` — fail only as the claiming worker

The claim operation uses PostgreSQL `FOR UPDATE SKIP LOCKED`, so two workers cannot claim the same queued job.

## V0.7 local worker

The heavy media pipeline runs on a machine that owns or syncs the RAW files instead of inside Railway. Configure the worker with `AUTOEDITOR_API_BASE_URL`, `AUTOEDITOR_API_TOKEN`, and `VIDEO_EDITOR_MEDIA_ROOT`, then run:

```bash
video-editor-worker --once
# or keep polling
video-editor-worker
```

Job payload paths are resolved under `VIDEO_EDITOR_MEDIA_ROOT`; path traversal and arbitrary filesystem access are rejected. This makes a Windows desktop, Mac, or later GPU box interchangeable as the render worker while Railway remains the lightweight control plane.
