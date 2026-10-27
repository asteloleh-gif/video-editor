#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
TASK_PYTHON="${ASTEL_PYTHON:-python3.12}"
if ! command -v "$TASK_PYTHON" >/dev/null 2>&1; then
  TASK_PYTHON="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3.12"
fi
[[ -x "$(command -v "$TASK_PYTHON" 2>/dev/null || true)" ]] || { echo 'Python 3.12 is required. Set ASTEL_PYTHON to its path.' >&2; exit 1; }
git submodule update --init vendor/voicebox
"$TASK_PYTHON" integration/voicebox/runtime.py --install
TASK_RUNTIME="${ASTEL_VOICEBOX_HOME:-$HOME/.local/share/astel-voicebox}"
if [[ ! -e "$TASK_RUNTIME/models/0.6B" ]]; then
  "$TASK_RUNTIME/venv/bin/python" integration/voicebox/download_model.py
fi
echo 'Local Voicebox API runtime prepared. Run scripts/start_voicebox_mac.sh.'
