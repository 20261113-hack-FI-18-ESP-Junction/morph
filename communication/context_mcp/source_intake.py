#!/usr/bin/env python3
"""Reconstruct explicit source deliveries into isolated, unaccepted review data.

Only the installed source-transfer collector is imported. Incoming files, note
content and companion metadata never select commands, imports, Git operations or
local comparison roots. Successful intake means verified bytes available for
review, not an accepted change or permission to execute those bytes.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from uuid import UUID, uuid4, uuid5

MAX_TRANSFERS = 16
MAX_TOTAL_BYTES = 20_000_000
MAX_TOTAL_FILES = 5000
MAX_TOTAL_PARTS = 5000
MAX_NOTE_BYTES = 256_000
MAX_RECEIPT_BYTES = MAX_TOTAL_BYTES
HASH = re.compile(r"[0-9a-f]{64}\Z")
ENVELOPE_KEYS = {"schemaVersion", "kind", "deliveryId", "sourceHost", "requestId", "transfers"}
TRANSFER_KEYS = {"transferId", "manifestNoteId", "bundleSha256"}
NOTE_FIELDS = {"note_id", "title", "content", "author", "evidence", "status"}
COLLECTOR_PATH = Path(__file__).resolve().parents[1] / "context/coordination/three-host-20261115/collect_source_response.py"


class IntakeError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate")
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, UnicodeError, RecursionError):
        raise IntakeError("invalid_json") from None


def checked_uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise IntakeError("invalid_identity") from None
    return value


def plain_path(path):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise IntakeError("path_traversal_rejected")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise IntakeError("symlink_rejected")
    return path


def private_dir(path):
    path = plain_path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise IntakeError("directory_not_private")
    return path


def read_bounded(path, maximum, *, private=False):
    path = plain_path(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_size > maximum
                    or (private and (before.st_mode & 0o077 or before.st_uid != os.getuid()
                                     or before.st_nlink != 1))):
                raise IntakeError("file_not_bounded_or_private")
            raw = handle.read(maximum + 1)
            after = os.fstat(handle.fileno())
        if (len(raw) > maximum or (before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_ino, after.st_size, after.st_mtime_ns)):
            raise IntakeError("file_changed_or_too_large")
        return raw
    except FileNotFoundError:
        raise IntakeError("source_or_receipt_missing") from None


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def create_json(path, value):
    path = plain_path(path)
    raw = encoded(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    sync_dir(path.parent)
    return digest(raw)


def replace_json(path, value):
    path = plain_path(path)
    temporary = path.parent / (".intake-write-" + str(uuid4()))
    try:
        create_json(temporary, value)
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def locked(state_dir):
    path = plain_path(state_dir / "intake.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise IntakeError("lock_not_private")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise IntakeError("intake_busy") from None
        yield
    finally:
        os.close(fd)


def load_collector():
    # This fixed project-owned implementation is not selected by the delivery.
    path = plain_path(COLLECTOR_PATH)
    specification = importlib.util.spec_from_file_location("morph_intake_collector", path)
    module = importlib.util.module_from_spec(specification)
    old_flag = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        specification.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_flag
    return module


def saved_note(notes, identity):
    identity = checked_uuid(identity)
    raw = read_bounded(notes / (identity + ".json"), MAX_NOTE_BYTES)
    note = parse(raw)
    if (not isinstance(note, dict) or not NOTE_FIELDS <= set(note)
            or note.get("note_id") != identity or note.get("redacted") is True
            or any(not isinstance(note.get(key), str) for key in NOTE_FIELDS)
            or len(note["content"]) > 23_000):
        raise IntakeError("invalid_or_redacted_note")
    return note, digest(raw)


def delivery_envelope(note):
    value = parse(note["content"])
    if (not isinstance(value, dict) or set(value) != ENVELOPE_KEYS
            or type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1
            or value.get("kind") != "morph-source-delivery" or value.get("sourceHost") != "intel"
            or not isinstance(value.get("transfers"), list)
            or not 1 <= len(value["transfers"]) <= MAX_TRANSFERS):
        raise IntakeError("invalid_delivery_envelope")
    checked_uuid(value["deliveryId"])
    checked_uuid(value["requestId"])
    seen = set()
    for transfer in value["transfers"]:
        if not isinstance(transfer, dict) or set(transfer) != TRANSFER_KEYS:
            raise IntakeError("invalid_transfer_reference")
        identity = checked_uuid(transfer["transferId"])
        manifest = checked_uuid(transfer["manifestNoteId"])
        if (identity in seen or manifest != str(uuid5(UUID(identity), "manifest"))
                or not isinstance(transfer["bundleSha256"], str)
                or not HASH.fullmatch(transfer["bundleSha256"])):
            raise IntakeError("invalid_transfer_reference")
        seen.add(identity)
    # Reference order carries no meaning; deduplication pins the exact set.
    return {**value, "transfers": sorted(value["transfers"], key=lambda row: row["transferId"])}


def validate_transfers(collector, notes, envelope):
    declarations, total_bytes, total_files, total_parts = [], 0, 0, 0
    for transfer in envelope["transfers"]:
        note, _ = saved_note(notes, transfer["manifestNoteId"])
        manifest = parse(note["content"])
        if (not isinstance(manifest, dict) or manifest.get("requestId") != envelope["requestId"]
                or manifest.get("transferId") != transfer["transferId"]
                or manifest.get("bundleSha256") != transfer["bundleSha256"]):
            raise IntakeError("manifest_reference_mismatch")
        for key, maximum in (("bundleBytes", MAX_TOTAL_BYTES), ("fileCount", MAX_TOTAL_FILES),
                             ("partCount", MAX_TOTAL_PARTS)):
            if type(manifest.get(key)) is not int or not 1 <= manifest[key] <= maximum:
                raise IntakeError("delivery_limit_exceeded")
        total_bytes += manifest["bundleBytes"]
        total_files += manifest["fileCount"]
        total_parts += manifest["partCount"]
        if total_bytes > MAX_TOTAL_BYTES or total_files > MAX_TOTAL_FILES or total_parts > MAX_TOTAL_PARTS:
            raise IntakeError("delivery_limit_exceeded")
        declarations.append((transfer, manifest))
    validated = []
    for transfer, manifest in declarations:
        # Reject explicit readback-redaction metadata too; the original collector
        # independently checks every complete six-field payload and source hash.
        for part in range(1, manifest["partCount"] + 1):
            saved_note(notes, str(uuid5(UUID(transfer["transferId"]), "part:" + str(part))))
        try:
            checked, _bundle, files = collector.validate(notes, transfer["manifestNoteId"], envelope["requestId"])
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError):
            raise IntakeError("transfer_incomplete_or_invalid") from None
        if checked != manifest:
            raise IntakeError("manifest_changed_during_validation")
        validated.append((transfer, checked, files))
    return validated


def compare_file(relative, source_hash, root, forbidden):
    if root is None:
        return {"state": "not_configured"}
    path = root / relative
    try:
        path = plain_path(path)
        if any(path == area or area in path.parents for area in forbidden):
            return {"state": "unavailable", "errorCode": "private_intake_path"}
        if not path.exists():
            return {"state": "missing"}
        raw = read_bounded(path, 2_000_000)
        sha = digest(raw)
        return {"state": "same" if sha == source_hash else "different", "bytes": len(raw), "sha256": sha}
    except (IntakeError, OSError):
        return {"state": "unavailable", "errorCode": "comparison_file_unavailable"}


def comparison_inventory(validated, roots, forbidden):
    rows = []
    for transfer, _manifest, files in validated:
        for relative, raw in files:
            sha = digest(raw)
            rows.append({"transferId": transfer["transferId"], "path": relative, "bytes": len(raw),
                "sha256": sha, **{label: compare_file(relative, sha, root, forbidden)
                                  for label, root in roots.items()}})
    return {"schemaVersion": 1, "capturedAt": now(), "comparisonRule": "Exact relative source paths only; no incoming target mapping is applied.",
            "comparisonRoots": {label: str(root) if root else None for label, root in roots.items()},
            "incomingAccepted": False, "omittedPathsAreDeletions": False, "files": rows}


def seal_collected(path):
    # The unchanged collector creates files exclusively. Flush their bytes and
    # directories before a durable intake receipt can name the attempt complete.
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in [*dirs, *files]:
            plain_path(Path(directory) / name)
        for name in files:
            fd = os.open(Path(directory) / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    for directory, _dirs, _files in os.walk(path, topdown=False, followlinks=False):
        sync_dir(directory)


def validate_output(output, identity_hash, envelope, *, receipt_sha=None, expected=None):
    raw = read_bounded(output / "receipt.json", MAX_RECEIPT_BYTES, private=True)
    if receipt_sha is not None:
        if not isinstance(receipt_sha, str) or not HASH.fullmatch(receipt_sha):
            raise IntakeError("saved_receipt_pin_invalid")
        if digest(raw) != receipt_sha:
            raise IntakeError("saved_receipt_hash_mismatch")
    receipt = parse(raw)
    if (not isinstance(receipt, dict) or receipt.get("identitySha256") != identity_hash
            or receipt.get("deliveryId") != envelope["deliveryId"]
            or receipt.get("requestId") != envelope["requestId"]
            or receipt.get("status") != "reconstructed_verified_for_review"
            or receipt.get("sourceAccepted") is not False
            or receipt.get("sourceExecuted") is not False
            or receipt.get("liveSourceOverwritten") is not False or receipt.get("gitMutated") is not False):
        raise IntakeError("saved_receipt_identity_mismatch")
    attempt_id = checked_uuid(receipt.get("attemptId"))
    if receipt.get("comparisonPath") != "attempts/" + attempt_id + "/comparison.json":
        raise IntakeError("saved_comparison_path_invalid")
    attempt = plain_path(output / "attempts" / attempt_id)
    comparison = read_bounded(attempt / "comparison.json", MAX_RECEIPT_BYTES, private=True)
    if digest(comparison) != receipt.get("comparisonSha256"):
        raise IntakeError("saved_comparison_hash_mismatch")
    transfers = receipt.get("transfers")
    if not isinstance(transfers, list) or len(transfers) != len(envelope["transfers"]):
        raise IntakeError("saved_transfer_inventory_mismatch")
    for index, reference in enumerate(envelope["transfers"]):
        result = transfers[index]
        if not isinstance(result, dict) or any(result.get(key) != value for key, value in reference.items()):
            raise IntakeError("saved_transfer_inventory_mismatch")
        folder = attempt / "transfers" / reference["transferId"]
        manifest_raw = read_bounded(folder / "manifest.json", MAX_NOTE_BYTES, private=True)
        report_raw = read_bounded(folder / "report.json", MAX_RECEIPT_BYTES, private=True)
        if (digest(manifest_raw) != result.get("manifestSha256") or digest(report_raw) != result.get("reportSha256")):
            raise IntakeError("saved_transfer_hash_mismatch")
        report = parse(report_raw)
        if (not isinstance(report, dict) or report.get("transferId") != reference["transferId"] or report.get("requestId") != envelope["requestId"]
                or report.get("bundleSha256") != reference["bundleSha256"] or report.get("verified") is not True
                or report.get("sourceExecuted") is not False or report.get("liveSourceOverwritten") is not False):
            raise IntakeError("saved_transfer_identity_mismatch")
        expected_rows = None
        if expected is not None:
            expected_rows = [{"path": path, "bytes": len(raw), "sha256": digest(raw)} for path, raw in expected[index][2]]
            if report.get("files") != expected_rows:
                raise IntakeError("saved_transfer_files_mismatch")
        rows = report.get("files")
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_TOTAL_FILES:
            raise IntakeError("saved_transfer_inventory_mismatch")
        expected_paths = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                raise IntakeError("saved_source_path_invalid")
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts or "\\" in row["path"] or relative.as_posix() != row["path"]:
                raise IntakeError("saved_source_path_invalid")
            path = plain_path(folder / "source" / relative)
            raw_file = read_bounded(path, 2_000_000, private=True)
            if len(raw_file) != row.get("bytes") or digest(raw_file) != row.get("sha256"):
                raise IntakeError("saved_source_hash_mismatch")
            if row["path"] in expected_paths:
                raise IntakeError("saved_source_path_invalid")
            expected_paths.add(row["path"])
        actual = set()
        for directory, dirs, files in os.walk(folder / "source", followlinks=False):
            for name in [*dirs, *files]:
                plain_path(Path(directory) / name)
            actual.update((Path(directory) / name).relative_to(folder / "source").as_posix() for name in files)
        if actual != expected_paths:
            raise IntakeError("unexpected_saved_source_file")
    return receipt, digest(raw)


def _intake_locked(notes, note_id, state_dir, incoming_root, roots):
    observations = private_dir(state_dir / "observations")
    records = private_dir(state_dir / "deliveries")
    try:
        note, note_hash = saved_note(notes, note_id)
        envelope = delivery_envelope(note)
    except (IntakeError, OSError) as error:
        code = error.code if isinstance(error, IntakeError) else "delivery_note_unavailable"
        result = {"schemaVersion": 1, "deliveryNoteId": note_id, "status": "pending", "errorCode": code,
                  "checkedAt": now(), "sourceAccepted": False}
        replace_json(observations / (note_id + ".json"), result)
        return result
    identity_hash = digest(encoded(envelope))
    output = plain_path(incoming_root / envelope["deliveryId"])
    record_path = records / (envelope["deliveryId"] + ".json")
    configuration = {"output": str(output), "comparisonRoots": {key: str(value) if value else None for key, value in roots.items()}}
    record = None
    if record_path.exists():
        record = parse(read_bounded(record_path, MAX_RECEIPT_BYTES, private=True))
        if not isinstance(record, dict) or record.get("identitySha256") != identity_hash or record.get("configuration") != configuration:
            raise IntakeError("delivery_identity_or_configuration_conflict")
    else:
        record = {"schemaVersion": 1, "deliveryId": envelope["deliveryId"], "requestId": envelope["requestId"],
            "deliveryNoteId": note_id, "deliveryNoteSha256": note_hash, "identitySha256": identity_hash,
            "envelope": envelope, "configuration": configuration, "firstSeenAt": now(), "status": "pending",
            "sourceAccepted": False}
        create_json(record_path, record)
    try:
        # Once completion established a trusted receipt hash, every recovery
        # path must retain that pin. A failed integrity check cannot downgrade
        # the record into an unpinned pre-completion recovery on the next retry.
        pin_required = (record.get("receiptPinRequired") is True
                        or record.get("status") == "reconstructed_verified_for_review"
                        or "receiptSha256" in record or "verifiedAt" in record)
        if pin_required:
            record["receiptPinRequired"] = True
            pin = record.get("receiptSha256")
            if not isinstance(pin, str) or not HASH.fullmatch(pin):
                raise IntakeError("saved_receipt_pin_invalid")
        if record.get("status") == "reconstructed_verified_for_review":
            receipt, _sha = validate_output(output, identity_hash, envelope, receipt_sha=record.get("receiptSha256"))
            return {**receipt, "reused": True, "output": str(output), "comparisonIsOriginalSnapshot": True}
        collector = load_collector()
        validated = validate_transfers(collector, notes, envelope)
        marker = {"schemaVersion": 1, "kind": "morph-source-intake-output", "deliveryId": envelope["deliveryId"], "identitySha256": identity_hash}
        if output.exists():
            if not output.is_dir() or not (output / "intake-owner.json").is_file():
                raise IntakeError("incoming_directory_conflict")
            if parse(read_bounded(output / "intake-owner.json", MAX_NOTE_BYTES, private=True)) != marker:
                raise IntakeError("incoming_directory_conflict")
        else:
            output.mkdir(mode=0o700)
            create_json(output / "intake-owner.json", marker)
        private_dir(output)
        # A crash after saving the receipt but before saving the ledger is
        # recovered only after the original transfer validates again.
        if (output / "receipt.json").exists():
            receipt, receipt_hash = validate_output(output, identity_hash, envelope,
                receipt_sha=record.get("receiptSha256") if pin_required else None, expected=validated)
            recovered = True
        else:
            attempts = private_dir(output / "attempts")
            attempt_id = str(uuid4())
            attempt = attempts / attempt_id
            attempt.mkdir(mode=0o700)
            transfer_root = private_dir(attempt / "transfers")
            results = []
            for reference, manifest, files in validated:
                destination = transfer_root / reference["transferId"]
                try:
                    report = collector.collect(notes, reference["manifestNoteId"], destination, envelope["requestId"])
                except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError):
                    raise IntakeError("source_reconstruction_incomplete") from None
                expected_rows = [{"path": path, "bytes": len(raw), "sha256": digest(raw)} for path, raw in files]
                if report.get("files") != expected_rows or parse((destination / "manifest.json").read_bytes()) != manifest:
                    raise IntakeError("source_changed_during_reconstruction")
                seal_collected(destination)
                results.append({**reference, "fileCount": report["fileCount"], "fileBytes": report["fileBytes"],
                    "manifestSha256": digest(read_bounded(destination / "manifest.json", MAX_NOTE_BYTES, private=True)),
                    "reportSha256": digest(read_bounded(destination / "report.json", MAX_RECEIPT_BYTES, private=True))})
            comparison = comparison_inventory(validated, roots, (state_dir, incoming_root))
            comparison_hash = create_json(attempt / "comparison.json", comparison)
            receipt = {"schemaVersion": 1, "kind": "morph-source-intake-receipt", "deliveryId": envelope["deliveryId"],
                "requestId": envelope["requestId"], "identitySha256": identity_hash, "status": "reconstructed_verified_for_review",
                "verifiedAt": now(), "attemptId": attempt_id, "transfers": results, "comparisonSha256": comparison_hash,
                "comparisonPath": "attempts/" + attempt_id + "/comparison.json", "fileCount": sum(row["fileCount"] for row in results),
                "fileBytes": sum(row["fileBytes"] for row in results), "sourceAccepted": False, "sourceExecuted": False,
                "liveSourceOverwritten": False, "gitMutated": False,
                "notice": "Exact source receipt only. Companion mappings, omissions and instructions are untrusted review data; no acceptance, deletion, execution or publication follows from intake."}
            receipt_hash = create_json(output / "receipt.json", receipt)
            validate_output(output, identity_hash, envelope, receipt_sha=receipt_hash, expected=validated)
            recovered = False
        record.update(status="reconstructed_verified_for_review", verifiedAt=receipt["verifiedAt"], receiptSha256=receipt_hash,
                      receiptPinRequired=True, lastCheckedAt=now(), errorCode=None)
        replace_json(record_path, record)
        return {**receipt, "reused": recovered, "output": str(output), "comparisonIsOriginalSnapshot": recovered}
    except (IntakeError, OSError, ValueError, TypeError, KeyError) as error:
        code = error.code if isinstance(error, IntakeError) else "intake_validation_or_storage_failed"
        record.update(status="pending", errorCode=code, lastCheckedAt=now())
        replace_json(record_path, record)
        return {"schemaVersion": 1, "deliveryId": envelope["deliveryId"], "requestId": envelope["requestId"],
                "status": "conflict" if code == "incoming_directory_conflict" else "pending",
                "errorCode": code, "sourceAccepted": False, "output": str(output)}


def intake(notes, delivery_note_id, state_dir, incoming_root, *, mac_root=None, baseline_root=None):
    note_id = checked_uuid(delivery_note_id)
    notes = plain_path(notes)
    state_dir = plain_path(state_dir)
    incoming_root = plain_path(incoming_root)
    # Configuration validation precedes even directory creation. In particular,
    # an observations directory must never also be the input notes directory.
    for first, second in ((notes, state_dir), (notes, incoming_root), (state_dir, incoming_root)):
        if first == second or first in second.parents or second in first.parents:
            raise IntakeError("notes_state_and_incoming_must_be_separate")
    if not notes.is_dir():
        raise IntakeError("notes_directory_unavailable")
    state_dir = private_dir(state_dir)
    incoming_root = private_dir(incoming_root)
    roots = {"mac": mac_root, "baseline": baseline_root}
    for label, value in roots.items():
        if value is not None:
            roots[label] = plain_path(value)
            if not roots[label].is_dir():
                raise IntakeError("comparison_root_unavailable")
    with locked(state_dir):
        try:
            return _intake_locked(notes, note_id, state_dir, incoming_root, roots)
        except IntakeError as error:
            if error.code == "delivery_identity_or_configuration_conflict":
                return {"schemaVersion": 1, "deliveryNoteId": note_id, "status": "conflict",
                        "errorCode": error.code, "sourceAccepted": False}
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes", required=True, type=Path)
    parser.add_argument("--delivery-note-id", required=True)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--incoming-root", required=True, type=Path)
    parser.add_argument("--mac-root", type=Path)
    parser.add_argument("--baseline-root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = intake(args.notes, args.delivery_note_id, args.state_dir, args.incoming_root,
                        mac_root=args.mac_root, baseline_root=args.baseline_root)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "reconstructed_verified_for_review" else 1
    except (IntakeError, OSError, ValueError, TypeError) as error:
        code = error.code if isinstance(error, IntakeError) else "intake_configuration_failed"
        print(json.dumps({"status": "rejected", "errorCode": code, "sourceAccepted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
