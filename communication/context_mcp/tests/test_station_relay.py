"""Isolated tests for the optional GET relay; no Intel, providers or hardware."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))

from station_relay import MAX_ACTIVE, MAX_CHUNK, StationRelay, iso, read_target
from server import create_server, http_app
from starlette.testclient import TestClient


class RelayFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="morph-relay-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        (self.root / "AGENTS.md").write_text("# Fixture project\n")
        self.time = 1_800_000_000.0
        self.relay = StationRelay(self.root, clock=lambda: self.time)

    def enqueue(self, **changes):
        values = {"station_id": "intel-test", "request_id": str(uuid4()), "path": "/api/v1/station/snapshot", "query": {}}
        values.update(changes)
        return self.relay.enqueue(**values)

    def claim(self, request=None):
        request = request or self.enqueue()
        claims = self.relay.claim("intel-test", "worker-test")
        return request, next(row for row in claims["requests"] if row["request_id"] == request["request_id"])

    def response(self, request, claim, raw=b'{"sourceMode":"simulation"}', **changes):
        values = {"station_id": "intel-test", "request_id": request["request_id"], "worker_id": "worker-test",
                  "claim_id": claim["claim_id"], "part_index": 0, "part_count": 1, "status_code": 200,
                  "content_type": "application/json", "body_base64": base64.b64encode(raw).decode(),
                  "response_sha256": hashlib.sha256(raw).hexdigest(), "captured_at": iso(self.time)}
        values.update(changes)
        return values


class RelayBoundaryTests(RelayFixture):
    def test_enqueue_is_idempotent_and_conflicts_preserve_original(self):
        request = self.enqueue()
        repeat = self.enqueue(request_id=request["request_id"])
        self.assertEqual(repeat, request)
        for changes in ({"path": "/api/v1/sessions"}, {"station_id": "other"}, {"query": {"sessionId": "new"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.enqueue(request_id=request["request_id"], **changes)
        self.assertEqual(self.relay.read("intel-test", request["request_id"]), request)

    def test_concurrent_duplicate_enqueue_and_claim_create_one_work_item(self):
        identity = str(uuid4())
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.enqueue(request_id=identity), range(16)))
        self.assertTrue(all(row == results[0] for row in results))
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(lambda i: self.relay.claim("intel-test", "worker-" + str(i)), range(8)))
        all_claimed = [row for group in claims for row in group["requests"]]
        self.assertEqual(len(all_claimed), 1)
        self.assertEqual(all_claimed[0]["request_id"], identity)

    def test_station_scoping_and_claim_limit(self):
        self.enqueue(station_id="other-station")
        mine = self.enqueue()
        self.assertEqual(len(self.relay.claim("intel-test", "worker-test")["requests"]), 1)
        with self.assertRaises(ValueError):
            self.relay.read("other-station", mine["request_id"])
        for limit in (0, 17, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.relay.claim("intel-test", "worker-test", limit)

    def test_control_urls_traversal_and_unbounded_queries_are_rejected(self):
        paths = ["/api/v1/commands", "/api/v1/control/dispatch", "/api/v1/voice/token",
                 "/api/v1/lab/providers/observe", "/api/v1/cameras/cam/stream", "https://host/api/v1/sessions",
                 "/api/v1/cycles/..", "/api/v1/cycles/a%2fb", "/api/v1/cycles/a?x=y",
                 "/api/v1/cycles/a#fragment", "/api/v1/cycles/a\\b", "/api/v1/cycles/a\n"]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.enqueue(path=path)
        for query in ([], "", False, {"Authorization": "value"}, {"sessionId": "line\nbreak"}, {"sessionId": 3}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.enqueue(query=query)
        for query in ({"limit": "1001"}, {"limit": "0"}, {"after": "-1"}, {"after": "1.0"}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.enqueue(path="/api/v1/events", query=query)

    def test_events_are_always_bounded_and_get_routes_remain_available(self):
        path, query = read_target("/api/v1/events", {"once": "false", "limit": "1000", "after": "23"})
        self.assertEqual(query, {"once": "true", "limit": "500", "after": "23"})
        for path in ("/api/v1/schema", "/api/v1/cameras", "/api/v1/cycles/item:2", "/api/v1/evidence/image.1",
                     "/api/v1/sessions/run-1/metrics", "/api/v1/sessions/run-1/export"):
            self.assertEqual(read_target(path, {})[0], path)
        with self.assertRaises(ValueError):
            read_target("/api/v1/sessions/run-1/export", {"format": "html"})

    def test_wrong_worker_claim_and_station_cannot_submit(self):
        request, claim = self.claim()
        for changes in ({"worker_id": "wrong"}, {"claim_id": str(uuid4())}, {"station_id": "wrong"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.relay.submit(**self.response(request, claim, **changes))
        self.assertEqual(self.relay.read("intel-test", request["request_id"])["state"], "claimed")

    def test_expired_reads_never_return_old_response_or_reset_on_duplicate(self):
        request, claim = self.claim()
        self.relay.submit(**self.response(request, claim))
        self.time += 31
        expired = self.relay.read("intel-test", request["request_id"])
        self.assertEqual(expired["state"], "expired")
        self.assertNotIn("body_base64", expired)
        self.assertEqual(self.enqueue(request_id=request["request_id"]), expired)
        with self.assertRaises(ValueError):
            self.relay.submit(**self.response(request, claim))
        self.assertEqual(self.relay.claim("intel-test", "worker-test")["requests"], [])
        with self.relay.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM parts").fetchone()[0], 0)
            self.assertIsNone(db.execute("SELECT body_base64 FROM reads").fetchone()[0])

    def test_pending_queue_is_bounded_and_expiration_releases_capacity(self):
        for _ in range(MAX_ACTIVE):
            self.enqueue()
        with self.assertRaisesRegex(ValueError, "queue is full"):
            self.enqueue()
        self.time += 31
        self.assertEqual(self.enqueue()["state"], "queued")

    def test_chunk_order_integrity_pagination_and_restart(self):
        request, claim = self.claim()
        raw = bytes(range(256)) * 250
        encoded = base64.b64encode(raw).decode()
        chunks = [encoded[:MAX_CHUNK], encoded[MAX_CHUNK:]]
        common = self.response(request, claim, raw, part_count=2, content_type="application/octet-stream")
        result = self.relay.submit(**{**common, "part_index": 1, "body_base64": chunks[1]})
        self.assertEqual(result["state"], "claimed")
        self.assertNotIn("body_base64", self.relay.read("intel-test", request["request_id"]))
        self.relay = StationRelay(self.root, clock=lambda: self.time)
        self.assertEqual(self.relay.submit(**{**common, "part_index": 0, "body_base64": chunks[0]})["state"], "ready")
        offset, pieces = 0, []
        while True:
            page = self.relay.read("intel-test", request["request_id"], offset, 137)
            pieces.append(page["body_base64"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        self.assertEqual(base64.b64decode("".join(pieces)), raw)
        self.assertEqual(page["response_sha256"], hashlib.sha256(raw).hexdigest())

    def test_hash_and_conflicting_part_fail_without_poisoning_original(self):
        request, claim = self.claim()
        good = self.response(request, claim)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.relay.submit(**{**good, "response_sha256": "0" * 64})
        self.assertEqual(self.relay.submit(**good)["state"], "ready")
        before = self.relay.read("intel-test", request["request_id"])
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.relay.submit(**{**good, "body_base64": base64.b64encode(b"different").decode()})
        with self.assertRaisesRegex(ValueError, "metadata changed"):
            self.relay.submit(**{**good, "status_code": 500})
        self.assertEqual(before, self.relay.read("intel-test", request["request_id"]))

    def test_concurrent_duplicate_submissions_keep_one_ready_response(self):
        request, claim = self.claim()
        body = self.response(request, claim)
        with ThreadPoolExecutor(max_workers=8) as pool:
            result = list(pool.map(lambda _: self.relay.submit(**body), range(16)))
        self.assertTrue(all(row["state"] == "ready" for row in result))
        with self.relay.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM parts").fetchone()[0], 1)

    def test_bad_parts_timestamps_status_and_headers_are_denied(self):
        request, claim = self.claim()
        invalid = [{"part_index": -1}, {"part_count": 95}, {"part_count": True}, {"body_base64": "not!base64"},
                   {"body_base64": "A" * (MAX_CHUNK + 1)}, {"status_code": 302}, {"status_code": True},
                   {"content_type": "text/html"}, {"content_type": "application/json;\x00broken"},
                   {"content_type": "application/json\r\nX: forged"}, {"content_type": "application/json;\x7fbad"},
                   {"captured_at": "2026-11-15T10:00:00"}, {"captured_at": iso(self.time + 11)},
                   {"captured_at": iso(self.time - 6)}]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.relay.submit(**self.response(request, claim, **changes))
        self.assertEqual(self.relay.read("intel-test", request["request_id"])["state"], "claimed")

    def test_body_bound_and_read_pagination_validation(self):
        request, claim = self.claim()
        with patch("station_relay.MAX_BODY", 5), self.assertRaises(ValueError):
            self.relay.submit(**self.response(request, claim))
        self.relay.submit(**self.response(request, claim))
        for offset, limit in ((-1, 1), (True, 1), (0, 0), (0, MAX_CHUNK + 1), (99999, 1)):
            with self.subTest(offset=offset, limit=limit), self.assertRaises(ValueError):
                self.relay.read("intel-test", request["request_id"], offset, limit)

    def test_storage_symlink_is_rejected(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (self.root / ".junction-setup").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.enqueue()
        self.assertEqual(list(outside.iterdir()), [])


class RelayMCPTests(RelayFixture):
    def rpc(self, client, headers, method, arguments=None):
        message = {"jsonrpc": "2.0", "id": 1, "method": method}
        if arguments is not None:
            message["params"] = arguments
        response = client.post("/mcp", json=message, headers=headers)
        self.assertEqual(response.status_code, 200)
        return response.json()["result"]

    def test_opt_in_registration_and_authenticated_real_tool_roundtrip(self):
        token = "relay-test-" + "x" * 40
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
        expected = {"enqueue_station_read", "claim_station_reads", "submit_station_read_chunk", "read_station_response"}
        for enabled in (False, True):
            app = http_app(create_server(self.root, enable_station_relay=enabled), token, "127.0.0.1", 8765)
            with TestClient(app, base_url="http://127.0.0.1:8765") as client:
                listed = self.rpc(client, headers, "tools/list")
                names = {row["name"] for row in listed["tools"]}
                self.assertEqual(names & expected, expected if enabled else set())
                if not enabled:
                    self.assertFalse(self.relay.db_path.exists())
                    continue
                def call(name, values):
                    result = self.rpc(client, headers, "tools/call", {"name": name, "arguments": values})
                    self.assertFalse(result.get("isError"), result)
                    return result["structuredContent"]
                identity = str(uuid4())
                params = {"station_id": "intel-test", "request_id": identity, "path": "/api/v1/sessions", "query": {}}
                unauthorized = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "enqueue_station_read", "arguments": params}})
                self.assertEqual(unauthorized.status_code, 401)
                queued = call("enqueue_station_read", params)
                claim = call("claim_station_reads", {"station_id": "intel-test", "worker_id": "worker-test"})["requests"][0]
                raw = b'[{"id":"fixture","sourceMode":"simulation"}]'
                values = self.response(queued, claim, raw, captured_at=iso(__import__("time").time()))
                self.assertEqual(call("submit_station_read_chunk", values)["state"], "ready")
                read = call("read_station_response", {"station_id": "intel-test", "request_id": identity})
                self.assertEqual(base64.b64decode(read["body_base64"]), raw)
                self.assertEqual(read["response_sha256"], hashlib.sha256(raw).hexdigest())
                denied = self.rpc(client, headers, "tools/call", {"name": "enqueue_station_read", "arguments": {**params, "request_id": str(uuid4()), "path": "/api/v1/commands"}})
                self.assertTrue(denied.get("isError"))


if __name__ == "__main__":
    unittest.main()
