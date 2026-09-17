#!/usr/bin/env bash
set -euo pipefail

echo "=== video-editor macOS setup ==="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install it from https://brew.sh and run again."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  brew install ffmpeg
fi

PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
if [ ! -x "$PYTHON_BIN" ]; then
  brew install python@3.11
  PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
fi

"$PYTHON_BIN" --version
rm -rf .venv
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

mkdir -p input output

CONFIG_DIR="$HOME/.config/video-editor"
KEY_FILE="$CONFIG_DIR/openai_api_key"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

if [ ! -s "$KEY_FILE" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
  printf '%s\n' "$OPENAI_API_KEY" > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  echo "Saved OPENAI_API_KEY for Video Editor.app."
elif [ ! -s "$KEY_FILE" ] && [ -t 0 ]; then
  echo
  echo "Vision mode needs an OpenAI API key."
  read -r -s -p "Paste OPENAI_API_KEY (hidden; Enter to skip): " API_KEY_INPUT
  echo
  if [ -n "$API_KEY_INPUT" ]; then
    printf '%s\n' "$API_KEY_INPUT" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    echo "Saved key to $KEY_FILE"
  else
    echo "Skipped API key. Vision mode will not run until a key is configured."
  fi
fi

echo
echo "Setup complete."
echo "Run:"
echo "  source .venv/bin/activate"
echo "  video-editor doctor"
