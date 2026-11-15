"""Real CLI shutdown with an open event stream, using only temporary records."""

import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import time

import pytest

import morph_station
from morph_station.models import RecordWrite
from morph_station.store import StationStore


def ledger_digest(database):
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        dump = "\n".join(connection.iterdump())
    return hashlib.sha256(dump.encode()).hexdigest()


@pytest.mark.skipif(sys.platform == "win32", reason="The CLI shutdown contract uses POSIX SIGTERM.")
def test_cli_sigterm_bounds_open_sse_and_preserves_records(tmp_path, record_property):
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    database = data / "station.sqlite3"
    store = StationStore(database, data / "evidence")
    store.upsert(RecordWrite(eventId="shutdown-session-created", recordType="session", record={
        "id": "shutdown-session", "name": "Isolated shutdown regression", "sourceMode": "simulation",
        "startedAt": "2026-11-15T00:00:00Z", "configId": "shutdown-test", "robotId": None, "modelRuns": [],
    }))
    store.upsert(RecordWrite(eventId="shutdown-cycle-created", recordType="cycle", record={
        "id": "shutdown-cycle", "sessionId": "shutdown-session", "objectId": "synthetic-object",
        "startedAt": "2026-11-15T00:00:01Z",
    }))
    before = ledger_digest(database)
    token = secrets.token_urlsafe(48)
    token_file = data / "api-token"
    token_file.write_text(token + "\n")
    token_file.chmod(0o600)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    station = Path(morph_station.__file__).resolve().parent.parent
    # An explicit environment prevents provider or real-station configuration
    # from entering this disposable subprocess.
    environment = {
        "PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONPATH": str(station),
        "PYTHONDONTWRITEBYTECODE": "1", "MORPH_DATA_DIR": str(data),
        "MORPH_TOKEN_FILE": str(token_file),
    }
    stream = None
    response = None
    with (tmp_path / "station.log").open("wb") as output:
        process = subprocess.Popen(
            [sys.executable, "-B", "-m", "morph_station", "serve", "--host", "127.0.0.1", "--port", str(port)],
            cwd=tmp_path, env=environment, stdin=subprocess.DEVNULL,
            stdout=output, stderr=output, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                assert process.poll() is None, "Isolated CLI exited before readiness"
                health = http.client.HTTPConnection("127.0.0.1", port, timeout=0.25)
                try:
                    health.request("GET", "/health")
                    reply = health.getresponse()
                    assert reply.status == 200
                    assert json.loads(reply.read())["hardwareIntegrated"] is False
                    break
                except (OSError, http.client.HTTPException):
                    assert time.monotonic() < deadline, "Isolated CLI readiness timed out"
                    time.sleep(0.05)
                finally:
                    health.close()
            stream = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            stream.request("GET", "/api/v1/events?after=0", headers={"Authorization": "Bearer " + token})
            response = stream.getresponse()
            assert response.status == 200
            assert response.getheader("Content-Type").startswith("text/event-stream")
            assert response.readline().startswith(b"id: ")
            assert not response.isclosed()
            started = time.monotonic()
            process.send_signal(signal.SIGTERM)
            # Keep the SSE response open during the entire wait. Closing it
            # first would hide the original unbounded graceful-drain defect.
            result = process.wait(timeout=15)
            elapsed = time.monotonic() - started
            record_property("sigtermExitSeconds", round(elapsed, 3))
            record_property("processReturnCode", result)
            assert result in (0, -signal.SIGTERM)
            assert elapsed < 15
            assert ledger_digest(database) == before
            record_property("canonicalRecordsUnchanged", True)
            assert list((data / "analysis" / "requests").glob("*.json")) == []
        finally:
            if response is not None:
                response.close()
            if stream is not None:
                stream.close()
            if process.poll() is None:
                # Close the owned client first, allowing even the previous
                # unbounded server to finish. Never target another process.
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=5)
