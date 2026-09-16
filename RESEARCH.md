# Deep-search notes — 2026-09-16

This document records the open-source tools reviewed before building the first pipeline.

## Selected building blocks

### FFmpeg / ffprobe
Role: deterministic decode, trim, concat, encode, audio analysis, metadata.
Decision: core runtime dependency.

### OpenCV + NumPy
Role: lightweight frame-difference motion scoring on downscaled frames.
Decision: core V0 analysis path. It avoids tying basic rough-cut logic to a third-party editor binary and works with high-resolution source footage because analysis is downscaled while rendering stays in FFmpeg.

### PySceneDetect
License: BSD-3-Clause.
Role: detect actual shot changes, fades, and content transitions.
Decision: optional adapter. Useful when footage contains cuts/camera changes; not a replacement for motion detection in a static-camera challenge.

### WyattBlue/auto-editor
Source license: Unlicense/public domain. Current tool supports audio/motion expressions and DaVinci Resolve export.
Decision: useful optional adapter/reference. Do not make the native pipeline depend on it. Recent binary releases have rendering/licensing constraints at some high resolutions and multi-source configurations, so the native path renders through FFmpeg directly.

### timkulbaev/ai-video-editor
License: MIT.
Role: good reference architecture for local CLI processing, structured JSON output, Silero VAD, faster-whisper, MCP, and Apple Silicon VideoToolbox encoding.
Decision: borrow architectural ideas, not a hard dependency. Its editing model is speech/talking-head oriented, while this project needs action/event footage.

### MakeMyClip/editor
License: MIT for editor source; bundled FFmpeg is separate GPL binary.
Role: deterministic FFmpeg operations exposed through typed tools/MCP, session log, undo/snapshots.
Decision: strong candidate for a future optional MCP editing backend instead of rebuilding dozens of generic editing operations.

### wassermanproductions/unofficial-davinci-mcp
License: Apache-2.0 with NOTICE/attribution requirements.
Role: DaVinci Resolve automation. Live scripting requires Studio; interchange/FCPXML workflows can support Resolve Free.
Decision: candidate final-review bridge. If code is copied or redistributed, preserve Apache NOTICE/attribution. Prefer invoking/integrating as a separate adapter.

### Relo-video/SynthCut
License: GPL-3.0-or-later.
Role: broad AI-native editor/MCP with many tools.
Decision: research/reference only for this repository. Do not merge its source into the core because that would change redistribution obligations for a derivative work.

### montage-ai / other long-to-shorts projects
Role: useful reference for OTIO/EDL, captions, reframing, beat workflows.
Decision: not required for V0. Most are optimized for dialogue/podcast footage rather than simple family/action challenges.

## Resulting architecture

```text
RAW MEDIA
  |
  +--> ffprobe metadata
  +--> OpenCV motion score (downscaled)
  +--> FFmpeg audio activity
  +--> optional scene boundaries
              |
              v
        interval planner
              |
              v
        JSON edit plan
          /       \
         v         v
   FFmpeg render   future Resolve/FCPXML adapter
         |
         v
     rough cut
```

## Next intelligence layer

The video-specific classifier should use a generic event grammar:

`READY -> ATTEMPT -> FAIL/SCORE -> REACTION -> RESET -> NEXT_ATTEMPT`

This avoids training separate logic for cup toss, bottle flip, card slide, etc.
