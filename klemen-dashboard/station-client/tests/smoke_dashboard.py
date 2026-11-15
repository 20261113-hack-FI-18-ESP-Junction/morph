"""Check an already-running local dashboard proxy without changing station records."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ORIGIN = "http://127.0.0.1:3000"
REPORT = Path(__file__).resolve().parents[1] / "verification/dashboard/http-proxy.json"


def main() -> None:
    checks: list[str] = []
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "origin": ORIGIN,
        "status": "running",
        "evidenceType": "Actual local UI proxy and persisted simulation; no hardware/provider operation.",
        "checks": checks,
    }

    def read(path: str, *, method: str = "GET", headers: dict | None = None):
        request = Request(ORIGIN + path, method=method, headers=headers or {})
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def payload(path: str):
        status, headers, data = read(path)
        assert status == 200, f"Unexpected HTTP {status} for {path}"
        assert headers.get_content_type() == "application/json"
        return json.loads(data)

    try:
        status, headers, html = read("/")
        assert status == 200 and b'Morph' in html
        checks.append("Dashboard document is served by the local UI server")
        for name in ("inter.ttf", "space-mono.ttf", "cormorant-italic.ttf"):
            status, _, data = read("/assets/fonts/" + name)
            assert status == 200 and len(data) > 1000
        checks.append("All three local fonts are served without external font requests")
        before = payload("/api/v1/station/snapshot")
        sessions = payload("/api/v1/sessions")
        simulation = next(session for session in sessions if session["sourceMode"] == "simulation")
        session_id = quote(simulation["id"], safe="")
        trace = payload(f"/api/v1/sessions/{session_id}/export?format=json")
        metrics = payload(f"/api/v1/sessions/{session_id}/metrics?includeSimulation=true")
        assert trace["session"]["id"] == simulation["id"] and trace["metrics"] == metrics
        checks.append("Complete export and metrics refer to the same persisted simulation session")
        live = payload("/api/v1/metrics?includeSimulation=false")
        simulated_ids = {session["id"] for session in sessions if session["sourceMode"] == "simulation"}
        assert not simulated_ids.intersection(live["filters"]["includedSessionIds"])
        checks.append("Default live reliability population excludes simulation sessions")
        cycle = trace["records"]["cycle"][0]
        detail = payload("/api/v1/cycles/" + quote(cycle["id"], safe=""))
        assert detail["cycle"]["id"] == cycle["id"]
        checks.append("Cycle detail retains its persisted identity")
        evidence = trace["records"]["evidence"][0]
        status, headers, image = read("/api/v1/evidence/" + quote(evidence["id"], safe=""))
        assert status == 200 and headers.get_content_type() == evidence["mediaType"]
        assert len(image) == evidence["size"] and hashlib.sha256(image).hexdigest() == evidence["sha256"]
        checks.append("Same-origin evidence bytes match the persisted size and SHA-256")
        status, headers, csv = read(f"/api/v1/sessions/{session_id}/export?format=csv")
        assert status == 200 and headers.get_content_type() == "text/csv"
        assert csv.startswith(b"section,recordType,id,dataJson")
        checks.append("CSV export is the canonical schema-versioned session export")
        status, headers, events = read("/api/v1/events?after=0&once=true&limit=1000")
        assert status == 200 and headers.get_content_type() == "text/event-stream"
        assert b"data:" in events and b"id:" in events
        checks.append("SSE forwards actual persisted event data and numeric cursors")
        for path in ("/api/v1/commands", "/api/v1/station/mode", "/api/v1/voice/token"):
            status, _, _ = read(path, method="POST")
            assert status in (404, 405), f"Write route was not blocked: {path} ({status})"
        checks.append("Command, mode mutation and voice-token POST routes are blocked")
        status, _, _ = read("/api/v1/station/snapshot", headers={"Origin": "https://outside.invalid"})
        assert status == 403
        status, _, _ = read("/api/v1/station/snapshot", headers={"Host": "outside.invalid:3000"})
        assert status == 403
        checks.append("Foreign Origin and Host requests are denied")
        status, _, _ = read("/api/v1/not-an-allowed-route")
        assert status == 404
        checks.append("Unknown API paths cannot reach the upstream")
        after = payload("/api/v1/station/snapshot")
        assert before["lastEventSequence"] == after["lastEventSequence"]
        report.update(status="passed", checkCount=len(checks), sequenceBefore=before["lastEventSequence"],
                      sequenceAfter=after["lastEventSequence"], sessionId=simulation["id"])
        checks.append("All reads and rejected writes leave the persisted event sequence unchanged")
        report["checkCount"] = len(checks)
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
