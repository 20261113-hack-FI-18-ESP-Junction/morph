#!/usr/bin/env python3
"""Read-only bundle/runtime check. No installation, credentials, network or robot I/O."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def version(command: str) -> dict:
    executable = shutil.which(command)
    if not executable:
        return {"available": False, "version": None}
    try:
        result = subprocess.run([executable, "--version"], capture_output=True,
                                text=True, timeout=10, check=False)
        raw = (result.stdout or result.stderr).strip().splitlines()
        match = re.search(r"\b[vV]?(\d+)\.(\d+)(?:\.(\d+))?", raw[0] if raw else "")
        return {"available": result.returncode == 0,
                "version": ".".join(part or "0" for part in match.groups()) if match else None}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "version": None}


def listening_ports() -> dict:
    ports = {3000: None, 8000: None, 7860: None}
    if platform.system() != "Linux":
        return {str(port): "unknown (Linux /proc check only)" for port in ports}
    observed = set()
    readable = False
    for name in ("tcp", "tcp6"):
        try:
            lines = Path("/proc/net", name).read_text().splitlines()[1:]
        except OSError:
            continue
        readable = True
        for line in lines:
            fields = line.split()
            if len(fields) > 3 and fields[3] == "0A":
                observed.add(int(fields[1].rsplit(":", 1)[1], 16))
    return {str(port): ("listening" if port in observed else "not observed listening")
            if readable else "unknown" for port in ports}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--require-linux", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    required = (
        "HachingJunction/AGENTS.md", "HachingJunction/station/run.sh",
        "HachingJunction/station/requirements.txt", "HachingJunction/station/web-client/package.json",
        "HachingJunction/station/web-client/tsconfig.json", "morph-station/package.json",
        "morph-station/package-lock.json", "morph-station/server.ts",
    )
    missing = [name for name in required if not (root / name).is_file()]
    runtimes = {name: version(name) for name in ("python3.12", "node", "npm")}
    failures = [f"Missing bundle file: {name}" for name in missing]
    for name, info in runtimes.items():
        if not info["available"]:
            failures.append(f"{name} is not available on PATH.")
    node_version = runtimes["node"]["version"]
    if node_version and tuple(map(int, node_version.split("."))) < (22, 12, 0):
        failures.append("This runbook selects Node >=22.12.0; prefer the existing Node 24 toolchain.")
    if args.require_linux and platform.system() != "Linux":
        failures.append("This is not a Linux host.")
    dependency = None
    try:
        dependency = json.loads((root / "morph-station/package.json").read_text())["dependencies"]["@morph/station-client"]
        if dependency != "file:../HachingJunction/station/web-client":
            failures.append("Local station client dependency differs from the documented sibling layout.")
    except (OSError, ValueError, KeyError):
        failures.append("Cannot verify the local station client dependency.")
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "evidence_kind": "read_only_bundle_and_runtime_preflight",
        "system": platform.system(), "architecture": platform.machine(),
        "root": str(root), "runtimes": runtimes, "missing_files": missing,
        "local_dependency": dependency, "tcp_ports": listening_ports(),
        "present_environment_overrides": [key for key in (
            "MORPH_PYTHON", "MORPH_DATA_DIR", "MORPH_DB_PATH", "MORPH_EVIDENCE_DIR",
            "MORPH_TOKEN_FILE", "MORPH_API_TOKEN", "MORPH_STATION_ORIGIN", "PORT",
        ) if key in os.environ],
        "hardware_or_provider_verified": False,
        "notes": [
            "No files were changed; no network requests, camera/serial access or movement occurred.",
            "A free-looking port can change after this check; inspect an occupied port before starting servers.",
            "Environment override names are reported without their values; inspect intended use privately.",
            "Passing this check does not verify the assigned Intel hardware or installed application dependencies.",
        ],
        "passed": not failures, "failures": failures,
    }
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
