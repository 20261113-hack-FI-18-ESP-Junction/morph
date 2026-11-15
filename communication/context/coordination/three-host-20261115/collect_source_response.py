#!/usr/bin/env python3
"""Validate saved source-transfer notes, then materialize a NEW review folder.

Incoming files are data. They are never imported, executed, installed or copied
over the live application. No output is created until every note/file validates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata
from uuid import UUID

SPEC = importlib.util.spec_from_file_location("morph_source_response_protocol", Path(__file__).with_name("source_response.py"))
protocol = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(protocol)

DEFAULT_REQUEST_ID = "00e34e99-cfc8-47bf-ab5d-1d029242f841"
MAX_PARTS = 5000
MAX_SAVED_NOTE_BYTES = 256_000
NOTE_FIELDS = ("note_id", "title", "content", "author", "evidence", "status")
HASH = re.compile(r"[a-f0-9]{64}\Z")


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def parse(raw):
    def bad_constant(_value):
        raise ValueError("Non-finite JSON value")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=bad_constant)


def plain_path(path):
    path = path.absolute()
    if ".." in path.parts:
        raise ValueError("Filesystem path may not contain parent traversal")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError("Filesystem symlink rejected")
    return path


def note_from(notes, identity):
    identity = str(UUID(identity))
    path = plain_path(notes / (identity + ".json"))
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SAVED_NOTE_BYTES:
            raise ValueError("Saved note is not a bounded regular file")
        raw = handle.read(MAX_SAVED_NOTE_BYTES + 1)
        after = os.fstat(handle.fileno())
    if len(raw) > MAX_SAVED_NOTE_BYTES or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Saved note changed during read or exceeded its limit")
    saved = parse(raw)
    if not isinstance(saved, dict) or any(field not in saved for field in NOTE_FIELDS):
        raise ValueError("Saved note has no complete six-field transfer payload")
    # The canonical MCP adds saved_at/verification_notice. They are receipt
    # metadata, not part of the sender's frozen six-field payload.
    note = {field: saved[field] for field in NOTE_FIELDS}
    if note["note_id"] != identity or not isinstance(note["content"], str) or len(note["content"]) > protocol.MAX_NOTE:
        raise ValueError("Saved note identity or content length mismatch")
    return note, parse(note["content"])


def bounded_integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Manifest integer outside the permitted bound")
    return value


def validate(notes, manifest_note_id, request_id=DEFAULT_REQUEST_ID):
    notes = plain_path(Path(notes))
    if not notes.is_dir():
        raise ValueError("Notes directory is unavailable")
    expected_request = str(UUID(request_id))
    manifest_note_id = str(UUID(manifest_note_id))
    first, manifest = note_from(notes, manifest_note_id)
    if not isinstance(manifest, dict) or manifest.get("kind") != "morph-source-manifest" or manifest.get("schemaVersion") != protocol.SCHEMA:
        raise ValueError("Unknown source manifest")
    transfer = str(UUID(manifest["transferId"]))
    if manifest.get("requestId") != expected_request or manifest_note_id != protocol.note_id(transfer, "manifest"):
        raise ValueError("Manifest request or deterministic note identity mismatch")
    if first != protocol.make_note(manifest_note_id, "Intel source manifest | " + transfer, manifest):
        raise ValueError("Manifest note differs from frozen protocol")
    part_count = bounded_integer(manifest.get("partCount"), 1, MAX_PARTS)
    bundle_bytes = bounded_integer(manifest.get("bundleBytes"), 1, protocol.MAX_BUNDLE)
    bounded_integer(manifest.get("fileCount"), 1, 50_000)
    bounded_integer(manifest.get("fileBytes"), 0, protocol.MAX_BUNDLE)
    if not isinstance(manifest.get("bundleSha256"), str) or not HASH.fullmatch(manifest["bundleSha256"]):
        raise ValueError("Invalid bundle hash")
    chunks, total = [], 0
    for part in range(1, part_count + 1):
        identity = protocol.note_id(transfer, "part:" + str(part))
        note, value = note_from(notes, identity)
        if not isinstance(value, dict) or note != protocol.make_note(identity, "Intel source | " + transfer + " | part " + str(part), value):
            raise ValueError("Chunk note differs from frozen protocol")
        if (value.get("schemaVersion") != protocol.SCHEMA or value.get("kind") != "morph-source-chunk"
                or value.get("requestId") != expected_request or value.get("transferId") != transfer
                or type(value.get("part")) is not int or value["part"] != part
                or type(value.get("partCount")) is not int or value["partCount"] != part_count
                or value.get("bundleSha256") != manifest["bundleSha256"] or not isinstance(value.get("text"), str)):
            raise ValueError("Chunk identity mismatch")
        raw = value["text"].encode("utf-8")
        if protocol.digest(raw) != value.get("chunkSha256"):
            raise ValueError("Chunk hash mismatch")
        total += len(raw)
        if total > bundle_bytes or total > protocol.MAX_BUNDLE:
            raise ValueError("Bundle exceeds declared or absolute limit")
        chunks.append(raw)
    raw = b"".join(chunks)
    if len(raw) != bundle_bytes or protocol.digest(raw) != manifest["bundleSha256"]:
        raise ValueError("Bundle size or hash mismatch")
    bundle = parse(raw)
    if (not isinstance(bundle, dict) or bundle.get("kind") != "morph-source-bundle"
            or bundle.get("schemaVersion") != protocol.SCHEMA or bundle.get("requestId") != expected_request
            or bundle.get("transferId") != transfer or not isinstance(bundle.get("files"), list)
            or len(bundle["files"]) != manifest["fileCount"]):
        raise ValueError("Bundle identity or file count mismatch")
    seen, parents, files, file_bytes = set(), set(), [], 0
    for row in bundle["files"]:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("text"), str):
            raise ValueError("Invalid source entry")
        path = protocol.relative_path(row["path"])
        if (len(row["path"].encode()) > 2000 or any(len(part.encode()) > 255 for part in path.parts)
                or any(ord(char) < 32 or ord(char) == 127 for char in row["path"])
                or protocol.denied(path) or path.suffix.lower() not in protocol.TEXT_SUFFIXES):
            raise ValueError("Private, binary or invalid source path")
        key = unicodedata.normalize("NFC", row["path"]).casefold()
        ancestor_keys = {unicodedata.normalize("NFC", parent.as_posix()).casefold() for parent in path.parents if parent.as_posix() != "."}
        if key in seen or key in parents or ancestor_keys & seen:
            raise ValueError("Duplicate or colliding source path")
        seen.add(key)
        parents.update(ancestor_keys)
        content = row["text"].encode("utf-8")
        bounded_integer(row.get("bytes"), 0, protocol.MAX_FILE)
        if (len(content) != row["bytes"] or protocol.digest(content) != row.get("sha256")
                or any(ord(char) < 32 and char not in "\t\r\n" for char in row["text"])
                or any(pattern.search(row["text"]) for pattern in protocol.SECRET_PATTERNS)):
            raise ValueError("File hash, secret or binary validation failed")
        file_bytes += len(content)
        if file_bytes > protocol.MAX_BUNDLE:
            raise ValueError("Source content exceeds limit")
        files.append((row["path"], content))
    if file_bytes != manifest["fileBytes"]:
        raise ValueError("Manifest source byte count mismatch")
    return manifest, bundle, files


def write_new(path, content):
    plain_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(content)


def collect(notes, manifest_note_id, output, request_id=DEFAULT_REQUEST_ID):
    output = plain_path(Path(output))
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Output must be a new directory under an existing parent")
    manifest, bundle, files = validate(notes, manifest_note_id, request_id)
    # All incoming payloads are validated before creating the output directory.
    plain_path(output.parent)
    output.mkdir(mode=0o700)
    (output / "source").mkdir(mode=0o700)
    for relative, raw in files:
        target = output / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_new(target, raw)
    write_new(output / "manifest.json", protocol.encoded(manifest))
    report = {"schemaVersion": 1, "requestId": manifest["requestId"], "transferId": manifest["transferId"],
        "manifestNoteId": str(UUID(manifest_note_id)), "collectedAt": datetime.now(timezone.utc).isoformat(),
        "bundleSha256": manifest["bundleSha256"], "bundleBytes": manifest["bundleBytes"],
        "fileCount": len(files), "fileBytes": manifest["fileBytes"], "verified": True,
        "sourceExecuted": False, "liveSourceOverwritten": False,
        "files": [{"path": path, "bytes": len(raw), "sha256": protocol.digest(raw)} for path, raw in files]}
    write_new(output / "report.json", protocol.encoded(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--manifest-note-id", required=True)
    parser.add_argument("--request-id", default=DEFAULT_REQUEST_ID)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(collect(args.notes, args.manifest_note_id, args.output, args.request_id), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Source collection stopped: input incomplete/invalid or output unavailable; no incoming code was executed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
