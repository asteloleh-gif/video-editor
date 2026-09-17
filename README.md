# video-editor

Local-first automation for short-form video editing.

The project is intentionally built as an **orchestrator**, not another giant NLE. It combines deterministic media tooling with optional AI layers so raw footage can become a reviewable rough cut with minimal manual work.

## V0 goal

`RAW -> motion/audio analysis -> keep/cut plan -> FFmpeg render -> JSON report + DaVinci timeline`

The first version is optimized for simple challenge/action footage shot on a mostly static camera. It does **not** try to understand the game yet. That comes in the event-classification layer.

## Why this architecture

A deep search of current open-source video tooling found several useful building blocks, but none matched the full requirement cleanly:

- FFmpeg: final deterministic media engine.
- Auto-Editor: excellent audio/motion first-pass and editor exports; optional reference/adapter, not required by the native pipeline.
- PySceneDetect: scene-boundary detection for footage with actual shot changes.
- AI Video Editor by timkulbaev: useful reference for structured CLI/MCP, VAD/Whisper and Apple Silicon encoding.
- MakeMyClip Editor: strong MIT local/MCP deterministic editing layer.
- davinci-resolve-mcp-free: proof of the Resolve Free pattern — interchange files + macOS Accessibility instead of Studio scripting.
- unofficial-davinci-mcp: useful Apache-2.0 path for DaVinci workflows, including interchange for Resolve Free.
- SynthCut: impressive AI-native/MCP editor, but GPL-3.0, so we do not merge its source into this project.

See `RESEARCH.md` for the integration decisions.

## Commands

```bash
video-editor doctor
video-editor analyze input.mov
video-editor process input.mov -o output.mp4
video-editor process input.mov -o output.mp4 --resolve
video-editor resolve input.mov -o output.fcpxml --open-resolve
video-editor batch ./input --output-dir ./output --resolve
```

`--resolve` writes an FCPXML 1.9 timeline referencing the original RAW. It is intended for DaVinci Resolve Free, so the rough cut remains editable instead of arriving only as a flattened MP4.

## Mac app

After `setup_mac.sh`, install the no-terminal wrapper:

```bash
bash install_mac_app.sh
```

Then open `Video Editor.app` from Spotlight or drag a RAW video onto it.

Each run creates:

```text
output/<name>_rough.mp4
output/<name>_rough.plan.json
output/<name>_rough.fcpxml
```

The app offers three handoff modes:

- **Show Files** — reveal the rough cut.
- **Open DaVinci** — launch Resolve and reveal the FCPXML.
- **Auto Import** — experimental macOS Accessibility automation: launch Resolve, trigger timeline import, select the generated FCPXML, and accept the import dialog.

`Auto Import` does not use the Studio scripting API. macOS may require Accessibility permission for `Video Editor.app`. If UI automation fails, the FCPXML remains usable through normal Resolve timeline import.

## Local stack

- Python 3.11+
- FFmpeg / ffprobe
- OpenCV + NumPy for lightweight local motion analysis
- FCPXML 1.9 interchange for Resolve Free
- optional macOS Accessibility automation
- later: vision event classifier + MCP

## Event grammar planned for V1

```text
READY -> ATTEMPT -> RESULT(FAIL|SCORE) -> REACTION -> RESET
```

The editor will learn these generic events instead of being hard-coded to a specific game.

## Status

V0 rough-cut core is working. Resolve Free timeline handoff is the current integration layer.
