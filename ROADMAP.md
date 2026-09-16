# Roadmap

## V0.1 — native rough cut
- ffprobe inspection
- OpenCV motion activity
- FFmpeg audio activity
- interval planner
- FFmpeg render
- JSON edit plan
- batch mode

## V0.2 — candidate events
- optional PySceneDetect boundaries
- contact sheets/keyframes
- event candidate windows
- preview mode without render
- better per-camera motion normalization

## V0.3 — action grammar
Classify candidate windows as:
- READY
- ATTEMPT
- FAIL
- SCORE
- REACTION
- RESET
- DEAD

## V0.4 — final-editor bridge
- FCPXML/Resolve interchange for Resolve Free
- optional DaVinci MCP adapter for Studio
- markers for event labels/confidence

## V0.5 — dataset/feedback
- ingest finished Shorts as positive style examples
- new RAW -> FINAL pairs
- capture restored/deleted AI cuts as feedback
- retention metadata import when available

## V1 — agent workflow
- MCP server
- `analyze_video`
- `process_video`
- `create_short`
- `create_variations`
- batch folder watch
