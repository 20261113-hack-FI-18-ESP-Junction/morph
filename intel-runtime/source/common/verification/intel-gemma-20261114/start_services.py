"""Start only owned verification services on unused ports with isolated saved records."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
output = Path(sys.argv[1]).resolve()
data = output / "data"
assert (data / "station.sqlite3").is_file()
dist = Path(__file__).resolve().parent / "dist"
assert (dist / "index.html").is_file()
token_file = data / "api-token"
if not token_file.exists():
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(secrets.token_urlsafe(48) + "\n")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


api_port, ui_port = free_port(), free_port()
while ui_port == api_port:
    ui_port = free_port()
config = {"observedAt": datetime.now(timezone.utc).isoformat(), "apiOrigin": f"http://127.0.0.1:{api_port}",
          "uiOrigin": f"http://127.0.0.1:{ui_port}", "dataDirectory": str(data), "distDirectory": str(dist),
          "output": str(output), "sourceMode": "simulation", "hardwareUsed": False,
          "providerCalls": "Only explicit analysis submissions may call hosted Gemma."}
config_file = output / "services.json"
config_file.write_text(json.dumps(config, indent=2) + "\n")
env = {k: v for k, v in os.environ.items() if k not in {"MORPH_API_TOKEN", "MORPH_DB_PATH", "MORPH_EVIDENCE_DIR", "MORPH_DATA_DIR", "MORPH_TOKEN_FILE", "PYTHONPATH"}}
env.update(MORPH_DATA_DIR=str(data), MORPH_TOKEN_FILE=str(token_file), PYTHONPATH=str(ROOT / "HachingJunction/station"), PYTHONDONTWRITEBYTECODE="1")
processes = []
try:
    for name, command, cwd in (
        ("api", [sys.executable, "-B", "-m", "morph_station", "serve", "--host", "127.0.0.1", "--port", str(api_port)], ROOT / "HachingJunction/station"),
        ("ui", ["node", "--import", "tsx", str(Path(__file__).with_name("browser-host.mjs")), str(config_file)], ROOT / "morph-station"),
    ):
        with (output / f"owned-{name}.log").open("w") as log:
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT))
    for origin, route in ((config["apiOrigin"], "/health"), (config["uiOrigin"], "/api/v1/station/snapshot")):
        for _ in range(100):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("An owned verification service exited; inspect its local log.")
            try:
                with urlopen(origin + route, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Owned verification service readiness timed out.")
    print(json.dumps(config, indent=2), flush=True)
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    while not (output / "stop-owned-services").exists():
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("An owned verification service exited unexpectedly.")
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    (output / "owned-services-cleanup.json").write_text(json.dumps({"observedAt": datetime.now(timezone.utc).isoformat(),
        "allOwnedServicesStopped": all(process.poll() is not None for process in processes),
        "existingPorts3001_8000_3000_7860NotRestarted": True}, indent=2) + "\n")
