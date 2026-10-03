#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[visual-stack] Installing agent skills..."
npx skills@latest add emilkowalski/skills
npx skills@latest add remotion-dev/skills
npx skills@latest add WyattBlue/auto-editor

echo "[visual-stack] Installing/updating Remotion runtime..."
(
  cd remotion
  npm install
)

if command -v auto-editor >/dev/null 2>&1; then
  echo "[visual-stack] auto-editor already available: $(auto-editor --version 2>/dev/null || true)"
elif [[ "$(uname -s)" == "Darwin" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "[visual-stack] Homebrew is required to install auto-editor on macOS." >&2
    exit 1
  fi
  echo "[visual-stack] Installing auto-editor with Homebrew..."
  brew install auto-editor
else
  cat >&2 <<'EOF'
[visual-stack] auto-editor is not installed.
The current upstream project no longer publishes the CLI on pip.
Install the official platform binary from:
https://auto-editor.com/installing
Then re-run this script.
EOF
  exit 1
fi

echo "[visual-stack] Verifying..."
python3 -m compileall -q src
(
  cd remotion
  npm run typecheck
)
auto-editor --version || auto-editor --help >/dev/null

echo "[visual-stack] Ready."
echo "Visual-only A/B test:"
echo "  source .venv/bin/activate"
echo "  video-editor restyle INPUT.mp4 -o output/INPUT_astelfam.mp4 --require-whisper"
