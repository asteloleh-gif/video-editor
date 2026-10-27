#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_RUNTIME="${ASTEL_VOICEBOX_HOME:-$HOME/.local/share/astel-voicebox}"
export PYTHONPATH="$TASK_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$TASK_RUNTIME/venv/bin/python" -m video_editor.voicebox "$@"
