"""Run the TypeScript client against two real servers sharing an isolated database."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


STATION = Path(__file__).resolve().parents[2]
WORKSPACE = STATION.parent
NODE = WORKSPACE / ".junction-setup" / "node" / "bin" / "node"
SMOKE = Path(__file__).with_name("smoke.ts")
REPORT = STATION / "web-client" / "verification" / "http-smoke.json"
PREFIX = "http-smoke"
LIVE_SESSION = f"{PREFIX}:live-session"


def main() -> None:
    report: dict = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "evidenceType": "Real local HTTP and deterministic simulation; no physical hardware or provider calls.",
        "isolatedTemporaryDatabase": True,
        "serverStarts": 0,
        "phases": [],
        "backgroundServerLeftRunning": False,
    }
    secret = ""
    try:
        with tempfile.TemporaryDirectory(prefix="morph-web-client-") as directory:
            temporary = Path(directory)
            env = {**os.environ, "PYTHONPATH": str(STATION), "MORPH_DATA_DIR": directory}
            for key in ("MORPH_API_TOKEN", "MORPH_TOKEN_FILE", "MORPH_DB_PATH", "MORPH_EVIDENCE_DIR"):
                env.pop(key, None)

            def cli(*args: str) -> str:
                result = subprocess.run(
                    [sys.executable, "-m", "morph_station", *args], env=env, cwd=STATION,
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode:
                    detail = (result.stderr or result.stdout)[-3000:]
                    if secret:
                        detail = detail.replace(secret, "[redacted]")
                    raise RuntimeError(f"Fixture CLI failed: {detail}")
                return result.stdout

            cli("init")
            first_seed = json.loads(cli("seed-demo", "--prefix", PREFIX))
            repeated_seed = json.loads(cli("seed-demo", "--prefix", PREFIX))
            assert first_seed["snapshot"]["lastEventSequence"] == repeated_seed["snapshot"]["lastEventSequence"]
            secret = (temporary / "api-token").read_text(encoding="utf-8").strip()

            # An explicit fixture creates an empty real-data session. Test reads below
            # must not add any records to this session or to the simulation.
            sys.path.insert(0, str(STATION))
            from morph_station.models import RecordWrite
            from morph_station.store import StationStore

            seeded = StationStore(temporary / "station.sqlite3", evidence_dir=temporary / "evidence")
            seeded.upsert(RecordWrite(
                eventId=f"{LIVE_SESSION}:created", recordType="session",
                record={"id": LIVE_SESSION, "name": "Empty live-data smoke fixture", "sourceMode": "live",
                        "startedAt": "2026-11-14T16:00:00+00:00", "configId": f"{PREFIX}:live-config"},
            ))
            expected_sequence = seeded.latest_sequence()
            resume_after = 0
            report.update({"simulationSeedRepeatedWithoutNewEvents": True,
                           "eventCountBeforeReads": expected_sequence})

            for phase in ("initial", "after-restart"):
                with socket.socket() as available:
                    available.bind(("127.0.0.1", 0))
                    port = available.getsockname()[1]
                base = f"http://127.0.0.1:{port}"
                with (temporary / f"{phase}-server.log").open("w", encoding="utf-8") as server_log:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "morph_station", "serve", "--host", "127.0.0.1", "--port", str(port)],
                        env=env, cwd=STATION, stdout=server_log, stderr=subprocess.STDOUT,
                    )
                    report["serverStarts"] += 1
                    report["backgroundServerLeftRunning"] = True
                    try:
                        for _ in range(150):
                            if process.poll() is not None:
                                raise RuntimeError("Station server exited during startup.")
                            try:
                                with urlopen(base + "/health", timeout=0.5) as response:
                                    if response.status == 200:
                                        break
                            except (URLError, TimeoutError):
                                pass
                            time.sleep(0.05)
                        else:
                            raise RuntimeError("Station server did not become healthy.")

                        phase_report = temporary / f"{phase}.json"
                        node_env = {
                            **env, "MORPH_SMOKE_BASE_URL": base, "MORPH_SMOKE_TOKEN": secret,
                            "MORPH_SMOKE_PREFIX": PREFIX, "MORPH_SMOKE_SESSION_ID": f"{PREFIX}:session",
                            "MORPH_SMOKE_LIVE_SESSION_ID": LIVE_SESSION, "MORPH_SMOKE_PHASE": phase,
                            "MORPH_SMOKE_EXPECTED_SEQUENCE": str(expected_sequence),
                            "MORPH_SMOKE_RESUME_AFTER": str(resume_after),
                            "MORPH_SMOKE_REPORT_PATH": str(phase_report),
                        }
                        result = subprocess.run([str(NODE), str(SMOKE)], env=node_env, cwd=STATION,
                                                capture_output=True, text=True, timeout=90)
                        if result.returncode:
                            detail = (result.stderr + result.stdout).replace(secret, "[redacted]")[-5000:]
                            raise RuntimeError(f"TypeScript {phase} smoke failed: {detail}")
                        checked = json.loads(phase_report.read_text(encoding="utf-8"))
                        assert checked["status"] == "passed"
                        assert checked["eventCountAfterReads"] == expected_sequence
                        report["phases"].append(checked)
                        resume_after = checked["resumeCursor"]

                        request = Request(base + "/api/v1/station/snapshot", headers={"Authorization": "Bearer " + secret})
                        with urlopen(request, timeout=5) as response:
                            authoritative = json.load(response)
                        assert authoritative["lastEventSequence"] == expected_sequence
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                        report["backgroundServerLeftRunning"] = False

            assert seeded.latest_sequence() == expected_sequence
            report.update({"status": "passed", "eventCountAfterRestartAndReads": expected_sequence,
                           "restartPreservedRecords": True, "readOnlyMountRefreshReconnect": True,
                           "simulationCorrectCycles": {"numerator": 2, "denominator": 4},
                           "simulationSuccessfulAttempts": {"numerator": 3, "denominator": 5},
                           "liveFinishedCycleDenominator": 0})
    except Exception as error:
        message = str(error)
        report.update({"status": "failed", "error": message.replace(secret, "[redacted]") if secret else message})
        raise
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
