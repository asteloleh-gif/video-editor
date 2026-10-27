#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_RUNTIME="${ASTEL_VOICEBOX_HOME:-$HOME/.local/share/astel-voicebox}"
cd "$TASK_ROOT"
[[ -x "$TASK_RUNTIME/venv/bin/python" ]] || { echo 'Run scripts/setup_voicebox_mac.sh first.' >&2; exit 1; }
exec "$TASK_RUNTIME/venv/bin/python" integration/voicebox/serve.py
