#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
mkdir -p output
.venv/bin/pytest -q
npm run build --prefix editor
npm run typecheck --prefix remotion
vendor/openreel/packages/agent/node_modules/.bin/tsc -p integration/openreel/tsconfig.json
vendor/openreel/packages/agent-runner/node_modules/.bin/tsup --config integration/openreel/tsup.config.mjs
# Synthetic fixture only; real analysis plans and media are never overwritten.
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from video_editor.openreel import plan_keep_ranges
plan = {'source': {'duration': 10}, 'keep': [{'start': 1, 'end': 3}, {'start': 5, 'end': 8}]}
recipe = plan_keep_ranges(plan, media_id='synthetic-media', track_id='synthetic-track', style=json.loads(Path('styles/astelfam.json').read_text()))
Path('output/openreel-recipe.json').write_text(json.dumps(recipe, indent=2))
PY
vendor/openreel/packages/agent/node_modules/.bin/vitest run --config integration/openreel/vitest.config.mjs
TASK_CLI_DIR="$(mktemp -d "$TASK_ROOT/output/openreel-cli.XXXXXX")"
node integration/openreel/build/astel-recipe.cjs output/openreel-empty.project.json output/openreel-bound.recipe.json "$TASK_CLI_DIR/candidate.project.json"
if [[ "${FULL_UPSTREAM:-0}" == 1 ]]; then
  cd vendor/openreel
  npx --yes pnpm@11.7.0 typecheck
  npx --yes pnpm@11.7.0 test
  npx --yes pnpm@11.7.0 build
  npx --yes pnpm@11.7.0 --filter @openreel/desktop build
  npx --yes pnpm@11.7.0 --filter @openreel/agent-runner build
fi
