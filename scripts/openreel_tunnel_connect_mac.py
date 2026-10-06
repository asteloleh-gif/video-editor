#!/usr/bin/env python3
"""Connect the existing Astel tunnel; credentials never enter command arguments."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ALIAS = "astel-openreel"
TUNNEL = "tunnel_6ac566f1fac08191b548240633db227d"
SHIM = Path("/Applications/OpenReel.app/Contents/Resources/app.asar.unpacked/dist/mcp-shim/index.js")


def main():
    credential = ROOT / ".env.local"
    if credential.is_symlink() or not credential.is_file():
        sys.exit("An approved local .env.local credential file is required.")
    if credential.stat().st_mode & 0o077:
        sys.exit("Credential file must have owner-only permissions (0600).")
    if subprocess.run(["git", "check-ignore", "-q", ".env.local"], cwd=ROOT).returncode:
        sys.exit("Credential file must be excluded from Git.")
    if subprocess.check_output(["git", "ls-files", ".env.local"], cwd=ROOT).strip():
        sys.exit("Credential file must not be tracked by Git.")
    match = re.search(r"(?m)^OPENAI_API_KEY=(sk-[A-Za-z0-9_-]+)$", credential.read_text())
    if not match:
        sys.exit("No usable OPENAI_API_KEY in the approved file.")
    key = match.group(1)
    if not SHIM.is_file():
        sys.exit("Install/start official OpenReel Desktop first.")
    endpoint = Path.home() / ".openreel" / "mcp-endpoint.json"
    if not endpoint.is_file():
        sys.exit("OpenReel MCP endpoint descriptor is missing; start OpenReel.")
    descriptor = json.loads(endpoint.read_text())
    # The official shim reads this descriptor itself, including rotated tokens.
    print("OpenReel MCP URL:", descriptor["url"])
    env = os.environ.copy()
    env["CONTROL_PLANE_API_KEY"] = key
    env["HEALTH_LISTEN_ADDR"] = "127.0.0.1:0"

    def cli(*args):
        result = subprocess.run(["tunnel-client", *args], env=env, capture_output=True,
                                text=True, timeout=55)
        if result.returncode:
            # Do not echo CLI output: it may contain upstream diagnostic data.
            sys.exit("tunnel-client command failed: " + args[0] + " (exit " + str(result.returncode) + ")")
        return result.stdout

    snapshot = json.loads(cli("runtimes", "status", ALIAS, "--json"))
    if snapshot.get("process_running") and snapshot.get("tunnel_id") != TUNNEL:
        sys.exit("Alias points at another running tunnel; refusing to replace it.")
    if not snapshot.get("process_running"):
        cli("runtimes", "connect", "--alias", ALIAS, "--profile", ALIAS,
            "--tunnel-id", TUNNEL, "--runtime-api-key", "env:CONTROL_PLANE_API_KEY",
            "--mcp-command", "/usr/local/bin/node " + str(SHIM))
    doctor = json.loads(cli("doctor", "--profile", ALIAS, "--explain", "--json"))
    print("Doctor:", doctor.get("result"))
    snapshot = json.loads(cli("runtimes", "status", ALIAS, "--json"))
    print(json.dumps({k: snapshot.get(k) for k in
                      ["tunnel_id", "process_running", "healthy", "ready", "ui_url"]}))
    if not all(snapshot.get(k) for k in ["process_running", "healthy", "ready"]):
        sys.exit("Runtime has not reached healthy and ready state.")
    base = snapshot["ui_url"].removesuffix("/ui")
    for route in ["/healthz", "/readyz"]:
        with urllib.request.urlopen(base + route, timeout=5) as response:
            print(route, response.status, response.read().decode())
    print("Runtime health is confirmed; verify tool discovery from ChatGPT/API separately.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        sys.exit("Local setup/health check failed; no credential values were printed.")
