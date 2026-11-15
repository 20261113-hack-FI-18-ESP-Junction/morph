"""Offline station-worker tests. All HTTP/MCP endpoints are in-memory fakes."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import uuid

MODULE_PATH = Path(__file__).resolve().parents[1] / "station_worker.py"
SPEC = importlib.util.spec_from_file_location("morph_station_worker_test_target", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)
TOKEN = "test-only-worker-token-" + "x" * 40
NOW = datetime(2026, 11, 15, 3, tzinfo=timezone.utc)


class Response:
    def __init__(self, body=b"{}", status=200, content_type="application/json", headers=None):
        self.content = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": content_type, **(headers or {})}
        self.closed = False

    def read(self, size):
        return self.content.read(size)

    read1 = read

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def claim(**changes):
    return {"request_id": "read-1", "path": "/api/v1/station/snapshot", "query": {},
            "claim_id": str(uuid.uuid4()), "expires_at": (NOW + timedelta(seconds=30)).isoformat(), **changes}


class FakeMCP:
    def __init__(self, requests):
        self.requests = requests
        self.calls = []

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "claim_station_reads":
            return {"requests": self.requests}
        return {"state": "ready" if arguments["part_index"] == arguments["part_count"] - 1 else "claimed"}


class FakeStation:
    def __init__(self, body=b"{}", status=200, content_type="application/json"):
        self.result = worker.ReadResult(status, content_type, body, NOW.isoformat())
        self.calls = []

    def read(self, path, query):
        self.calls.append((path, query))
        return self.result


class WorkerRouteTests(unittest.TestCase):
    def test_dashboard_read_query_is_bounded_and_explicit(self):
        query = {"sessionId": "session-1", "cycleId": "cycle-1", "sourceMode": "simulation", "limit": 100}
        self.assertEqual(worker.validated_read("/api/v1/dashboard", query),
                         ("/api/v1/dashboard", {**query, "limit": "100"}))
        for invalid in ({"limit": 101}, {"limit": 0}, {"sourceMode": "all"},
                        {"sessionId": ".."}, {"cycleId": "../other"}, {"includeSimulation": True}):
            with self.subTest(query=invalid), self.assertRaises(worker.WorkerError):
                worker.validated_read("/api/v1/dashboard", invalid)

    def test_allowed_reads_and_scoped_query_preserved(self):
        paths = {"/api/v1/schema": {}, "/api/v1/station/snapshot": {"sessionId": "s1"},
            "/api/v1/sessions": {}, "/api/v1/metrics": {"includeSimulation": False},
            "/api/v1/cycles": {"sessionId": "s1", "limit": 500, "startedAfter": NOW.isoformat()},
            "/api/v1/cameras": {}, "/api/v1/sessions/s1/metrics": {"includeSimulation": True},
            "/api/v1/sessions/s1/export": {"format": "csv"}, "/api/v1/cycles/c1": {},
            "/api/v1/evidence/frame1": {}}
        for path, query in paths.items():
            with self.subTest(path=path):
                actual, _ = worker.validated_read(path, query)
                self.assertEqual(actual, path)

    def test_events_always_finite_and_bounded(self):
        _, query = worker.validated_read("/api/v1/events", {"after": 51, "once": False, "limit": 1000})
        self.assertEqual(query, {"after": "51", "once": "true", "limit": "500"})
        self.assertEqual(worker.validated_read("/api/v1/events", {})[1], {"once": "true", "limit": "100"})

    def test_actions_encoded_paths_traversal_and_hosts_rejected(self):
        forbidden = ["/api/v1/commands", "/api/v1/control/snapshot", "/api/v1/control/dispatch",
            "/api/v1/lab/providers/observe", "/api/v1/voice/token", "/api/v1/records",
            "/api/v1/cameras/c1/stream", "/api/v1/sessions/s1/end", "/health", "https://other/api/v1/sessions",
            "//other/api/v1/sessions", "/api/v1/evidence/../token", "/api/v1/evidence/%2e%2e",
            "/api/v1/evidence/..", "/api/v1/sessions?redirect=other", "/api/v1/sessions#fragment",
            "/api/v1/cycles/c1\\other", "/api/v1/cycles/c1/", "/api/v1/sessions//export"]
        for path in forbidden:
            with self.subTest(path=path), self.assertRaises(worker.WorkerError):
                worker.validated_read(path, {})

    def test_unknown_or_unbounded_query_rejected(self):
        for path, query in [("/api/v1/sessions", {"command": "start"}),
                ("/api/v1/events", {"limit": 1001}), ("/api/v1/events", {"after": -1}),
                ("/api/v1/events", {"limit": 0}), ("/api/v1/events", {"once": "sometimes"}),
                ("/api/v1/cycles", {"modelId": {"url": "other"}}),
                ("/api/v1/station/snapshot", {"sessionId": "x\nHeader: bad"})]:
            with self.subTest(path=path, query=query), self.assertRaises(worker.WorkerError):
                worker.validated_read(path, query)


class StationHTTPTests(unittest.TestCase):
    def test_fixed_origin_get_token_header_and_query_encoding(self):
        response = Response(b'{"cycles":[]}', content_type="application/json; charset=utf-8")
        opener = Opener(response)
        station = worker.StationHTTP("http://127.0.0.1:8000/", TOKEN, opener=opener)
        result = station.read("/api/v1/cycles", {"modelId": "abc&url=https://other"})
        request, timeout = opener.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(timeout, 15)
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/api/v1/cycles?modelId=abc%26url%3Dhttps%3A%2F%2Fother")
        self.assertEqual(result.body, b'{"cycles":[]}')
        self.assertEqual(result.content_type, "application/json; charset=utf-8")
        self.assertTrue(response.closed)
        self.assertNotIn(TOKEN, result.body.decode())

    def test_forbidden_request_never_contacts_api(self):
        opener = Opener()
        result = worker.StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener).read("/api/v1/commands", {})
        self.assertEqual(opener.requests, [])
        self.assertEqual(result.status_code, 502)
        self.assertEqual(json.loads(result.body), {"error": "read_path_not_allowed"})

    def test_redirect_denied_and_credentials_not_forwarded(self):
        with self.assertRaisesRegex(worker.WorkerError, "redirect_rejected"):
            worker.NoRedirect().redirect_request(None, None, 302, "secret", {}, "https://other")
        opener = Opener(Response(b"secret", status=302))
        result = worker.StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener).read("/api/v1/sessions", {})
        self.assertEqual(result.status_code, 502)
        self.assertEqual(json.loads(result.body), {"error": "redirect_rejected"})
        self.assertEqual(len(opener.requests), 1)

    def test_size_timeout_and_unsupported_type_errors_sanitized(self):
        for response, expected in [(Response(b"x" * (worker.MAX_BODY_BYTES + 1)), "response_too_large"),
                (TimeoutError("the-secret-token"), "station_transport_error"),
                (Response(b"the-secret-token", content_type="text/html"), "unsupported_content_type")]:
            with self.subTest(expected=expected):
                result = worker.StationHTTP("http://127.0.0.1:8000", TOKEN, opener=Opener(response)).read("/api/v1/sessions", {})
                self.assertEqual(json.loads(result.body), {"error": expected})
                self.assertEqual(result.status_code, 502)

    def test_http_error_status_and_finite_sse_bytes_preserved(self):
        failure = urllib.error.HTTPError("http://private", 409, "Conflict", {"Content-Type": "application/json"}, io.BytesIO(b'{"detail":"cursor ahead"}'))
        result = worker.StationHTTP("http://127.0.0.1:8000", TOKEN, opener=Opener(failure)).read("/api/v1/events", {"after": 99})
        self.assertEqual((result.status_code, result.body), (409, b'{"detail":"cursor ahead"}'))
        body = b'id: 1\nevent: record.updated\ndata: {"id":"cycle1"}\n\n: caught-up\n\n'
        opener = Opener(Response(body, content_type="text/event-stream; charset=utf-8"))
        result = worker.StationHTTP("http://127.0.0.1:8000", TOKEN, opener=opener).read("/api/v1/events", {})
        self.assertEqual(result.body, body)
        self.assertTrue(opener.requests[0][0].full_url.endswith("once=true&limit=100"))

    def test_endpoint_configuration_cannot_smuggle_url(self):
        for endpoint in ["file:///etc/passwd", "http://user:password@localhost", "http://localhost/path",
                "http://localhost?secret=yes", "http://localhost/#fragment", "http://localhost:99999"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(worker.WorkerError):
                worker.StationHTTP(endpoint, TOKEN)
        with self.assertRaises(worker.WorkerError):
            worker.checked_url("http://localhost:8765/mcp", mcp=True)

    def test_body_deadline_does_not_accept_endless_small_chunks(self):
        response = Response(b"still streaming")
        with patch.object(worker.time, "monotonic", return_value=16):
            with self.assertRaisesRegex(worker.WorkerError, "response_timeout"):
                worker.bounded_read(response, 100, deadline=15)


class MCPTests(unittest.TestCase):
    def test_existing_initialize_protocol_then_only_queue_tools(self):
        def rpc(identity, result):
            return Response(json.dumps({"jsonrpc": "2.0", "id": identity, "result": result}).encode())
        opener = Opener(rpc(1, {"protocolVersion": "2025-11-25", "serverInfo": {"name": "morph-context"}}),
            Response(b"", status=202), rpc(2, {"structuredContent": {"requests": []}}))
        client = worker.MCPClient("https://mac.example:8765/mcp", TOKEN, opener=opener)
        client.initialize()
        self.assertEqual(client.call("claim_station_reads", {"station_id": "intel-main"}), {"requests": []})
        payloads = [json.loads(request.data) for request, _ in opener.requests]
        self.assertEqual([p["method"] for p in payloads], ["initialize", "notifications/initialized", "tools/call"])
        self.assertEqual(payloads[0]["params"]["protocolVersion"], "2025-11-25")
        self.assertNotIn("id", payloads[1])
        self.assertEqual(opener.requests[2][0].get_header("Mcp-protocol-version"), "2025-11-25")
        with self.assertRaises(worker.WorkerError):
            client.call("save_handoff", {})
        self.assertEqual(len(opener.requests), 3)

    def test_rpc_and_provider_error_text_never_escapes(self):
        for response in [Response(json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"message": TOKEN}}).encode()),
                urllib.error.URLError(TOKEN),
                Response(json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": [{"text": TOKEN}]}}).encode())]:
            client = worker.MCPClient("https://mac.example/mcp", TOKEN, opener=Opener(response))
            with self.assertRaises(worker.WorkerError) as caught:
                client.call("claim_station_reads", {})
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_private_file_permissions_and_no_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token"
            path.write_text(TOKEN)
            path.chmod(0o600)
            self.assertEqual(worker.private_text(path), TOKEN)
            link = Path(directory) / "linked-token"
            link.symlink_to(path)
            with self.assertRaises(worker.WorkerError):
                worker.private_text(link)
            path.chmod(0o644)
            with self.assertRaises(worker.WorkerError):
                worker.private_text(path)


class QueueWorkerTests(unittest.TestCase):
    def test_4mb_binary_chunks_zero_based_hash_and_metadata_stable(self):
        body = bytes(range(256)) * (worker.MAX_BODY_BYTES // 256)
        mcp, station = FakeMCP([claim()]), FakeStation(body, content_type="image/png")
        instance = worker.StationWorker(mcp, station, clock=lambda: NOW)
        result = instance.run_once()
        self.assertEqual(result, {"claimed": 1, "completed": 1, "expired": 0, "failed": 0})
        parts = [arguments for name, arguments in mcp.calls if name == "submit_station_read_chunk"]
        self.assertEqual(len(parts), 94)
        self.assertEqual([part["part_index"] for part in parts], list(range(94)))
        self.assertTrue(all(part["part_count"] == 94 and len(part["body_base64"]) <= 60000 for part in parts))
        self.assertEqual(base64.b64decode("".join(part["body_base64"] for part in parts), validate=True), body)
        self.assertTrue(all(part["response_sha256"] == hashlib.sha256(body).hexdigest() for part in parts))
        self.assertEqual(len({part["worker_id"] for part in parts}), 1)
        self.assertEqual(mcp.calls[0][1]["limit"], 1)

    def test_empty_body_still_has_one_chunk(self):
        mcp = FakeMCP([claim()])
        result = worker.StationWorker(mcp, FakeStation(b"", 204), clock=lambda: NOW).run_once()
        self.assertEqual(result["completed"], 1)
        part = mcp.calls[-1][1]
        self.assertEqual((part["part_index"], part["part_count"], part["body_base64"]), (0, 1, ""))
        self.assertEqual(part["response_sha256"], hashlib.sha256(b"").hexdigest())

    def test_expired_claim_never_calls_station_and_tampering_stays_read_only(self):
        station = FakeStation()
        mcp = FakeMCP([claim(expires_at=NOW.isoformat()), claim(request_id="read-2", path="/api/v1/control/dispatch")])
        result = worker.StationWorker(mcp, station, clock=lambda: NOW).run_once(limit=2)
        self.assertEqual(result, {"claimed": 2, "completed": 1, "expired": 1, "failed": 0})
        self.assertEqual(station.calls, [])
        part = mcp.calls[-1][1]
        self.assertEqual(part["status_code"], 502)
        self.assertEqual(json.loads(base64.b64decode(part["body_base64"])), {"error": "read_path_not_allowed"})

    def test_expiry_during_read_never_submits_stale_result(self):
        moment = [NOW]
        class SlowStation(FakeStation):
            def read(self, path, query):
                moment[0] += timedelta(seconds=31)
                return super().read(path, query)
        mcp = FakeMCP([claim()])
        result = worker.StationWorker(mcp, SlowStation(), clock=lambda: moment[0]).run_once()
        self.assertEqual(result["expired"], 1)
        self.assertEqual(result["completed"], 0)
        self.assertEqual(len(mcp.calls), 1)

    def test_missing_final_readback_not_claimed_complete(self):
        class IncompleteMCP(FakeMCP):
            def call(self, name, arguments):
                result = super().call(name, arguments)
                return {"state": "claimed"} if name == "submit_station_read_chunk" else result
        mcp = IncompleteMCP([claim()])
        result = worker.StationWorker(mcp, FakeStation(), clock=lambda: NOW).run_once()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["completed"], 0)

    def test_lost_submit_reply_retries_identical_chunk_not_station_read(self):
        class LostReplyMCP(FakeMCP):
            lost = False
            def call(self, name, arguments):
                result = super().call(name, arguments)
                if name == "submit_station_read_chunk" and not self.lost:
                    self.lost = True
                    raise worker.WorkerError("mcp_transport_error")
                return result
        mcp, station = LostReplyMCP([claim()]), FakeStation()
        result = worker.StationWorker(mcp, station, clock=lambda: NOW).run_once()
        self.assertEqual(result["completed"], 1)
        self.assertEqual(len(station.calls), 1)
        self.assertEqual(mcp.calls[-2][1], mcp.calls[-1][1])

    def test_contract_roundtrip_with_actual_relay_and_fake_station(self):
        path = MODULE_PATH.with_name("station_relay.py")
        if not path.is_file():
            self.skipTest("Standalone worker copy has no Mac relay; worker unit checks still apply")
        spec = importlib.util.spec_from_file_location("morph_actual_relay_test_target", path)
        relay_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(relay_module)
        with tempfile.TemporaryDirectory() as directory:
            relay = relay_module.StationRelay(Path(directory), clock=lambda: NOW.timestamp())
            class DirectMCP:
                def call(self, name, arguments):
                    return {"claim_station_reads": relay.claim, "submit_station_read_chunk": relay.submit}[name](**arguments)
            request_id = str(uuid.uuid4())
            relay.enqueue("intel-main", request_id, "/api/v1/events", {"once": "false", "limit": "1000"})
            body = b': caught-up\n\n' * 10_000
            station = FakeStation(body, content_type="text/event-stream; charset=utf-8")
            result = worker.StationWorker(DirectMCP(), station, clock=lambda: NOW).run_once()
            self.assertEqual(result["completed"], 1)
            self.assertEqual(station.calls, [("/api/v1/events", {"once": "true", "limit": "500"})])
            offset, encoded = 0, ""
            while True:
                page = relay.read("intel-main", request_id, offset=offset)
                self.assertEqual(page["state"], "ready")
                encoded += page["body_base64"]
                if page["next_offset"] is None:
                    break
                offset = page["next_offset"]
            self.assertEqual(base64.b64decode(encoded), body)
            self.assertEqual(page["response_sha256"], hashlib.sha256(body).hexdigest())

    def test_worker_identity_stable_across_rounds(self):
        mcp = FakeMCP([])
        instance = worker.StationWorker(mcp, FakeStation(), clock=lambda: NOW)
        instance.run_once()
        instance.run_once()
        self.assertEqual(mcp.calls[0][1]["worker_id"], mcp.calls[1][1]["worker_id"])
        with self.assertRaises(worker.WorkerError):
            instance.run_once(limit=9)

    def test_invalid_configuration_exits_without_raw_token_or_network(self):
        with patch.dict(os.environ, {"MORPH_API_TOKEN": "private-bad-value"}, clear=True), patch("sys.stdout", new_callable=io.StringIO) as output:
            code = worker.main(["--once", "--pairing-folder", "/missing-pairing"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue()), {"error": "invalid_token_configuration"})
        self.assertNotIn("private-bad-value", output.getvalue())


if __name__ == "__main__":
    unittest.main()
