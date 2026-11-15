"""Start owned local M16 test services with explicit simulation in a new data directory."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from itertools import count
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-id", required=True)
args = parser.parse_args()
if not args.run_id.replace("-", "").isalnum():
    raise SystemExit("Use an alphanumeric run ID with optional hyphens.")
output = Path(__file__).resolve().parent / "runs" / args.run_id
output.mkdir(parents=True, exist_ok=False)
data = output / "data"
station = root / "HachingJunction/station"
sys.path[:0] = [str(station), str(station / "tests")]
from morph_station.__main__ import initialize
from morph_station.models import RecordWrite
from morph_station.simulation import seed_demo
from morph_station.store import StationStore
from test_store import finished_cycle

env = dict(os.environ)
for key in ("MORPH_API_TOKEN", "MORPH_DB_PATH", "MORPH_EVIDENCE_DIR", "MORPH_DATA_DIR", "MORPH_TOKEN_FILE", "PYTHONPATH"):
    env.pop(key, None)
    os.environ.pop(key, None)
env.update(MORPH_DATA_DIR=str(data), MORPH_TOKEN_FILE=str(data / "api-token"), PYTHONPATH=str(station), PYTHONDONTWRITEBYTECODE="1")
os.environ.update({key: value for key, value in env.items() if key.startswith("MORPH_")})
initialize()
store = StationStore(data / "station.sqlite3")
serial = count(1)

def put(kind, record, *, event_id=None, expected_revision=None):
    record = deepcopy(record)
    record.pop("revision", None)
    return store.upsert(RecordWrite(eventId=event_id or f"m16-fixture-event-{next(serial)}", recordType=kind, record=record, expectedRevision=expected_revision))

finished_cycle(store, put, cycle_id="m16-recovery", session_id="m16-recovery:session", source="simulation", failed_attempts=1, outcome="unverified", attempt_outcome="unverified")
seed_demo(store, prefix="m16-history")
for number in range(7):
    put("cycle", {"id": f"m16-history:pending-{number}", "sessionId": "m16-history:session", "objectId": f"m16-history:pending-object-{number}", "startedAt": f"2026-11-14T16:0{number}:00+00:00", "outcome": "in_progress"})

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

api_port, ui_port = free_port(), free_port()
api = f"http://127.0.0.1:{api_port}"
ui = f"http://127.0.0.1:{ui_port}"
processes = []
try:
    for name, command, cwd, extra in (
        ("api", [sys.executable, "-m", "morph_station", "serve", "--host", "127.0.0.1", "--port", str(api_port)], station, {}),
        ("ui", ["node", "--import", "tsx", "server.ts"], root / "morph-station", {"NODE_ENV": "production", "PORT": str(ui_port), "MORPH_STATION_ORIGIN": api}),
    ):
        with (output / f"{name}.log").open("w") as log:
            process = subprocess.Popen(command, cwd=cwd, env={**env, **extra}, stdout=log, stderr=subprocess.STDOUT)
        processes.append(process)
    for origin, endpoint in ((api, "/health"), (ui, "/api/v1/station/snapshot")):
        for attempt in range(100):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("An owned service exited during startup; inspect its log.")
            try:
                with urlopen(origin + endpoint, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("An owned service did not become ready.")
    result = {"status": "ready", "observedAt": datetime.now(timezone.utc).isoformat(), "uiOrigin": ui, "apiOrigin": api, "output": str(output), "sourceMode": "simulation", "initialEventSequence": store.latest_sequence(), "hardwareOrProvidersUsed": False}
    (output / "services.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    def interrupted(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    while not (output / "stop-requested").exists():
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("An owned test service exited unexpectedly.")
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    (output / "cleanup.json").write_text(json.dumps({"observedAt": datetime.now(timezone.utc).isoformat(), "allOwnedServicesStopped": all(process.poll() is not None for process in processes)}, indent=2) + "\n")
