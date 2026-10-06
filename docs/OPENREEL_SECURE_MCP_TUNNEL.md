# ChatGPT ↔ OpenReel via OpenAI Secure MCP Tunnel

## Status checked on 2026-10-06

Setup is **prepared, not connected**. Do not treat the previous report of 311
OpenReel tools as a current discovery result.

- Feature branch: `feat/opencut-kevin-live-editor`.
- `http://127.0.0.1:58187/mcp` refused connections; no listener was found there.
- No running OpenReel process or installed OpenReel application was found in the
  inspected Applications, Downloads and Documents locations on this Mac.
- Official `tunnel-client` installed at `/opt/homebrew/bin/tunnel-client`:
  `0.0.15+a390c168ff1b2d14e73a95991c186c6aba3ff5a0`.
- Darwin arm64 release ZIP SHA-256 matched GitHub release metadata:
  `b2cae3aa9df45b4c2fe9b1d700ebacce39f9feb6a6b46b86e6499f9a51bf72ff`.
- Platform Create tunnel form prepared as **Astel OpenReel**, with the Personal
  organization and the available ChatGPT workspace selected. Final Create is
  pending the account owner's action. No Astel tunnel ID exists yet.
- No runtime credential was found in the current environment or conventional
  `.env` / `.env.local` files in the existing local checkout. No key was created.
- CLI quickstart/help and HTTP sample were inspected. Profile generation passed
  using a disposable placeholder tunnel ID; this does **not** validate a real tunnel.
- Shell syntax passed. Launcher failed safely at local reachability (exit 3).
- Tunnel doctor, runtime health, tunneled discovery and timeline READ remain pending.
- No editor mutations, split, export or publishing were executed.

## Official sources

Checked against the live [Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
and installed client help, rather than relying on the original draft.

- [Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels)
- [Latest official release](https://github.com/openai/tunnel-client/releases/latest)
- [Custom MCP server guide](https://developers.openai.com/api/docs/guides/custom-mcp-server)

Always resolve the latest release and verify its digest before installing the
matching Mac architecture. The version above records this check, not a future pin.

## Private network boundary

ChatGPT → OpenAI tunnel service → outbound HTTPS polling by `tunnel-client`
→ loopback OpenReel MCP → active project. No public ingress or direct localhost
exposure is required. Do not use a public forwarding service as a fallback.
Keep health/admin endpoints loopback-only and raw HTTP logging disabled.

## Account owner step

Open Platform tunnel settings. The prepared form uses name **Astel OpenReel**.
Review the selected organization and ChatGPT workspace, then press **Create**.
Creating/editing requires Tunnels Read + Manage; running/selecting requires
Tunnels Read + Use. The runtime credential principal needs those runtime rights.
Associating only the Platform organization does not guarantee ChatGPT visibility.

After creation, the tunnel ID may be shared: it is an identifier, not a credential.
Do not paste API keys or OpenReel bearer tokens into chat.

## Credentials

Use the secure local OpenAI Platform setup flow when a runtime key is needed.
Store it only in an owner-readable file outside every Git checkout, or keep it
in the process environment. Do not type a literal key into shell history.
Never give an admin key to the runtime daemon.

The launcher accepts either `CONTROL_PLANE_API_KEY` already present in its
local environment or a reference to an existing private file:

```bash
export OPENREEL_RUNTIME_KEY_REF='file:/absolute/private/path/runtime-key'
export OPENREEL_TUNNEL_ID='tunnel_<actual-id>'
export OPENREEL_MCP_URL='http://127.0.0.1:<current-port>/mcp'
./scripts/openreel_secure_tunnel_mac.sh
```

The file contains only the runtime key; use owner-only permissions (0600).
No secret is embedded in the profile. No credential file was written in this run.
If OpenReel requires a static bearer header, provision the complete header locally
as `OPENREEL_AUTHORIZATION` using a hidden prompt or secure setup. The launcher
passes only its environment reference for forwarding and discovery.

## Commands checked against v0.0.15

```bash
tunnel-client --version
tunnel-client help quickstart
tunnel-client profiles samples show sample_mcp_remote_no_auth

tunnel-client init \
  --sample sample_mcp_remote_no_auth \
  --profile astel-openreel \
  --tunnel-id "$OPENREEL_TUNNEL_ID" \
  --control-plane-api-key-ref "$OPENREEL_RUNTIME_KEY_REF" \
  --mcp-server-url "$OPENREEL_MCP_URL" \
  --health-listen-addr 127.0.0.1:0

tunnel-client doctor --profile astel-openreel --explain
tunnel-client run --profile astel-openreel
```

Use `env:CONTROL_PLANE_API_KEY` as the key reference for environment-only setup.
Explicitly select the HTTP no-OAuth sample: `init` otherwise defaults to the
DCR sample for an HTTP target. If OpenReel advertises OAuth, inspect that contract
and choose the corresponding sample instead. Do not overwrite existing profiles
automatically. For an existing profile, inspect it locally and run doctor/run.
With bearer auth, both doctor and run also need:

```bash
--mcp.extra-headers 'Authorization: env:OPENREEL_AUTHORIZATION' \
--mcp.discovery-extra-headers 'Authorization: env:OPENREEL_AUTHORIZATION'
```

For a long-lived agent-managed runtime, the official client provides supervision:

```bash
tunnel-client runtimes connect \
  --alias astel-openreel \
  --profile astel-openreel \
  --tunnel-id "$OPENREEL_TUNNEL_ID" \
  --runtime-api-key "$OPENREEL_RUNTIME_KEY_REF" \
  --mcp-server-url "$OPENREEL_MCP_URL"
tunnel-client runtimes status astel-openreel --json
```

Review generated configuration before using this alternative, especially health
binding and OpenReel authentication. Do not use `nohup` or `disown` for supervision.
Do not report success until process_running, healthy and ready are confirmed.

## Discovery and READ acceptance

1. Start OpenReel Desktop and verify its current Settings → MCP URL and auth mode.
2. Locally initialize MCP, send notifications/initialized, then tools/list,
   including pagination. Inspect actual input schemas and read annotations.
3. Run doctor successfully and keep the real tunnel client running. Check its
   actual local `/healthz`, `/readyz` and `/ui` endpoints; startup alone is insufficient.
4. In ChatGPT Plugins → plus → Add custom MCP server, choose Connection: Tunnel,
   select Astel OpenReel, review authentication and create the private plugin.
   Workspace UI creation/permissions require the owner's confirmation.
5. Verify tools/list through that tunnel. Record the actual discovered count.
6. Call only verified READ tools for editor state, active project, tracks, clips
   and selection. Record successful results without media or credential dumps.

A local tools/list is not proof of tunneled discovery. Doctor/health are not proof
of a successful current-timeline READ. This run did not reach either acceptance check.
The form description and these instructions are not a transport-level write filter;
keep approvals enabled and do not invoke mutation tools during validation.

## Reversible split test (pending READ and separate approval)

After a successful READ, prepare one exact split request using the discovered
schema, selected clip ID, track ID, project identity and an interior split time.
Show Oleg the clip and time before requesting approval. Do not execute yet.
Re-read selection immediately before an approved split and abort if it changed.
First verify the editor's actual undo operation/transaction behavior; do not assume
split is reversible without that evidence. After approval, split once, verify the
two resulting clips and undo once to restore the original timeline. No export,
publishing or broad auto-approval is part of this test.
