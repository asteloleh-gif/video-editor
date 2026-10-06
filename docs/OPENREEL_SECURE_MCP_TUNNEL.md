# Astel OpenReel: working Secure MCP Tunnel

Verified on 2026-10-06. The tunnel is running; current-timeline READ is pending
because no project is open in OpenReel. No project edits were executed.

## Verified state

- Tunnel: `tunnel_6ac566f1fac08191b548240633db227d`, name **Astel OpenReel**.
- Associated Personal Platform organization and ChatGPT workspace were verified
  with a runtime-key metadata lookup.
- Official OpenReel Desktop restored at `/Applications/OpenReel.app` and launched.
  Version `1.0.0-alpha.17`; arm64 DMG digest matched release metadata:
  `f5bfe615f2d0a1cf5bbaa30bfc826950c42f62f81602cbabf4f87605adc502f5`.
- Current local MCP URL: `http://127.0.0.1:62730/mcp`. The old port `58187` was
  unavailable. The port/token can change when OpenReel restarts.
- Local MCP initialize succeeded and tools/list returned **311 tools**, no cursor.
- Official tunnel-client: `0.0.15+a390c168ff1b2d14e73a95991c186c6aba3ff5a0`.
- Managed alias/profile: `astel-openreel`; process_running, healthy, ready: **true**.
- Doctor result: **ok**. Stdio reachability checks are skipped by doctor; actual
  discovery was validated separately.
- Current local health/admin base: `http://127.0.0.1:62763`; `/healthz` and `/readyz`
  returned 200 (`live`, `ready`). Use the runtime status to obtain future ports.
- **Tunneled discovery:** Responses API produced an `mcp_list_tools` result with
  **311 tools** and no error. This request disabled tool execution. The overall
  model response hit its small output limit after successful discovery; the tool
  list itself completed.
- **Tunneled READ:** `list_projects` completed successfully and returned 3 saved
  projects. `get_editor_state` reached OpenReel but returned `No project is open`.
- Local `list_tracks` and `list_clips` also returned `No project is open`.
- No write/edit, split, export, publishing or project-opening tool was invoked.
- ChatGPT plugin **Astel OpenReel** was created and connected after explicit
  approval. Its detail page shows **Connected** and **Try in chat**.
  Plugin URL: https://chatgpt.com/plugins/plugin_asdk_app_6ac56bfb439481918b56f0ebca892670
- Tool count and project READ were verified through the Responses API; a READ
  within a ChatGPT chat is the next end-to-end product check.

## Network and credential boundary

OpenAI products → OpenAI Secure MCP Tunnel → outbound polling tunnel-client on
this Mac → official OpenReel stdio shim → authenticated loopback Desktop MCP.
No public listener or direct exposure of localhost is used. Health/admin binding
is loopback-only. Raw HTTP logging is disabled.

An **existing** OpenAI API key was reused after explicit approval. No new key was
created. The approved checkout-local `.env.local` stores `OPENAI_API_KEY`, has mode
0600, is excluded by `.gitignore`, and is untracked. The launch helper reads it
without shell sourcing or echoing it, and gives the runtime an environment-only
`CONTROL_PLANE_API_KEY`. No key appears in command arguments or profile content.

The official OpenReel shim reads `~/.openreel/mcp-endpoint.json` itself; that file
is written by OpenReel with mode 0600 and contains its current URL/token. Do not
copy or print it. The bearer token is not embedded in tunnel configuration.
An exact-value scan of tracked files and the Astel tunnel configuration/logs found
neither credential. Never commit or paste credentials, even while troubleshooting.

## Working launcher

Start OpenReel Desktop first, then run from this feature checkout:

```bash
./scripts/openreel_secure_tunnel_mac.sh
```

The default path uses `scripts/openreel_tunnel_connect_mac.py`: validate the ignored
owner-only credential file, reuse the managed runtime, run doctor, and check health.
Credentials stay in memory/environment; CLI output is restricted to safe summaries.
The legacy direct-HTTP setup is available with `OPENREEL_TUNNEL_TRANSPORT=http`, but
requires configuring the current URL and appropriate local Authorization reference.
The shim is preferred because it follows port changes and token rotation.

The native CLI commands used were:

```bash
tunnel-client help quickstart
tunnel-client runtimes connect \
  --alias astel-openreel \
  --profile astel-openreel \
  --tunnel-id tunnel_6ac566f1fac08191b548240633db227d \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-command '/usr/local/bin/node /Applications/OpenReel.app/Contents/Resources/app.asar.unpacked/dist/mcp-shim/index.js'
tunnel-client doctor --profile astel-openreel --explain --json
tunnel-client runtimes status astel-openreel --json
```

The helper injects the runtime key and `HEALTH_LISTEN_ADDR=127.0.0.1:0` privately
before these commands. Do not run a second foreground daemon for the same tunnel.
Do not use nohup/disown. Keep OpenReel and the managed tunnel running while testing.
For a restart, use the launcher so the environment-only credential is loaded again.

## ChatGPT connection and remaining acceptance

In ChatGPT Plugins → plus → Add custom MCP server, name it **Astel OpenReel**,
choose Connection: Tunnel, and select the tunnel ID above. This tunnel uses the
local authenticated shim; do not paste a loopback URL or API key into ChatGPT.
Review the final creation/access confirmation in the UI.

Keep tool approvals enabled. The description's read-only wording is not a
transport-level write filter: the upstream still advertises all 311 tools.
For API validation, allow only the exact READ tool being tested. The completed
READ requests allowed only `list_projects` or only `get_editor_state`; no mutation
was available to those requests.

Oleg should open the intended existing project in OpenReel. Then verify
`get_editor_state`, `list_tracks`, `list_clips` and selection through the tunnel.
Do not claim current-timeline success until those READ calls return actual data.
The 3 saved projects were two named `Vertical` and one named
`Astel OpenReel Stage 1 — synthetic validation`.

## Split test: separate approval required

After successful timeline READ, prepare an exact split request using the discovered
schema, project/track/selected clip IDs and an interior split time. Verify a working
undo operation first; show the target and time to Oleg. Do not execute the split
without separate approval. No export, publishing or broad auto-approval is included.

## Official references

- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels)
- [Latest official tunnel-client release](https://github.com/openai/tunnel-client/releases/latest)
- [ChatGPT custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)
- [OpenReel Desktop releases](https://github.com/Augani/openreel-video/releases)
- [OpenReel external-agent setup](https://github.com/Augani/openreel-video/blob/main/docs/AGENT-GUIDE.md)

Commands were checked against installed CLI help. Resolve latest releases and
verify official digests when reinstalling; recorded versions are evidence, not a
future version pin.
