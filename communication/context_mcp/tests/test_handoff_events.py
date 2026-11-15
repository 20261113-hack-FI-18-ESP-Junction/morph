"""Offline durable handoff lifecycle tests; no runner, provider or network."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

# Locate the existing ContextStore without copying or changing canonical code.
MODULE_PATH = Path(__file__).resolve().parents[1] / "handoff_events.py"
for parent in MODULE_PATH.parents:
    candidate = parent / "context_mcp/store.py"
    if candidate.is_file() and candidate.parent != MODULE_PATH.parent:
        sys.path.insert(0, str(candidate.parent))
        break
sys.path.insert(0, str(MODULE_PATH.parent))
from handoff_events import HandoffEvents, REVIEW_AUTHOR
from store import ContextStore


RESULT = hashlib.sha256(b'{"ok":true}\n').hexdigest()
OTHER_RESULT = hashlib.sha256(b'{"ok":false}\n').hexdigest()


class Clock:
    def __init__(self):
        self.value = 1_800_000_000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class EventsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "AGENTS.md").write_text("# Test workspace\n")
        self.clock = Clock()
        self.store = HandoffEvents(self.root, clock=self.clock)
        self.context = ContextStore(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def note(self, content="Implemented a bounded reader.", author="Intel contributor", **changes):
        identifier = str(uuid4())
        args = {"note_id": identifier, "title": "Substantive work", "content": content,
                "author": author, "evidence": "Software tests retained.", "status": "implemented"}
        args.update(changes)
        self.context.save_note(**args)
        path = "context/notes/" + identifier + ".json"
        return identifier, self.context.read(path)["sha256"]

    def publish(self, **note_args):
        note_id, sha = self.note(**note_args)
        return self.store.publish(note_id, "mac", "intel", sha)["event"]

    def claim(self, event, who="intel-receiver", seconds=300):
        result = self.store.claim("intel", who, event["event_id"], seconds)
        self.assertTrue(result["claimed"])
        return result["event"]

    def finish(self, claim, outcome="processed", result=RESULT, code=""):
        return self.store.complete("intel", claim["consumer_id"], claim["event_id"], claim["claim_id"], outcome, result, code)

    def test_legacy_saved_note_does_not_create_event(self):
        self.note()
        self.assertEqual(self.store.poll("intel", "receiver")["events"], [])

    def test_durable_publish_sequence_and_identical_retry(self):
        note_id, sha = self.note()
        first = self.store.publish(note_id, "mac", "intel", sha)
        again = HandoffEvents(self.root, clock=self.clock).publish(note_id, "mac", "intel", sha)
        self.assertTrue(first["created"])
        self.assertFalse(again["created"])
        self.assertEqual(first["event"], again["event"])
        second = self.publish()
        self.assertGreater(second["seq"], first["event"]["seq"])
        self.assertEqual(self.store.poll("intel", "receiver")["high_water"], second["seq"])

    def test_publish_hash_collision_does_not_change_event(self):
        event = self.publish()
        path = self.root / event["note_path"]
        data = json.loads(path.read_text())
        data["content"] = "Changed after publication."
        path.write_text(json.dumps(data))
        changed = self.context.read(event["note_path"])["sha256"]
        with self.assertRaisesRegex(ValueError, "event_content_conflict"):
            self.store.publish(event["note_id"], "mac", "intel", changed)
        self.assertEqual(self.store.status("intel", event["event_id"])["event"]["note_sha256"], event["note_sha256"])

    def test_full_unicode_note_pagination_and_hash_verified(self):
        identifier, sha = self.note(content="Ž" * 24_000, evidence="E" * 4000)
        real_read = self.store.context.read
        with patch.object(self.store.context, "read", wraps=real_read) as reads:
            event = self.store.publish(identifier, "mac", "intel", sha)["event"]
        self.assertEqual(reads.call_count, 2)
        self.assertGreater(event["note_characters"], 24_000)

    def test_changed_hash_between_pages_is_rejected(self):
        identifier, sha = self.note(content="A" * 24_000)
        real_read = self.store.context.read
        def changing(*args, **kwargs):
            result = real_read(*args, **kwargs)
            if kwargs["offset"]:
                result["sha256"] = "0" * 64
            return result
        with patch.object(self.store.context, "read", side_effect=changing):
            with self.assertRaisesRegex(ValueError, "invalid_saved_note"):
                self.store.publish(identifier, "mac", "intel", sha)

    def test_missing_redacted_or_malformed_note_rejected_without_secret_error(self):
        with self.assertRaisesRegex(ValueError, "invalid_saved_note"):
            self.store.publish(str(uuid4()), "mac", "intel", "0" * 64)
        identifier, sha = self.note()
        original = self.store.context.read
        for change in ({"redacted": True}, {"next_offset": 1}, {"total_characters": 999_999}, {"content": "broken"}):
            with self.subTest(change=change):
                with patch.object(self.store.context, "read", side_effect=lambda *a, **kw: {**original(*a, **kw), **change}):
                    with self.assertRaisesRegex(ValueError, "^invalid_saved_note$"):
                        self.store.publish(identifier, "mac", "intel", sha)

    def test_note_identity_status_and_saved_time_are_checked(self):
        for key, value in (("note_id", str(uuid4())), ("status", "Done"), ("saved_at", "2026-11-15T00:00:00")):
            identifier, sha = self.note()
            path = self.root / "context/notes" / (identifier + ".json")
            data = json.loads(path.read_text()); data[key] = value
            path.write_text(json.dumps(data))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "invalid_saved_note"):
                self.store.publish(identifier, "mac", "intel", self.context.read(path.relative_to(self.root).as_posix())["sha256"])

    def test_no_review_receipt_or_structured_ack_loops(self):
        for content, author in (("Important new work", REVIEW_AUTHOR), ('{"event_type":"ack"}', "Intel"), ('{"kind":"receipt"}', "Mac")):
            identifier, sha = self.note(content=content, author=author)
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.store.publish(identifier, "mac", "intel", sha)
        self.assertEqual(self.store.poll("intel", "receiver")["high_water"], 0)
        accepted = self.publish(content="Implemented code, saved its receipt and acknowledgment evidence.")
        self.assertEqual(accepted["seq"], 1)

    def test_top_level_structured_ack_is_rejected(self):
        identifier, _ = self.note()
        path = self.root / "context/notes" / (identifier + ".json")
        note = json.loads(path.read_text()); note["kind"] = "ACK"
        path.write_text(json.dumps(note))
        with self.assertRaisesRegex(ValueError, "acknowledgment_not_work"):
            self.store.publish(identifier, "mac", "intel", self.context.read(path.relative_to(self.root).as_posix())["sha256"])

    def test_poll_and_status_do_not_ack_or_mutate_database(self):
        event = self.publish()
        before = self.store.db_path.read_bytes()
        for _ in range(2):
            polled = self.store.poll("intel", "receiver", after_seq=event["seq"])
            self.assertEqual(len(polled["events"]), 1)
            self.assertIsNone(polled["events"][0]["received_at"])
            self.assertIsNone(self.store.status("intel", event["event_id"])["event"]["processed_at"])
        self.assertEqual(self.store.db_path.read_bytes(), before)

    def test_offline_catchup_retains_older_failure_below_cursor(self):
        old = self.publish(); newer = self.publish()
        claim = self.claim(old)
        self.finish(claim, "failed", OTHER_RESULT, "runner_failed")
        polled = self.store.poll("intel", "receiver", after_seq=newer["seq"])
        self.assertEqual([e["seq"] for e in polled["events"]], [old["seq"], newer["seq"]])
        self.assertFalse(polled["events"][0]["claimable"])
        self.clock.advance(5)
        again = HandoffEvents(self.root, clock=self.clock).poll("intel", "receiver", after_seq=newer["seq"])
        self.assertTrue(again["events"][0]["claimable"])

    def test_simultaneous_publish_creates_one_sequence(self):
        identifier, sha = self.note()
        barrier = threading.Barrier(2)
        def run(_):
            barrier.wait()
            return self.store.publish(identifier, "mac", "intel", sha)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(r["created"] for r in results), 1)
        self.assertEqual(results[0]["event"]["event_id"], results[1]["event"]["event_id"])
        self.assertEqual(self.store.poll("intel", "receiver")["high_water"], 1)

    def test_simultaneous_consumers_get_only_one_target_lease(self):
        events = [self.publish(), self.publish()]
        barrier = threading.Barrier(2)
        def run(index):
            barrier.wait()
            return self.store.claim("intel", "receiver-" + str(index), events[index]["event_id"])
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(r["claimed"] for r in results), 1)
        self.assertEqual([r["reason"] for r in results if not r["claimed"]], ["target_busy"])

    def test_same_event_live_claim_is_idempotent_only_for_owner(self):
        event = self.publish(); first = self.claim(event)
        again = self.store.claim("intel", first["consumer_id"], event["event_id"])
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["event"]["claim_id"], first["claim_id"])
        self.assertEqual(again["event"]["attempts"], 1)
        other = self.store.claim("intel", "another-receiver", event["event_id"])
        self.assertFalse(other["claimed"])
        self.assertEqual(other["reason"], "event_busy")

    def test_simultaneous_consumers_on_same_event_have_one_winner(self):
        event = self.publish()
        barrier = threading.Barrier(2)
        def run(index):
            barrier.wait()
            return self.store.claim("intel", "receiver-" + str(index), event["event_id"])
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(r["claimed"] for r in results), 1)
        self.assertEqual([r["reason"] for r in results if not r["claimed"]], ["event_busy"])
        self.assertEqual(self.store.status("intel", event["event_id"])["event"]["attempts"], 1)

    def test_targets_have_independent_leases_and_scoping(self):
        event = self.publish()
        note_id, sha = self.note()
        other = self.store.publish(note_id, "intel", "mac", sha)["event"]
        self.claim(event)
        self.assertTrue(self.store.claim("mac", "mac-receiver", other["event_id"])["claimed"])
        with self.assertRaisesRegex(ValueError, "unknown_event"):
            self.store.status("mac", event["event_id"])

    def test_received_and_processed_times_are_distinct(self):
        event = self.publish(); self.clock.advance(10); claim = self.claim(event)
        self.assertNotEqual(claim["created_at"], claim["received_at"])
        self.assertIsNone(claim["processed_at"])
        self.clock.advance(10); result = self.finish(claim)["event"]
        self.assertNotEqual(result["received_at"], result["processed_at"])

    def test_expired_lease_reclaim_has_new_claim_and_attempt(self):
        event = self.publish(); first = self.claim(event, seconds=5)
        self.clock.advance(5)
        with self.assertRaisesRegex(ValueError, "stale_or_invalid_claim"):
            self.finish(first)
        newer = self.claim(event, who="replacement", seconds=10)
        self.assertEqual(newer["attempts"], 2)
        self.assertNotEqual(newer["claim_id"], first["claim_id"])
        self.assertEqual(newer["received_at"], first["received_at"])
        with self.assertRaisesRegex(ValueError, "stale_or_invalid_claim"):
            self.finish(first)

    def test_wrong_claim_owner_and_claim_uuid_cannot_ack(self):
        claim = self.claim(self.publish())
        for changed in ({"consumer_id": "other"}, {"claim_id": str(uuid4())}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "stale_or_invalid_claim"):
                self.finish({**claim, **changed})

    def test_renew_retains_identity_and_does_not_shorten_lease(self):
        claim = self.claim(self.publish(), seconds=60)
        same = self.store.renew("intel", claim["consumer_id"], claim["event_id"], claim["claim_id"], 5)["event"]
        self.assertEqual(same["lease_expires_at"], claim["lease_expires_at"])
        self.clock.advance(50)
        renewed = self.store.renew("intel", claim["consumer_id"], claim["event_id"], claim["claim_id"], 60)["event"]
        self.assertGreater(renewed["lease_expires_at"], claim["lease_expires_at"])
        self.assertEqual(renewed["attempts"], 1)
        self.clock.advance(60)
        with self.assertRaisesRegex(ValueError, "stale_or_invalid_claim"):
            self.store.renew("intel", claim["consumer_id"], claim["event_id"], claim["claim_id"], 60)

    def test_processed_ack_is_durable_idempotent_after_deadline(self):
        claim = self.claim(self.publish(), seconds=5)
        result = self.finish(claim)
        self.assertFalse(result["duplicate"])
        self.clock.advance(999)
        self.store = HandoffEvents(self.root, clock=self.clock)
        duplicate = self.finish(claim)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(result["event"], duplicate["event"])
        with self.assertRaisesRegex(ValueError, "completion_conflict"):
            self.finish(claim, result=OTHER_RESULT)
        self.assertEqual(self.store.claim("intel", "receiver", claim["event_id"])["reason"], "already_processed")
        self.assertEqual(self.store.poll("intel", "receiver", after_seq=claim["seq"])["events"], [])

    def test_failed_completion_idempotence_and_bounded_retry_backoff(self):
        event = self.publish()
        for attempt in range(1, 10):
            claim = self.claim(event)
            failed = self.finish(claim, "failed", OTHER_RESULT, "runner_failed")["event"]
            self.assertEqual(failed["attempts"], attempt)
            duplicate = self.finish(claim, "failed", OTHER_RESULT, "runner_failed")
            self.assertTrue(duplicate["duplicate"])
            wait = datetime.fromisoformat(failed["retry_at"]).timestamp() - self.clock.value
            self.assertEqual(wait, min(5 * 2 ** (attempt - 1), 300))
            self.assertEqual(self.store.claim("intel", "receiver", event["event_id"])["reason"], "retry_backoff")
            self.clock.advance(wait)
        claim = self.claim(event); self.finish(claim)
        self.assertEqual(self.store.status("intel", event["event_id"])["event"]["state"], "processed")

    def test_failed_retry_cannot_be_overwritten_by_old_ack(self):
        event = self.publish(); old = self.claim(event)
        self.finish(old, "failed", OTHER_RESULT, "runner_failed")
        self.clock.advance(5); self.claim(event)
        with self.assertRaisesRegex(ValueError, "stale_or_invalid_claim"):
            self.finish(old, "failed", OTHER_RESULT, "runner_failed")

    def test_private_storage_modes_and_custom_private_path(self):
        self.assertEqual(stat.S_IMODE(self.store.db_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.store.db_path.parent.stat().st_mode), 0o700)
        custom = HandoffEvents(self.root, db_path="private-events/custom.sqlite3", clock=self.clock)
        self.assertTrue(custom.db_path.is_file())

    def test_symlinked_database_and_parent_rejected(self):
        target = self.root / "ordinary"; target.write_text("not a database")
        bad = self.root / "bad"; bad.mkdir(); (bad / "events.sqlite3").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "storage_symlink"):
            HandoffEvents(self.root, db_path=bad / "events.sqlite3")
        link = self.root / "linked"; link.symlink_to(bad, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "storage_symlink"):
            HandoffEvents(self.root, db_path=link / "another.sqlite3")
        self.assertEqual(target.read_text(), "not a database")

    def test_sqlite_sidecar_symlinks_and_loosened_permissions_rejected(self):
        target = self.root / "ordinary"; target.write_text("unchanged")
        for suffix in ("-journal", "-wal", "-shm"):
            path = Path(str(self.store.db_path) + suffix)
            path.symlink_to(target)
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "storage_symlink"):
                self.store.poll("intel", "receiver")
            path.unlink()
        self.store.db_path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "storage_permissions"):
            self.store.poll("intel", "receiver")
        self.assertEqual(target.read_text(), "unchanged")

    def test_note_symlink_rejected(self):
        identifier, _ = self.note()
        path = self.root / "context/notes" / (identifier + ".json")
        original = path.read_bytes(); path.unlink()
        target = self.root / "copy.json"; target.write_bytes(original); path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "invalid_saved_note"):
            self.store.publish(identifier, "mac", "intel", hashlib.sha256(original).hexdigest())

    def test_input_bounds_and_safe_error_messages(self):
        identifier, sha = self.note()
        calls = [lambda: self.store.publish(identifier, "intel", "intel", sha),
                 lambda: self.store.publish(identifier, "mac", "elsewhere", sha),
                 lambda: self.store.publish(identifier, "mac", "intel", sha, "ack"),
                 lambda: self.store.publish("../secret", "mac", "intel", sha),
                 lambda: self.store.poll("intel", "bad consumer"),
                 lambda: self.store.poll("intel", "receiver", after_seq=True),
                 lambda: self.store.poll("intel", "receiver", limit=101)]
        for call in calls:
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertRegex(str(caught.exception), r"^[a-z_]+$")
        event = self.publish()
        for seconds in (True, 0, 4, 3601):
            with self.assertRaisesRegex(ValueError, "invalid_lease_seconds"):
                self.store.claim("intel", "receiver", event["event_id"], seconds)
        claim = self.claim(event)
        with self.assertRaisesRegex(ValueError, "invalid_completion"):
            self.finish(claim, "failed", OTHER_RESULT, "raw error with secrets")
        with self.assertRaisesRegex(ValueError, "invalid_completion"):
            self.finish(claim, outcome=[])

    def test_aware_clock_is_supported_and_naive_clock_rejected(self):
        aware = HandoffEvents(self.root, clock=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc))
        self.assertIn("+00:00", aware.poll("intel", "receiver")["checked_at"])
        bad = HandoffEvents(self.root, clock=lambda: datetime(2026, 11, 15))
        with self.assertRaisesRegex(ValueError, "invalid_clock"):
            bad.poll("intel", "receiver")


if __name__ == "__main__":
    unittest.main()
