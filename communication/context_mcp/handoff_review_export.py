"""Create-only public review summaries from durable private Mac receiver results.

The caller holds the receiver lock. This performs no MCP publication, event
creation, Notion write or application action. The existing review workflow must
reconcile proposals independently and keep its own idempotent receipt ledger.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import stat
from uuid import UUID, uuid4

from handoff_receiver import (MAX_RESULT_BYTES, ReceiverError, atomic_json,
    canonical, digest, parse_json, private_dir, read_private, timestamp, validate_event)
from handoff_codex_runner import (REVIEW_SCHEMA, SECRET_PATTERN, RunnerFailure,
                                  validate_review, validate_snapshot)

MAX_PUBLIC_BYTES = 128 * 1024
PRIVATE_REFERENCE = re.compile(
    r"(?i)(?:\.junction-setup[/\\]|\.codex[/\\]|\.aws[/\\]|"
    r"(?:^|[/\\])\.env(?:[./\\]|$)|connection\.json|server-key\.pem|"
    r"\.env\.providers|provider\.env|private-key)")


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _public_folder(project_root):
    current = project_root
    for part in ("context", "automation-reviews"):
        current = current / part
        if current.is_symlink():
            raise ReceiverError("review_export_symlink")
        current.mkdir(mode=0o755, exist_ok=True)
        if not current.is_dir():
            raise ReceiverError("review_export_path_invalid")
    return current


def _existing_public(path):
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ReceiverError("review_export_file_invalid")
            data = handle.read(MAX_PUBLIC_BYTES + 1)
        if len(data) > MAX_PUBLIC_BYTES:
            raise ReceiverError("review_export_file_invalid")
        return data
    except ReceiverError:
        raise
    except OSError:
        raise ReceiverError("review_export_read_failed") from None


def _create_only(path, payload):
    data = canonical(payload) + b"\n"
    if len(data) > MAX_PUBLIC_BYTES:
        raise ReceiverError("review_export_too_large")
    if path.exists() or path.is_symlink():
        if _existing_public(path) != data:
            raise ReceiverError("review_export_conflict")
        return False, digest(data)
    temporary = path.parent / (".review-export-" + str(uuid4()))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # link is atomic and cannot replace an existing destination.
            os.link(temporary, path, follow_symlinks=False)
            created = True
        except FileExistsError:
            if _existing_public(path) != data:
                raise ReceiverError("review_export_conflict")
            created = False
        temporary.unlink()
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return created, digest(data)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_review_payload(event_dir, local):
    if local.get("status") not in {"acknowledged", "processed_pending_ack"}:
        return None
    run_name = local.get("runDirectory")
    if run_name is None:
        # Server-completed work owned by another consumer has no local review.
        return None
    if not isinstance(run_name, str) or not re.fullmatch(r"run-[0-9]{1,8}", run_name):
        raise ReceiverError("review_export_run_invalid")
    run = private_dir(event_dir / run_name)
    input_path = run / "input.json"
    input_raw = read_private(input_path, 256 * 1024)
    envelope = parse_json(input_raw)
    try:
        note, canonical_hash, source_hash = validate_snapshot(input_path)
        event = validate_event(envelope.get("event"), "mac")
        if (event["event_id"] != event_dir.name or local.get("eventId") != event_dir.name
                or event["note_id"] != note["note_id"] or event["note_sha256"] != source_hash
                or event["note_characters"] != len(envelope["noteSourceText"])
                or local.get("noteSha256") != source_hash):
            raise ReceiverError("review_export_source_mismatch")
        raw = read_private(run / "result.json", MAX_RESULT_BYTES)
        result_hash = digest(raw)
        result = parse_json(raw)
        if (not isinstance(result, dict) or type(result.get("schemaVersion")) is not int
                or result.get("schemaVersion") != 1
                or result.get("runnerStatus") != "processed"
                or local.get("resultSha256") != result_hash
                or result.get("sourceNoteId") != note["note_id"]
                or result.get("sourceNoteSha256") != canonical_hash
                or result.get("sourceNoteSourceSha256") != source_hash
                or result.get("externalWritesPerformed") is not False
                or result.get("desktopChatWoken") is not False):
            raise ReceiverError("review_export_result_mismatch")
        review = validate_review({key: result[key] for key in REVIEW_SCHEMA["required"]})
        reviewed_at = result.get("completedAt")
        value = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReceiverError("review_export_time_invalid")
    except ReceiverError:
        raise
    except (RunnerFailure, KeyError, TypeError, ValueError, AttributeError):
        raise ReceiverError("review_export_validation_failed") from None
    payload = {"schemaVersion": 1, "eventId": event["event_id"], "eventSequence": event["seq"],
        "noteId": note["note_id"], "notePath": event["note_path"],
        "sourceNoteSha256": source_hash, "sourceNoteCanonicalSha256": canonical_hash,
        "reviewResultSha256": result_hash, "reviewedAt": reviewed_at,
        "state": "pending_reconciliation", "reviewKind": "read_only_source_review",
        "notionSync": "pending" if review["proposed_task_updates"] else "not_required",
        "externalWritesPerformed": False, **review,
        "notice": "Read-only review proposals require independent evidence reconciliation. No Notion update or new work event was published by this export."}
    text = canonical(payload).decode("utf-8")
    if SECRET_PATTERN.search(text) or PRIVATE_REFERENCE.search(text):
        raise ReceiverError("review_export_sensitive_content")
    return payload


def export_reviews(state_dir, project_root, *, target="mac", limit=100):
    """Visit at most limit event states per call, retrying failures independently.

    A separate scan cursor rotates through event directory names. It is never an
    event acknowledgment, never changes the receiver cursor, and cannot hide a
    failed export permanently. Directory names are cheap to enumerate; input and
    result reads/validation are bounded to limit entries each invocation.
    """
    if target != "mac" or type(limit) is not int or not 1 <= limit <= 100:
        raise ReceiverError("review_export_configuration_invalid")
    state_dir = private_dir(state_dir)
    project_root = Path(project_root).resolve(strict=True)
    receiver_state = parse_json(read_private(state_dir / "state.json"))
    if (not isinstance(receiver_state, dict) or receiver_state.get("target") != "mac"
            or receiver_state.get("projectRoot") != str(project_root)
            or not (project_root / "AGENTS.md").is_file()):
        raise ReceiverError("review_export_project_mismatch")
    events_dir = state_dir / "events"
    summary = {"scanned": 0, "created": 0, "existing": 0, "failed": 0, "skipped": 0}
    if events_dir.is_symlink():
        raise ReceiverError("review_export_symlink")
    if not events_dir.exists():
        return summary
    private_dir(events_dir)
    names = sorted(p.name for p in events_dir.iterdir() if _uuid(p.name))
    scan_path = state_dir / "review-export-state.json"
    scan = parse_json(read_private(scan_path)) if scan_path.exists() or scan_path.is_symlink() else {}
    if not isinstance(scan, dict):
        raise ReceiverError("review_export_scan_invalid")
    after = scan.get("afterEventId", "")
    if not isinstance(after, str) or (after and not _uuid(after)):
        raise ReceiverError("review_export_scan_invalid")
    candidates = [name for name in names if name > after]
    if not candidates:
        candidates = names
    for name in candidates[:limit]:
        summary["scanned"] += 1
        event_dir = events_dir / name
        local = None
        try:
            private_dir(event_dir)
            local = parse_json(read_private(event_dir / "state.json"))
            if not isinstance(local, dict):
                raise ReceiverError("review_export_state_invalid")
            payload = build_review_payload(event_dir, local)
            if payload is None:
                summary["skipped"] += 1
            else:
                destination = _public_folder(project_root) / (name + ".json")
                created, public_hash = _create_only(destination, payload)
                local["reviewExport"] = {"status": "exported", "payloadSha256": public_hash,
                    "path": "context/automation-reviews/" + name + ".json"}
                atomic_json(event_dir / "state.json", local)
                summary["created" if created else "existing"] += 1
        except (ReceiverError, OSError, ValueError, TypeError) as error:
            summary["failed"] += 1
            code = error.code if isinstance(error, ReceiverError) else "review_export_failed"
            if isinstance(local, dict) and not event_dir.is_symlink():
                local["reviewExport"] = {"status": "retry_pending", "errorCode": code,
                                          "lastAttemptAt": timestamp()}
                try:
                    atomic_json(event_dir / "state.json", local)
                except (ReceiverError, OSError, ValueError):
                    pass
        scan = {"schemaVersion": 1, "afterEventId": name}
        atomic_json(scan_path, scan)
    return summary
