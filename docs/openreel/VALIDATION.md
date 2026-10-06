# Verification — 2026-10-06, Mac reference environment

Pinned OpenReel: `c9340465e5d37e684cc25bdbe746c4ccd45e165c`. Astel base: `6d0877a1a86ac04991d0521eb1990d9d8777e017`. Actual runtime: Node **20.14.0**, pnpm **11.19.0**, Python **3.11.16**, system FFmpeg on macOS. New setup recommends modern Node and upstream-pinned pnpm; this audit did not modify global runtimes.

| Check | Result | Evidence / scope |
|---|---|---|
| Full clones/history | PASS | Both `git rev-parse --is-shallow-repository` return false; remote refs retained. |
| OpenReel frozen-lockfile install | PASS | No upstream tracked-file modifications. |
| OpenReel workspace typecheck | PASS | All recursive workspace typechecks exit 0. |
| OpenReel workspace tests | PASS | **3,258 passed, 34 skipped**. Core 1,315 passed/20 skipped; agent 480 passed; agent-runner 21 passed; Desktop 132 passed/7 skipped; web 1,042 passed/7 skipped; other packages 268 passed. Skipped tests remain unverified. |
| OpenReel web build | PASS | AssemblyScript WASM builds plus browser build. Large-chunk/stale-browser-data warnings remain upstream. |
| OpenReel Desktop build | PASS | Renderer and Electron main/preload/MCP shim built. Native Aurora staging skipped: missing optional native binary. Packaging/notarization not run. |
| Headless runner build | PASS | Standalone CLI bundled. No LLM call, provider key validation or export-job execution. |
| Preserved Astel Python tests | PASS | **30 passed**, including 4 new adapter tests; compileall passes. No live Supabase calls. |
| Preserved Astel browser editor | PASS | TypeScript + Vite build. Existing demo draft behavior remains unchanged. |
| Preserved Remotion | PASS | Typecheck; real branded Remotion render not run. |
| Astel/OpenReel layer | PASS | Separate TypeScript typecheck/build, **2 integration tests** against pinned tools and serializer. |
| Python KEEP → upstream tools | PASS | `[1,3]`, `[5,8]` source ranges become clips at output 0 and 2 with durations 2 and 3; in/out points preserved. Input project unchanged; invalid binding and non-empty track fail. Native JSON save/load works. |
| Standalone offline recipe CLI | PASS | Reads native input + bound recipe, saves a new native project. Output file created exclusively; no live editor writes. |
| Current capability catalog | PASS | Executed registry yields **311 tools**; generated docs/JSON checked in. |
| Mac Desktop runtime + MCP | PASS, connection scope | Source-built Electron started. Authenticated initialize/tools/list returns **311**. Created a separate blank 1080×1920 / 30fps synthetic validation project via live MCP, then read it with the Astel probe. No existing project was open before creation. Token excluded from saved evidence. |
| Synthetic FFmpeg baseline | PASS | Generated test video/audio only; Astel FFmpeg rough cut is **5.000000 seconds**, measured by ffprobe. This is the Astel baseline, not a native OpenReel export. |
| MIT notices | PASS | Original OpenReel LICENSE preserved plus unchanged copy in integration layer. |
| Git diff / setup shell syntax | PASS | No whitespace errors; setup/verification scripts parse. Production configs untouched. |

Raw console logs are local in the parent `integration-workspace/` directory. Structured durable summary: `VALIDATION-SUMMARY.json`. Synthetic project/recipe, desktop snapshot and media artifacts are local under ignored `output/`. Registry docs are intentionally committed; endpoint tokens and RAW media are not.

## Remaining acceptance gates

- Real media A/B and human visual review have **not** passed yet; no real GTA clips were provided to this checkout.
- Live split → human move → reread → text create → human resize/retime → correction learning is **not** proven end-to-end. Desktop connection/read was verified; the full live writer is future work. Current correction adapter only captures main media clips.
- Local-path import and overlay readback from upstream PR #107 are not merged. Manual media import and separate overlay adapter are still required.
- Native OpenReel H.264/ProRes/alpha export, GPU/browser parity, Remotion visual parity, render-job injection and AV-sync review remain unverified.
- Kevin/Windows remains Stage 2. No remote worker, production deployment, publishing or YouTube action occurred.

Re-run `bash scripts/verify_openreel_integration.sh`; add `FULL_UPSTREAM=1` for complete upstream build/typecheck/test verification. The synthetic fixture is explicitly generated and cannot substitute for actual RAW/manual-final A/B.
