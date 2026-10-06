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
| `styles/astelfam.json`, `remotion/src/AstelFamShort.tsx`, visual `restyle` path | KEEP + PORT | Brand colors, emoji reactions, counters and timing are Astel IP/behavior. Motion Creator offers primitives, not these exact compositions. Keep external Remotion rendering until visual parity; port selected graphics as editable motion layers later. |
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

## Notices

OpenReel's original MIT license remains at `vendor/openreel/LICENSE`, with an unchanged copy in `integration/openreel/licenses/OPENREEL-MIT.txt`. Preserve copyright and license in redistributed OpenReel code/binaries and any substantial copied code; keep third-party notices from packaged dependencies. Astel currently has no repository LICENSE detected by GitHub: this branch does not invent or change Astel's licensing.

Primary evidence: [Astel repository](https://github.com/asteloleh-gif/video-editor), [OpenReel pinned source](https://github.com/Augani/openreel-video/tree/c9340465e5d37e684cc25bdbe746c4ccd45e165c), local generated catalog and the recorded Git histories. See `VALIDATION.md` for exact verification limits and `MAC_SETUP.md` for setup.
