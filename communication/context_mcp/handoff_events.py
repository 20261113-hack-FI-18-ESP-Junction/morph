"""Opt-in, durable work events over immutable shared-context handoffs.

Polls never acknowledge work. A target has at most one live processing lease;
failed work remains discoverable below any receiver cursor. Neither this store
nor a legacy save_handoff call executes or automatically publishes anything.
Acknowledgments must never be published as new work events.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from urllib.parse import quote
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from store import ContextStore


HOSTS = frozenset({"mac", "intel"})
REVIEW_AUTHOR = "Codex on Mac | scheduled project review"
NOTE_STATUSES = frozenset({"proposed", "implemented", "verified", "blocked", "handoff"})
MAX_NOTE_CHARACTERS = 128_000
PAGE_CHARACTERS = 24_000
HASH = re.compile(r"[a-f0-9]{64}\Z")
CONSUMER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z")
ERROR_CODE = re.compile(r"(?:[a-z][a-z0-9_]{0,63})?\Z")
ACK_KINDS = frozenset({"ack", "receipt"})


def checked_uuid(value):
    try:
        if not isinstance(value, str) or len(value) != 36:
            raise ValueError
        canonical = str(UUID(value))
        if value != canonical:
            raise ValueError
        return canonical
    except (ValueError, AttributeError):
        raise ValueError("invalid_uuid") from None


def host(value):
    if not isinstance(value, str) or value not in HOSTS:
        raise ValueError("invalid_host")
    return value


def consumer(value):
    if not isinstance(value, str) or not CONSUMER.fullmatch(value):
        raise ValueError("invalid_consumer")
    return value


def digest(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError("invalid_sha256")
    return value


def bounded_integer(value, low, high, code):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(code)
    return value


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("invalid_json_constant")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


class HandoffEvents:
    def __init__(self, root, db_path=None, clock=None):
        try:
            self.root = Path(root).resolve(strict=True)
            self.context = ContextStore(self.root)
            self.db_path = Path(db_path) if db_path is not None else self.root / ".junction-setup/context-share/handoff-events.sqlite3"
            if not self.db_path.is_absolute():
                self.db_path = self.root / self.db_path
            if ".." in self.db_path.parts or not self.db_path.is_relative_to(self.root) or self.db_path.parent == self.root:
                raise ValueError("invalid_storage_path")
            self.clock = clock or time.time
            self._prepare()
        except (OSError, sqlite3.Error):
            raise ValueError("storage_unavailable") from None

    def _now(self):
        value = self.clock()
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("invalid_clock")
            value = value.timestamp()
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 253_402_300_799:
            raise ValueError("invalid_clock")
        return float(value)

    def _check_path(self):
        current = self.root
        for part in self.db_path.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("storage_symlink")
            if current.exists():
                info = current.stat()
                if current == self.db_path:
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError("invalid_storage_file")
                elif not stat.S_ISDIR(info.st_mode):
                    raise ValueError("invalid_storage_directory")
                if hasattr(os, "getuid") and info.st_uid != os.getuid():
                    raise ValueError("invalid_storage_owner")
        for suffix in ("-journal", "-wal", "-shm"):
            if Path(str(self.db_path) + suffix).is_symlink():
                raise ValueError("storage_symlink")

    def _prepare(self):
        self._check_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path.parent.chmod(0o700)
        try:
            descriptor = os.open(self.db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            self._check_path()
        else:
            os.close(descriptor)
        self.db_path.chmod(0o600)
        with self._db(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS handoff_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                note_id TEXT NOT NULL, note_path TEXT NOT NULL,
                note_sha256 TEXT NOT NULL, note_characters INTEGER NOT NULL,
                origin TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL,
                created REAL NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0, received REAL,
                consumer_id TEXT, claim_id TEXT, lease_expires REAL,
                processed REAL, failed REAL, retry REAL,
                result_sha256 TEXT, error_code TEXT NOT NULL DEFAULT '')""")
            db.execute("CREATE INDEX IF NOT EXISTS handoff_target_seq ON handoff_events(target,seq)")

    @contextmanager
    def _db(self, write=False):
        db = None
        try:
            self._check_path()
            if not self.db_path.is_file():
                raise ValueError("storage_unavailable")
            if stat.S_IMODE(self.db_path.stat().st_mode) != 0o600 or stat.S_IMODE(self.db_path.parent.stat().st_mode) != 0o700:
                raise ValueError("storage_permissions")
            mode = "rw" if write else "ro"
            db = sqlite3.connect("file:" + quote(str(self.db_path), safe="/") + "?mode=" + mode,
                                 uri=True, timeout=10, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            if not write:
                db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except sqlite3.Error:
            if db is not None:
                db.rollback()
            raise ValueError("storage_unavailable") from None
        except BaseException:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    def _note(self, note_id, expected_hash):
        path = "context/notes/" + note_id + ".json"
        chunks, offset, total = [], 0, None
        try:
            while True:
                page = self.context.read(path, offset=offset, limit=PAGE_CHARACTERS)
                if (page.get("redacted") is not False or page.get("path") != path
                        or page.get("offset") != offset or page.get("sha256") != expected_hash):
                    raise ValueError
                count = page.get("total_characters")
                if type(count) is not int or not 1 <= count <= MAX_NOTE_CHARACTERS or (total is not None and count != total):
                    raise ValueError
                total = count
                content = page.get("content")
                if not isinstance(content, str) or len(content) != min(PAGE_CHARACTERS, total - offset):
                    raise ValueError
                chunks.append(content)
                offset += len(content)
                following = page.get("next_offset")
                if offset == total:
                    if following is not None:
                        raise ValueError
                    break
                if type(following) is not int or following != offset:
                    raise ValueError
            raw = "".join(chunks)
            if hashlib.sha256(raw.encode("utf-8")).hexdigest() != expected_hash:
                raise ValueError
            note = strict_json(raw)
            if not isinstance(note, dict) or note.get("note_id") != note_id or note.get("status") not in NOTE_STATUSES:
                raise ValueError
            for field, bound in (("title", 200), ("author", 200), ("content", 24_000), ("evidence", 4000)):
                if not isinstance(note.get(field), str) or not note[field].strip() or len(note[field]) > bound:
                    raise ValueError
            saved_at = datetime.fromisoformat(note["saved_at"].replace("Z", "+00:00"))
            if saved_at.tzinfo is None or saved_at.utcoffset() is None:
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError):
            raise ValueError("invalid_saved_note") from None
        if note["author"] == REVIEW_AUTHOR:
            raise ValueError("reconciliation_note_not_work")
        containers = [note]
        try:
            body = strict_json(note["content"])
            if isinstance(body, dict):
                containers.append(body)
        except (ValueError, RecursionError):
            pass
        if any(isinstance(item.get(key), str) and item[key].casefold() in ACK_KINDS
               for item in containers for key in ("kind", "event_type")):
            raise ValueError("acknowledgment_not_work")
        return path, total

    @staticmethod
    def _row(db, target, event_id):
        row = db.execute("SELECT * FROM handoff_events WHERE target=? AND event_id=?", (target, event_id)).fetchone()
        if row is None:
            raise ValueError("unknown_event")
        return row

    @staticmethod
    def _busy(db, target, event_id, now):
        return db.execute("SELECT event_id FROM handoff_events WHERE target=? AND state='claimed' AND lease_expires>? AND event_id!=? LIMIT 1",
                          (target, now, event_id)).fetchone() is not None

    def _event(self, db, row, now):
        result = {key: row[key] for key in ("event_id", "seq", "note_id", "note_path", "note_sha256", "note_characters",
                  "origin", "target", "kind", "state", "attempts", "consumer_id", "claim_id", "result_sha256", "error_code")}
        for output, column in (("created_at", "created"), ("received_at", "received"), ("processed_at", "processed"),
                               ("failed_at", "failed"), ("retry_at", "retry"), ("lease_expires_at", "lease_expires")):
            result[output] = iso(row[column])
        available = row["state"] == "queued" or (row["state"] == "failed" and row["retry"] <= now) or (
            row["state"] == "claimed" and row["lease_expires"] <= now)
        result["claimable"] = available and not self._busy(db, row["target"], row["event_id"], now)
        return result

    def publish(self, note_id, origin, target, note_sha256, kind="work"):
        note_id, origin, target, note_sha256 = checked_uuid(note_id), host(origin), host(target), digest(note_sha256)
        if origin == target or kind != "work":
            raise ValueError("invalid_event_direction_or_kind")
        path, characters = self._note(note_id, note_sha256)
        event_id = str(uuid5(NAMESPACE_URL, f"morph:handoff-event:v1:{note_id}:{origin}:{target}"))
        with self._db(write=True) as db:
            row = db.execute("SELECT * FROM handoff_events WHERE event_id=?", (event_id,)).fetchone()
            created = row is None
            if row is not None:
                if (row["note_id"], row["origin"], row["target"], row["note_sha256"], row["kind"], row["note_path"], row["note_characters"]) != (
                        note_id, origin, target, note_sha256, kind, path, characters):
                    raise ValueError("event_content_conflict")
            else:
                db.execute("INSERT INTO handoff_events(event_id,note_id,note_path,note_sha256,note_characters,origin,target,kind,created) VALUES(?,?,?,?,?,?,?,?,?)",
                           (event_id, note_id, path, note_sha256, characters, origin, target, kind, self._now()))
                row = self._row(db, target, event_id)
            return {"created": created, "event": self._event(db, row, self._now())}

    def poll(self, target, consumer_id, after_seq=0, limit=20):
        target, consumer_id = host(target), consumer(consumer_id)
        bounded_integer(after_seq, 0, 2**63 - 1, "invalid_cursor")
        bounded_integer(limit, 1, 100, "invalid_poll_limit")
        with self._db() as db:
            now = self._now()
            high_water = db.execute("SELECT COALESCE(MAX(seq),0) FROM handoff_events WHERE target=?", (target,)).fetchone()[0]
            # A discovery cursor cannot acknowledge or hide unfinished old work.
            rows = db.execute("SELECT * FROM handoff_events WHERE target=? AND (seq>? OR state!='processed') ORDER BY seq LIMIT ?",
                              (target, after_seq, limit)).fetchall()
            return {"target": target, "consumer_id": consumer_id, "after_seq": after_seq, "high_water": high_water,
                    "events": [self._event(db, row, now) for row in rows], "checked_at": iso(now)}

    def claim(self, target, consumer_id, event_id, lease_seconds=300):
        target, consumer_id, event_id = host(target), consumer(consumer_id), checked_uuid(event_id)
        bounded_integer(lease_seconds, 5, 3600, "invalid_lease_seconds")
        with self._db(write=True) as db:
            now = self._now()
            row = self._row(db, target, event_id)
            reason = None
            if row["state"] == "processed":
                reason = "already_processed"
            elif row["state"] == "claimed" and row["lease_expires"] > now:
                if row["consumer_id"] == consumer_id:
                    return {"claimed": True, "duplicate": True, "event": self._event(db, row, now)}
                reason = "event_busy"
            elif self._busy(db, target, event_id, now):
                reason = "target_busy"
            elif row["state"] == "failed" and row["retry"] > now:
                reason = "retry_backoff"
            if reason:
                return {"claimed": False, "reason": reason, "event": self._event(db, row, now)}
            db.execute("UPDATE handoff_events SET state='claimed',attempts=attempts+1,received=COALESCE(received,?),consumer_id=?,claim_id=?,lease_expires=?,retry=NULL,result_sha256=NULL,error_code='' WHERE event_id=?",
                       (now, consumer_id, str(uuid4()), now + lease_seconds, event_id))
            return {"claimed": True, "duplicate": False, "event": self._event(db, self._row(db, target, event_id), now)}

    @staticmethod
    def _lease(row, consumer_id, claim_id, now):
        if row["state"] != "claimed" or row["consumer_id"] != consumer_id or row["claim_id"] != claim_id or row["lease_expires"] <= now:
            raise ValueError("stale_or_invalid_claim")

    def renew(self, target, consumer_id, event_id, claim_id, lease_seconds=300):
        target, consumer_id, event_id, claim_id = host(target), consumer(consumer_id), checked_uuid(event_id), checked_uuid(claim_id)
        bounded_integer(lease_seconds, 5, 3600, "invalid_lease_seconds")
        with self._db(write=True) as db:
            now = self._now()
            row = self._row(db, target, event_id)
            self._lease(row, consumer_id, claim_id, now)
            db.execute("UPDATE handoff_events SET lease_expires=? WHERE event_id=?", (max(row["lease_expires"], now + lease_seconds), event_id))
            return {"renewed": True, "event": self._event(db, self._row(db, target, event_id), now)}

    def complete(self, target, consumer_id, event_id, claim_id, outcome, result_sha256, error_code=""):
        target, consumer_id, event_id, claim_id = host(target), consumer(consumer_id), checked_uuid(event_id), checked_uuid(claim_id)
        result_sha256 = digest(result_sha256)
        if not isinstance(outcome, str) or outcome not in {"processed", "failed"} or not isinstance(error_code, str) or not ERROR_CODE.fullmatch(error_code) or (outcome == "processed" and error_code):
            raise ValueError("invalid_completion")
        with self._db(write=True) as db:
            now = self._now()
            row = self._row(db, target, event_id)
            if row["state"] in {"processed", "failed"}:
                identity = (row["consumer_id"], row["claim_id"], row["state"], row["result_sha256"], row["error_code"])
                if identity == (consumer_id, claim_id, outcome, result_sha256, error_code):
                    return {"duplicate": True, "event": self._event(db, row, now)}
                raise ValueError("completion_conflict")
            self._lease(row, consumer_id, claim_id, now)
            if outcome == "processed":
                db.execute("UPDATE handoff_events SET state='processed',processed=?,retry=NULL,result_sha256=?,error_code='' WHERE event_id=?",
                           (now, result_sha256, event_id))
            else:
                backoff = min(5 * 2 ** min(row["attempts"] - 1, 6), 300)
                db.execute("UPDATE handoff_events SET state='failed',failed=?,retry=?,result_sha256=?,error_code=? WHERE event_id=?",
                           (now, now + backoff, result_sha256, error_code, event_id))
            return {"duplicate": False, "event": self._event(db, self._row(db, target, event_id), now)}

    def status(self, target, event_id):
        target, event_id = host(target), checked_uuid(event_id)
        with self._db() as db:
            return {"event": self._event(db, self._row(db, target, event_id), self._now())}
