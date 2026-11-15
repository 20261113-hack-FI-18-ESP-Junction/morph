"""Offline review/analysis transport regression tests; no real endpoints or models."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from station_relay import StationRelay, request_target
from station_worker import StationHTTP, StationWorker, WorkerError, validated_request
from test_station_worker import Opener, Response, TOKEN
from server import create_server, http_app
from starlette.testclient import TestClient

REVIEW = '{ "id": "review-1", "eventId": "event-1", "expectedRevision": 2 }'
ANALYSIS = '{"requestId":"analysis-1","expectedSelectionDigest":"' + 'a' * 64 + '"}'


class WriteTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="morph-write-relay-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "AGENTS.md").write_text("# Isolated transport fixture\n")
        self.now = 1_800_000_000.0
        self.relay = StationRelay(self.root, clock=lambda: self.now)

    def enqueue(self, **changes):
        args = dict(station_id="intel-test", request_id=str(uuid4()), method="POST",
            path="/api/v1/cycles/cycle-1/review", query={}, body=REVIEW, intent="record-review")
        args.update(changes)
        return self.relay.enqueue_request(**args)

    def test_legacy_workers_cannot_claim_writes_and_capable_worker_claims_once(self):
        queued = self.enqueue()
        self.assertEqual(self.relay.claim("intel-test", "old")["requests"], [])
        claim = self.relay.claim("intel-test", "new", supports_writes=True)["requests"][0]
        self.assertEqual((claim["method"], claim["body"], claim["intent"]), ("POST", REVIEW, "record-review"))
        self.assertEqual(claim["request_id"], queued["request_id"])
        self.assertEqual(self.relay.claim("intel-test", "new", supports_writes=True)["requests"], [])

    def test_duplicate_envelopes_never_replay_and_changed_body_conflicts(self):
        queued = self.enqueue()
        self.assertEqual(self.enqueue(request_id=queued["request_id"]), queued)
        with self.assertRaises(ValueError):
            self.enqueue(request_id=queued["request_id"], body=REVIEW.replace('2', '3'))
        self.relay.claim("intel-test", "worker", supports_writes=True)
        self.now += 31
        repeated = self.enqueue(request_id=queued["request_id"])
        self.assertEqual(repeated["state"], "expired")
        self.assertEqual(self.relay.claim("intel-test", "worker", supports_writes=True)["requests"], [])
        with sqlite3.connect(self.relay.db_path) as db:
            self.assertIsNone(db.execute("SELECT request_body FROM reads").fetchone()[0])

    def test_migration_preserves_existing_get_and_new_writes(self):
        self.relay.db_path.parent.mkdir(parents=True)
        identity = str(uuid4())
        with sqlite3.connect(self.relay.db_path) as db:
            db.execute('''CREATE TABLE reads (request_id TEXT PRIMARY KEY, station_id TEXT NOT NULL,
                path TEXT NOT NULL, query TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
                expires REAL NOT NULL, worker_id TEXT, claim_id TEXT, metadata TEXT,
                body_base64 TEXT, completed REAL)''')
            db.execute("INSERT INTO reads(request_id,station_id,path,query,state,created,expires) VALUES(?,?,?,?,?,?,?)",
                (identity, "intel-test", "/api/v1/sessions", "{}", "queued", self.now, self.now + 30))
        self.assertEqual(self.relay.enqueue("intel-test", identity, "/api/v1/sessions")["state"], "queued")
        self.enqueue()
        reads = self.relay.claim("intel-test", "legacy")["requests"]
        self.assertEqual([x["request_id"] for x in reads], [identity])

    def test_control_routes_bad_intent_queries_and_non_json_never_enter_queue(self):
        cases = [dict(path="/api/v1/commands"), dict(path="/api/v1/sessions/s/end"),
            dict(path="/api/v1/cycles/%2e%2e/review"), dict(method="DELETE"),
            dict(intent=None), dict(intent="evidence-analysis"), dict(query={"redirect": "other"}),
            dict(body="[]"), dict(body='{"id":"r","eventId":"e","x":NaN}'),
            dict(body='{"id":"r","id":"other","eventId":"e"}'),
            dict(body='{"id":"r"}'), dict(body=" " * 65537)]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.enqueue(**changes)
        self.assertEqual(self.relay.claim("intel-test", "worker", supports_writes=True)["requests"], [])

    def test_analysis_requires_explicit_intent_and_stable_application_id(self):
        self.enqueue(path="/api/v1/analysis/reports", body=ANALYSIS, intent="evidence-analysis")
        for body, intent in [('{}', 'evidence-analysis'), (ANALYSIS, 'record-review')]:
            with self.assertRaises(ValueError):
                self.enqueue(path="/api/v1/analysis/reports", body=body, intent=intent)

    def test_multi_session_selection_survives_queue_and_http_encoding(self):
        query = {"kind": "comparison", "sessionIds": ["baseline-1", "adaptive-2"]}
        queued = self.relay.enqueue("intel-test", str(uuid4()), "/api/v1/analysis/context", query)
        claim = self.relay.claim("intel-test", "reader")["requests"][0]
        self.assertEqual(claim["request_id"], queued["request_id"])
        opener = Opener(Response())
        StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener).read(claim["path"], claim["query"])
        parsed = urllib.parse.parse_qs(urllib.parse.urlsplit(opener.requests[0][0].full_url).query)
        self.assertEqual(parsed["sessionIds"], ["baseline-1", "adaptive-2"])
        for sessions in [[], ["a", "b", "c"], ["a", "../b"]]:
            with self.assertRaises(ValueError):
                request_target("GET", "/api/v1/analysis/context", {"sessionIds": sessions})
            with self.assertRaises(WorkerError):
                validated_request("GET", "/api/v1/analysis/context", {"sessionIds": sessions})

    def test_http_preserves_body_status_errors_and_never_retries_post(self):
        for code in [200, 202, 409, 422, 429, 503]:
            with self.subTest(code=code):
                opener = Opener(Response(b'{"detail":"preserved"}', code))
                result = StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener).request(
                    "POST", "/api/v1/cycles/c/review", {}, REVIEW, "record-review")
                sent = opener.requests[0][0]
                self.assertEqual((sent.method, sent.data), ("POST", REVIEW.encode()))
                self.assertEqual(result.status_code, code)
                self.assertEqual(result.body, b'{"detail":"preserved"}')
                self.assertEqual(len(opener.requests), 1)
        opener = Opener(urllib.error.URLError("lost after dispatch"))
        result = StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener).request(
            "POST", "/api/v1/analysis/reports", {}, ANALYSIS, "evidence-analysis")
        self.assertEqual(json.loads(result.body)["error"], "station_write_outcome_unknown")
        self.assertEqual(len(opener.requests), 1)

    def test_forged_write_claim_is_denied_by_default_worker(self):
        outer = self
        class MCP:
            saved = []
            def call(self, name, arguments):
                if name == "claim_station_reads":
                    return {"requests": [{"method": "POST", "path": "/api/v1/cycles/c/review",
                        "query": {}, "body": REVIEW, "intent": "record-review", "request_id": str(uuid4()),
                        "claim_id": str(uuid4()), "expires_at": datetime.fromtimestamp(outer.now+30, timezone.utc).isoformat()}]}
                self.saved.append(arguments)
                return {"state": "ready"}
        opener = Opener()
        mcp = MCP()
        result = StationWorker(mcp, StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener),
            clock=lambda: datetime.fromtimestamp(self.now, timezone.utc)).run_once()
        self.assertEqual(result["completed"], 1)
        self.assertEqual(opener.requests, [])
        self.assertEqual(json.loads(base64.b64decode(mcp.saved[0]["body_base64"]))["error"], "worker_writes_disabled")

    def test_lost_mcp_reply_resends_response_only_not_post(self):
        outer = self
        class DirectMCP:
            lost = False
            def call(self, name, arguments):
                if name == "claim_station_requests":
                    return outer.relay.claim(**arguments)
                result = outer.relay.submit(**arguments)
                if not self.lost:
                    self.lost = True
                    raise WorkerError("mcp_transport_error")
                return result
        queued = self.enqueue(path="/api/v1/analysis/reports", body=ANALYSIS, intent="evidence-analysis")
        opener = Opener(Response(b'{"reportId":"report-1","status":"pending"}', 202))
        worker = StationWorker(DirectMCP(), StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener),
            station_id="intel-test", allow_writes=True,
            clock=lambda: datetime.fromtimestamp(self.now, timezone.utc))
        # Use the same synthetic clock for the fake HTTP result and relay's timestamp check.
        from unittest.mock import patch
        with patch("station_worker.timestamp", return_value=datetime.fromtimestamp(self.now, timezone.utc).isoformat()):
            self.assertEqual(worker.run_once()["completed"], 1)
        self.assertEqual(len(opener.requests), 1)
        saved = self.relay.read("intel-test", queued["request_id"])
        self.assertEqual(saved["status_code"], 202)
        self.assertEqual(base64.b64decode(saved["body_base64"]), b'{"reportId":"report-1","status":"pending"}')

    def test_new_tools_work_through_authenticated_mcp(self):
        token = "offline-mcp-test-" + "x" * 40
        app = http_app(create_server(self.root, enable_station_relay=True), token, "127.0.0.1", 8765)
        with TestClient(app, base_url="http://127.0.0.1:8765") as client:
            headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
            def rpc(method, params):
                response = client.post("/mcp", headers=headers, json={"jsonrpc":"2.0", "id":1, "method":method, "params":params})
                self.assertEqual(response.status_code, 200)
                return response.json()["result"]
            def call(name, args):
                result = rpc("tools/call", {"name":name, "arguments":args})
                self.assertFalse(result.get("isError"), result)
                return result["structuredContent"]
            queued = call("enqueue_station_request", {"station_id":"intel-test", "request_id":str(uuid4()),
                "method":"POST", "path":"/api/v1/cycles/c/review", "body":REVIEW, "intent":"record-review"})
            self.assertEqual(call("claim_station_reads", {"station_id":"intel-test", "worker_id":"legacy"})["requests"], [])
            claims = call("claim_station_requests", {"station_id":"intel-test", "worker_id":"new", "supports_writes":True})["requests"]
            self.assertEqual(claims[0]["request_id"], queued["request_id"])
            self.assertEqual(claims[0]["body"], REVIEW)


if __name__ == "__main__":
    unittest.main()
