"""Explicit hosted Gemma evaluation on a test-owned saved simulation database."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "HachingJunction/station"))
from morph_station.analysis import AnalysisService, TERMINAL, atomic_json
from morph_station.analysis_models import AnalysisRequest, Selection
from morph_station.store import StationStore, fingerprint


def ledger_state(store):
    with store._connection() as db:
        return {table: [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("records", "events", "revisions", "request_receipts", "review_requests")}


def evaluate(output: Path, selected: str, interval_seconds: float = 0):
    cases = json.loads((output / "cases.json").read_text())
    if selected != "all":
        cases = [case for case in cases if case["name"] in selected.split(",")]
    if not cases:
        raise SystemExit("No matching evaluation cases.")
    store = StationStore(output / "data/station.sqlite3")
    before = fingerprint(ledger_state(store))
    service = AnalysisService(store, output / "data/analysis")
    results = []
    run_id = str(uuid4())
    previous_start = None
    try:
        for case in cases:
            if previous_start is not None:
                remaining = interval_seconds - (time.monotonic() - previous_start)
                if remaining > 0:
                    time.sleep(remaining)
            previous_start = time.monotonic()
            selection = Selection.model_validate({k: v for k, v in case.items() if k not in ("name", "question")})
            context = service.context(selection)
            request = AnalysisRequest(**selection.model_dump(), requestId=str(uuid4()),
                question=case["question"], expectedSelectionDigest=context["contentDigest"])
            accepted = service.submit(request)
            deadline = time.monotonic() + 40
            report = accepted
            while report["status"] not in TERMINAL and time.monotonic() < deadline:
                time.sleep(0.1)
                report = service.get(accepted["reportId"])
            assert report["status"] in TERMINAL, "Analysis did not reach a terminal state within its expected deadline"
            # Same request must read the saved result and not enqueue a second call.
            repeated = service.submit(request)
            assert repeated["reportId"] == report["reportId"]
            result = {"case": case["name"], "reportId": report["reportId"], "status": report["status"],
                "freshness": report["freshness"], "provenance": report["provenance"], "timings": report["timings"],
                "validation": report["validation"], "error": report["error"], "output": report["output"],
                "sourceDigest": context["contentDigest"], "contextBytes": len(json.dumps(context).encode()),
                "factCount": len(context["facts"]), "metricCount": len(context["metrics"]),
                "compatibility": context.get("compatibility"), "knownGaps": context["knownGaps"],
                "sampling": context["sampling"], "identicalRequestReused": True}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        service.close()
        after = fingerprint(ledger_state(store))
        summary = {"runId": run_id, "observedAt": datetime.now(timezone.utc).isoformat(),
            "provider": "Hosted Google Gemma", "requestedModel": "gemma-4-26b-a4b-it",
            "sourceMode": "simulation", "hardwareUsed": False, "results": results,
            "ledgerBeforeSha256": before, "ledgerAfterSha256": after, "canonicalLedgerUnchanged": before == after,
            "semanticEvaluation": "Pending independent claim/citation review; structural validation alone is not usefulness acceptance."}
        atomic_json(output / f"hosted-results-{run_id}.json", summary)
    assert before == after, "Analysis changed the canonical ledger"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", default="saved-m16-recovery")
    parser.add_argument("--interval-seconds", type=float, default=0,
                        help="Explicit spacing between different cases; never retries a failed request.")
    args = parser.parse_args()
    if not 0 <= args.interval_seconds <= 60:
        parser.error("Use a spacing from zero to sixty seconds.")
    evaluate(args.output.resolve(), args.cases, args.interval_seconds)
