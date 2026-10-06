#!/usr/bin/env bash
set -euo pipefail

PROFILE="${OPENREEL_TUNNEL_PROFILE:-astel-openreel}"
MCP_URL="${OPENREEL_MCP_URL:-http://127.0.0.1:58187/mcp}"

echo "Astel ↔ OpenReel Secure MCP Tunnel"
echo
echo "Local OpenReel MCP: $MCP_URL"
echo
echo "Requirements:"
echo "  1) OpenReel Desktop is running"
echo "  2) Settings → MCP shows Running"
echo "  3) CONTROL_PLANE_API_KEY is set locally"
echo "  4) OPENREEL_TUNNEL_ID is set locally"
echo
: "${CONTROL_PLANE_API_KEY:?Set CONTROL_PLANE_API_KEY locally; do not paste it into chat}"
: "${OPENREEL_TUNNEL_ID:?Set OPENREEL_TUNNEL_ID locally}"

if ! command -v tunnel-client >/dev/null 2>&1; then
  echo "tunnel-client is not installed."
  echo "Install the latest official OpenAI tunnel-client from Platform tunnel settings, then rerun."
  exit 2
fi

tunnel-client init   --profile "$PROFILE"   --tunnel-id "$OPENREEL_TUNNEL_ID"   --mcp-server-url "$MCP_URL"

echo
echo "Running diagnostics..."
tunnel-client doctor --profile "$PROFILE" --explain

echo
echo "Starting tunnel. Keep this process running while ChatGPT uses OpenReel."
exec tunnel-client run --profile "$PROFILE"
