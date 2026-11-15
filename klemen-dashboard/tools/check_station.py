#!/usr/bin/env python3
"""Bounded GET-only inspection of an already running loopback dashboard."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import json
import math
import re
import socket
import threading
import time

MAX_BYTES = 4 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")
STATES = {"starting", "connecting", "streaming", "stale", "disconnected", "failed", "stopped"}
COUNTERS = ("acceptedFrames", "submittedFrames", "encodedFramesReported", "replacedFrames",
            "staleFrames", "publisherStarts", "publisherRestarts", "publisherFailures", "writeTimeouts")


def nonnegative(value):
    return value if type(value) is int and 0 <= value <= 2**53 - 1 else None


def _invalid_constant(_):
    raise ValueError("Nonfinite JSON")


def get_json(port: int, route: str, *, timeout: float = 45, token: str | None = None,
             max_bytes: int = MAX_BYTES) -> dict:
    """No redirects, proxies, cookies, arbitrary host, response text or error echo."""
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    wire = None
    timer = None
    response = None
    try:
        connection.connect()
        # Keep an owned duplicate for the deadline: HTTPConnection closes its
        # socket object after Connection: close headers, while the body still reads.
        wire = connection.sock.dup()
        def expire():
            try:
                wire.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(max(0.001, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        connection.request("GET", route, headers=headers)
        response = connection.getresponse()
        status = response.status
        if status != 200:
            return {"status": "http-error", "httpStatus": status}
        if response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
            return {"status": "invalid-json"}
        if response.getheader("Content-Encoding", "identity") != "identity":
            return {"status": "unsupported-encoding"}
        length = response.getheader("Content-Length")
        if length is not None and (not length.isdigit() or int(length) >= max_bytes):
            return {"status": "oversized-response"}
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {"status": "timeout"}
            chunk = response.read1(min(65536, max_bytes - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size >= max_bytes:
                return {"status": "oversized-response"}
        data = json.loads(b"".join(chunks), parse_constant=_invalid_constant)
        if not isinstance(data, dict):
            return {"status": "invalid-json"}
        return {"status": "ok", "data": data}
    except (TimeoutError, socket.timeout):
        return {"status": "timeout"}
    except (ValueError, UnicodeError, RecursionError):
        return {"status": "invalid-json"}
    except (OSError, http.client.HTTPException):
        return {"status": "timeout" if time.monotonic() >= deadline else "unavailable"}
    finally:
        if timer is not None:
            timer.cancel()
        if response is not None:
            response.close()
        connection.close()
        if wire is not None:
            wire.close()


def transport_result(result: dict) -> dict:
    return {key: value for key, value in result.items() if key in ("status", "httpStatus")}


def summarize_runtime(result: dict) -> dict:
    summary = transport_result(result)
    if result["status"] != "ok":
        return summary
    data = result["data"]
    mode, transport, station = data.get("runtimeMode"), data.get("recordsTransport"), data.get("stationId")
    valid = data.get("version") == 1 and data.get("controlHost") == "jose" and data.get("motionRoutes") is False
    valid = valid and ((mode == "demo" and transport == "local-simulation" and station is None) or
                       (mode == "station" and transport == "mac-mcp" and isinstance(station, str) and SAFE_ID.fullmatch(station)))
    if not valid:
        return {"status": "invalid-contract"}
    return {"status": "ok", "runtimeMode": mode, "recordsTransport": transport, "stationId": station,
            "controlHost": "jose", "motionRoutes": False, "authorityEvidence": "configured-route-only"}


def summarize_schema(result: dict) -> dict:
    if result["status"] != "ok":
        return transport_result(result)
    capabilities = result["data"].get("capabilities")
    capability = capabilities.get("dashboardRead") if isinstance(capabilities, dict) else None
    supported = isinstance(capability, dict) and capability.get("version") == 1 and capability.get("path") == "/api/v1/dashboard"
    return {"status": "ok", "dashboardRead": "supported" if supported else "unavailable"}


def summarize_records(result: dict, mode: str) -> dict:
    if result["status"] != "ok":
        return transport_result(result)
    data = result["data"]
    sessions, cycles, snapshot = data.get("sessions"), data.get("recentCycles"), data.get("snapshot")
    if not all(isinstance(item, dict) for item in (sessions, cycles, snapshot)):
        return {"status": "invalid-contract"}
    session_items, cycle_items = sessions.get("items"), cycles.get("items")
    valid = data.get("schemaVersion") == 1 and data.get("dashboardVersion") == 1 and data.get("sourceMode") == mode
    valid = valid and nonnegative(data.get("lastEventSequence")) is not None
    valid = valid and data.get("generatedAt") == snapshot.get("generatedAt") and data.get("lastEventSequence") == snapshot.get("lastEventSequence")
    valid = valid and isinstance(data.get("metrics"), dict) and data["metrics"] == snapshot.get("metrics")
    valid = valid and isinstance(session_items, list) and len(session_items) <= 50 and isinstance(cycle_items, list) and len(cycle_items) <= 1
    valid = valid and sessions.get("limit") == 50 and cycles.get("limit") == 1 and cycles.get("offset") == 0
    valid = valid and nonnegative(sessions.get("total")) is not None and nonnegative(cycles.get("total")) is not None
    selected = data.get("selectedSessionId")
    valid = valid and "selectedSessionId" in data and (selected is None or isinstance(selected, str) and SAFE_ID.fullmatch(selected))
    if not valid:
        return {"status": "invalid-contract"}
    if not consistent_selection(data, mode):
        return {"status": "invalid-contract"}
    return {"status": "ok", "sourceMode": mode, "eligibleData": "present" if selected is not None else "no-eligible-session",
            "sessionCount": sessions["total"], "selectedSessionCycleCount": cycles["total"],
            "recentCyclesReturned": len(cycle_items), "lastEventSequence": data["lastEventSequence"],
            "readConsistency": "matching-snapshot-cursor-and-metrics"}


def consistent_selection(data: dict, mode: str) -> bool:
    """Cycles inherit source mode from their selected session in the v1 contract."""
    selected, snapshot = data["selectedSessionId"], data["snapshot"]
    sessions, cycles = data["sessions"], data["recentCycles"]
    session_items, cycle_items = sessions["items"], cycles["items"]
    def identifier(value):
        return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None
    if any(not isinstance(item, dict) or not identifier(item.get("id")) or item.get("sourceMode") != mode for item in session_items):
        return False
    if len({item["id"] for item in session_items}) != len(session_items) or sessions["total"] < len(session_items):
        return False
    if selected is None:
        return (snapshot.get("session") is None and snapshot.get("sourceMode") is None and snapshot.get("cycle") is None
                and not session_items and sessions["total"] == 0 and not cycle_items and cycles["total"] == 0
                and data.get("currentDetail") is None and data.get("detail") is None)
    session = snapshot.get("session")
    if (not isinstance(session, dict) or session.get("id") != selected or session.get("sourceMode") != mode
            or snapshot.get("sourceMode") != mode or sessions["total"] < 1):
        return False
    def selected_cycle(cycle):
        return (isinstance(cycle, dict) and identifier(cycle.get("id")) and cycle.get("sessionId") == selected
                and ("sourceMode" not in cycle or cycle["sourceMode"] == mode))
    if any(not selected_cycle(cycle) for cycle in cycle_items):
        return False
    if len({cycle["id"] for cycle in cycle_items}) != len(cycle_items) or cycles["total"] < len(cycle_items):
        return False
    current = snapshot.get("cycle")
    if current is None:
        return not cycle_items and cycles["total"] == 0 and data.get("currentDetail") is None and data.get("detail") is None
    if not selected_cycle(current) or cycles["total"] < 1:
        return False
    for key in ("currentDetail", "detail"):
        detail = data.get(key)
        if not isinstance(detail, dict) or not selected_cycle(detail.get("cycle")) or detail["cycle"]["id"] != current["id"]:
            return False
        # Inspect only contract-level records; provider outputs are opaque evidence.
        for name in ("attempts", "frames", "inspections", "modelRuns", "utterances", "decisions", "executions",
                     "referenceLabels", "confirmations", "corrections", "evidence", "events"):
            records = detail.get(name, [])
            if not isinstance(records, list):
                return False
            for record in records:
                if (not isinstance(record, dict) or record.get("sessionId") != selected or record.get("cycleId") != current["id"]
                        or "sourceMode" in record and record["sourceMode"] != mode):
                    return False
    return True


def summarize_media(result: dict, mode: str) -> dict:
    if result["status"] != "ok":
        return transport_result(result)
    data = result["data"]
    if data.get("version") != 1 or type(data.get("configured")) is not bool or data.get("sourceMode") not in ("live", "simulation"):
        return {"status": "invalid-contract"}
    summary = {"status": "ok", "configured": data["configured"], "sourceMode": data["sourceMode"],
               "matchesRequestedMode": data["sourceMode"] == mode, "producerStatus": "unavailable",
               "browserPlayback": "not-tested", "iceConnectivity": "not-tested", "captureLatency": "not-measured"}
    producer = data.get("producer")
    if isinstance(producer, dict) and isinstance(producer.get("state"), str) and producer["state"] in STATES:
        counters = producer.get("counters", {})
        summary["producerStatus"] = producer["state"]
        summary["counters"] = {key: counters[key] for key in COUNTERS if isinstance(counters, dict) and nonnegative(counters.get(key)) is not None}
        age = producer.get("receiptAgeMs")
        if type(age) in (int, float) and math.isfinite(age) and age >= 0:
            summary["producerReceiptAgeMs"] = age
    return summary


def check(port: int, source_mode: str, *, timeout: float = 45, require_media: bool = False) -> dict:
    routes = {"runtime": "/api/local/v1/runtime", "schema": "/api/v1/schema",
              "records": f"/api/v1/dashboard?sourceMode={source_mode}&limit=1", "media": "/api/media/v1/status"}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {key: executor.submit(get_json, port, route, timeout=timeout) for key, route in routes.items()}
        raw = {key: future.result() for key, future in futures.items()}
    runtime = summarize_runtime(raw["runtime"])
    schema = summarize_schema(raw["schema"])
    records = summarize_records(raw["records"], source_mode)
    media = summarize_media(raw["media"], source_mode)
    records_ready = runtime["status"] == schema["status"] == records["status"] == "ok" and schema.get("dashboardRead") == "supported"
    media_ready = media.get("configured") is True and media.get("matchesRequestedMode") is True and media.get("producerStatus") == "streaming"
    return {"version": 1, "checkedAt": datetime.now(timezone.utc).isoformat(), "dashboardPort": port,
            "requestedSourceMode": source_mode, "ok": records_ready and (media_ready or not require_media),
            "runtime": runtime, "schema": schema, "records": records, "media": media,
            "scope": "GET-only-local-dashboard", "physicalAcceptance": "not-verified", "requestsMade": 4}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--source-mode", choices=("live", "simulation"), default="live")
    parser.add_argument("--timeout", type=float, default=45, help="Per-request total deadline, 1–60 seconds")
    parser.add_argument("--require-media", action="store_true", help="Require matching configured video and a streaming producer status")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.timeout <= 60:
        parser.error("Choose a valid port and a timeout from 1 to 60 seconds")
    result = check(args.port, args.source_mode, timeout=args.timeout, require_media=args.require_media)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
