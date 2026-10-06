#!/usr/bin/env bash
set -euo pipefail
# Disable inherited tracing before accessing any credentials.
set +x
umask 077

# Prefer OpenReel's official shim, which follows changing ports and tokens.
if [[ "${OPENREEL_TUNNEL_TRANSPORT:-stdio}" == "stdio" ]]; then
  exec python3 "$(dirname "$0")/openreel_tunnel_connect_mac.py"
fi

PROFILE="${OPENREEL_TUNNEL_PROFILE:-astel-openreel}"
MCP_URL="${OPENREEL_MCP_URL:-http://127.0.0.1:58187/mcp}"

if ! command -v tunnel-client >/dev/null 2>&1; then
  echo "tunnel-client is not installed."
  echo "Install the latest official OpenAI tunnel-client from Platform tunnel settings, then rerun."
  exit 2
fi

python3 - "$MCP_URL" <<'PY'
import sys
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1])
if (u.scheme != 'http' or u.hostname not in ('127.0.0.1', 'localhost', '::1')
        or u.username or u.password or u.query or u.fragment or u.path != '/mcp'):
    sys.exit('Use a loopback HTTP /mcp URL without credentials or query parameters.')
PY

# An HTTP error still proves reachability; doctor checks the MCP contract/auth.
if ! curl --silent --show-error --max-time 5 --output /dev/null "$MCP_URL"; then
  echo "OpenReel MCP is unreachable. Start OpenReel and check Settings → MCP."
  exit 3
fi

: "${OPENREEL_TUNNEL_ID:?Create Astel OpenReel in Platform tunnel settings first}"
KEY_REF="${OPENREEL_RUNTIME_KEY_REF:-env:CONTROL_PLANE_API_KEY}"
case "$KEY_REF" in
  env:CONTROL_PLANE_API_KEY)
    : "${CONTROL_PLANE_API_KEY:?Use secure local credential setup; never paste a key into chat}"
    ;;
  file:/*) ;; # A private, owner-only file outside Git; contains only the key.
  *) echo "Use env:CONTROL_PLANE_API_KEY or file:/absolute/path for the runtime key."; exit 4 ;;
esac

# No OAuth metadata: explicitly choose the HTTP sample instead of init's DCR default.
# init refuses an existing profile; do not overwrite it automatically.
tunnel-client init \
  --sample sample_mcp_remote_no_auth \
  --profile "$PROFILE" \
  --tunnel-id "$OPENREEL_TUNNEL_ID" \
  --control-plane-api-key-ref "$KEY_REF" \
  --mcp-server-url "$MCP_URL" \
  --health-listen-addr 127.0.0.1:0

AUTH_ARGS=()
if [[ -n "${OPENREEL_AUTHORIZATION:-}" ]]; then
  # Variable contains the complete Authorization header, including Bearer.
  AUTH_ARGS=(--mcp.extra-headers 'Authorization: env:OPENREEL_AUTHORIZATION'
             --mcp.discovery-extra-headers 'Authorization: env:OPENREEL_AUTHORIZATION')
fi

echo
echo "Running diagnostics..."
tunnel-client doctor --profile "$PROFILE" --explain "${AUTH_ARGS[@]}"

echo
echo "Starting tunnel. Keep this process running while ChatGPT uses OpenReel."
exec tunnel-client run --profile "$PROFILE" "${AUTH_ARGS[@]}"
