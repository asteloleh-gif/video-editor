# ChatGPT ↔ OpenReel via Secure MCP Tunnel

This is the preferred connection path for the Mac-first editor test.

Architecture:

ChatGPT
→ OpenAI Secure MCP Tunnel
→ tunnel-client on Mac
→ OpenReel Desktop MCP on 127.0.0.1
→ active OpenReel project

The OpenReel MCP endpoint is never exposed directly to the public Internet.

## Verified local state

OpenReel Desktop MCP has been visually verified running with 311 tools.
The exact localhost port can change between sessions; use the URL shown in
OpenReel Settings → MCP.

Do not commit or paste the OpenReel bearer token, Platform runtime API key,
or other secrets into chat/repository files.

## Setup

1. In OpenAI Platform tunnel settings, create a private MCP tunnel and associate
   it with the ChatGPT workspace/account that will use it.
2. Create/use a runtime API key that has tunnel use permission.
3. Download the latest official OpenAI `tunnel-client` on the Mac.
4. In Terminal, set the two secrets locally:

   export CONTROL_PLANE_API_KEY="<runtime key>"
   export OPENREEL_TUNNEL_ID="<tunnel id>"

5. If OpenReel uses a different port in Settings → MCP:

   export OPENREEL_MCP_URL="http://127.0.0.1:<port>/mcp"

6. Run:

   ./scripts/openreel_secure_tunnel_mac.sh

7. Require `tunnel-client doctor` to pass before connecting ChatGPT.
8. In ChatGPT Plugins → Add custom MCP server → Connection: Tunnel, select the
   Astel/OpenReel tunnel, scan tools, create/install the private plugin.

## First test policy

Start read-only:
- editor/project state
- tracks
- clips
- selected clip

Then one reversible write:
- split one selected clip

Then human correction:
- Oleg moves the split clip manually
- agent reads the new position

Do not enable broad auto-approve until this round-trip is proven.
