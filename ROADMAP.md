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

## V0.5 — review / learning loop
- FastAPI review state for renders, detected events, edits and feedback
- canonical feedback grammar: keep / cut / shorter / longer / goal / reaction / bad / more_like_this
- deterministic OLEH_STYLE candidate adaptation from human review
- learning snapshots stored in Supabase; candidates are never auto-promoted
- cold-start / learning / grounded confidence bands at <20 / 20–49 / 50+ examples
- groundwork for watched-folder and Google Drive ingest/output adapters

## V1 — agent workflow
- stable tool surface: analyze_video / create_short / create_variations
- MCP adapter if CLI orchestration is no longer sufficient
- batch queue with job state
- cost/latency report per video
- platform-specific render presets for Shorts / Reels / TikTok

## V0.6 — secure worker queue
- bearer protection for all /v1 mutation/read APIs; /health stays public
- Supabase-backed analyze/create_short job queue
- atomic SKIP LOCKED worker claim RPC
- worker-scoped complete/fail transitions
- reference project/source metadata seeded from Google Drive for the first Battle Box learning set
