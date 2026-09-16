# video-editor

Local-first automation for short-form video editing.

The project is intentionally built as an **orchestrator**, not another giant NLE. It combines deterministic media tooling with optional AI layers so raw footage can become a reviewable rough cut with minimal manual work.

## V0 goal

`RAW -> motion/audio analysis -> keep/cut plan -> FFmpeg render -> JSON report`

The first version is optimized for simple challenge/action footage shot on a mostly static camera. It does **not** try to understand the game yet. That comes in the event-classification layer.

## Why this architecture

A deep search of current open-source video tooling found several useful building blocks, but none matched the full requirement cleanly:

- FFmpeg: final deterministic media engine.
- Auto-Editor: excellent audio/motion first-pass and editor exports; optional reference/adapter, not required by the native pipeline.
- PySceneDetect: scene-boundary detection for footage with actual shot changes.
- AI Video Editor by timkulbaev: useful reference for structured CLI/MCP, VAD/Whisper and Apple Silicon encoding.
- MakeMyClip Editor: strong MIT local/MCP deterministic editing layer.
- unofficial-davinci-mcp: useful Apache-2.0 path for DaVinci workflows, including interchange for Resolve Free.
- SynthCut: impressive AI-native/MCP editor, but GPL-3.0, so we do not merge its source into this project.

See `RESEARCH.md` for the integration decisions.

## Commands planned for V0

```bash
video-editor doctor
video-editor analyze input.mov
video-editor process input.mov -o output.mp4
video-editor batch ./input --output-dir ./output
```

## Local stack

- Python 3.11+
- FFmpeg / ffprobe
- OpenCV + NumPy for lightweight local motion analysis
- optional PySceneDetect
- later: vision event classifier + MCP + DaVinci interchange

## Event grammar planned for V1

```text
READY -> ATTEMPT -> RESULT(FAIL|SCORE) -> REACTION -> RESET
```

The editor will learn these generic events instead of being hard-coded to a specific game.

## Status

Early V0. The current branch under development is `feature/super-tools`.
