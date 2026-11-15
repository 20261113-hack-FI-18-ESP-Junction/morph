#!/usr/bin/env python3
"""Explicit disposable simulation using the actual Intel API and dashboard proxy."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib

PACKAGE = Path(__file__).resolve().parents[1]
DASHBOARD = PACKAGE / "dashboard"
STATION = PACKAGE.parent / "intel-runtime/source/common/HachingJunction/station"


def synthetic_png() -> bytes:
    """Draw an obviously synthetic brick diagram, without image dependencies."""
    width, height = 640, 480
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)
        for x in range(width):
            color = (25, 29, 30)
            if x % 40 == 0 or y % 40 == 0:
                color = (35, 41, 41)
            if 122 <= x <= 526 and 162 <= y <= 336:
                color = (65, 43, 34)
            if 112 <= x <= 516 and 144 <= y <= 312:
                color = (164, 94, 53)
                if x < 120 or y < 152:
                    color = (207, 145, 88)
            for cx in (178, 314, 450):
                for cy in (187, 268):
                    distance = ((x - cx) / 39) ** 2 + ((y - cy) / 23) ** 2
                    if distance <= 1:
                        color = (218, 155, 98) if y < cy + 5 else (186, 116, 68)
            pixels.extend(color)
    def chunk(name, value):
        return struct.pack(">I", len(value)) + name + value + struct.pack(">I", zlib.crc32(name + value))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def seed_rich_example(store):
    from morph_station.models import EvidenceUpload, RecordWrite
    from morph_station.simulation import seed_demo

    seeded = seed_demo(store, prefix="local-demo")
    sid, cid = seeded["sessionId"], "local-demo:inspection-example"
    start = datetime.now(timezone.utc) - timedelta(seconds=25)
    stamp = lambda seconds: (start + timedelta(seconds=seconds)).isoformat()
    def write(kind, record, revision=None, tag="create"):
        value = {k: v for k, v in record.items() if k != "revision"}
        return store.upsert(RecordWrite(eventId=f"{record['id']}:{tag}", recordType=kind,
                                       record=value, expectedRevision=revision))["record"]

    # Preserve the earlier incomplete fixture as an unverified finished cycle.
    old = store.get("cycle", "local-demo:in_progress")
    old_end = (datetime.fromisoformat(old["startedAt"]) + timedelta(seconds=20)).isoformat()
    write("cycle", {**old, "outcome": "unverified", "endedAt": old_end}, old["revision"], "close-demo")
    cycle = write("cycle", {"id": cid, "sessionId": sid, "objectId": "synthetic-brick-6",
                             "startedAt": stamp(0), "commandedDestination": "good_bin"})
    scope = {"sessionId": sid, "cycleId": cid}
    evidence_id, frame_id = cid + ":image", cid + ":frame"
    store.put_evidence(EvidenceUpload(id=evidence_id, eventId=evidence_id + ":upload", **scope,
                                     mediaType="image/png", contentBase64=base64.b64encode(synthetic_png()).decode(),
                                     capturedAt=stamp(2)))
    write("frame", {"id": frame_id, **scope, "objectId": cycle["objectId"], "cameraId": "synthetic-diagram-camera",
                    "capturedAt": stamp(2), "receivedAt": stamp(2.03), "width": 640, "height": 480,
                    "evidenceId": evidence_id})
    inspection_model = cid + ":inspection-model"
    write("model_run", {"id": inspection_model, **scope, "provider": "simulation",
                        "modelId": "anomalib-fixture-only", "frameIds": [frame_id],
                        "input": {"source": "Generated brick diagram; not a camera capture"},
                        "output": {"classification": "good", "score": 0.18, "fixture": True},
                        "requestedAt": stamp(3), "completedAt": stamp(3.12), "latencyMs": 120,
                        "device": "simulation", "precision": "not measured"})
    inspection_id = cid + ":inspection"
    write("inspection", {"id": inspection_id, **scope, "objectId": cycle["objectId"], "frameIds": [frame_id],
                         "modelRunId": inspection_model, "score": 0.18, "threshold": 0.5,
                         "classification": "good", "requestedAt": stamp(3), "completedAt": stamp(3.12)})
    for name, output, elapsed in (("nemotron", {"observations": ["Synthetic fixture: a six-stud brick diagram is centered in the inspection view."],
                                               "hypotheses": [], "uncertainty": "Generated fixture; no visual provider was invoked.",
                                               "fixture": True}, 260),
                                  ("gemini", {"selectedChoice": "route_good", "fixture": True}, 180)):
        write("model_run", {"id": cid + ":" + name, **scope, "provider": "simulation",
                            "modelId": name + "-fixture-only", "frameIds": [frame_id],
                            "input": {"source": "Synthetic demonstration record; no provider invoked"}, "output": output,
                            "requestedAt": stamp(4), "completedAt": stamp(4 + elapsed / 1000), "latencyMs": elapsed})
    decision_id = cid + ":decision"
    write("decision", {"id": decision_id, **scope, "kind": "task", "modelRunId": cid + ":gemini",
                       "offeredChoices": ["inspect_again", "route_good", "route_defective"], "selectedChoice": "route_good",
                       "stateVersion": store.latest_sequence(), "goalVersion": 1, "frameIds": [frame_id],
                       "requestedAt": stamp(4), "completedAt": stamp(4.18), "accepted": True})
    write("utterance", {"id": cid + ":instruction", **scope, "text": "Inspect and sort the synthetic demonstration brick.",
                        "source": "typed", "startedAt": stamp(0), "completedAt": stamp(0.1), "status": "finalized"})
    reference_id = cid + ":reference"
    write("reference_label", {"id": reference_id, **scope, "objectId": cycle["objectId"], "quality": "good",
                              "authorId": "demo-fixture-generator", "method": "Independent synthetic fixture label",
                              "evidenceIds": [evidence_id], "createdAt": stamp(1)})
    first = write("attempt", {"id": cid + ":attempt-1", **scope, "ordinal": 1,
                              "startedAt": stamp(5), "endedAt": stamp(8), "outcome": "failed",
                              "errorCode": "simulated_failed_grasp"})
    second = write("attempt", {"id": cid + ":attempt-2", **scope, "ordinal": 2,
                               "startedAt": stamp(9), "retryOfAttemptId": first["id"],
                               "retryReason": "The previous simulated grasp failed"})
    write("execution", {"id": cid + ":execution", **scope, "attemptId": second["id"], "taskId": "route_good",
                        "policyId": "simulation-only-no-robot", "decisionId": decision_id, "status": "finished",
                        "requestedAt": stamp(9), "acknowledgedAt": stamp(9.1), "finishedAt": stamp(18)})
    confirmation_id = cid + ":confirmation"
    write("confirmation", {"id": confirmation_id, **scope, "source": "operator", "authorId": "demo-fixture-generator",
                           "attemptId": second["id"], "confirmedAt": stamp(19), "physicalSuccess": True,
                           "observedDestination": "good_bin", "evidenceIds": [evidence_id]})
    write("attempt", {**second, "endedAt": stamp(19), "outcome": "successful", "confirmationId": confirmation_id},
          second["revision"], "finish")
    write("cycle", {**cycle, "endedAt": stamp(20), "outcome": "correct", "observedDestination": "good_bin",
                    "referenceLabelId": reference_id, "inspectionId": inspection_id, "confirmationId": confirmation_id},
          cycle["revision"], "finish")


def run_backend():
    runtime = Path(os.environ["MORPH_DEMO_RUNTIME_DIR"])
    if json.loads((runtime / "demo-instance.json").read_text()).get("mode") != "disposable-simulation":
        raise RuntimeError("This backend requires an owned disposable demo directory")
    database = runtime / "station.sqlite3"
    if database.exists():
        raise RuntimeError("Refusing to seed an existing database")
    sys.path.insert(0, str(STATION))
    from morph_station.api import create_app
    import uvicorn

    def disabled_provider(*_args, **_kwargs):
        raise RuntimeError("Provider calls are disabled in the local demo")
    app = create_app(db_path=database, token=(runtime / "api-token").read_text().strip(),
                     evidence_dir=runtime / "evidence", analysis_dir=runtime / "analysis",
                     analysis_provider=disabled_provider)
    seed_rich_example(app.state.store)
    @app.middleware("http")
    async def reads_only(request, call_next):
        if request.method != "GET":
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "The disposable simulation demo permits GET only."},
                                status_code=405, headers={"Allow": "GET"})
        return await call_next(request)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["MORPH_DEMO_API_PORT"]),
                log_level="warning", access_log=False)


def local_port():
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def minimal_environment():
    return {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TMPDIR", "SystemRoot", "WINDIR") if key in os.environ}


def python_executable():
    if os.environ.get("MORPH_DEMO_PYTHON"):
        return os.environ["MORPH_DEMO_PYTHON"]
    for ancestor in PACKAGE.parents:
        prepared = ancestor / ".junction-setup/python/bin/python"
        if prepared.is_file():
            return str(prepared)
    return sys.executable


def wait_ready(url, children, *, token=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in children):
            raise RuntimeError("A demo process stopped before it became ready")
        try:
            headers = {"Authorization": "Bearer " + token} if token else {}
            with opener.open(urllib.request.Request(url, headers=headers), timeout=1) as response:
                return json.loads(response.read())
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise RuntimeError("The local demo did not become ready within 30 seconds")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3101, help="Loopback dashboard port (default: 3101)")
    parser.add_argument("--media-config", type=Path, help="Explicit private configuration for loopback simulation video only")
    parser.add_argument("--backend", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.backend:
        run_backend()
        return 0
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    media_config = str(args.media_config.resolve(strict=True)) if args.media_config else None
    tsx = DASHBOARD / "node_modules/.bin/tsx"
    if not tsx.is_file():
        parser.error("Install the dashboard dependencies before running the demo")
    try:
        with socket.socket() as check:
            check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            check.bind(("127.0.0.1", args.port))
    except OSError:
        parser.error("The dashboard port is already in use; choose a different --port")
    children = []
    stopping = False
    def stop(_signal, _frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix="morph-disposable-demo-") as directory:
        runtime = Path(directory)
        (runtime / "demo-instance.json").write_text(json.dumps({"mode": "disposable-simulation"}))
        token = secrets.token_urlsafe(48)
        token_file = runtime / "api-token"
        token_file.touch(mode=0o600)
        token_file.write_text(token)
        api_port = local_port()
        environment = {**minimal_environment(), "MORPH_DEMO_RUNTIME_DIR": str(runtime),
                       "MORPH_DEMO_API_PORT": str(api_port), "MORPH_DEMO_PORT": str(args.port),
                       "MORPH_DEMO_ORIGIN": f"http://127.0.0.1:{api_port}",
                       "MORPH_DEMO_TOKEN_FILE": str(token_file), "MORPH_DEMO_MODE": "1",
                       "DISABLE_HMR": "true", "NODE_ENV": "development"}
        with (runtime / "backend.log").open("w+") as backend_log, (runtime / "dashboard.log").open("w+") as dashboard_log:
            try:
                children.append(subprocess.Popen([python_executable(), str(Path(__file__).resolve()), "--backend"],
                                                 cwd=STATION, env=environment, stdout=backend_log, stderr=backend_log,
                                                 start_new_session=True))
                schema = wait_ready(f"http://127.0.0.1:{api_port}/api/v1/schema", children, token=token)
                if schema.get("capabilities", {}).get("dashboardRead", {}).get("version") != 1:
                    raise RuntimeError("The demo backend does not expose the modified dashboard contract")
                dashboard_environment = dict(environment)
                if media_config:
                    dashboard_environment["MORPH_MEDIA_CONFIG_FILE"] = media_config
                children.append(subprocess.Popen([str(tsx), "tools/demoServer.ts"], cwd=DASHBOARD,
                                                 env=dashboard_environment, stdout=dashboard_log, stderr=dashboard_log,
                                                 start_new_session=True))
                view = wait_ready(f"http://127.0.0.1:{args.port}/api/v1/dashboard?sourceMode=simulation", children)
                if view.get("sourceMode") != "simulation" or view.get("selectedSessionId") != "local-demo:session":
                    raise RuntimeError("The proxy did not return the owned simulation session")
                print(f"Morph simulation dashboard ready: http://127.0.0.1:{args.port}", flush=True)
                print("Select Simulation in the dashboard. Synthetic records only; writes, providers and robot actions are disabled.", flush=True)
                print("Press Ctrl+C to stop both owned services and remove the temporary database and token.", flush=True)
                while not stopping and all(child.poll() is None for child in children):
                    time.sleep(0.2)
                return 0 if stopping else 1
            except Exception as error:
                print(f"Local demo could not start: {type(error).__name__}. No live configuration was used.", file=sys.stderr)
                for name, handle in (("Backend", backend_log), ("Dashboard", dashboard_log)):
                    handle.flush()
                    handle.seek(0)
                    diagnostic = handle.read(6000).replace(token, "[redacted]")
                    if diagnostic:
                        print(f"{name} diagnostic:\n{diagnostic}", file=sys.stderr)
                return 1
            finally:
                for child in reversed(children):
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGTERM)
                for child in reversed(children):
                    try:
                        # Media negotiation may need its 12-second deadline plus session cleanup.
                        child.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
