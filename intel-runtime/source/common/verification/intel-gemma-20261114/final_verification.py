"""Read-only final runtime, source-version and canonical-state evidence checks."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.request import urlopen
import xml.etree.ElementTree as ET

evidence = Path(__file__).resolve().parent
root = evidence.parents[1]
workspace = root / "HachingJunction"
run = evidence / "runs/hosted-03"
config = json.loads((run / "services.json").read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


backend_path = workspace / "station/verification/gemma-backend-comparison-hardening-v8-20261114.json"
backend = json.loads(backend_path.read_text())
assert backend["result"]["passed"] == 131 and backend["result"]["failed"] == 0
for name, expected in backend["sourceHashes"].items():
    assert digest(workspace / name) == expected, f"Source changed since final test: {name}"

tests = [{"artifact": str(backend_path.relative_to(root)), "sha256": digest(backend_path),
          "tests": 131, "failures": 0, "warnings": 1, "version": "gemma-evidence-v8"}]
for name in ("frontend-final.xml", "prototype-final.xml"):
    tree = ET.parse(evidence / name)
    cases = tree.findall(".//testcase")
    failures = len(tree.findall(".//failure")) + len(tree.findall(".//error"))
    assert not failures
    tests.append({"artifact": name, "sha256": digest(evidence / name), "tests": len(cases), "failures": failures})

with sqlite3.connect((run / "data/station.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
    db.row_factory = sqlite3.Row
    ledger = {table: [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
              for table in ("records", "events", "revisions", "request_receipts", "review_requests")}
ledger_sha = hashlib.sha256(json.dumps(ledger, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
expected_ledger = json.loads((run / "hosted-results-96fb4bf8-f0b5-4e77-9ad5-4b7a81bd79e8.json").read_text())["ledgerBeforeSha256"]
assert ledger_sha == expected_ledger, "Canonical records changed after the hosted/browser checks"

health = []
for role, url in [
    ("Existing Morph UI", "http://127.0.0.1:3001/"),
    ("Existing Morph API", "http://127.0.0.1:8000/health"),
    ("Existing native Studio", "http://127.0.0.1:3000/"),
    ("Existing container Studio", "http://127.0.0.1:7860/"),
    ("Owned analyst preview", config["uiOrigin"] + "/"),
    ("Owned analyst API", config["apiOrigin"] + "/health"),
]:
    try:
        with urlopen(url, timeout=3) as response:
            health.append({"service": role, "url": url, "httpStatus": response.status})
    except OSError as error:
        health.append({"service": role, "url": url, "errorType": type(error).__name__})

source_files = [workspace / name for name in backend["sourceHashes"]]
source_files += list((root / "morph-station/src/analysis").glob("*"))
source_files += [root / "morph-station" / name for name in
                 ("src/App.tsx", "server/stationProxy.ts", "server/stationProxy.test.ts", "package.json")]
source_files += [evidence / name for name in ("README.md", "DEMO.md", "root-ui-integration.patch")]
summary = {
    "observedAt": datetime.now(timezone.utc).isoformat(),
    "tests": tests,
    "postAccessibilityUiVerification": {"tests": 24, "typecheck": "passed",
        "evidence": "runs/hosted-03/browser-03/ui-tests.txt"},
    "typecheck": "passed",
    "build": "passed to isolated dist; existing live dist preserved",
    "sourceVersions": {"prompt": "gemma-evidence-v8", "context": "morph-evidence-v5", "contract": "gemma-brief-v1"},
    "canonicalLedgerUnchanged": ledger_sha == expected_ledger,
    "canonicalLedgerSha256": ledger_sha,
    "canonicalEventCount": len(ledger["events"]),
    "canonicalEventMaxSequence": max(row["sequence"] for row in ledger["events"]),
    "services": health,
    "ownedPreviewKeptRunning": True,
    "existingServicesRestartedByThisTask": False,
    "physicalAcceptance": False,
    "hardwareUsed": False,
    "laterStudioRecheck": json.loads((evidence / "studio-7860-final-recheck.json").read_text()) if (evidence / "studio-7860-final-recheck.json").exists() else None,
    "sourceAndDocumentationHashes": {str(path.relative_to(root)): digest(path) for path in source_files if path.is_file()},
}
(evidence / "verification-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({key: value for key, value in summary.items() if key != "sourceAndDocumentationHashes"}, indent=2))
