# OpenCut Live Editor — execution order

## Stage 1 — Mac (primary development and proof)

Mac is the reference environment for the first working round-trip.

Goal:

1. Open the pinned OpenCut deployment.
2. Create/open `ASAP GTA6 — LIVE EDIT TEST 01`.
3. Import 2–3 short local GTA clips manually.
4. Astel Bridge reads the active project/scene/timeline.
5. Bridge performs one split through OpenCut's EditorCore/TimelineManager command layer.
6. The split must appear in the OpenCut UI without manual reconstruction.
7. Human moves the resulting element.
8. Bridge reads the changed start time.
9. Bridge inserts one text element.
10. Human moves/resizes/retimes the text.
11. Bridge observes those changes.
12. Save `ai_before.json`, `human_after.json`, and `corrections.json`.

Pass = one shared editable timeline works bidirectionally.

Only after this passes do we add AI editing features, Remotion motion graphics, or a remote worker.

## Stage 2 — Kevin / Windows (secondary worker validation)

Kevin is NOT required to prove the architecture.

After Stage 1 passes:

- reproduce the same bridge contract on Kevin's desktop;
- keep OpenCut open as a live worker;
- map media IDs to Kevin-local paths;
- test local render/export;
- confirm Windows-specific paths do not leak into project semantics.

If Kevin goes offline or the Windows worker fails, Mac remains the reference editor and production fallback.

## Architecture rule

The bridge must never depend on GUI mouse automation for timeline edits when OpenCut exposes an EditorCore/TimelineManager command.

The bridge contract is platform-neutral.
Machine-local media paths belong in a worker/media mapping layer, not in timeline semantics.
