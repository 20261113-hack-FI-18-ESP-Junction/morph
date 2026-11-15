"""Offline fake-client checks for the prepared relay harness; no network calls."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).with_name("verify_live_dashboard_relay.py")
spec = importlib.util.spec_from_file_location("reviewed_relay_harness", SOURCE)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def detail(identifier, with_image=False):
    cycle = {"id": identifier, "sessionId": "session-1", "objectId": "object-1"}
    result = {"cycle": cycle, "frames": [], "evidence": [], "inspections": []}
    if with_image:
        result["frames"] = [{"id": "frame-1", "evidenceId": "evidence-1", **{
            k: cycle[k] for k in ("sessionId", "objectId")}, "cycleId": identifier}]
        result["evidence"] = [{"id": "evidence-1", "mediaType": "image/png", "sessionId": "session-1",
                               "cycleId": identifier, "sha256": h.digest(b"offline-image"), "size": 13}]
        result["inspections"] = [{"frameIds": ["frame-1"]}]
    return result


def aggregate(focused=None, live=False):
    current = detail("cycle-current")
    result = {"sourceMode": "live" if live else "simulation", "selectedSessionId": None if live else "session-1",
              "generatedAt": "first-generation", "lastEventSequence": 50, "metrics": {},
              "sessions": {"total": 0 if live else 1}, "currentDetail": None if live else current,
              "detail": None if live else focused or current,
              "recentCycles": {"items": [] if live else [current["cycle"], detail("cycle-image")["cycle"]],
                               "total": 0 if live else 2, "offset": 0, "limit": 20, "hasMore": False}}
    result["snapshot"] = {"generatedAt": "first-generation", "lastEventSequence": 50, "stateVersion": 50,
                          "metrics": {}, "session": None if live else {"id": "session-1", "sourceMode": "simulation"}}
    return result


class FakeClient:
    def __init__(self, scenario, raw):
        self.scenario, self.raw, self.request_id = scenario, raw, None
        self.expires = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def call(self, method, **args):
        if method == "enqueue_station_read":
            self.request_id = args["request_id"]
            return {"request_id": self.request_id, "state": "queued", "expires_at": self.expires}
        encoded = base64.b64encode(self.raw).decode()
        offset = args["offset"]
        chunk = encoded[offset:offset + 8]
        result = {"request_id": self.request_id, "state": "expired" if self.scenario == "expired" else "ready",
                  "expires_at": self.expires, "captured_at": self.timestamp, "completed_at": self.timestamp,
                  "content_type": "application/json", "response_sha256": h.digest(self.raw), "status_code": 200,
                  "offset": offset, "body_base64": chunk,
                  "next_offset": offset + len(chunk) if offset + len(chunk) < len(encoded) else None}
        if self.scenario == "bad_hash":
            result["response_sha256"] = "0" * 64
        if self.scenario == "changed_metadata" and offset:
            result["captured_at"] = self.expires
        return result


class PreparedHarnessTests(unittest.TestCase):
    def test_generation_fields_only_are_ignored(self):
        original = {"generatedAt": "one", "snapshot": {"generatedAt": "one", "capturedAt": "keep"},
                    "record": {"generatedAt": "preserve"}, "lastEventSequence": 50}
        self.assertEqual(h.semantic(original), {"snapshot": {"capturedAt": "keep"},
                                               "record": {"generatedAt": "preserve"}, "lastEventSequence": 50})
        self.assertIn("generatedAt", original)

    def test_route_scope(self):
        for path, query in (("/api/v1/schema", {}), ("/api/v1/dashboard", {"sourceMode": "simulation"}),
                            ("/api/v1/evidence/image-1", {})):
            h.allowed_route(path, query)
        for path, query in (("/health", {}), ("/api/v1/command", {}), ("/api/v1/dashboard/extra", {}),
                            ("/api/v1/evidence/../secret", {}), ("/api/v1/schema", {"x": "1"}),
                            ("/api/v1/dashboard", {"limit": "101"}), ("/api/v1/dashboard", {"sourceMode": "all"})):
            with self.subTest(path=path, query=query), self.assertRaises(h.CheckFailure):
                h.allowed_route(path, query)

    def test_cycle_discovery_is_scoped_deduplicated_and_bounded(self):
        value = aggregate()
        self.assertEqual(h.discovered_cycle_ids(value, "session-1"), ["cycle-current", "cycle-image"])
        value["recentCycles"]["items"][1]["sessionId"] = "other-session"
        with self.assertRaisesRegex(h.CheckFailure, "saved_cycle_scope_mismatch"):
            h.discovered_cycle_ids(value, "session-1")
        value = aggregate()
        value["recentCycles"]["items"] *= 11
        with self.assertRaisesRegex(h.CheckFailure, "cycle_discovery_page_unbounded"):
            h.discovered_cycle_ids(value, "session-1")

    def test_images_require_inspection_frame_and_evidence_link(self):
        value = detail("cycle-image", True)
        self.assertEqual(len(h.image_candidates(value)), 1)
        value["inspections"] = []
        self.assertEqual(h.image_candidates(value), [])
        value = detail("cycle-image", True)
        value["evidence"][0]["id"] = "unlinked-evidence"
        self.assertEqual(h.image_candidates(value), [])

    def fake_case(self, scenario, expected_error=None):
        with tempfile.TemporaryDirectory() as directory:
            harness = h.Harness(Path(directory))
            raw = b'{"value":12345}'
            harness.client = FakeClient(scenario, raw)
            harness.budget = SimpleNamespace(deadline=0)
            harness.direct = lambda *args: ({"httpStatus": 200, "contentType": "application/json"}, raw)
            if expected_error:
                with self.assertRaisesRegex(h.CheckFailure, expected_error):
                    harness.case("offline", "/api/v1/schema", {})
                saved = json.loads((Path(directory) / "offline/failure.json").read_text())
                self.assertEqual(saved["errorCode"], expected_error)
            else:
                self.assertEqual(harness.case("offline", "/api/v1/schema", {}), {"value": 12345})
                self.assertEqual(harness.report["cases"][0]["responsePages"], 3)

    def test_multipart_response(self):
        self.fake_case("multipart")

    def test_bad_hash_is_saved_and_rejected(self):
        self.fake_case("bad_hash", "relay_body_hash_or_size_mismatch")

    def test_expired_response_is_saved_and_rejected(self):
        self.fake_case("expired", "relay_response_expired")

    def test_changed_pagination_metadata_is_saved_and_rejected(self):
        self.fake_case("changed_metadata", "relay_pagination_metadata_changed")

    def test_older_image_cycle_is_discovered_without_seeding(self):
        class FakeHarness(h.Harness):
            def initialize(self):
                pass

            def case(self, label, path, query, expected_status=200, *, image=False):
                self.report["cases"].append({"label": label, "status": "passed", "query": query})
                if path == "/api/v1/schema":
                    return {"capabilities": {"dashboardRead": h.CAPABILITY}, "responses": {"Dashboard": {}}}
                if image:
                    return b"offline-image"
                if expected_status != 200:
                    return {"detail": "expected fake rejection"}
                if query["sourceMode"] == "live":
                    return aggregate(live=True)
                if query.get("cycleId") == "cycle-image":
                    return aggregate(detail("cycle-image", True))
                return aggregate()

        original = h.EVIDENCE_DIRECTORY
        try:
            with tempfile.TemporaryDirectory() as directory:
                h.EVIDENCE_DIRECTORY = Path(directory)
                (Path(directory) / h.digest(b"offline-image")).write_bytes(b"offline-image")
                harness = FakeHarness(Path(directory))
                harness.execute()
                self.assertEqual(harness.report["status"], "passed")
                self.assertEqual(harness.report["discoveredCycleId"], "cycle-image")
                self.assertEqual(harness.report["imageCycleDiscovery"]["attemptedCycleIds"],
                                 ["cycle-current", "cycle-image"])
                self.assertEqual(harness.report["requestedCasesPassed"], 9)
        finally:
            h.EVIDENCE_DIRECTORY = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
