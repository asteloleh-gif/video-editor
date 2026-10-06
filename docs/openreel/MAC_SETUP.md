# Mac-first setup and MCP configuration

This is an isolated local candidate. No production publishing/deployment setup is changed.

## Checkout and install

Use the integration checkout created for this task, or clone the candidate branch:

```bash
git clone --branch integration/openreel-mac-first --recurse-submodules https://github.com/asteloleh-gif/video-editor.git
cd video-editor
git submodule update --init --recursive
bash scripts/setup_openreel_mac.sh
```

The existing integration checkout needs no reclone. Requirements: macOS, Python 3.11+, Node 22+ (use Node 24+ with pinned pnpm 11), npm, FFmpeg/ffprobe for the legacy media pipeline. Setup installs isolated Python extras and workspace npm dependencies; it does not install animation skills, call AI providers, change Codex global configuration, or deploy services.

Upstream declares `pnpm@11.7.0`; the setup script uses that explicit version through npx. Audit used the available pnpm 11.19.0 with a frozen lockfile; Node was recorded in validation. Keep the upstream lockfile unchanged.

```bash
cd vendor/openreel
npx --yes pnpm@11.7.0 build
npx --yes pnpm@11.7.0 --filter @openreel/desktop build
npx --yes pnpm@11.7.0 --filter @openreel/desktop start
```

The source-built Desktop candidate opens locally. For a packaged app, use upstream's `fetch:ffmpeg`/`pack` instructions and include all notices; build success does not mean packaging, notarization or native Aurora is verified. For development native FFmpeg resolution, inspect `apps/desktop/src/main/sidecar/ffmpeg-path.ts` and ensure FFmpeg is on PATH.

## Stage 1: connect external tools to the Mac editor

Desktop starts MCP and writes `~/.openreel/mcp-endpoint.json`. Do not paste its bearer token into Git, documents, logs or chat. First use the read-only probe from the Astel root:

```bash
.venv/bin/python -m video_editor.openreel snapshot --out output/ai_before.json
# After an actual human edit, save a new snapshot, never overwrite evidence:
.venv/bin/python -m video_editor.openreel snapshot --out output/human_after.json
.venv/bin/python -m video_editor.openreel diff output/ai_before.json output/human_after.json --out output/corrections.json
```

Keep the editor idle while each snapshot is taken: multiple reads are not atomic. Probe paginates clips and fetches source trim/effect details. Current diff covers main-timeline media clips only; text/subtitle/motion correction collection is a next-step adapter. A project must be open. Every artifact uses exclusive creation, so choose a new filename on each run.

For a Codex/client MCP connection, configure a new local stdio server named `openreel-astel-local` with:

```json
{
  "command": "/absolute/path/to/node",
  "args": ["/absolute/path/to/video-editor/vendor/openreel/apps/desktop/dist/mcp-shim/index.js"]
}
```

Resolve both paths on this Mac. The shim reads the current endpoint and handles token rotation; no hard-coded bearer token is needed. This is a configuration example, not a configuration already applied to Codex. Verify `initialize`, `tools/list`, `get_editor_state`, `list_media`, `list_tracks`, `list_clips`, `get_clip` before enabling writes. Current source exposes 311 tools. A release binary's count can differ.

Settings → MCP → Trusted local auto-allow permits destructive/expensive tools. Leave it disabled for observation; only enable it for an isolated test project when testing those operations. It is a broad gate. Live transactions, rollback and conflict detection are not provided by our read-only probe.

## Astel plan handoff

Analyze via the existing Astel CLI only when you intend to use its configured vision provider, or use an already reviewed plan. Import RAW manually in OpenReel and obtain real media/empty track IDs through read tools:

```bash
.venv/bin/python -m video_editor.openreel plan output/input.plan.json \
  --media-id ACTUAL_OPENREEL_MEDIA_ID --track-id ACTUAL_EMPTY_TRACK_ID \
  --style styles/astelfam.json --out output/openreel.recipe.json
```

This creates a review-only recipe, not a direct project import or live edit. `$clip:N` bindings must be resolved from add_clip results. `integration/openreel/execute-recipe.ts` executes recipes on a cloned HeadlessHost, enforcing empty unlocked track and source-duration preconditions. The integration test exercises it against the real pinned registry and serializer. Astel style metadata remains in a sidecar; it does not automatically generate native graphics.

```bash
bash scripts/verify_openreel_integration.sh
```

The standalone offline writer is also built and exercised. To apply a reviewed recipe to a native OpenReel project with an empty matching track:

```bash
node integration/openreel/build/astel-recipe.cjs input.project.json recipe.json NEW-candidate.project.json
```

It refuses existing output filenames; no LLM or live editor writes occur.

This runs Python tests, legacy editor build, Remotion typecheck, integration typecheck and the synthetic headless round-trip; use `FULL_UPSTREAM=1` for the full upstream typecheck/tests/web/Desktop/runner builds. It uses no LLM or production backend.

## Headless AI runner later

```bash
cd vendor/openreel
npx --yes pnpm@11.7.0 --filter @openreel/agent-runner build
node packages/agent-runner/dist/cli.cjs --project /absolute/path/input.project.json \
  --prompt "Describe the planned edit" --provider openai --model YOUR_VERIFIED_MODEL \
  --dry-run --out /absolute/path/candidate.project.json
```

This requires a provider key and can incur model usage even in dry-run. No key is needed for the deterministic integration test. Verify an available model explicitly; do not rely on upstream hard-coded defaults. Render/export needs a JobRunner; do not assume the CLI is a turnkey render farm.

## Stage 2: Kevin/Windows

Wait for Mac shared-project correction round-trip + actual media export A/B. Then reproduce the protocol with Windows-local media mappings and the existing authenticated Astel worker. No Windows worker availability may block Mac editing, feedback collection or export. Do not expose the Mac loopback MCP endpoint as a remote worker API.
