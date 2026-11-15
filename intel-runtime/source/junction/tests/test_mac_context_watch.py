"""Exercise shared-context polling without credentials, network, or hardware."""
import hashlib
import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


watch = load_module("mac_watcher_under_test", ROOT / "scripts/watch_mac_context.py")
client_module = load_module("existing_mac_client_under_test", watch.CLIENT_SOURCE)
GUIDE = "PHYSICAL_AI_WORKFLOW.md"
NOTE_ID = "97fc6306-5c96-454b-8093-f03c47414d2e"
NOTE_PATH = f"context/notes/{NOTE_ID}.json"


def note(content="A colleague update", identity=NOTE_ID):
    return json.dumps({"note_id": identity, "title": "Verified update", "author": "Test colleague",
        "content": content, "evidence": [], "status": "checkpoint", "saved_at": "2026-11-14T21:00:00Z"})


class FakeClient:
    """Use the real Client.read pagination implementation, without initialization."""
    read = client_module.Client.read

    def __init__(self, files, pages=None, corrupt_page=False, fail_path=None):
        self.files = files
        self.pages = pages if pages is not None else [list(files)]
        self.corrupt_page, self.fail_path, self.calls = corrupt_page, fail_path, []

    def call(self, name, **arguments):
        self.calls.append((name, arguments))
        if name == "list_context":
            assert arguments["prefix"] == "" and arguments["limit"] == 200
            index = arguments["offset"] // 200
            return {"files": [{"path": p} for p in self.pages[index]],
                    "next_offset": (index + 1) * 200 if index + 1 < len(self.pages) else None}
        assert name == "read_context", f"Remote mutation forbidden: {name}"
        path, offset = arguments["path"], arguments["offset"]
        if path == self.fail_path:
            raise RuntimeError("secret-example-must-never-be-logged")
        text = self.files[path]
        end = min(offset + arguments["limit"], len(text))
        sha = hashlib.sha256(text.encode()).hexdigest()
        if self.corrupt_page and offset > 0:
            sha = "0" * 64
        return {"path": path, "content": text[offset:end], "offset": offset,
                "next_offset": end if end < len(text) else None, "sha256": sha,
                "redacted": False, "total_characters": len(text)}


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.directory = self.root / "mac-sync"
        self.local = self.root / "project" / GUIDE
        self.local.parent.mkdir()

    def watcher(self, documents=None, selected=None):
        config = {"documents": documents if documents is not None else {},
                  "auto_apply": selected if selected is not None else []}
        path = self.root / "config.json"
        watch.save_json(path, config)
        return watch.Watcher(self.root, self.directory, watch.configuration(path, self.root))

    def state(self):
        return json.loads((self.directory / "watch-state.json").read_text())

    def run_cycle(self, watcher, client):
        return watcher.cycle(lambda: client, timeout=10)

    def test_catalog_and_real_text_pagination_duplicate_paths_and_hash_dedup(self):
        body = note("A" * 52000)
        reader = FakeClient({NOTE_PATH: body}, pages=[[NOTE_PATH], [NOTE_PATH]])
        watcher = self.watcher()
        self.assertTrue(self.run_cycle(watcher, reader))
        state = self.state()
        self.assertEqual((state["catalog_pages"], state["notes_count"], state["new_count"]), (2, 1, 1))
        offsets = [args["offset"] for name, args in reader.calls if name == "read_context"]
        self.assertEqual(offsets, [0, 24000, 48000])
        sha = state["files"][NOTE_PATH]["sha256"]
        self.assertEqual((self.directory / "snapshots" / (sha + ".txt")).read_text(), body)
        self.assertTrue(self.run_cycle(watcher, FakeClient({NOTE_PATH: body})))
        self.assertEqual(self.state()["new_count"], 0)
        self.assertEqual(len(list((self.directory / "snapshots").glob("*.txt"))), 1)
        self.assertEqual(watcher.pending(self.state()), [NOTE_PATH])
        watch.save_json(self.directory / "reviewed.json", {NOTE_PATH: sha})
        self.assertEqual(watcher.pending(self.state()), [])

    def test_failure_and_mutating_paginated_read_preserve_last_success(self):
        watcher = self.watcher({GUIDE: None})
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "known"})))
        old = self.state()
        reader = FakeClient({GUIDE: "B" * 49000}, corrupt_page=True)
        self.assertFalse(self.run_cycle(watcher, reader))
        failed = self.state()
        self.assertEqual(failed["last_success"], old["last_success"])
        self.assertEqual(failed["files"], old["files"])
        self.assertEqual(failed["last_error"], "RuntimeError")
        self.assertFalse(self.run_cycle(watcher, FakeClient({GUIDE: "x"}, fail_path=GUIDE)))
        self.assertNotIn("secret-example", (self.root / "MAC_UPDATES.md").read_text())
        self.assertNotIn("secret-example", (self.directory / "watch-state.json").read_text())
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "B" * 49000})))
        self.assertIsNone(self.state()["last_error"])
        self.assertEqual(self.state()["new_count"], 1)

    def test_first_difference_and_review_acknowledgment_do_not_authorize_overwrite(self):
        self.local.write_text("local work")
        watcher = self.watcher({GUIDE: str(self.local)}, [GUIDE])
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "remote one"})))
        first = self.state()["files"][GUIDE]
        self.assertEqual(first["action"], "review_required")
        self.assertIsNone(first["baseline_sha256"])
        watch.save_json(self.directory / "reviewed.json", {GUIDE: first["sha256"]})
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "remote two"})))
        self.assertEqual(self.local.read_text(), "local work")
        self.assertIsNone(self.state()["files"][GUIDE]["baseline_sha256"])

    def test_matching_baseline_applies_with_backup_then_preserves_local_edits(self):
        self.local.write_text("shared baseline")
        watcher = self.watcher({GUIDE: str(self.local)}, [GUIDE])
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "shared baseline"})))
        baseline = self.state()["files"][GUIDE]["baseline_sha256"]
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "remote update"})))
        applied = self.state()["files"][GUIDE]
        self.assertEqual((self.local.read_text(), applied["action"]), ("remote update", "applied"))
        self.assertEqual(applied["backup_sha256"], baseline)
        self.assertEqual((self.directory / "snapshots" / (baseline + ".txt")).read_text(), "shared baseline")
        self.local.write_text("new local edit")
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "another remote update"})))
        conflict = self.state()["files"][GUIDE]
        self.assertEqual(conflict["action"], "review_required")
        self.assertEqual(conflict["baseline_sha256"], applied["sha256"])
        self.assertEqual(self.local.read_text(), "new local edit")

    def test_default_no_apply_and_missing_local_is_not_created(self):
        watcher = self.watcher({GUIDE: str(self.local)})
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "remote"})))
        self.assertFalse(self.local.exists())
        self.local.write_text("remote")
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "remote"})))
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "updated"})))
        self.assertEqual(self.local.read_text(), "remote")
        self.assertEqual(self.state()["files"][GUIDE]["action"], "review_required")

    def test_concurrent_local_edit_prevents_atomic_replacement(self):
        self.local.write_text("base")
        watcher = self.watcher({GUIDE: str(self.local)}, [GUIDE])
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "base"})))
        old = self.state()
        original_atomic = watch.atomic_bytes
        def concurrent(path, content, before_replace=None):
            if path == self.local:
                self.local.write_text("concurrent edit")
            return original_atomic(path, content, before_replace)
        with patch.object(watch, "atomic_bytes", side_effect=concurrent):
            self.assertFalse(self.run_cycle(watcher, FakeClient({GUIDE: "new remote"})))
        self.assertEqual(self.local.read_text(), "concurrent edit")
        self.assertEqual(self.state()["last_success"], old["last_success"])
        self.assertEqual(self.state()["files"], old["files"])

    def test_immutable_note_mutation_rejected_and_identity_validated(self):
        watcher = self.watcher()
        self.assertTrue(self.run_cycle(watcher, FakeClient({NOTE_PATH: note()})))
        old = self.state()
        self.assertFalse(self.run_cycle(watcher, FakeClient({NOTE_PATH: note("rewritten")})))
        self.assertEqual(self.state()["files"], old["files"])
        other = "a4c844dd-5b59-4c24-a61c-246ac05456e7"
        self.assertFalse(self.run_cycle(watcher, FakeClient({NOTE_PATH: note(identity=other)})))
        self.assertEqual(self.state()["files"], old["files"])

    def test_markdown_note_does_not_block_canonical_notes_or_selected_guides(self):
        markdown_path = "context/notes/20261114-01a1dbfa-mac-offline-evidence.md"
        body = "# Local Mac evidence work ready for colleague publication\n\nSaved simulated results.\n"
        watcher = self.watcher({GUIDE: None})
        reader = FakeClient({NOTE_PATH: note(), markdown_path: body, GUIDE: "current guide"})
        self.assertTrue(self.run_cycle(watcher, reader))
        state = self.state()
        self.assertEqual(state["notes_count"], 2)
        self.assertEqual(state["files"][markdown_path]["note_format"], "markdown")
        self.assertEqual(state["files"][markdown_path]["title"], "Local Mac evidence work ready for colleague publication")
        self.assertIsNone(state["files"][markdown_path]["saved_at"])
        sha = state["files"][markdown_path]["sha256"]
        self.assertEqual((self.directory / "snapshots" / (sha + ".txt")).read_text(), body)
        self.assertIn(markdown_path, watcher.pending(state))
        self.assertIn(GUIDE, state["files"])

    def test_editable_note_revisions_preserve_snapshots_and_do_not_rewrite_local_files(self):
        path = "context/notes/operator-notes.md"
        watcher = self.watcher({GUIDE: str(self.local)})
        self.local.write_text("local guide work")
        self.assertTrue(self.run_cycle(watcher, FakeClient({path: "# First revision", GUIDE: "remote guide"})))
        old_hash = self.state()["files"][path]["sha256"]
        self.assertTrue(self.run_cycle(watcher, FakeClient({path: "# Updated revision", GUIDE: "remote guide"})))
        self.assertNotEqual(self.state()["files"][path]["sha256"], old_hash)
        self.assertEqual((self.directory / "snapshots" / (old_hash + ".txt")).read_text(), "# First revision")
        self.assertEqual(self.local.read_text(), "local guide work")
        self.assertTrue(self.run_cycle(watcher, FakeClient({GUIDE: "remote guide"})))
        self.assertNotIn(path, self.state()["files"])
        self.assertTrue((self.directory / "snapshots" / (old_hash + ".txt")).exists())

    def test_canonical_uuid_json_never_falls_back_to_plain_text(self):
        watcher = self.watcher()
        self.assertTrue(self.run_cycle(watcher, FakeClient({NOTE_PATH: note()})))
        previous = self.state()
        for invalid in ("# Markdown at the canonical JSON path", "[]", '{"note_id":"invalid"}'):
            with self.subTest(invalid=invalid):
                self.assertFalse(self.run_cycle(watcher, FakeClient({NOTE_PATH: invalid})))
                self.assertEqual(self.state()["files"], previous["files"])
                self.assertEqual(self.state()["last_success"], previous["last_success"])

    def test_remote_traversal_and_nonadvancing_catalog_rejected(self):
        watcher = self.watcher()
        self.assertFalse(self.run_cycle(watcher, FakeClient({}, pages=[["context/notes/../../bad"]])))
        class Stuck(FakeClient):
            def call(self, name, **arguments):
                return {"files": [], "next_offset": 0}
        self.assertFalse(self.run_cycle(watcher, Stuck({})))
        self.assertNotIn("last_success", self.state())

    def test_autoupdate_allowlist_workspace_and_symlink_checks(self):
        with self.assertRaises(watch.VerificationError):
            self.watcher({"AGENTS.md": str(self.root / "AGENTS.md")}, ["AGENTS.md"])
        with self.assertRaises(watch.VerificationError):
            self.watcher({GUIDE: "/etc/PHYSICAL_AI_WORKFLOW.md"}, [GUIDE])
        self.local.symlink_to(self.root / "elsewhere.md")
        with self.assertRaises(watch.VerificationError):
            self.watcher({GUIDE: str(self.local)}, [GUIDE])
        self.local.unlink()
        directory_link = self.root / "linked"
        directory_link.symlink_to(self.local.parent, target_is_directory=True)
        with self.assertRaises(watch.VerificationError):
            self.watcher({GUIDE: str(directory_link / GUIDE)}, [GUIDE])

    def test_lock_and_atomic_failure_preserve_existing_content(self):
        with watch.exclusive(self.directory):
            with self.assertRaises(BlockingIOError):
                with watch.exclusive(self.directory):
                    self.fail("A second watcher acquired the lock")
        with watch.exclusive(self.directory):
            pass
        target = self.root / "atomic.json"
        target.write_text("original")
        def reject():
            raise watch.VerificationError()
        with self.assertRaises(watch.VerificationError):
            watch.atomic_bytes(target, b"replacement", reject)
        self.assertEqual(target.read_text(), "original")
        self.assertFalse(list(self.root.glob(".mac-watch-*")))

    def test_snapshot_collision_and_deadline_fail_without_advancing(self):
        watcher = self.watcher({GUIDE: None})
        sha = watcher.snapshot(b"original")
        target = self.directory / "snapshots" / (sha + ".txt")
        target.write_text("tampered")
        with self.assertRaises(watch.VerificationError):
            watcher.snapshot(b"original")
        self.assertEqual(target.read_text(), "tampered")
        previous_handler = signal.getsignal(signal.SIGALRM)
        def timeout():
            signal.raise_signal(signal.SIGALRM)
        self.assertFalse(watcher.cycle(timeout, timeout=10))
        self.assertEqual(self.state()["last_error"], "CycleTimeout")
        self.assertNotIn("last_success", self.state())
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous_handler)

    def test_retains_known_notes_and_orders_pending_by_aware_saved_time(self):
        watcher = self.watcher()
        second_id = "abcdef12-5c96-454b-8093-f03c47414d2e"
        second_path = f"context/notes/{second_id}.json"
        newer = json.loads(note(identity=second_id))
        newer["saved_at"] = "2026-11-14T23:00:00+01:00"
        files = {NOTE_PATH: note(), second_path: json.dumps(newer)}
        self.assertTrue(self.run_cycle(watcher, FakeClient(files)))
        self.assertEqual(watcher.pending(self.state()), [second_path, NOTE_PATH])
        self.assertTrue(self.run_cycle(watcher, FakeClient(files, pages=[[second_path]])))
        self.assertEqual(set(self.state()["files"]), set(files))
        self.assertIn(newer["saved_at"], (self.root / "MAC_UPDATES.md").read_text())

    def test_pid_requires_exact_script_and_watch_flag(self):
        script = ROOT / "scripts/watch_mac_context.py"
        record = {"pid": 43210, "script": str(script)}
        with patch.object(watch, "read_json", return_value=record):
            with patch.object(watch.Path, "read_bytes", return_value=b"python3\0other.py\0--watch\0"):
                self.assertIsNone(watch.process_matches(self.directory / "watch.pid", script))
            with patch.object(watch.Path, "read_bytes", return_value=b"python3\0" + bytes(script) + b"\0--once\0"):
                self.assertIsNone(watch.process_matches(self.directory / "watch.pid", script))
            with patch.object(watch.Path, "read_bytes", return_value=b"python3\0" + bytes(script) + b"\0--watch\0"):
                self.assertEqual(watch.process_matches(self.directory / "watch.pid", script), 43210)

    def test_cli_hidden_process_with_held_lock_is_unknown_and_cannot_be_stopped(self):
        script = ROOT / "scripts/watch_mac_context.py"
        watch.save_json(self.directory / "watch.pid", {"pid": 43210, "script": str(script)})
        watch.save_json(self.directory / "watch-state.json", {"last_success": "previous success", "files": {}})
        with watch.exclusive(self.directory), patch.object(watch, "ROOT", self.root), \
                patch.object(watch, "process_matches", return_value=None), patch.object(watch.os, "kill") as kill:
            for mode, expected_exit in (("--status", 0), ("--stop", 1)):
                with self.subTest(mode=mode), patch.object(sys, "argv", [str(script), mode]):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(watch.main(), expected_exit)
                    result = json.loads(output.getvalue())
                    self.assertIsNone(result["running"])
                    self.assertTrue(result["lock_held"])
                    self.assertEqual(result["pid"], 43210)
                    self.assertEqual(result["process_visibility"], "unverified")
                    self.assertFalse(result["stop_requested"])
                    self.assertEqual(result["last_success"], "previous success")
                    self.assertEqual(result["error"], "ProcessIdentityUnverified" if mode == "--stop" else None)
            kill.assert_not_called()

    def test_cli_only_signals_verified_process_and_reports_idle_without_lock(self):
        script = ROOT / "scripts/watch_mac_context.py"
        with patch.object(watch, "ROOT", self.root), patch.object(watch.os, "kill") as kill, \
                patch.object(sys, "argv", [str(script), "--stop"]):
            with patch.object(watch, "process_matches", return_value=43210):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(watch.main(), 0)
                result = json.loads(output.getvalue())
                self.assertTrue(result["running"])
                self.assertTrue(result["stop_requested"])
                self.assertEqual(result["process_visibility"], "verified")
                kill.assert_called_once_with(43210, signal.SIGTERM)
            kill.reset_mock()
            with patch.object(watch, "process_matches", return_value=None):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(watch.main(), 0)
                result = json.loads(output.getvalue())
                self.assertFalse(result["running"])
                self.assertFalse(result["lock_held"])
                kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
