"""Review-only execution of the hash-verified Intel test subset in temporary data.

Provider invocation and outbound socket connections fail immediately. No source
file is changed and no existing application database is used.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "handoff/three-host-20261115/incoming/intel-jose-8dfe841b/source"
OUTPUT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE / "station"))
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "VERDA_INFERENCE_KEY", "ELEVENLABS_API_KEY", "MORPH_API_TOKEN",
            "MORPH_DB_PATH", "MORPH_DATA_DIR", "MORPH_EVIDENCE_DIR", "MORPH_TOKEN_FILE", "MORPH_CORS_ORIGINS"):
    os.environ.pop(key, None)

attempts = {"provider": 0, "network": 0}


def no_network(*args, **kwargs):
    attempts["network"] += 1
    raise RuntimeError("Outbound network is disabled during source acceptance")


def no_provider(*args, **kwargs):
    attempts["provider"] += 1
    raise RuntimeError("Provider execution is disabled during source acceptance")


with patch.object(socket.socket, "connect", no_network), patch.object(socket.socket, "connect_ex", no_network):
    from morph_station.analysis_provider import GemmaProvider
    from morph_station.api import create_app
    import pytest
    from fastapi.testclient import TestClient

    with patch.object(GemmaProvider, "__call__", no_provider):
        os.chdir(SOURCE)
        result = pytest.main([
            str(SOURCE / "station/tests/test_store.py"), str(SOURCE / "station/tests/test_reviews.py"),
            "-q", "-p", "no:cacheprovider", "--junitxml=" + str(OUTPUT / "imported-tests.xml"),
        ])
        with tempfile.TemporaryDirectory(prefix="morph-intel-contract-") as directory:
            db = Path(directory) / "records.sqlite3"
            app = create_app(db, token="review-only-" + "x" * 40, analysis_provider=no_provider)
            with TestClient(app, headers={"Authorization": "Bearer " + "review-only-" + "x" * 40}) as client:
                openapi = client.get("/openapi.json").json()
                schema = client.get("/api/v1/schema").json()
                snapshot = client.get("/api/v1/station/snapshot").json()
                statuses = {path: client.post(path).status_code for path in [
                    "/api/v1/commands", "/api/v1/voice/token", "/api/v1/voice/utterances"]}
                assert statuses == {path: 503 for path in statuses}
                assert snapshot["goalVersion"] is None and snapshot["goal"] is None and snapshot["availableActions"] == []
                assert client.get("/api/v1/sessions").json() == []
                assert app.state.store.latest_sequence() == 0
            (OUTPUT / "current-source-openapi.json").write_text(json.dumps(openapi, indent=2) + "\n")
            (OUTPUT / "current-source-record-schema.json").write_text(json.dumps(schema, indent=2) + "\n")
            (OUTPUT / "empty-source-snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")

summary = {
    "checkedAt": datetime.now(timezone.utc).isoformat(), "pytestExitCode": int(result),
    "providerAttempts": attempts["provider"], "outboundSocketAttempts": attempts["network"],
    "stubStatuses": statuses, "source": str(SOURCE),
    "scope": "Imported source in isolated temporary data, with network/provider execution blocked. Not Intel runtime or physical verification.",
}
(OUTPUT / "execution-review.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
raise SystemExit(result or (1 if any(attempts.values()) else 0))
