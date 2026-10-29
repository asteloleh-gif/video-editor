#!/bin/sh
# Candidate-specific stdio MCP. The dynamic token stays in its private descriptor.
set -eu
ASTEL_WORKSPACE_NODE="$HOME/.local/share/astel-media-workspace/bin/node"
ASTEL_WORKSPACE_SHIM="$HOME/Applications/OpenReel Astel.app/Contents/Resources/app.asar.unpacked/dist/mcp-shim/index.js"
export OPENREEL_MCP_ENDPOINT_FILE="$HOME/.openreel/astel-voicebox-mcp-endpoint.json"
if [ ! -x "$ASTEL_WORKSPACE_NODE" ] || [ ! -f "$ASTEL_WORKSPACE_SHIM" ] || [ ! -f "$OPENREEL_MCP_ENDPOINT_FILE" ]; then
  echo 'Start OpenReel Astel and install its media workspace before connecting MCP.' >&2
  exit 1
fi
exec "$ASTEL_WORKSPACE_NODE" "$ASTEL_WORKSPACE_SHIM"
