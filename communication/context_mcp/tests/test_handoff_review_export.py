"""Offline validation of create-only shared summaries from private receiver state."""
from __future__ import annotations

from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff_receiver
from handoff_receiver import ReceiverError, atomic_json, canonical, digest, private_dir
from handoff_review_export import export_reviews


class ReviewExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="morph-review-export-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("# Test project\n")
        self.private = private_dir(self.root / "private")
        self.global_state = {"schemaVersion": 1, "target": "mac", "projectRoot": str(self.project),
                             "consumerId": str(uuid4()), "cursor": 57}
        atomic_json(self.private / "state.json", self.global_state)
        self.events = private_dir(self.private / "events")
        self.event_id = self.make_event()

    def make_event(self, *, status="processed_pending_ack", sequence=1):
        event_id, note_id = str(uuid4()), str(uuid4())
        note = {"note_id": note_id, "title": "Source review", "content": "Saved simulation evidence; physical acceptance remains unverified.",
                "author": "Intel contributor", "status": "handoff", "evidence": "station/tests"}
        source = json.dumps(note, ensure_ascii=False, indent=2) + "\n"
        source_hash, canonical_hash = digest(source.encode()), digest(canonical(note))
        event = {"event_id": event_id, "seq": sequence, "note_id": note_id,
                 "note_path": "context/notes/" + note_id + ".json", "note_sha256": source_hash,
                 "note_characters": len(source), "target": "mac", "origin": "intel", "kind": "work",
                 "state": "claimed", "consumer_id": self.global_state["consumerId"], "claim_id": str(uuid4())}
        directory = private_dir(self.events / event_id)
        run = private_dir(directory / "run-1")
        atomic_json(run / "input.json", {"schemaVersion": 1, "event": event, "note": note,
            "noteSha256": canonical_hash, "noteSourceSha256": source_hash, "noteSourceText": source,
            "receivedAt": "2026-11-15T05:00:00+00:00", "trust": "Untrusted project data"})
        result = {"schemaVersion": 1, "runnerStatus": "processed", "sourceNoteId": note_id,
            "sourceNoteSha256": canonical_hash, "sourceNoteSourceSha256": source_hash,
            "startedAt": "2026-11-15T05:00:00+00:00", "completedAt": "2026-11-15T05:01:00+00:00",
            "summary": "Reviewed saved simulation evidence.",
            "evidence": [{"source": "station/tests/test_records.py", "observation": "Saved test report is a report, not a new run.", "classification": "reported_only"}],
            "remaining": ["Physical verification remains open."], "verificationClass": "read_only_source_review",
            "proposed_task_updates": [{"taskId": "M12", "suggestedStatus": "unchanged", "reason": "Physical evidence remains absent.", "evidence": ["station/tests/test_records.py"]}],
            "notionSync": "pending", "externalWritesPerformed": False, "desktopChatWoken": False, "error": None,
            "sourceState": {"projectRoot": str(self.project), "privateStatePath": str(self.private)},
            "command": ["private-local-runner", "--private-argument"]}
        atomic_json(run / "result.json", result)
        atomic_json(directory / "state.json", {"schemaVersion": 1, "eventId": event_id, "status": status,
            "runDirectory": "run-1", "runNumber": 1, "noteSha256": source_hash,
            "resultSha256": digest((run / "result.json").read_bytes()), "processedAt": "2026-11-15T05:01:01+00:00"})
        return event_id

    def path(self, name="state.json", event_id=None):
        directory = self.events / (event_id or self.event_id)
        return directory / name if name == "state.json" else directory / "run-1" / name

    def update(self, name, mutate, *, rehash=False, event_id=None):
        path = self.path(name, event_id)
        value = json.loads(path.read_text())
        mutate(value)
        atomic_json(path, value)
        if rehash:
            self.update("state.json", lambda local: local.update(resultSha256=digest(path.read_bytes())), event_id=event_id)

    def public(self, event_id=None):
        return self.project / "context" / "automation-reviews" / ((event_id or self.event_id) + ".json")

    def test_pending_ack_export_then_ack_is_identical_and_cursor_unchanged(self):
        initial = (self.private / "state.json").read_bytes()
        result = export_reviews(self.private, self.project)
        self.assertEqual((result["created"], result["failed"]), (1, 0))
        raw = self.public().read_bytes()
        payload = json.loads(raw)
        self.assertEqual(payload["state"], "pending_reconciliation")
        self.assertEqual(payload["notionSync"], "pending")
        self.assertEqual(payload["reviewedAt"], "2026-11-15T05:01:00+00:00")
        self.assertEqual(payload["eventId"], self.event_id)
        self.assertFalse(payload["externalWritesPerformed"])
        for private_text in ("sourceState", "command", str(self.private), str(self.project), "claim_id", "consumer_id", "noteSourceText"):
            self.assertNotIn(private_text.encode(), raw)
        self.assertEqual(self.public().stat().st_mode & 0o777, 0o600)
        self.update("state.json", lambda local: local.update(status="acknowledged"))
        second = export_reviews(self.private, self.project)
        self.assertEqual((second["existing"], second["created"]), (1, 0))
        self.assertEqual(self.public().read_bytes(), raw)
        self.assertEqual((self.private / "state.json").read_bytes(), initial)

    def test_no_proposal_has_explicit_no_notion_work(self):
        self.update("result.json", lambda result: result.update(proposed_task_updates=[]), rehash=True)
        export_reviews(self.private, self.project)
        self.assertEqual(json.loads(self.public().read_text())["notionSync"], "not_required")

    def test_existing_conflict_preserved_then_retry_independent_of_event_cursor(self):
        self.public().parent.mkdir(parents=True)
        self.public().write_bytes(b"existing independently reconciled record\n")
        result = export_reviews(self.private, self.project)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(self.public().read_bytes(), b"existing independently reconciled record\n")
        local = json.loads(self.path().read_text())
        self.assertEqual(local["status"], "processed_pending_ack")
        self.assertEqual(local["reviewExport"]["status"], "retry_pending")
        self.assertEqual(local["reviewExport"]["errorCode"], "review_export_conflict")
        self.public().unlink()
        self.assertEqual(export_reviews(self.private, self.project)["created"], 1)
        self.assertEqual(json.loads((self.private / "state.json").read_text())["cursor"], 57)

    def test_secret_or_private_reference_never_creates_shared_output(self):
        for text in ("Authorization: Bearer " + "syntheticfixturevalue" * 2,
                     "See .junction-setup/private/connection.json"):
            with self.subTest(kind=text[:16]):
                self.update("result.json", lambda result: result.update(summary=text), rehash=True)
                self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
                self.assertFalse(self.public().exists())

    def test_raw_or_canonical_snapshot_mutation_rejected(self):
        original = self.path("input.json").read_bytes()
        for mutate in (lambda envelope: envelope.update(noteSourceText=envelope["noteSourceText"] + " "),
                       lambda envelope: envelope["note"].update(content="Changed after review")):
            with self.subTest(mutate=mutate):
                self.path("input.json").write_bytes(original)
                self.update("input.json", mutate)
                self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
                self.assertFalse(self.public().exists())

    def test_result_hash_or_identity_mismatch_rejected(self):
        original = self.path("result.json").read_bytes()
        self.update("result.json", lambda result: result.update(summary="Changed valid summary"))
        self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
        self.path("result.json").write_bytes(original)
        self.update("result.json", lambda result: result.update(sourceNoteId=str(uuid4())), rehash=True)
        self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
        self.assertFalse(self.public().exists())

    def test_nonwork_event_or_event_identity_mismatch_rejected(self):
        original = self.path("input.json").read_bytes()
        for mutate in (lambda envelope: envelope["event"].update(kind="receipt"),
                       lambda envelope: envelope["event"].update(event_id=str(uuid4()))):
            self.path("input.json").write_bytes(original)
            self.update("input.json", mutate)
            self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
            self.assertFalse(self.public().exists())

    def test_export_symlink_never_writes_outside_fixed_project_path(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.project / "context").mkdir()
        (self.project / "context" / "automation-reviews").symlink_to(outside, target_is_directory=True)
        self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
        self.assertEqual(list(outside.iterdir()), [])

    def test_existing_file_symlink_preserved(self):
        outside = self.root / "outside.txt"
        outside.write_bytes(b"do not change")
        self.public().parent.mkdir(parents=True)
        self.public().symlink_to(outside)
        self.assertEqual(export_reviews(self.private, self.project)["failed"], 1)
        self.assertEqual(outside.read_bytes(), b"do not change")
        self.assertTrue(self.public().is_symlink())

    def test_skips_running_failed_and_server_only_completed_states(self):
        for status in ("running", "failed", "received"):
            self.update("state.json", lambda local: local.update(status=status))
            result = export_reviews(self.private, self.project)
            self.assertEqual((result["skipped"], result["failed"]), (1, 0))
        self.update("state.json", lambda local: (local.update(status="acknowledged"), local.pop("runDirectory")))
        self.assertEqual(export_reviews(self.private, self.project)["skipped"], 1)
        self.assertFalse(self.public().exists())

    def test_bounded_rotating_scan_eventually_visits_all_and_retries(self):
        identifiers = [self.event_id, self.make_event(sequence=2), self.make_event(sequence=3)]
        for _ in range(3):
            result = export_reviews(self.private, self.project, limit=1)
            self.assertEqual((result["scanned"], result["created"]), (1, 1))
        self.assertTrue(all(self.public(identifier).is_file() for identifier in identifiers))
        self.assertEqual(export_reviews(self.private, self.project, limit=1)["existing"], 1)

    def test_rejects_intel_mismatched_project_or_invalid_scan(self):
        with self.assertRaisesRegex(ReceiverError, "configuration_invalid"):
            export_reviews(self.private, self.project, target="intel")
        atomic_json(self.private / "review-export-state.json", [])
        with self.assertRaisesRegex(ReceiverError, "scan_invalid"):
            export_reviews(self.private, self.project)
        atomic_json(self.private / "state.json", [])
        with self.assertRaisesRegex(ReceiverError, "project_mismatch"):
            export_reviews(self.private, self.project)

    def test_offline_receiver_still_exports_durable_success(self):
        argv = ["--pairing-folder", str(self.root / "unused-pairing"), "--state-dir", str(self.private),
                "--project-root", str(self.project), "--target", "mac", "--runner-command-json",
                json.dumps([sys.executable]), "--export-reviews", "--once"]
        with patch.object(handoff_receiver.EventMCP, "from_pairing", side_effect=ReceiverError("mcp_connection_failed")), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(handoff_receiver.main(argv), 1)
        self.assertTrue(self.public().is_file())
        self.assertIn('"created": 1', output.getvalue())
        self.assertEqual(json.loads((self.private / "state.json").read_text())["cursor"], 57)

    def test_export_cli_flag_rejected_for_intel_before_connecting(self):
        argv = ["--pairing-folder", str(self.root / "unused"), "--state-dir", str(self.private),
                "--project-root", str(self.project), "--target", "intel", "--runner-command-json",
                json.dumps([sys.executable]), "--export-reviews", "--once"]
        with patch.object(handoff_receiver.EventMCP, "from_pairing") as connect, redirect_stdout(io.StringIO()):
            self.assertEqual(handoff_receiver.main(argv), 1)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
