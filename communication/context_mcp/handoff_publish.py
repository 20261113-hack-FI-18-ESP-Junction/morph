#!/usr/bin/env python3
"""Explicitly publish one verified work handoff and its durable event.

Only this opt-in path creates an event; legacy save_handoff remains unchanged.
Receipts bind the exact source payload across retries. No payload, credentials
or raw remote errors are printed. The only transport dependency is the existing
standard-library station_worker module and its private HTTPS pairing.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

FIELDS = frozenset({"note_id", "title", "content", "author", "evidence", "status"})
STATUSES = frozenset({"proposed", "implemented", "verified", "blocked", "handoff"})
REVIEW_AUTHOR = "Codex on Mac | scheduled project review"
MAX_PAYLOAD_BYTES = 256_000
MAX_NOTE_CHARACTERS = 128_000
MAX_RECEIPT_BYTES = 32_000
PAGE_CHARACTERS = 24_000
HASH = re.compile(r"[a-f0-9]{64}\Z")
TOOLS = frozenset({"save_handoff", "read_context", "publish_handoff_event"})
SECRET_MARKERS = (
    re.compile(r"(?i)\b(?:sk-(?:proj-)?[a-z0-9_-]{16,}|nvapi-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9_]{20,}|github_pat_[a-z0-9_]{20,}|AIza[a-z0-9_-]{30,})"),
    re.compile(r"(?i)\bBearer\s+[a-z0-9._~+/-]{16,}"),
    re.compile(r"(?im)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|authorization|MORPH_CONTEXT_TOKEN)[\"']?\s*[:=]\s*[\"'][^\"'\r\n]{8,}[\"']"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class PublisherError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    def invalid(_):
        raise ValueError
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise PublisherError("invalid_json") from None


def canonical_uuid(value):
    try:
        if not isinstance(value, str) or len(value) != 36 or str(UUID(value)) != value:
            raise ValueError
        return value
    except (ValueError, AttributeError):
        raise PublisherError("invalid_note_id") from None


def work_payload(payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise PublisherError("invalid_payload_fields")
    canonical_uuid(payload["note_id"])
    if not isinstance(payload["status"], str) or payload["status"] not in STATUSES:
        raise PublisherError("invalid_note_status")
    for field, bound in (("title", 200), ("author", 200), ("content", 24_000), ("evidence", 4000)):
        value = payload[field]
        if not isinstance(value, str) or not value.strip() or len(value) > bound:
            raise PublisherError("invalid_payload_field")
        if any(pattern.search(value) for pattern in SECRET_MARKERS):
            raise PublisherError("possible_secret_in_payload")
    if payload["author"] == REVIEW_AUTHOR:
        raise PublisherError("reconciliation_note_not_work")
    try:
        content = parse_json(payload["content"])
    except PublisherError:
        content = None
    if isinstance(content, dict) and any(isinstance(content.get(key), str) and content[key].casefold() in {"ack", "receipt"}
                                         for key in ("kind", "event_type")):
        raise PublisherError("acknowledgment_not_work")
    return payload


def no_symlinks(path):
    if ".." in path.parts:
        raise PublisherError("invalid_local_path")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise PublisherError("local_symlink_rejected")


def read_file(path, maximum, private=False):
    try:
        no_symlinks(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise PublisherError("invalid_local_file")
        if private and (stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid()):
            raise PublisherError("receipt_not_private")
        with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise PublisherError("local_file_too_large")
        return raw
    except OSError:
        raise PublisherError("local_file_unavailable") from None


def private_directory(path):
    no_symlinks(path)
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
            raise PublisherError("receipt_directory_not_private")
    except OSError:
        raise PublisherError("receipt_directory_unavailable") from None


def atomic_receipt(path, value):
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_RECEIPT_BYTES:
        raise PublisherError("receipt_too_large")
    if path.exists() or path.is_symlink():
        read_file(path, MAX_RECEIPT_BYTES, private=True)
    temporary = path.parent / (".handoff-receipt-" + str(uuid4()))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        raise PublisherError("receipt_write_failed") from None
    finally:
        temporary.unlink(missing_ok=True)


class EventMCP:
    def __init__(self, client, source_provenance=None):
        self.client = client
        self.source_provenance = source_provenance

    @classmethod
    def from_pairing(cls, folder):
        try:
            import station_worker
            source = Path(station_worker.__file__).resolve()
            client = station_worker.MCPClient.from_pairing(Path(folder))
            client.initialize()
            return cls(client, {"path": str(source), "sha256": sha256(source.read_bytes())})
        except Exception:
            raise PublisherError("mcp_connection_failed") from None

    def call(self, name, arguments):
        if name not in TOOLS:
            raise PublisherError("mcp_tool_not_allowed")
        try:
            reply = self.client._request("tools/call", {"name": name, "arguments": arguments})
            if reply.get("isError") or not isinstance(reply.get("structuredContent"), dict):
                raise PublisherError("mcp_tool_failed")
            return reply["structuredContent"]
        except PublisherError:
            raise
        except Exception:
            raise PublisherError("mcp_transport_failed") from None


class HandoffPublisher:
    def __init__(self, mcp, payload_path, origin, target, receipt_file):
        if not isinstance(origin, str) or not isinstance(target, str) or origin not in {"mac", "intel"} or target not in {"mac", "intel"} or origin == target:
            raise PublisherError("invalid_direction")
        self.mcp, self.origin, self.target = mcp, origin, target
        self.payload_path = Path(payload_path).absolute()
        self.receipt_file = Path(receipt_file).absolute()
        self.raw_payload = read_file(self.payload_path, MAX_PAYLOAD_BYTES)
        self.payload = work_payload(parse_json(self.raw_payload))
        self.payload_sha256 = sha256(self.raw_payload)
        self.note_id = self.payload["note_id"]
        self.note_path = "context/notes/" + self.note_id + ".json"
        self.event_id = str(uuid5(NAMESPACE_URL, f"morph:handoff-event:v1:{self.note_id}:{origin}:{target}"))
        source = Path(__file__).resolve()
        self.source = {"path": str(source), "sha256": sha256(source.read_bytes())}

    @contextmanager
    def locked(self):
        private_directory(self.receipt_file.parent)
        lock_path = self.receipt_file.with_name(self.receipt_file.name + ".lock")
        no_symlinks(lock_path)
        fd = None
        try:
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
                raise PublisherError("receipt_lock_not_private")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PublisherError("publisher_already_running") from None
            yield
        except OSError:
            raise PublisherError("receipt_lock_unavailable") from None
        finally:
            if fd is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _prepare(self):
        if sha256(read_file(self.payload_path, MAX_PAYLOAD_BYTES)) != self.payload_sha256:
            raise PublisherError("payload_changed")
        identity = {"schemaVersion": 1, "note_id": self.note_id, "note_path": self.note_path,
                    "origin": self.origin, "target": self.target, "kind": "work",
                    "payload_path": str(self.payload_path), "payload_sha256": self.payload_sha256}
        if self.receipt_file.exists() or self.receipt_file.is_symlink():
            receipt = parse_json(read_file(self.receipt_file, MAX_RECEIPT_BYTES, private=True))
            if not isinstance(receipt, dict) or any(receipt.get(key) != value for key, value in identity.items()):
                raise PublisherError("receipt_identity_conflict")
            if receipt.get("phase") not in {"prepared", "saved_note", "event_published"}:
                raise PublisherError("invalid_receipt_phase")
            if receipt["phase"] != "prepared" and (not isinstance(receipt.get("note_sha256"), str) or not HASH.fullmatch(receipt["note_sha256"])):
                raise PublisherError("invalid_receipt_note")
            if receipt["phase"] == "event_published" and (receipt.get("event_id") != self.event_id or type(receipt.get("event_seq")) is not int or receipt["event_seq"] < 1):
                raise PublisherError("invalid_receipt_event")
            return receipt
        receipt = {**identity, "phase": "prepared", "prepared_at": timestamp(), "publisher_source": self.source}
        atomic_receipt(self.receipt_file, receipt)
        return receipt

    def prepare(self):
        with self.locked():
            return self._prepare()

    def _call(self, name, arguments):
        try:
            result = self.mcp.call(name, arguments)
            if not isinstance(result, dict):
                raise PublisherError("invalid_mcp_result")
            return result
        except PublisherError:
            raise
        except Exception:
            raise PublisherError("mcp_call_failed") from None

    def _readback(self):
        offset, total, expected_hash, chunks = 0, None, None, []
        while True:
            page = self._call("read_context", {"path": self.note_path, "offset": offset, "limit": PAGE_CHARACTERS})
            count, current_hash, content = page.get("total_characters"), page.get("sha256"), page.get("content")
            if (page.get("path") != self.note_path or page.get("offset") != offset or page.get("redacted") is not False
                    or type(count) is not int or not 1 <= count <= MAX_NOTE_CHARACTERS
                    or (total is not None and count != total) or not isinstance(current_hash, str) or not HASH.fullmatch(current_hash)
                    or (expected_hash is not None and current_hash != expected_hash) or not isinstance(content, str)
                    or len(content) != min(PAGE_CHARACTERS, count - offset)):
                raise PublisherError("saved_note_page_mismatch")
            total, expected_hash = count, current_hash
            chunks.append(content)
            offset += len(content)
            if offset == total:
                if page.get("next_offset") is not None:
                    raise PublisherError("saved_note_page_mismatch")
                break
            if type(page.get("next_offset")) is not int or page["next_offset"] != offset:
                raise PublisherError("saved_note_page_mismatch")
        try:
            raw = "".join(chunks).encode("utf-8")
        except UnicodeError:
            raise PublisherError("invalid_saved_note_encoding") from None
        if sha256(raw) != expected_hash:
            raise PublisherError("saved_note_hash_mismatch")
        note = parse_json(raw)
        if not isinstance(note, dict) or any(note.get(key) != value for key, value in self.payload.items()):
            raise PublisherError("saved_note_content_mismatch")
        try:
            saved_at = datetime.fromisoformat(note["saved_at"].replace("Z", "+00:00"))
            if saved_at.tzinfo is None or saved_at.utcoffset() is None:
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            raise PublisherError("invalid_saved_note_timestamp") from None
        return {"note_sha256": expected_hash, "note_characters": total, "note_saved_at": note["saved_at"]}

    def run(self):
        with self.locked():
            receipt = self._prepare()
            if receipt["phase"] == "event_published":
                return {"phase": "event_published", "note_id": self.note_id, "event_id": self.event_id,
                        "event_seq": receipt["event_seq"], "reused_receipt": True}
            if receipt["phase"] == "prepared":
                saved = self._call("save_handoff", dict(self.payload))
                if saved.get("path") != self.note_path or not isinstance(saved.get("note"), dict) or saved["note"].get("note_id") != self.note_id:
                    raise PublisherError("saved_note_identity_mismatch")
            readback = self._readback()
            if receipt.get("note_sha256") is not None and receipt["note_sha256"] != readback["note_sha256"]:
                raise PublisherError("saved_note_changed")
            receipt.update(readback, phase="saved_note", verified_at=timestamp(), last_publisher_source=self.source)
            provenance = getattr(self.mcp, "source_provenance", None)
            if provenance is not None:
                receipt["transport_source"] = provenance
            atomic_receipt(self.receipt_file, receipt)
            result = self._call("publish_handoff_event", {"note_id": self.note_id, "origin": self.origin,
                "target": self.target, "note_sha256": readback["note_sha256"], "kind": "work"})
            event = result.get("event")
            expected = {"event_id": self.event_id, "note_id": self.note_id, "note_path": self.note_path,
                        "note_sha256": readback["note_sha256"], "note_characters": readback["note_characters"],
                        "origin": self.origin, "target": self.target, "kind": "work"}
            if (not isinstance(event, dict) or any(event.get(key) != value for key, value in expected.items())
                    or type(event.get("seq")) is not int or event["seq"] < 1):
                raise PublisherError("event_publication_mismatch")
            receipt.update(phase="event_published", event_id=self.event_id, event_seq=event["seq"],
                           event_published_at=timestamp(), event_created=bool(result.get("created")))
            atomic_receipt(self.receipt_file, receipt)
            return {"phase": "event_published", "note_id": self.note_id, "event_id": self.event_id,
                    "event_seq": event["seq"], "reused_receipt": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairing-folder", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True, help="Exact saved six-field work-note JSON; unchanged on retry")
    parser.add_argument("--origin", choices=("mac", "intel"), required=True)
    parser.add_argument("--target", choices=("mac", "intel"), required=True)
    parser.add_argument("--receipt-file", type=Path, required=True, help="Durable receipt in an owner-only private directory")
    args = parser.parse_args(argv)
    try:
        publisher = HandoffPublisher(None, args.payload, args.origin, args.target, args.receipt_file)
        prepared = publisher.prepare()
        if prepared["phase"] != "event_published":
            publisher.mcp = EventMCP.from_pairing(args.pairing_folder)
        print(json.dumps(publisher.run(), sort_keys=True))
        return 0
    except KeyboardInterrupt:
        return 130
    except (PublisherError, OSError, ValueError, TypeError) as error:
        code = error.code if isinstance(error, PublisherError) else "publisher_failed"
        print(json.dumps({"phase": "retry_pending", "error_code": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
