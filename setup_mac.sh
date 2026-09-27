#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== Battle Box AutoEditor macOS setup ==="

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install it from https://brew.sh and run again."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  brew install ffmpeg
fi

PYTHON_BIN="$(brew --prefix python@3.11 2>/dev/null || true)/bin/python3.11"
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

mkdir -p input output assets

CONFIG_DIR="$HOME/.config/video-editor"
KEY_FILE="$CONFIG_DIR/openai_api_key"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

if [ ! -s "$KEY_FILE" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
  printf '%s
' "$OPENAI_API_KEY" > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  echo "Saved OPENAI_API_KEY for Video Editor.app."
elif [ ! -s "$KEY_FILE" ] && [ -t 0 ]; then
  echo
  echo "Semantic vision mode needs an OpenAI API key."
  read -r -s -p "Paste OPENAI_API_KEY (hidden; Enter to skip): " API_KEY_INPUT
  echo
  if [ -n "$API_KEY_INPUT" ]; then
    printf '%s
' "$API_KEY_INPUT" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    echo "Saved key to $KEY_FILE"
  else
    echo "Skipped API key. Vision mode will not run until a key is configured."
  fi
fi

if [ "${VIDEO_EDITOR_SKIP_WHISPER:-0}" != "1" ]; then
  if ! command -v whisper-cli >/dev/null 2>&1; then
    brew install whisper.cpp
  fi
  WHISPER_DIR="$HOME/.cache/video-editor/whisper"
  WHISPER_MODEL="$WHISPER_DIR/ggml-base.bin"
  mkdir -p "$WHISPER_DIR"
  if [ ! -s "$WHISPER_MODEL" ]; then
    echo "Downloading multilingual Whisper base model (~150 MB)..."
    curl -fL --retry 3       "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"       -o "$WHISPER_MODEL.tmp"
    mv "$WHISPER_MODEL.tmp" "$WHISPER_MODEL"
  fi
else
  echo "Skipping local Whisper (VIDEO_EDITOR_SKIP_WHISPER=1)."
fi

if [ "${VIDEO_EDITOR_SKIP_REMOTION:-0}" != "1" ]; then
  if ! command -v node >/dev/null 2>&1; then
    brew install node
  fi
  if [ -f "$PROJECT_DIR/remotion/package.json" ]; then
    echo "Installing Remotion renderer..."
    (cd "$PROJECT_DIR/remotion" && npm install)
  fi
else
  echo "Skipping Remotion (VIDEO_EDITOR_SKIP_REMOTION=1)."
fi

echo
echo "Setup complete."
echo "Run:"
echo "  source .venv/bin/activate"
echo "  video-editor doctor --full"
echo "  video-editor create-short input.mov -o output/final.mp4 --open"
