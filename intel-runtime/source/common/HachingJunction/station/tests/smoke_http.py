"""Real HTTP/CLI restart check. Run from station with the prepared Python."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "verification"


def run():
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="morph-http-") as directory:
        env = {**os.environ, "PYTHONPATH": str(ROOT), "MORPH_DATA_DIR": directory}
        for key in ("MORPH_API_TOKEN", "MORPH_TOKEN_FILE", "MORPH_DB_PATH", "MORPH_EVIDENCE_DIR"):
            env.pop(key, None)

        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "morph_station", *args],
                                    env=env, cwd=ROOT, capture_output=True, text=True, check=True)
            return result.stdout

        cli("init")
        first_seed = json.loads(cli("seed-demo"))
        second_seed = json.loads(cli("seed-demo"))
        assert first_seed["snapshot"]["lastEventSequence"] == second_seed["snapshot"]["lastEventSequence"]
        secret = (Path(directory) / "api-token").read_text().strip()
        headers = {"Authorization": "Bearer " + secret}
        snapshots = []
        for restart in range(2):
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            process = subprocess.Popen([sys.executable, "-m", "morph_station", "serve", "--port", str(port)],
                                       env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                with httpx.Client(base_url=base, timeout=5) as client:
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError("Station server exited during startup")
                        try:
                            if client.get("/health").status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        time.sleep(0.05)
                    else:
                        raise RuntimeError("Station server failed to start")

                    assert client.get("/api/v1/sessions").status_code == 401
                    snapshot_response = client.get("/api/v1/station/snapshot", headers=headers)
                    snapshot_response.raise_for_status()
                    snapshot = snapshot_response.json()
                    snapshots.append(snapshot)
                    schema = client.get("/api/v1/schema", headers=headers)
                    schema.raise_for_status()
                    live_metrics = client.get("/api/v1/metrics", headers=headers).json()
                    assert live_metrics["endToEnd"]["denominator"] == 0
                    assert live_metrics["endToEnd"]["value"] is None
                    metrics = client.get("/api/v1/metrics?includeSimulation=true", headers=headers).json()
                    assert (metrics["endToEnd"]["numerator"], metrics["endToEnd"]["denominator"]) == (2, 4)
                    assert (metrics["physicalExecution"]["numerator"], metrics["physicalExecution"]["denominator"]) == (3, 5)
                    assert (metrics["retries"], metrics["additionalInspections"], metrics["recoveredCycles"]) == (1, 1, 1)
                    trace = client.get("/api/v1/cycles/demo:retry", headers=headers).json()
                    assert len(trace["attempts"]) == 2 and len(trace["inspections"]) == 2
                    assert trace["cycle"]["outcome"] == "correct"
                    assert client.post("/api/v1/commands", headers=headers, json={}).status_code == 503
                    before = snapshot["lastEventSequence"]
                    events_response = client.get("/api/v1/events?after=0&once=true&limit=1000", headers=headers)
                    events_response.raise_for_status()
                    events = [json.loads(line[6:]) for line in events_response.text.splitlines() if line.startswith("data: ")]
                    assert len(events) == before
                    assert [e["sequence"] for e in events] == list(range(1, before + 1))
                    caught = client.get("/api/v1/events?once=true", headers={**headers, "Last-Event-ID": str(before)})
                    assert caught.status_code == 200 and "data:" not in caught.text
                    exported = client.get("/api/v1/sessions/demo:session/export", headers=headers).json()
                    assert len(exported["records"]["cycle"]) == 5
                    csv_response = client.get("/api/v1/sessions/demo:session/export?format=csv", headers=headers)
                    csv_response.raise_for_status()
                    assert len(csv_response.text.splitlines()) > 50
                    assert client.get("/api/v1/station/snapshot", headers=headers).json()["lastEventSequence"] == before
                    # Also exercise the documented token-file CLI client over actual HTTP.
                    cli_snapshot = json.loads(cli("request", "/api/v1/station/snapshot", "--url", base))
                    assert cli_snapshot["lastEventSequence"] == before
                    if restart == 1:
                        artifacts = {"sample-snapshot.json": snapshot, "sample-events.json": events,
                                     "sample-cycle-retry.json": trace, "sample-export.json": exported,
                                     "api-schema.json": schema.json()}
                        for name, value in artifacts.items():
                            (OUTPUT / name).write_text(json.dumps(value, indent=2) + "\n")
                        (OUTPUT / "sample-export.csv").write_text(csv_response.text)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        assert snapshots[0]["lastEventSequence"] == snapshots[1]["lastEventSequence"] == 50
        assert snapshots[0]["metrics"] == snapshots[1]["metrics"]
        assert snapshots[0]["session"] == snapshots[1]["session"]
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat(), "status": "passed",
            "evidenceType": "local HTTP and deterministic simulation, no physical hardware",
            "serverStarts": 2, "eventCountBeforeAndAfterRestart": 50,
            "simulationSeedRepeated": True, "readOnlyReplayAndExport": True,
            "unauthenticatedDataRejected": True, "unavailableHardwareCommandRejected": True,
            "simulatedCorrectCycles": {"numerator": 2, "denominator": 4},
            "simulatedSuccessfulAttempts": {"numerator": 3, "denominator": 5},
            "liveMetricDenominator": 0, "backgroundServerLeftRunning": False,
        }
        (OUTPUT / "smoke-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
