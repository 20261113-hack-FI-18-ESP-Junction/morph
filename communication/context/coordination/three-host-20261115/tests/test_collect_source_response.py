"""Offline receiver checks against actual helper-generated transfer notes."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from uuid import uuid4

PATH = Path(__file__).resolve().parents[1] / "collect_source_response.py"
SPEC = importlib.util.spec_from_file_location("morph_source_receiver_tests", PATH)
receiver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receiver)
protocol = receiver.protocol


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        source = self.root / "original"
        source.mkdir()
        (source / "app.py").write_text("raise RuntimeError('this transferred source must never execute')\n" + "# A source comment\n" * 1500)
        self.outbox = self.root / "outbox"
        self.transfer = str(uuid4())
        self.manifest = protocol.prepare(source, ["app.py"], receiver.DEFAULT_REQUEST_ID, self.transfer, self.outbox)
        self.notes = self.outbox / "notes"
        self.manifest_id = protocol.note_id(self.transfer, "manifest")
        self.output = self.root / "incoming"
        # Emulate canonical MCP save_handoff receipt fields.
        for path in self.notes.glob("*.json"):
            note = json.loads(path.read_text())
            note.update(saved_at="2026-11-15T04:00:00+00:00", verification_notice="Caller report, not certification")
            path.write_bytes(protocol.encoded(note))

    def collect(self, **changes):
        return receiver.collect(self.notes, self.manifest_id, changes.get("output", self.output), changes.get("request_id", receiver.DEFAULT_REQUEST_ID))

    def rewrite_bundle(self, mutation):
        bundle = json.loads((self.outbox / "bundle.json").read_text())
        mutation(bundle)
        raw = protocol.encoded(bundle)
        text = raw.decode()
        pieces = [text[index:index + 1000] for index in range(0, len(text), 1000)]
        manifest = dict(self.manifest, bundleSha256=protocol.digest(raw), bundleBytes=len(raw),
            partCount=len(pieces), fileCount=len(bundle["files"]), fileBytes=sum(row["bytes"] for row in bundle["files"]))
        for index, part in enumerate(pieces, 1):
            payload = {"schemaVersion": protocol.SCHEMA, "kind": "morph-source-chunk",
                "requestId": manifest["requestId"], "transferId": self.transfer,
                "part": index, "partCount": len(pieces), "bundleSha256": manifest["bundleSha256"],
                "chunkSha256": protocol.digest(part.encode()), "text": part}
            identity = protocol.note_id(self.transfer, "part:" + str(index))
            note = protocol.make_note(identity, "Intel source | " + self.transfer + " | part " + str(index), payload)
            (self.notes / (identity + ".json")).write_bytes(protocol.encoded(note))
        note = protocol.make_note(self.manifest_id, "Intel source manifest | " + self.transfer, manifest)
        (self.notes / (self.manifest_id + ".json")).write_bytes(protocol.encoded(note))

    def test_helper_roundtrip_saved_metadata_and_no_source_execution(self):
        (self.notes / "unrelated-note.json").write_text("invalid unrelated data must never be read")
        report = self.collect()
        self.assertTrue(report["verified"])
        self.assertFalse(report["sourceExecuted"])
        self.assertFalse(report["liveSourceOverwritten"])
        self.assertEqual((self.output / "source/app.py").read_bytes(), (self.root / "original/app.py").read_bytes())
        self.assertTrue((self.output / "manifest.json").exists())
        self.assertEqual(json.loads((self.output / "report.json").read_text())["bundleSha256"], self.manifest["bundleSha256"])

    def test_missing_chunk_creates_no_output(self):
        (self.notes / (protocol.note_id(self.transfer, "part:1") + ".json")).unlink()
        with self.assertRaises(OSError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_mutated_chunk_creates_no_output(self):
        path = self.notes / (protocol.note_id(self.transfer, "part:1") + ".json")
        note = json.loads(path.read_text())
        chunk = json.loads(note["content"])
        chunk["text"] += "mutation"
        note["content"] = protocol.encoded(chunk).decode()
        path.write_bytes(protocol.encoded(note))
        with self.assertRaisesRegex(ValueError, "Chunk hash"):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_wrong_request_and_non_deterministic_manifest_rejected(self):
        with self.assertRaises(ValueError):
            self.collect(request_id=str(uuid4()))
        self.assertFalse(self.output.exists())
        note = json.loads((self.notes / (self.manifest_id + ".json")).read_text())
        other = str(uuid4())
        note["note_id"] = other
        (self.notes / (other + ".json")).write_bytes(protocol.encoded(note))
        with self.assertRaises(ValueError):
            receiver.collect(self.notes, other, self.output)
        self.assertFalse(self.output.exists())

    def test_resigned_traversal_secret_binary_and_duplicates_rejected(self):
        def bad_path(bundle):
            bundle["files"][0]["path"] = "../escape.py"
        self.rewrite_bundle(bad_path)
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())
        for text in ["binary\x00data", "api_key = 'synthetic-secret-fixture'"]:
            def bad_content(bundle):
                row = bundle["files"][0]
                row.update(text=text, bytes=len(text.encode()), sha256=protocol.digest(text.encode()))
            self.rewrite_bundle(bad_content)
            with self.assertRaises(ValueError):
                self.collect()
            self.assertFalse(self.output.exists())
        def duplicate(bundle):
            bundle["files"].append(dict(bundle["files"][0], path="APP.py"))
        self.rewrite_bundle(duplicate)
        with self.assertRaisesRegex(ValueError, "colliding"):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_existing_output_and_symlink_destination_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "preserve.txt"
        sentinel.write_text("existing work")
        with self.assertRaises(ValueError):
            self.collect()
        self.assertEqual(sentinel.read_text(), "existing work")
        linked = self.root / "linked"
        linked.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.collect(output=linked / "new-child")
        self.assertFalse((self.output / "new-child").exists())

    def test_manifest_part_limit_and_note_symlink_rejected(self):
        path = self.notes / (self.manifest_id + ".json")
        original = path.read_bytes()
        note = json.loads(original)
        manifest = json.loads(note["content"])
        manifest["partCount"] = 5001
        note["content"] = protocol.encoded(manifest).decode()
        path.write_bytes(protocol.encoded(note))
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())
        elsewhere = self.root / "actual-note.json"
        elsewhere.write_bytes(original)
        path.unlink()
        path.symlink_to(elsewhere)
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
