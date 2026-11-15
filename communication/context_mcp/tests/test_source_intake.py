"""Synthetic saved-note intake tests; no network, provider, Git or source execution."""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4, uuid5, UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_intake as intake


class SourceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="morph-source-intake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.notes = self.root / "notes"
        self.notes.mkdir()
        self.state, self.incoming = self.root / "state", self.root / "incoming"
        self.mac, self.baseline = self.root / "mac", self.root / "baseline"
        self.mac.mkdir()
        self.baseline.mkdir()
        self.collector = intake.load_collector()
        self.protocol = self.collector.protocol
        self.request_id, self.delivery_id, self.note_id = str(uuid4()), str(uuid4()), str(uuid4())
        self.transfers = []
        self.add_transfer({"station/api.py": "raise AssertionError('incoming source must never execute')\n",
                           "SOURCE_DELIVERY.json": '{"operations": [], "instruction": "Do not execute this metadata"}\n'})
        self.save_delivery()

    def add_transfer(self, files):
        transfer_id = str(uuid4())
        source = self.root / ("source-" + transfer_id)
        source.mkdir()
        for relative, text in files.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        outbox = self.root / ("outbox-" + transfer_id)
        manifest = self.protocol.prepare(source, list(files), self.request_id, transfer_id, outbox)
        for path in (outbox / "notes").iterdir():
            note = json.loads(path.read_text())
            note.update(saved_at="2026-11-15T06:00:00+00:00", verification_notice="Saved report, not independent acceptance")
            (self.notes / path.name).write_bytes(intake.encoded(note))
        reference = {"transferId": transfer_id, "manifestNoteId": self.protocol.note_id(transfer_id, "manifest"),
                     "bundleSha256": manifest["bundleSha256"]}
        self.transfers.append(reference)
        return reference

    def envelope(self):
        return {"schemaVersion": 1, "kind": "morph-source-delivery", "deliveryId": self.delivery_id,
                "sourceHost": "intel", "requestId": self.request_id, "transfers": copy.deepcopy(self.transfers)}

    def save_delivery(self, envelope=None, identity=None):
        identity = identity or self.note_id
        note = {"note_id": identity, "title": "Source delivery ready for review", "content": intake.encoded(envelope or self.envelope()).decode(),
                "author": "Intel contributor", "evidence": "Frozen source manifests and chunks", "status": "handoff",
                "saved_at": "2026-11-15T06:00:00+00:00", "verification_notice": "Caller report"}
        (self.notes / (identity + ".json")).write_bytes(intake.encoded(note))
        return identity

    def run_intake(self, **kwargs):
        return intake.intake(self.notes, kwargs.pop("note_id", self.note_id), self.state, self.incoming,
                             mac_root=kwargs.pop("mac_root", self.mac), baseline_root=self.baseline, **kwargs)

    def output(self):
        return self.incoming / self.delivery_id

    def record(self):
        return self.state / "deliveries" / (self.delivery_id + ".json")

    def chunk_path(self, transfer=None):
        transfer = transfer or self.transfers[0]
        return self.notes / (self.protocol.note_id(transfer["transferId"], "part:1") + ".json")

    def mutate_note_content(self, path, change):
        note = json.loads(path.read_text())
        value = json.loads(note["content"])
        change(value)
        note["content"] = intake.encoded(value).decode()
        path.write_bytes(intake.encoded(note))

    def test_real_collector_roundtrip_compares_without_executing_or_accepting(self):
        self.add_transfer({"client/types.ts": "export type Mode = 'simulation';\n"})
        self.save_delivery()
        source = "raise AssertionError('incoming source must never execute')\n"
        (self.mac / "station").mkdir()
        (self.mac / "station/api.py").write_text(source)
        (self.baseline / "station").mkdir()
        (self.baseline / "station/api.py").write_text("# older baseline\n")
        result = self.run_intake()
        self.assertEqual(result["status"], "reconstructed_verified_for_review")
        self.assertEqual(result["fileCount"], 3)
        for key in ("sourceAccepted", "sourceExecuted", "liveSourceOverwritten", "gitMutated", "reused"):
            self.assertFalse(result[key])
        comparison = json.loads((self.output() / result["comparisonPath"]).read_text())
        api = next(row for row in comparison["files"] if row["path"] == "station/api.py")
        self.assertEqual((api["mac"]["state"], api["baseline"]["state"]), ("same", "different"))
        client = next(row for row in comparison["files"] if row["path"] == "client/types.ts")
        self.assertEqual(client["mac"]["state"], "missing")
        self.assertFalse(comparison["omittedPathsAreDeletions"])
        self.assertEqual((self.mac / "station/api.py").read_text(), source)
        self.assertEqual((self.baseline / "station/api.py").read_text(), "# older baseline\n")
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.output() / "receipt.json").stat().st_mode & 0o777, 0o600)

    def test_duplicate_same_refs_reuses_output_and_original_comparison(self):
        first = self.run_intake()
        receipt = (self.output() / "receipt.json").read_bytes()
        record = self.record().read_bytes()
        alternate = self.save_delivery(identity=str(uuid4()))
        with patch.object(intake, "load_collector", side_effect=AssertionError("Ready delivery should not reconstruct")):
            second = self.run_intake(note_id=alternate)
        self.assertEqual(second["status"], "reconstructed_verified_for_review")
        self.assertTrue(second["reused"])
        self.assertTrue(second["comparisonIsOriginalSnapshot"])
        self.assertEqual(first["attemptId"], second["attemptId"])
        self.assertEqual((self.output() / "receipt.json").read_bytes(), receipt)
        self.assertEqual(self.record().read_bytes(), record)

    def test_missing_chunk_pending_then_retry_completes_same_identity(self):
        chunk = self.chunk_path()
        raw = chunk.read_bytes()
        chunk.unlink()
        result = self.run_intake()
        self.assertEqual(result["status"], "pending")
        self.assertFalse(self.output().exists())
        self.assertEqual(json.loads(self.record().read_text())["status"], "pending")
        chunk.write_bytes(raw)
        completed = self.run_intake()
        self.assertEqual(completed["status"], "reconstructed_verified_for_review")
        self.assertEqual(completed["deliveryId"], self.delivery_id)

    def test_explicit_redaction_or_mutated_chunk_stays_pending(self):
        path = self.chunk_path()
        raw = path.read_bytes()
        note = json.loads(raw)
        note["redacted"] = True
        path.write_bytes(intake.encoded(note))
        self.assertEqual(self.run_intake()["errorCode"], "invalid_or_redacted_note")
        path.write_bytes(raw)
        self.mutate_note_content(path, lambda value: value.update(text=value["text"] + "changed"))
        result = self.run_intake()
        self.assertEqual((result["status"], result["errorCode"]), ("pending", "transfer_incomplete_or_invalid"))
        self.assertFalse(self.output().exists())

    def test_same_delivery_with_changed_refs_conflicts_and_preserves_receipt(self):
        self.run_intake()
        record = self.record().read_bytes()
        receipt = (self.output() / "receipt.json").read_bytes()
        envelope = self.envelope()
        envelope["transfers"][0]["bundleSha256"] = "a" * 64
        self.save_delivery(envelope)
        result = self.run_intake()
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(self.record().read_bytes(), record)
        self.assertEqual((self.output() / "receipt.json").read_bytes(), receipt)

    def test_duplicate_transfer_and_noncanonical_manifest_identity_rejected(self):
        envelope = self.envelope()
        envelope["transfers"].append(copy.deepcopy(envelope["transfers"][0]))
        self.save_delivery(envelope)
        self.assertEqual(self.run_intake()["status"], "pending")
        envelope = self.envelope()
        envelope["transfers"][0]["manifestNoteId"] = str(uuid4())
        self.save_delivery(envelope)
        self.assertEqual(self.run_intake()["errorCode"], "invalid_transfer_reference")
        self.assertFalse(self.output().exists())

    def test_wrong_request_or_bundle_reference_rejected_before_output(self):
        manifest = self.notes / (self.transfers[0]["manifestNoteId"] + ".json")
        self.mutate_note_content(manifest, lambda value: value.update(requestId=str(uuid4())))
        self.assertEqual(self.run_intake()["errorCode"], "manifest_reference_mismatch")
        self.assertFalse(self.output().exists())

    def test_hash_valid_private_traversal_secret_and_binary_bundles_rejected(self):
        cases = [("../outside.py", "# traversal\n"), ("station/.env.py", "# private path\n"),
                 ("station/api.py", 'api_key = "syntheticfixturevalue000000"\n'),
                 ("station/api.py", "binary\x00content")]
        for relative, text in cases:
            with self.subTest(relative=relative, kind="nul" if "\x00" in text else "text"):
                self.delivery_id = str(uuid4())
                reference = self.transfers[0]
                raw_file = text.encode()
                bundle = {"schemaVersion": 1, "kind": "morph-source-bundle", "requestId": self.request_id,
                    "transferId": reference["transferId"], "files": [{"path": relative, "bytes": len(raw_file),
                    "sha256": intake.digest(raw_file), "text": text}]}
                raw_bundle = intake.encoded(bundle)
                sha = intake.digest(raw_bundle)
                manifest = {"schemaVersion": 1, "kind": "morph-source-manifest", "requestId": self.request_id,
                    "transferId": reference["transferId"], "bundleSha256": sha, "bundleBytes": len(raw_bundle),
                    "fileCount": 1, "fileBytes": len(raw_file), "partCount": 1}
                chunk = {"schemaVersion": 1, "kind": "morph-source-chunk", "requestId": self.request_id,
                    "transferId": reference["transferId"], "part": 1, "partCount": 1,
                    "bundleSha256": sha, "chunkSha256": sha, "text": raw_bundle.decode()}
                for identity, title, value in [(reference["manifestNoteId"], "Intel source manifest | " + reference["transferId"], manifest),
                    (self.protocol.note_id(reference["transferId"], "part:1"), "Intel source | " + reference["transferId"] + " | part 1", chunk)]:
                    (self.notes / (identity + ".json")).write_bytes(intake.encoded(self.protocol.make_note(identity, title, value)))
                reference["bundleSha256"] = sha
                self.save_delivery()
                result = self.run_intake()
                self.assertEqual((result["status"], result["errorCode"]), ("pending", "transfer_incomplete_or_invalid"))
                self.assertFalse(self.output().exists())

    def test_combined_delivery_limit_checked_before_collector(self):
        second = self.add_transfer({"another.py": "# second\n"})
        self.save_delivery()
        for reference in self.transfers:
            path = self.notes / (reference["manifestNoteId"] + ".json")
            self.mutate_note_content(path, lambda value: value.update(bundleBytes=12_000_000))
        with patch.object(self.collector, "validate", side_effect=AssertionError("Limits must precede collection")), \
             patch.object(intake, "load_collector", return_value=self.collector):
            self.assertEqual(self.run_intake()["errorCode"], "delivery_limit_exceeded")
        self.assertFalse(self.output().exists())

    def test_interrupted_collection_preserved_and_retried_in_new_attempt(self):
        original = self.collector.collect
        created = []
        def interrupt(notes, manifest, output, request):
            output.mkdir()
            (output / "partial.txt").write_text("Retain this interrupted attempt")
            created.append(output)
            raise OSError("Synthetic interrupted write")
        with patch.object(self.collector, "collect", side_effect=interrupt), \
             patch.object(intake, "load_collector", return_value=self.collector):
            result = self.run_intake()
        self.assertEqual(result["status"], "pending")
        completed = self.run_intake()
        self.assertEqual(completed["status"], "reconstructed_verified_for_review")
        self.assertEqual((created[0] / "partial.txt").read_text(), "Retain this interrupted attempt")
        self.assertEqual(len(list((self.output() / "attempts").iterdir())), 2)

    def test_crash_after_receipt_recovers_without_new_reconstruction(self):
        original = intake.replace_json
        def interrupt(path, value):
            if path == self.record() and value.get("status") == "reconstructed_verified_for_review":
                raise KeyboardInterrupt
            return original(path, value)
        with patch.object(intake, "replace_json", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_intake()
        self.assertTrue((self.output() / "receipt.json").is_file())
        with patch.object(self.collector, "collect", side_effect=AssertionError("Durable receipt already exists")), \
             patch.object(intake, "load_collector", return_value=self.collector):
            result = self.run_intake()
        self.assertEqual(result["status"], "reconstructed_verified_for_review")
        self.assertTrue(result["reused"])
        self.assertEqual(len(list((self.output() / "attempts").iterdir())), 1)

    def test_modified_reconstructed_file_blocks_without_overwrite(self):
        result = self.run_intake()
        path = self.output() / "attempts" / result["attemptId"] / "transfers" / self.transfers[0]["transferId"] / "source/station/api.py"
        path.write_text("# modified after collection\n")
        repeated = self.run_intake()
        self.assertEqual((repeated["status"], repeated["errorCode"]), ("pending", "saved_source_hash_mismatch"))
        self.assertEqual(path.read_text(), "# modified after collection\n")
        self.assertEqual(len(list((self.output() / "attempts").iterdir())), 1)

    def test_tampered_ready_receipt_remains_pinned_across_repeated_retries(self):
        result = self.run_intake()
        original_pin = json.loads(self.record().read_text())["receiptSha256"]
        comparison_path = self.output() / result["comparisonPath"]
        comparison = json.loads(comparison_path.read_text())
        comparison["files"][0]["mac"] = {"state": "same", "sha256": "f" * 64, "bytes": 1}
        comparison_path.write_bytes(intake.encoded(comparison))
        receipt_path = self.output() / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["comparisonSha256"] = intake.digest(comparison_path.read_bytes())
        receipt["comparisonPath"] = "../../unexpected-path.json"
        receipt_path.write_bytes(intake.encoded(receipt))
        tampered = receipt_path.read_bytes()
        for _ in range(3):
            retry = self.run_intake()
            self.assertEqual((retry["status"], retry["errorCode"]), ("pending", "saved_receipt_hash_mismatch"))
            ledger = json.loads(self.record().read_text())
            self.assertEqual(ledger["receiptSha256"], original_pin)
            self.assertTrue(ledger["receiptPinRequired"])
            self.assertEqual(receipt_path.read_bytes(), tampered)
        self.assertEqual(len(list((self.output() / "attempts").iterdir())), 1)

    def test_completed_record_missing_or_invalid_pin_never_recovers_unpinned(self):
        self.run_intake()
        original = json.loads(self.record().read_text())
        for invalid in (None, "", "not-a-hash", False, "missing"):
            with self.subTest(pin=invalid):
                record = copy.deepcopy(original)
                record.pop("receiptPinRequired", None)
                if invalid == "missing":
                    record.pop("receiptSha256")
                else:
                    record["receiptSha256"] = invalid
                self.record().write_bytes(intake.encoded(record))
                for _ in range(2):
                    retry = self.run_intake()
                    self.assertEqual((retry["status"], retry["errorCode"]), ("pending", "saved_receipt_pin_invalid"))
                    self.assertTrue(json.loads(self.record().read_text())["receiptPinRequired"])

    def test_preledger_recovery_rejects_nonderived_comparison_path(self):
        replace = intake.replace_json
        def interrupt(path, value):
            if path == self.record() and value.get("status") == "reconstructed_verified_for_review":
                raise KeyboardInterrupt
            return replace(path, value)
        with patch.object(intake, "replace_json", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_intake()
        self.assertNotIn("receiptSha256", json.loads(self.record().read_text()))
        path = self.output() / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt["comparisonPath"] = "../../unexpected-path.json"
        path.write_bytes(intake.encoded(receipt))
        for _ in range(2):
            retry = self.run_intake()
            self.assertEqual((retry["status"], retry["errorCode"]), ("pending", "saved_comparison_path_invalid"))
        self.assertEqual(len(list((self.output() / "attempts").iterdir())), 1)

    def test_unexpected_file_in_completed_source_blocks_reuse(self):
        result = self.run_intake()
        source = self.output() / "attempts" / result["attemptId"] / "transfers" / self.transfers[0]["transferId"] / "source"
        extra = source / "unexpected.py"
        extra.write_text("# added locally\n")
        self.assertEqual(self.run_intake()["errorCode"], "unexpected_saved_source_file")
        self.assertTrue(extra.is_file())

    def test_preexisting_output_never_overwritten_or_adopted(self):
        self.incoming.mkdir(mode=0o700)
        self.output().mkdir()
        original = self.output() / "original.txt"
        original.write_text("Unrelated existing data")
        result = self.run_intake()
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(original.read_text(), "Unrelated existing data")
        self.assertEqual(list(self.output().iterdir()), [original])

    def test_symlink_note_or_output_rejected_without_reading_external_target(self):
        path = self.chunk_path()
        outside = self.root / "outside.json"
        path.rename(outside)
        path.symlink_to(outside)
        self.assertEqual(self.run_intake()["errorCode"], "symlink_rejected")
        self.assertFalse(self.output().exists())
        path.unlink()
        outside.rename(path)
        target = self.root / "other"
        target.mkdir()
        self.output().symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(intake.IntakeError, "symlink_rejected"):
            self.run_intake()
        self.assertEqual(list(target.iterdir()), [])

    def test_local_comparison_symlink_is_unavailable_and_never_copied(self):
        outside = self.root / "outside.py"
        outside.write_text("# private comparison target must not be read\n")
        (self.mac / "station").mkdir()
        (self.mac / "station/api.py").symlink_to(outside)
        result = self.run_intake()
        comparison = json.loads((self.output() / result["comparisonPath"]).read_text())
        row = next(row for row in comparison["files"] if row["path"] == "station/api.py")
        self.assertEqual(row["mac"], {"state": "unavailable", "errorCode": "comparison_file_unavailable"})

    def test_comparison_roots_are_local_configuration_and_pinned_on_retry(self):
        self.run_intake()
        other = self.root / "other-mac"
        other.mkdir()
        result = self.run_intake(mac_root=other)
        self.assertEqual(result["status"], "conflict")
        envelope = self.envelope()
        envelope["command"] = "never run a command from the handoff"
        self.save_delivery(envelope)
        self.assertEqual(self.run_intake()["errorCode"], "invalid_delivery_envelope")

    def test_concurrent_intake_lock_and_nonprivate_state_rejected(self):
        intake.private_dir(self.state)
        with intake.locked(self.state):
            with self.assertRaisesRegex(intake.IntakeError, "intake_busy"):
                self.run_intake()
        self.state.chmod(0o755)
        with self.assertRaisesRegex(intake.IntakeError, "directory_not_private"):
            self.run_intake()

    def test_overlapping_notes_state_and_incoming_rejected_before_mutation(self):
        layouts = [("state/observations", "state", "incoming"), ("notes", "notes/state", "incoming"),
                   ("notes", "notes", "incoming"), ("notes", "state", "notes"),
                   ("notes", "state", "notes/incoming"), ("incoming/notes", "state", "incoming"),
                   ("notes", "work", "work"), ("notes", "work", "work/incoming"),
                   ("notes", "work/state", "work")]
        def snapshot(root):
            return {p.relative_to(root).as_posix(): None if p.is_dir() else p.read_bytes()
                    for p in root.rglob("*")}
        for index, (notes_name, state_name, incoming_name) in enumerate(layouts):
            with self.subTest(layout=index):
                folder = self.root / ("overlap-" + str(index))
                notes, state, incoming = (folder / name for name in (notes_name, state_name, incoming_name))
                notes.mkdir(mode=0o700, parents=True)
                original = notes / (self.note_id + ".json")
                original.write_bytes(b"{malformed original input must remain unchanged}")
                before = snapshot(folder)
                with self.assertRaisesRegex(intake.IntakeError, "notes_state_and_incoming_must_be_separate"):
                    intake.intake(notes, self.note_id, state, incoming)
                self.assertEqual(snapshot(folder), before)
                self.assertEqual(original.read_bytes(), b"{malformed original input must remain unchanged}")

    def test_missing_delivery_note_has_durable_pending_observation(self):
        (self.notes / (self.note_id + ".json")).unlink()
        result = self.run_intake()
        self.assertEqual(result["status"], "pending")
        saved = json.loads((self.state / "observations" / (self.note_id + ".json")).read_text())
        self.assertEqual(saved["deliveryNoteId"], self.note_id)
        self.assertFalse(saved["sourceAccepted"])

    def test_cli_uses_only_configured_paths_and_returns_pending_nonzero(self):
        self.chunk_path().unlink()
        args = ["--notes", str(self.notes), "--delivery-note-id", self.note_id,
                "--state-dir", str(self.state), "--incoming-root", str(self.incoming),
                "--mac-root", str(self.mac), "--baseline-root", str(self.baseline)]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(intake.main(args), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "pending")
        self.assertNotIn("Synthetic", output.getvalue())


if __name__ == "__main__":
    unittest.main()
