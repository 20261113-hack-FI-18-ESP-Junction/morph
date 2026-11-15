#!/usr/bin/env python3
"""Run only received record/export and fake-device/watch tests without live access."""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STATION = ROOT / "source/common/HachingJunction/station"
JUNCTION = ROOT / "source/junction"


def digest(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/verification" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        parser.error("Output directory must be new to avoid overwriting prior evidence")
    out.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    origins = json.loads((ROOT / "SOURCE_ORIGINS.json").read_text())
    before = {row["path"]: digest(ROOT / row["path"]) for row in origins["files"]}
    mismatches = [row["path"] for row in origins["files"] if before[row["path"]] != {key: row[key] for key in ("bytes", "sha256")}]
    if mismatches:
        raise RuntimeError(f"Imported source mismatch: {mismatches}")
    python_files = sorted((ROOT / "source").rglob("*.py"))
    for path in python_files:
        ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
    shell_files = sorted((ROOT / "source").rglob("*.sh")) + [ROOT / "run.sh"]
    for path in shell_files:
        subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True, text=True)
    for key in list(os.environ):
        if key.startswith(("MORPH_", "GEMINI_", "GOOGLE_", "GEMMA_", "NVIDIA_", "ELEVENLABS_", "OPENAI_")) or key in {"API_KEY", "HF_TOKEN"}:
            os.environ.pop(key, None)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["MORPH_AUDIT_FIXTURE_ROOT"] = str(ROOT / "fixtures/audit")
    os.environ["MORPH_OFFLINE_REPORT_DIR"] = str(out)
    sys.dont_write_bytecode = True
    launcher_guards = out / "launcher-guards"
    launcher_guards.mkdir()
    with tempfile.TemporaryDirectory(prefix="morph-launcher-") as temporary:
        scratch = Path(temporary) / "station"
        env = dict(os.environ)
        env.update(MORPH_PYTHON=sys.executable, MORPH_DATA_DIR=str(scratch),
                   MORPH_OFFLINE_GUARD="1", MORPH_OFFLINE_REPORT_DIR=str(launcher_guards),
                   PYTHONPATH=str(ROOT / "tools"))
        help_result = subprocess.run(["bash", str(ROOT / "run.sh"), "--help"], env=env, capture_output=True, text=True, timeout=30)
        help_wrote_data = scratch.exists()
        init_result = subprocess.run(["bash", str(ROOT / "run.sh"), "init"], env=env, capture_output=True, text=True, timeout=30)
        if help_result.returncode or init_result.returncode:
            raise RuntimeError("Portable launcher failed; output withheld to avoid leaking private runtime configuration")
        with sqlite3.connect(scratch / "station.sqlite3") as db:
            records = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            events = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        token_permissions = stat.S_IMODE((scratch / "api-token").stat().st_mode)
        launcher = {"helpExitCode": help_result.returncode, "helpCreatedData": help_wrote_data,
                    "initExitCode": init_result.returncode, "initializedRecords": records,
                    "initializedEvents": events, "privateTokenMode": oct(token_permissions),
                    "scratchRuntimeDeletedAfterCheck": True}
        launcher["passed"] = not help_wrote_data and records == 0 and events == 0 and token_permissions == 0o600
    sys.path.insert(0, str(STATION))
    import pytest
    import offline_guard
    offline_guard.install()
    from morph_station.analysis_provider import GemmaProvider
    GemmaProvider.__call__ = lambda *a, **k: offline_guard.reject("provider invocation")
    test_paths = [STATION / "tests" / name for name in ("test_store.py", "test_reviews.py", "test_api.py", "test_export_audit.py")]
    test_paths += [JUNCTION / "tests" / name for name in ("test_motor_discovery.py", "test_mac_context_watch.py")]
    class CollectionCounter:
        count = 0

        def pytest_collection_finish(self, session):
            self.count = len(session.items)

    collection = CollectionCounter()
    with tempfile.TemporaryDirectory(prefix="morph-offline-") as temp:
        os.environ["MORPH_DATA_DIR"] = str(Path(temp) / "unused-default-data")
        with (out / "pytest.log").open("w") as log, redirect_stdout(log), redirect_stderr(log):
            code = pytest.main(["-q", "-p", "no:cacheprovider", "--tb=short", "--basetemp", str(Path(temp) / "pytest"), "--junitxml", str(out / "tests.xml"), *map(str, test_paths)], plugins=[collection])
        unexpected_default_data = Path(os.environ["MORPH_DATA_DIR"]).exists()
    after = {row["path"]: digest(ROOT / row["path"]) for row in origins["files"]}
    changed = [name for name in before if before[name] != after[name]]
    junit = ET.parse(out / "tests.xml").getroot()
    suites = list(junit) if junit.tag == "testsuites" else [junit]
    counts = {field: sum(int(suite.get(field, "0")) for suite in suites) for field in ("tests", "failures", "errors", "skipped")}
    child_reports = [json.loads(path.read_text()) for path in sorted(out.glob("guard-*.json"))]
    launcher_reports = [json.loads(path.read_text()) for path in sorted(launcher_guards.glob("guard-*.json"))]
    attempts = list(offline_guard.ATTEMPTS) + [entry for report in child_reports + launcher_reports for entry in report["attempts"]]
    result = {
        "startedAt": started, "finishedAt": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": sys.platform,
        "requestId": origins["requestId"], "testExitCode": int(code), "counts": counts,
        "collectedTests": collection.count, "additionalSubtestCases": counts["tests"] - collection.count,
        "pythonSourcesParsed": len(python_files), "shellScriptsSyntaxChecked": len(shell_files),
        "importedFilesHashCheckedBeforeAndAfter": len(before), "importedFilesChanged": changed,
        "reviewedExportCliChildProcesses": len(child_reports), "blockedOperationAttempts": attempts,
        "unexpectedDefaultDataCreated": unexpected_default_data,
        "portableLauncher": launcher, "guardedLauncherChildProcesses": len(launcher_reports),
        "testFiles": [str(path.relative_to(ROOT)) for path in test_paths],
        "scope": "Offline records/export tests and fake-device/watch tests. No live provider, robot, camera, training, tunnel, service, or watcher launched.",
        "limits": ["Process-local guards are audit controls, not an OS sandbox.", "Original Intel analyst and provider-check test files remain unreceived; this is not the full Intel test suite.", "Historical reports under source/ are preserved claims, not new execution evidence."],
    }
    result["passed"] = code == 0 and not changed and not attempts and not unexpected_default_data and launcher["passed"]
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
