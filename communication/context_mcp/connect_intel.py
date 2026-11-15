#!/usr/bin/env python3
"""Connect Intel to the shared Mac context; use --project for the transferred project directory."""
import argparse
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("The MCP endpoint redirected; refusing to forward its access token")


def check_connection(connection, folder):
    tls = ssl.create_default_context(cafile=str(folder / "morph-ca.pem"))
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=tls))
    headers = {"Authorization": "Bearer " + connection["token"], "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    def request(payload):
        req = urllib.request.Request(connection["url"], data=json.dumps(payload).encode(), headers=headers)
        with opener.open(req, timeout=20) as response:
            body = response.read()
            result = json.loads(body) if body else {}
            if "error" in result:
                raise RuntimeError("MCP returned error: " + str(result["error"]))
            return result

    hello = request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "morph-intel-pairing-check", "version": "1.0"}}})
    headers["MCP-Protocol-Version"] = hello["result"]["protocolVersion"]
    request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    result = request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_project_context", "arguments": {}}})
    if result.get("result", {}).get("isError"):
        raise RuntimeError("Connected, but get_project_context returned a tool error")
    context = result.get("result", {}).get("structuredContent", {})
    if not context.get("overview", {}).get("content"):
        raise RuntimeError("Connected, but the shared overview was missing")
    print("Verified HTTPS, authentication, MCP initialization and get_project_context.")
    print("Server:", hello["result"]["serverInfo"]["name"])
    return {"server": hello["result"]["serverInfo"]["name"], "protocol": headers["MCP-Protocol-Version"], "overview_characters": context["overview"]["total_characters"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check only; do not configure or launch Codex")
    parser.add_argument("--folder", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--project", type=Path, help="Project directory containing AGENTS.md; Codex starts here")
    args = parser.parse_args()
    folder = args.folder.resolve()
    project = args.project.resolve() if args.project else Path.cwd()
    if args.project and not (project / "AGENTS.md").is_file():
        raise SystemExit("The --project directory must contain the transferred project's AGENTS.md.")
    connection = json.loads((folder / "connection.json").read_text())
    try:
        check_connection(connection, folder)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise SystemExit("Connection check failed: " + str(error) + ". Check Wi-Fi, Mac server, certificate expiry and network client isolation.")
    if args.check:
        return
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("Connection works. Install Codex CLI on Intel, then run this script again.")
    env = {**os.environ, "MORPH_CONTEXT_TOKEN": connection["token"], "CODEX_CA_CERTIFICATE": str(folder / "morph-ca.pem")}
    existing = subprocess.run([codex, "mcp", "get", "morph_context", "--json"], capture_output=True, text=True, env=env, cwd=project)
    if existing.returncode == 0:
        try:
            config = json.loads(existing.stdout)
            transport = config.get("transport", config)
            if transport.get("url") != connection["url"] or transport.get("bearer_token_env_var") != "MORPH_CONTEXT_TOKEN":
                raise SystemExit("An existing morph_context configuration differs. Review it before replacing it; no changes made.")
        except json.JSONDecodeError:
            raise SystemExit("Cannot verify existing morph_context configuration; no changes made.")
    else:
        subprocess.run([codex, "mcp", "add", "morph_context", "--url", connection["url"], "--bearer-token-env-var", "MORPH_CONTEXT_TOKEN"], env=env, cwd=project, check=True)
    print("Launching Codex with the shared context. Use this launcher again for future sessions.")
    subprocess.run([codex, "Read the local AGENTS.md and context/INTEL_CODEX.md. Use morph_context.get_project_context and read_context to read the shared Mac context, including context/INTEL_CODEX.md and the latest handoffs. Follow the Intel reporting instructions: publish and read back a session_start note before substantive work, record meaningful changes/tests/blockers and end-of-session progress, preserve unsynchronized payloads for same-UUID retry, and update the existing Notion tasks. Distinguish Intel-local files from evidence actually shared with the Mac."], env=env, cwd=project, check=True)


if __name__ == "__main__":
    main()
