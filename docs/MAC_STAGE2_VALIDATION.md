# macOS Stage-2 Validation

Run only after the Kevin/Windows live-editor round-trip passes.

## Purpose

Prove that the Astel/OpenCut workflow is not coupled to Kevin's Windows desktop.

## Test

Use the same project concept as Stage 1:

`ASAP GTA6 — LIVE EDIT TEST 01`

On Mac:

1. Launch `scripts/mac_editor_validation.sh`.
2. Open the same OpenCut deployment.
3. Import equivalent local test media if browser-local media handles are not portable.
4. Bridge reads active timeline.
5. Bridge performs one split and one text insert.
6. Human moves the split element and text in OpenCut.
7. Bridge reads the changed values.
8. Save before/after/correction snapshots.
9. Confirm render/export can be initiated locally without changing publication state.

## Pass criteria

- Same bridge operation schema works on both Windows/Kevin and macOS.
- No Windows-only path assumptions exist in bridge payloads.
- Media identity is separated from machine-local file paths.
- Human edits remain visible to bridge after refresh/persistence.
- No YouTube upload/publication is triggered.

If Stage 1 passes but Stage 2 fails, keep OpenCut as experimental until portability is fixed.
