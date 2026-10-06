#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
[[ "$(uname -s)" == Darwin ]] || { echo 'This setup targets macOS.' >&2; exit 1; }
TASK_PYTHON="${ASTEL_PYTHON:-python3.11}"
command -v "$TASK_PYTHON" >/dev/null
command -v node >/dev/null
command -v npm >/dev/null
"$TASK_PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
git submodule update --init --recursive
"$TASK_PYTHON" -m venv .venv
.venv/bin/pip install -e '.[api,dev]'
npm ci --prefix editor
npm ci --prefix remotion
(cd vendor/openreel && npx --yes pnpm@11.7.0 install --frozen-lockfile)
echo 'Ready. See docs/openreel/MAC_SETUP.md to build and start Desktop.'
