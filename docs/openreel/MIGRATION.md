# Astel × OpenReel: audited migration, 2026-10-06

OpenReel is a **candidate editor core**, not an activated replacement. The integration branch keeps the current editor, media engine, API, workers, Remotion, learning tables, and OpenCut experiments. No production deployment, publishing configuration, YouTube upload, or Supabase mutation is part of this migration.

## Provenance and safe repository structure

- Astel default `main`: `275bc4c` (V0.7 local/remote worker).
- Integration base: `origin/feat/opencut-kevin-live-editor`, `6d0877a1a86ac04991d0521eb1990d9d8777e017` (2026-10-05). This branch includes the AstelFam visual stack and browser editor missing from main.
- Integration branch: `integration/openreel-mac-first`.
- OpenReel full clone, pinned submodule `vendor/openreel`: `c9340465e5d37e684cc25bdbe746c4ccd45e165c` (2026-10-03).
- No unrelated-history merge. Both clones retain full Git history and upstream remote branches. `ASTEL-REFS.txt` records Astel branch tips; `UPSTREAM-HISTORY.txt` records recent upstream history.
- Upstream latest release at audit: `v1.0.0-alpha.17`, published 2026-08-29. Release binaries predate the audited source; do not assume the release contains this source's exact tools.
- Submodule branch `integration/astel-core-candidate` points to unchanged upstream source. Astel integration lives outside it, so future upstream upgrades do not overwrite our layer.

```text
Astel agent/style/learning layer
  src/video_editor/vision.py, pipeline.py, learning.py, style.py
  styles/ + remotion/ + worker.py + API/control plane
                 |
        src/video_editor/openreel.py
        KEEP recipe / media identity / correction evidence
                 |
  integration/openreel/execute-recipe.ts (isolated headless clone)
                 |                        |
       OpenReel project + tools       Mac Desktop MCP
                                      same live UI project

Fallback / A/B baseline: editor/, FFmpeg + Remotion, OpenCut experiments
Stage 2 only: Kevin / Windows worker with machine-local media mappings
```

## Inventory and migration map

| Component / evidence | Decision | OpenReel overlap and work to preserve |
|---|---|---|
| `styles/astelfam.json`, `remotion/src/AstelFamShort.tsx`, visual `restyle` path | KEEP + PORT | Brand colors, emoji reactions, counters and timing are Astel-specific behavior. Motion Creator offers primitives, not these exact compositions. Keep external Remotion rendering until visual parity; port selected graphics as editable motion layers later. |
| `remotion_bridge.py`, `final.py`, `timeline.py`, both Remotion compositions | KEEP | Deterministic graphics and source-to-output remapping remain usable. OpenReel does not execute Remotion JSX. Import rendered assets separately; do not claim a style sidecar applies native graphics. |
| `scripts/setup_visual_stack.sh`: `emilkowalski/skills`, `remotion-dev/skills` | KEEP reference + PORT policy | Emil exists as an installer invocation, not a runtime package, copied skill library, animation protocol, or renderer integration. Retain motion guidance; review/pin external skills separately. New setup does not rerun the old unpinned installer. |
| `render.py`, `probe.py`, `audio.py`, `motion.py` | KEEP, possible REPLACE BY OPENREEL for interactive export | FFmpeg/ffprobe are working deterministic tools. Auto-Editor is optional doctor/installer/research integration, not the engine actually executing cuts. Native desktop export overlaps encoding but does not replace semantic range planning. |
| `vision.py`, `pipeline.py`, event grammar | KEEP + PORT output | OpenReel timeline operations do not replace Battle Box semantic labels and keep decisions. New compiler preserves source trims and flattened timeline positions via actual add/trim/move tools. |
| `transcript.py`, local whisper.cpp + caption mapping | KEEP + PORT | Local ASR policy and source-time remapping remain Astel responsibilities. OpenReel subtitle tools overlap display, not this local transcription pipeline. |
| `learning.py`, API review routes, learning snapshots, OLEH_STYLE SQL seed | KEEP + PORT correction evidence | Deterministic candidate adaptation is implemented, not a trained ranking model. Never activate a candidate automatically. Native undo/history is not a preference-learning system. New clip diff preserves evidence; text/motion full diff still needs an adapter. |
| `api.py`, `backend.py`, Supabase schemas, `worker.py` | KEEP | Authenticated control plane, atomic claims, owner-scoped completion and media-root checks are separate from MCP editing. Keep deployments and credentials unchanged. Stage 1 does not require a remote worker. |
| `editor/src/App.tsx` | REPLACE BY OPENREEL after A/B; DEPRECATE LATER | Browser timeline/preview/localStorage/JSON prototype remains runnable. Its `aiDraft` is a hard-coded demo sequence, not semantic AI. Saved JSON has `sourceStart/sourceEnd` and percentage overlay coordinates, so it cannot be loaded as an OpenReel project without a converter. |
| `docs/EXECUTION_ORDER_MAC_FIRST.md`, `MAC_STAGE2_VALIDATION.md`, `scripts/mac_editor_validation.sh` | KEEP experiments; DEPRECATE LATER only after A/B | These specify OpenCut tests, but no OpenCut checkout, implemented EditorCore bridge, correction collector, or working deployment URL is checked in. New Mac path targets OpenReel; old experiment documents are not erased. |
| ASAP GTA6 | KEEP requirements only | Found as a live test project name in OpenCut docs. No GTA6-specific semantic hook, gameplay planner or publishing integration in code. A temporary Rockstar media-transfer branch exists in history; its workflow was subsequently removed. Do not revive it. |
| Approved manual/scene-library export branches (`3ba6933`, `af1d246`) | KEEP in history; PORT separately when needed | Real additional source-range export work exists on `feat/manual-scene-export-20261002` / `feat/scene-library-export-2026-10-02`, not the selected OpenCut base. Remains accessible in full clone; no automatic cherry-pick of divergent CLI changes. |
| Astel `.env.example`, Dockerfiles, Railway, existing CI | KEEP | No publishing, production env, cloud schema, or deployment mutations. Add integration checks separately from production workflows. |

## OpenReel code audit

### Core and native project format

`packages/core/src` contains timeline/action execution/history, media import, audio processing, text/graphics, transitions, effects/color, storage, motion and export engines. `types/project.ts` defines project settings, media library, timeline and optional text/shape/SVG/sticker/motion/creation state. `storage/project-serializer.ts` uses schema **1.2.0**, a `{version, minimumReaderVersion?, capabilities?, project}` envelope, normalization and reader-compatibility checks.

Astel `*.plan.json`, flattened `*.project.json`, browser editor `version:1` JSON, and OpenReel project files are different formats. Keep separate extensions/artifact names. Media blobs/FileSystem handles are not portable JSON; OpenReel stores source-file hints and needs media relinking. Preserve stable logical asset IDs and per-worker paths in a sidecar; never put a Kevin filesystem path into portable timeline semantics.

### Agent registry and actual tool count

`packages/agent/src/registry.ts` is the source of truth; `toMcpTools()` currently returns **311**, not the earlier 303. `integration/openreel/tool-catalog.json` and `UPSTREAM-CAPABILITIES.md` were generated by executing the pinned registry. Domains cover observation, project/track/clip, transforms, speed, effects/color, audio, captions/keyframes/transitions, motion/3D creation, export and action escape hatches. Catalog presence does not guarantee each tool is supported in every host.

`get_editor_state` is a summary, not a complete project dump. `list_clips` supports offset/limit; `get_clip` reads source trim/effect detail for media clips. `execute_action` / `batch_actions` are capability escape hatches and should not receive arbitrary unvalidated Astel payloads. New offline recipe uses only `add_clip`, `trim_clip`, `move_clip`, explicit media/track IDs, response bindings and an empty unlocked track precondition.

`loop.ts` groups an AI turn, supports dry-run, approval hooks and snapshot rollback on error. `executor.ts` alone dispatches tools; it does not wrap every call in a transaction. `HeadlessHost` snapshots project state and delegates render jobs to an injected `JobRunner`.

### Desktop MCP

Electron `apps/desktop/src/main/mcp/server.ts` starts authenticated loopback HTTP `/mcp`, dynamic port by default (`OPENREEL_MCP_PORT` optional). It writes a mode-0600 `~/.openreel/mcp-endpoint.json` descriptor; `OPENREEL_MCP_ENDPOINT_FILE` can override the location. Token rotation updates the live server. `dist/mcp-shim/index.js` bridges newline JSON-RPC stdio to the current local endpoint.

The renderer bridge uses `apps/web/src/services/agent/mcp-listener.ts` and the shared `LiveEditorHost`, serialized with `runExclusive`. Thus MCP edits and mouse edits can act on the same project, not reconstructed timelines. Destructive/expensive tools are blocked with `CONFIRMATION_REQUIRED` unless Settings → MCP → Trusted local auto-allow is enabled. This is a broad local trust gate, not the AI panel's per-turn confirmation dialog. Do not claim MCP supplies automatic batch rollback or a dry-run parameter on every tool.

### Headless runner

`packages/agent-runner/src/{cli,run,project-io,export-queue}.ts` loads/saves native JSON and runs AI turns in Node; CLI supports provider/model, `--project`, `--out`, `--dry-run`. The default without `--out` writes in place, so always use a distinct output for experiments. A dry-run still calls the LLM and needs an API key. No provider call was made in this audit. The runner requires an injected JobRunner for actual render/GPU/export jobs; compiling or editing JSON alone does not prove media export. `create_project`/media-import host support differs between desktop and HeadlessHost.

### Motion Creator

`packages/core/src/motion` and `apps/web/src/motion` implement composition/layer state, masks, shape modifiers, text animators, variables/components, markers/beat actions, shaders and scene3D. Agent tools expose composition creation/read, editable properties/keyframes and `render_motion_frame`. Frame preview needs a rendering host and is marked expensive. These are good candidates for an editable AstelFam graphics port, but are not a drop-in Remotion renderer. The desktop build logs skip native Aurora staging when `packages/creation-core/build` has no native binary: JS/Electron build passes, native Aurora rendering remains unverified.

### Export

Browser `packages/core/src/export/export-engine.ts` uses browser codecs/MediaBunny and capability negotiation; actual codec availability is machine-dependent. Desktop's web export job runner delegates native encoding via Electron IPC to FFmpeg (`apps/desktop/src/main/sidecar/export-job.ts`). Renderer composition + encoder are both required; a standalone FFmpeg process is not proof of matching motion graphics/export. ProRes/alpha paths belong to native desktop, not an assumed browser equivalence. Old Astel FFmpeg render remains a baseline/fallback.

## History and upstream gaps

- Astel history: `8116a1f` adds Whisper/Remotion, `5377990` API/learning backend, `7a865ae` review/candidates, `f5916dc` secured queue, `275bc4c` worker. Visual-stack commits `b7945fe`–`c6fe2e3` add AstelFam composition/preset/installer. `25012ea` builds the browser timeline; `6d0877a` changes Mac-first ordering.
- OpenReel public history contains bulk sync commits (`7ef1b6c`, `128d99b`, `3efdb84`), so individual feature provenance cannot always be inferred from a fine-grained commit trail. Current files/tests are stronger evidence than old plans.
- Upstream documentation drifts from executable code: `docs/AGENT-GUIDE.md` still says 228 tools, checked-in `docs/AGENT-CAPABILITIES.md` says 303, while executed registry and Desktop return 311. Both documents and `apps/desktop/DISTRIBUTION.md` were inspected. Distribution prose says binaries are not on GitHub Releases; current release history/workflow now publishes GitHub artifacts and optionally R2. Use current code/workflow for configuration; do not copy old release/publishing assumptions.
- Open upstream [PR #107](https://github.com/Augani/openreel-video/pull/107) adds local-path import and text/subtitle readback. At audit it is OPEN, not in the pinned core. Keep manual local import and explicitly limited clip correction collection until reviewed/ported. Do not count PR features as current main capabilities.
- Open PRs #98/#93 concern preview ghosting; #99 export bitrate modes; #97/#75 keyframes. These warrant A/B inspection, not blind application. Current open issue #110 concerns Escape navigation; source may differ from latest release.

## A/B gates and next configuration work

1. Stage 1 Mac: source-built Desktop MCP connection and tool discovery, then shared-project split → mouse move → reread → text creation → mouse retime/resize → full correction diff. Token stays local; current Python probe is read-only.
2. Import the same 2–3 short local GTA/other representative clips into Astel and OpenReel manually. Bind logical media IDs to actual OpenReel IDs. Use a separate empty track/project; validate durations/source ranges before mutations.
3. Review/port local-path import and text/subtitle readback from upstream PR #107 with focused tests, or implement equivalent narrow host adapters. Add motion composition readback so text position/style/keyframes enter correction evidence.
4. Add live recipe execution with project identity/revision checks, conflict detection between human and AI edits, per-batch snapshot/undo verification and failures that leave no partial state. Offline clone execution already passes; it is not the live writer.
5. Compare AstelFam Remotion and editable Motion Creator variants on font, geometry, emoji, caption timing and reaction zoom. Keep Remotion external assets while native parity is incomplete.
6. Export both versions, inspect with ffprobe and frames: duration/frame-rate, source cuts, caption alignment, AV sync, transition frames, graphics layout, 1080×1920 H.264 and optional ProRes/alpha. Record render time/memory and failure recovery. Human approval of the same RAW pair is required to select the winner.
7. Convert reviewed clip/text corrections into explicit KEEP/CUT/SHORTER/LONGER evidence with source mapping. Feed existing candidate builder only after human interpretation; never automatically promote OLEH_STYLE from a raw structural diff.
8. Only after Mac A/B passes, Stage 2 Kevin/Windows: media-root mapping, worker claim/complete, desktop export and project relinking. Simulate Kevin offline; Mac must remain fully operational.
9. Deprecate old editor/OpenCut only after round-trip, graphics and export gates pass. Nothing in this branch removes them.

## Voicebox integration decision — 2026-10-27

**Decision: extend OpenReel's existing Text to Speech panel with a local Voicebox provider and an Astel narration-job coordinator.** Keep Voicebox as a separate local service; OpenReel remains the editing UI. The same job API can later be exposed to chat through MCP. Generation and editing from the application must work independently of the cloud chat tunnel.

This is an implementation decision, not an installed feature. The current branch has a working standalone Voicebox adapter and accepted test WAVs; it does not yet have the new OpenReel provider, persistent narration jobs, automatic caption/shot assembly, or a tested live timeline applier. The installed desktop application was not replaced in this review.

### Evidence and reuse

Reviewed the pinned checkout `c9340465e5d37e684cc25bdbe746c4ccd45e165c` and current upstream `367d7e90b61b5181f9861b852bb8b9d7a7d2954a` (2026-10-17). Upstream was fetched for inspection without changing the checked-out submodule commit. Voicebox upstream remains `8af7efe62fab8d33e2a5dfbedabaa45f68a5184f`.

- `apps/web/src/components/editor/inspector/TextToSpeechPanel.tsx` already provides text input, generation, preview and an audio result. `stores/settings-store.ts` still declares only `TtsProvider = "elevenlabs"` in current upstream. No built-in Voicebox provider was found in these paths.
- `inspector/hooks/useTtsActions.ts` already imports generated audio and adds it to a new track. Reuse its editor integration after validating real media-ID semantics; do not reuse its ElevenLabs-only argument contract unchanged. The current hook aborts an in-flight request on component unmount, and `tts-store.ts` retains an in-memory Blob rather than a recoverable generation job. A provider dropdown alone does not meet the background-job requirement.
- `AutoCaptionPanel.tsx` and `workers/whisper-worker.ts` already perform local transcription and map segment timestamps through clip trims/speed into subtitle positions. The worker requests segment timestamps, not validated word-level forced alignment. Do not interpret the UI's assigned `confidence: 1` as measured recognition confidence.
- The panel, TTS action hook, caption panel and Whisper worker are unchanged between the pinned checkout and the reviewed upstream commit. Updating upstream alone will not add the proposed Voicebox workflow.
- Reuse Astel's required-clone adapter, versioned artifacts and selected voice processing. The Russian tone B preference applies to Russian test audio; English has a separate reference and pacing history. The accepted short English speed factor is not a universal duration policy.

### Application flow

Inside Text to Speech, add provider **Voicebox — local**, profile **Oleh RU / Oleh EN**, script blocks and a primary action **Create narrated draft**. Selected source clips come from the current project's media library. Show stage progress and results inside the application; source paths, IPC and service configuration belong in settings and diagnostics.

```text
OpenReel panel -> typed desktop IPC -> Astel narration coordinator -> Voicebox REST
                                     |                     |
                              asset preparation      synthesis + tone/tempo
                                     |                     |
                                     |             final audio + alignment
                                     +----------> editable timeline draft
```

Use typed Electron IPC with a dedicated local adapter rather than adding an arbitrary URL to the existing cloud-provider proxy. The coordinator must preserve reference/profile binding checks, exact approved script, model identity, seed and the one-submission/resume behavior already implemented by the Astel adapter. OpenReel's existing ElevenLabs path remains available.

### Parallel work and timecodes

Video metadata analysis, shot suggestions and planning may run while narration is being synthesized. Final shot placement and captions depend on the completed audio after all tone/tempo processing. On this 16 GB Mac, serialize heavy TTS and alignment inference initially rather than loading two competing models simultaneously.

Persist a job with project ID, baseline revision/fingerprint, stable script-block IDs, selected asset IDs, generation IDs, settings and artifact hashes. Each completed block needs an actual measured audio duration. Alignment is tied to the final audio hash; changing speed or replacing a block invalidates affected timing. Use approved script text for captions, with alignment mismatches surfaced for review rather than silently adopting ASR substitutions. Segment-level cues are the first milestone; word highlighting needs separately validated word alignment.

Stable block IDs permit regenerating one passage and retiming its dependent shots/captions. They do not yet exist in the standalone long-pilot generator. Preserve original speech, previous versions and manual edits. If the project changed during background processing, offer a new candidate or explicit conflict resolution; do not silently apply an old plan to the current timeline.

### Delivery order and acceptance

1. **Provider and background job:** generate from the native panel using existing local profiles, persist WAV/manifest, survive panel switching and recover known generation IDs without duplicate POSTs. Cancellation must distinguish a local abort, a queued cancellation and an active backend cancellation request.
2. **Audio and captions:** auto-import the final WAV, create editable caption cues on its measured timeline, preserve accepted processing, and verify project identity, trims and speed handling. A failed operation must leave inspectable artifacts and no unexplained partial edits.
3. **Narration-led draft:** map selected assets to script blocks, assemble editable video/audio/caption tracks, and verify undo/conflict handling. A generic commentary-to-shot planner is additional Astel logic; Battle Box event detection and ordinary clip tools alone do not provide it.
4. **End-to-end validation:** UI -> local job -> actual WAV -> timing -> native timeline -> local MP4, including RU/EN text, corrected speed, regeneration of one passage, recovery after restart, a human timeline edit during generation, and AV/caption checks. Run relevant typechecks/builds and integration tests when implementation exists. This architecture review does not count as those tests passing.

Keep local media as the first asset pool. Search/download automation, face/lip-sync, Kevin/Windows and Distribution publishing remain separate later work. Preserve MIT and bundled dependency notices. Detailed decision metadata: [OPENREEL_INTEGRATION_DECISION.json](../voicebox/OPENREEL_INTEGRATION_DECISION.json).

Primary source reviewed: [OpenReel TTS panel at current upstream](https://github.com/Augani/openreel-video/blob/367d7e90b61b5181f9861b852bb8b9d7a7d2954a/apps/web/src/components/editor/inspector/TextToSpeechPanel.tsx), [TTS action hook](https://github.com/Augani/openreel-video/blob/367d7e90b61b5181f9861b852bb8b9d7a7d2954a/apps/web/src/components/editor/inspector/hooks/useTtsActions.ts), [caption panel](https://github.com/Augani/openreel-video/blob/367d7e90b61b5181f9861b852bb8b9d7a7d2954a/apps/web/src/components/editor/inspector/AutoCaptionPanel.tsx).

## Notices

OpenReel's original MIT license remains at `vendor/openreel/LICENSE`, with an unchanged copy in `integration/openreel/licenses/OPENREEL-MIT.txt`. Preserve copyright and license in redistributed OpenReel code/binaries and any substantial copied code; keep third-party notices from packaged dependencies. Desktop also preserves `apps/desktop/LICENSES/FFMPEG.md`, `BLENDER.md`, `GPL-2.0.txt` and `GPL-3.0.txt`; OpenReel MIT does not replace those bundled-tool notices. No distributable binary was produced here. Astel currently has no repository LICENSE detected by GitHub: this branch does not invent or change Astel's licensing.

Primary evidence: [Astel repository](https://github.com/asteloleh-gif/video-editor), [OpenReel pinned source](https://github.com/Augani/openreel-video/tree/c9340465e5d37e684cc25bdbe746c4ccd45e165c), local generated catalog and the recorded Git histories. See `VALIDATION.md` for exact verification limits and `MAC_SETUP.md` for setup.


## Native Voicebox speech implemented — 2026-10-27

The isolated OpenReel Astel candidate now implements paste text → approved RU/EN personal voice → durable local background job → preview/download → guarded audio timeline import. This closes the first native speech UI milestone. Broader narrated video assembly, word timing/captions and publishing remain outside this milestone. See [installation and verification](../voicebox/OPENREEL_LOCAL_SPEECH.md). The original application, clean upstream submodule, project data and existing MCP tunnel remain preserved.
