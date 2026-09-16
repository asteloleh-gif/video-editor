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

if ! command -v python3 >/dev/null 2>&1; then
  brew install python
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

mkdir -p input output

echo
echo "Setup complete."
echo "Run:"
echo "  source .venv/bin/activate"
echo "  video-editor doctor"
