# Roadmap

## V0.1 — native rough cut
- ffprobe inspection
- OpenCV motion activity
- FFmpeg audio activity
- interval planner
- FFmpeg render
- JSON edit plan
- batch mode

## V0.2 — semantic vision rough cut
- chronological sampled frames
- OpenAI semantic keep ranges
- diagnostics and confidence
- FCPXML/Resolve Free bridge

## V0.3 — Battle Box AutoEditor
- reusable game event grammar: ready / attempt / score / miss / reaction / reset / dead
- FFmpeg rough cut remains source of truth
- local whisper.cpp transcription
- RAW -> flattened timeline mapping
- Remotion vertical renderer
- captions, event badges, generic score/attempt counters, reaction zoom
- drag-and-drop Mac app
- Codex / Claude Code operating contract in AGENTS.md

## V0.4 — challenge-aware game logic
- participant identity supplied from session metadata, not guessed from faces
- per-player/team score rules
- challenge-type presets
- SFX / PNG asset cues
- automatic replay / slow-motion cue for selected score events
- edit-quality comparison against RAW -> FINAL ground truth pairs

## V0.5 — ingest / review loop
- watched input folder
- optional Google Drive ingest/output adapter
- lightweight review UI: keep / delete / restore
- feedback dataset from approved edits

## V1 — agent workflow
- stable tool surface: analyze_video / create_short / create_variations
- MCP adapter if CLI orchestration is no longer sufficient
- batch queue with job state
- cost/latency report per video
- platform-specific render presets for Shorts / Reels / TikTok
