"""One explicit hosted insufficient-evidence comparison through the isolated actual API."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

config = json.loads(Path(sys.argv[1]).read_text())
origin = config["apiOrigin"]
assert urlsplit(origin).hostname == "127.0.0.1"
data = Path(config["dataDirectory"])
token = (data / "api-token").read_text().strip()
selection = {"kind": "session_comparison", "sessionIds": ["m16-recovery:session", "gemma-eval-classification-mismatch:session"],
             "sourceMode": "simulation", "baselineSessionId": "m16-recovery:session", "adaptiveSessionId": "gemma-eval-classification-mismatch:session"}
with httpx.Client(base_url=origin, headers={"Authorization": "Bearer " + token}, timeout=10, trust_env=False, follow_redirects=False) as client:
    facts = client.get("/api/v1/analysis/context", params=selection)
    facts.raise_for_status()
    context = facts.json()
    assert context["compatibility"]["state"] == "unknown"
    request = {**selection, "requestId": str(uuid4()), "expectedSelectionDigest": context["contentDigest"],
        "question": "Explain only the missing reviewed comparison metadata. There is no supported matched comparison. Use the supplied evidence gaps and avoid interpretations when no cited comparison claim is supported."}
    response = client.post("/api/v1/analysis/reports", json=request)
    response.raise_for_status()
    initial = response.json()
    deadline = time.monotonic() + 65
    report = initial
    while report["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.3)
        saved = client.get("/api/v1/analysis/reports/" + initial["reportId"])
        saved.raise_for_status()
        report = saved.json()
    repeated = client.post("/api/v1/analysis/reports", json=request)
    repeated.raise_for_status()
    assert repeated.json()["reportId"] == report["reportId"]
    result = {"request": request, "postHttpStatus": response.status_code, "reportId": report["reportId"],
        "status": report["status"], "validation": report["validation"], "provenance": report["provenance"],
        "timings": report["timings"], "error": report["error"], "output": report["output"],
        "comparisonState": context["compatibility"]["state"], "descriptiveDeltas": context["descriptiveDeltas"],
        "duplicateRequestReused": True, "sourceMode": "simulation", "hardwareUsed": False}
    destination = Path(config["output"]) / ("comparison-api-" + report["reportId"] + ".json")
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
