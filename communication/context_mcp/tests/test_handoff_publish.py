"""Offline publisher tests against the real ContextStore and event store."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

MODULE_DIR = Path(__file__).resolve().parents[1]
for parent in MODULE_DIR.parents:
    candidate = parent / "context_mcp/store.py"
    if candidate.is_file() and candidate.parent != MODULE_DIR:
        sys.path.insert(0, str(candidate.parent))
        break
sys.path.insert(0, str(MODULE_DIR))
from handoff_events import HandoffEvents
from handoff_publish import HandoffPublisher, PublisherError, EventMCP, REVIEW_AUTHOR, main
from store import ContextStore


class FakeMCP:
    def __init__(self, root):
        self.context = ContextStore(root)
        self.events = HandoffEvents(root)
        self.calls = []
        self.lost_save = False
        self.lost_publish = False
        self.read_hook = None
        self.event_hook = None

    def call(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if name == "save_handoff":
            result = self.context.save_note(**arguments)
            if self.lost_save:
                self.lost_save = False
                raise OSError("private remote diagnostic must not escape")
            return result
        if name == "read_context":
            result = self.context.read(arguments["path"], arguments["offset"], arguments["limit"])
            return self.read_hook(result) if self.read_hook else result
        if name == "publish_handoff_event":
            result = self.events.publish(**arguments)
            if self.lost_publish:
                self.lost_publish = False
                raise OSError("private remote diagnostic must not escape")
            return self.event_hook(result) if self.event_hook else result
        raise AssertionError("Unexpected tool")


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "AGENTS.md").write_text("# Test project\n")
        self.payload = {"note_id": str(uuid4()), "title": "Implemented reader", "content": "The read-only reader now validates evidence.",
                        "author": "Codex on Mac | implementation", "evidence": "Offline tests saved.", "status": "verified"}
        self.payload_path = self.root / "payload.json"
        self.receipt = self.root / "private-receipts/receipt.json"
        self.write_payload()
        self.mcp = FakeMCP(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def write_payload(self):
        self.payload_path.write_text(json.dumps(self.payload, ensure_ascii=False) + "\n")

    def publisher(self, mcp=None):
        return HandoffPublisher(mcp or self.mcp, self.payload_path, "mac", "intel", self.receipt)

    def load_receipt(self):
        return json.loads(self.receipt.read_text())

    def count(self, name):
        return sum(call[0] == name for call in self.mcp.calls)

    def test_save_verify_publish_order_and_exact_provenance(self):
        result = self.publisher().run()
        self.assertEqual([name for name, _ in self.mcp.calls], ["save_handoff", "read_context", "publish_handoff_event"])
        receipt = self.load_receipt()
        self.assertEqual(receipt["phase"], "event_published")
        self.assertEqual(receipt["note_id"], self.payload["note_id"])
        self.assertEqual(receipt["payload_path"], str(self.payload_path))
        self.assertEqual(receipt["payload_sha256"], hashlib.sha256(self.payload_path.read_bytes()).hexdigest())
        self.assertEqual(receipt["note_sha256"], self.mcp.context.read(receipt["note_path"])["sha256"])
        self.assertEqual(receipt["event_id"], result["event_id"])
        source = Path(receipt["publisher_source"]["path"])
        self.assertEqual(receipt["publisher_source"]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertNotIn("content", receipt)
        self.assertEqual(stat.S_IMODE(self.receipt.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.receipt.parent.stat().st_mode), 0o700)

    def test_completed_receipt_retry_has_no_network_or_duplicate(self):
        first = self.publisher().run(); before = len(self.mcp.calls)
        again = self.publisher().run()
        self.assertTrue(again["reused_receipt"])
        self.assertEqual(first["event_id"], again["event_id"])
        self.assertEqual(len(self.mcp.calls), before)
        self.assertEqual(len(self.mcp.events.poll("intel", "receiver")["events"]), 1)

    def test_lost_publish_reply_retries_same_event_without_resaving_note(self):
        self.mcp.lost_publish = True
        with self.assertRaisesRegex(PublisherError, "mcp_call_failed"):
            self.publisher().run()
        saved = self.load_receipt()
        self.assertEqual(saved["phase"], "saved_note")
        self.assertEqual(self.mcp.events.poll("intel", "receiver")["high_water"], 1)
        result = self.publisher().run()
        self.assertEqual(self.count("save_handoff"), 1)
        self.assertEqual(self.count("publish_handoff_event"), 2)
        self.assertEqual(result["event_seq"], 1)
        self.assertFalse(self.load_receipt()["event_created"])

    def test_lost_save_reply_retains_prepared_identity_and_reuses_uuid(self):
        self.mcp.lost_save = True
        with self.assertRaisesRegex(PublisherError, "mcp_call_failed"):
            self.publisher().run()
        self.assertEqual(self.load_receipt()["phase"], "prepared")
        self.assertEqual(self.count("publish_handoff_event"), 0)
        result = self.publisher().run()
        self.assertEqual(result["event_seq"], 1)
        self.assertEqual(self.count("save_handoff"), 2)
        saved_ids = {args["note_id"] for name, args in self.mcp.calls if name == "save_handoff"}
        self.assertEqual(saved_ids, {self.payload["note_id"]})

    def test_paginated_unicode_note_preserves_full_source_hash(self):
        self.payload["content"] = "Ž" * 24_000
        self.payload["evidence"] = "E" * 4000
        self.write_payload()
        self.publisher().run()
        self.assertEqual(self.count("read_context"), 2)
        receipt = self.load_receipt()
        self.assertGreater(receipt["note_characters"], 24_000)
        raw = (self.root / receipt["note_path"]).read_bytes()
        self.assertEqual(receipt["note_sha256"], hashlib.sha256(raw).hexdigest())

    def test_saved_note_mismatch_prevents_event(self):
        def change(page):
            note = json.loads(page["content"]); note["title"] = "Unexpected title"
            raw = json.dumps(note)
            return {**page, "content": raw, "total_characters": len(raw), "sha256": hashlib.sha256(raw.encode()).hexdigest()}
        self.mcp.read_hook = change
        with self.assertRaisesRegex(PublisherError, "saved_note_content_mismatch"):
            self.publisher().run()
        self.assertEqual(self.count("publish_handoff_event"), 0)
        self.assertEqual(self.load_receipt()["phase"], "prepared")

    def test_page_redaction_and_hash_or_pagination_mismatch_prevent_event(self):
        for index, modification in enumerate(({"redacted": True}, {"sha256": "0" * 64}, {"next_offset": 1}, {"total_characters": 999_999})):
            self.receipt = self.root / "private-receipts" / f"receipt-{index}.json"
            self.mcp.read_hook = lambda page: {**page, **modification}
            with self.subTest(modification=modification), self.assertRaises(PublisherError):
                self.publisher().run()
        self.assertEqual(self.count("publish_handoff_event"), 0)

    def test_hash_change_between_pages_prevents_event(self):
        self.payload["content"] = "A" * 24_000; self.write_payload()
        self.mcp.read_hook = lambda page: {**page, "sha256": "0" * 64} if page["offset"] else page
        with self.assertRaisesRegex(PublisherError, "saved_note_page_mismatch"):
            self.publisher().run()
        self.assertEqual(self.count("publish_handoff_event"), 0)

    def test_saved_phase_detects_subsequently_changed_note(self):
        self.mcp.lost_publish = True
        with self.assertRaises(PublisherError):
            self.publisher().run()
        path = self.root / self.load_receipt()["note_path"]
        note = json.loads(path.read_text()); note["verification_notice"] += " changed"
        path.write_text(json.dumps(note))
        with self.assertRaisesRegex(PublisherError, "saved_note_changed"):
            self.publisher().run()
        self.assertEqual(self.count("publish_handoff_event"), 1)

    def test_scheduled_author_and_structured_ack_rejected_before_network(self):
        original = dict(self.payload)
        for change in ({"author": REVIEW_AUTHOR}, {"content": '{"event_type":"ack"}'}, {"content": '{"kind":"receipt"}'}):
            self.payload = {**original, **change}; self.write_payload()
            with self.subTest(change=change), self.assertRaises(PublisherError):
                self.publisher()
        self.assertEqual(self.mcp.calls, [])
        self.assertFalse(self.receipt.exists())

    def test_narrative_receipt_word_is_valid_substantive_work(self):
        self.payload["content"] = "Implemented bounded source checks and saved a receipt for the test result."
        self.write_payload()
        self.assertEqual(self.publisher().run()["phase"], "event_published")

    def test_extra_fields_duplicate_json_and_invalid_status_rejected(self):
        self.payload["event_type"] = "work"; self.write_payload()
        with self.assertRaisesRegex(PublisherError, "invalid_payload_fields"):
            self.publisher()
        del self.payload["event_type"]; self.payload["status"] = "Done"; self.write_payload()
        with self.assertRaisesRegex(PublisherError, "invalid_note_status"):
            self.publisher()
        self.payload_path.write_text('{"note_id":"one","note_id":"two"}')
        with self.assertRaisesRegex(PublisherError, "invalid_json"):
            self.publisher()
        self.assertEqual(self.mcp.calls, [])

    def test_changed_payload_receipt_and_direction_are_not_rebound(self):
        self.publisher().prepare()
        self.payload["content"] += " Changed"; self.write_payload()
        with self.assertRaisesRegex(PublisherError, "receipt_identity_conflict"):
            self.publisher().run()
        with self.assertRaisesRegex(PublisherError, "invalid_direction"):
            HandoffPublisher(self.mcp, self.payload_path, "mac", "mac", self.receipt)
        with self.assertRaisesRegex(PublisherError, "invalid_direction"):
            HandoffPublisher(self.mcp, self.payload_path, [], "intel", self.receipt)
        self.assertEqual(self.mcp.calls, [])

    def test_payload_change_after_construction_is_rejected(self):
        publisher = self.publisher()
        self.payload_path.write_bytes(self.payload_path.read_bytes() + b" ")
        with self.assertRaisesRegex(PublisherError, "payload_changed"):
            publisher.run()
        self.assertEqual(self.mcp.calls, [])

    def test_wrong_event_reply_retains_saved_note_for_retry(self):
        self.mcp.event_hook = lambda result: {**result, "event": {**result["event"], "event_id": str(uuid4())}}
        with self.assertRaisesRegex(PublisherError, "event_publication_mismatch"):
            self.publisher().run()
        self.assertEqual(self.load_receipt()["phase"], "saved_note")
        self.mcp.event_hook = None
        self.assertEqual(self.publisher().run()["event_seq"], 1)

    def test_unprivate_or_symlink_receipt_rejected(self):
        self.publisher().prepare()
        self.receipt.chmod(0o644)
        with self.assertRaisesRegex(PublisherError, "receipt_not_private"):
            self.publisher().run()
        self.receipt.unlink(); self.receipt.symlink_to(self.payload_path)
        with self.assertRaisesRegex(PublisherError, "local_symlink_rejected"):
            self.publisher().run()
        self.assertEqual(self.mcp.calls, [])

    def test_receipt_lock_rejects_parallel_publisher(self):
        publisher = self.publisher()
        with publisher.locked():
            with self.assertRaisesRegex(PublisherError, "publisher_already_running"):
                self.publisher().run()
        self.assertEqual(self.mcp.calls, [])

    def test_corrupt_completed_receipt_does_not_claim_success(self):
        self.publisher().run()
        receipt = self.load_receipt(); receipt["event_id"] = str(uuid4())
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(PublisherError, "invalid_receipt_event"):
            self.publisher().run()

    def test_secret_marker_refused_without_printing_it(self):
        marker = "nvapi-" + "A" * 40
        self.payload["content"] = marker; self.write_payload()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch.object(EventMCP, "from_pairing") as connect:
            result = main(["--pairing-folder", str(self.root / "unused"), "--payload", str(self.payload_path),
                           "--origin", "mac", "--target", "intel", "--receipt-file", str(self.receipt)])
        self.assertEqual(result, 1)
        self.assertNotIn(marker, out.getvalue() + err.getvalue())
        self.assertIn("possible_secret_in_payload", err.getvalue())
        connect.assert_not_called()

    def test_transport_restricts_tool_set_and_sanitizes_remote_errors(self):
        class Client:
            def _request(self, *args):
                raise RuntimeError("secret remote contents")
        transport = EventMCP(Client())
        with self.assertRaisesRegex(PublisherError, "mcp_tool_not_allowed"):
            transport.call("claim_station_reads", {})
        with self.assertRaisesRegex(PublisherError, "^mcp_transport_failed$"):
            transport.call("save_handoff", {})


if __name__ == "__main__":
    unittest.main()
