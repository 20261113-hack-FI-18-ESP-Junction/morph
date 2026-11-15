#!/usr/bin/env python3
"""Freeze reviewed source into an outbox, then send it through the existing MCP.

Only explicit source paths are read. No code is executed, installed or adopted.
The sender never starts a watcher, contacts a robot, or overwrites source files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID, uuid5

SCHEMA = 1
MAX_FILE = 2_000_000
MAX_BUNDLE = 20_000_000
MAX_NOTE = 23_000
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs", ".css", ".html", ".svg", ".sql", ".md", ".txt", ".toml", ".yaml", ".yml", ".json", ".sh", ".in", ".lock"}
DENIED_DIRS = {"node_modules", "__pycache__", "dist", "build", "tmp", "logs", "data", "datasets", "recordings", "weights", "checkpoints", "cache", "caches", "evidence", "coverage", "venv", "vendor"}
DENIED_NAMES = {"connection.json", "connection.toml", "connection.yaml", "connection.yml", "robot-connections.json", "settings.json"}
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:sk-(?:proj-)?[a-z0-9_-]{16,}|nvapi-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9_]{20,}|github_pat_[a-z0-9_]{20,}|AIza[a-z0-9_-]{30,})"),
    re.compile(r"(?i)\bBearer\s+[a-z0-9._~+/-]{16,}"),
    re.compile(r"(?im)[\"']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|authorization|MORPH_CONTEXT_TOKEN)[\"']?\s*[:=]\s*(?P<quote>[\"'])[^\"'\r\n]{8,}(?P=quote)"),
    re.compile(r"(?im)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret|authorization|MORPH_CONTEXT_TOKEN)\s*[:=]\s*[a-z0-9][a-z0-9_+/=-]{15,}(?=[ \t]*(?:[#;]|$))"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative_path(value):
    p = PurePosixPath(value)
    if not value or "\\" in value or "\x00" in value or p.is_absolute() or ".." in p.parts or p.as_posix() != value or value == ".":
        raise ValueError("Include must be an exact relative source path")
    return p


def denied(path):
    parts = path.parts
    name = path.name.lower()
    if any(x.startswith(".") or x.lower() in DENIED_DIRS for x in parts):
        return True
    return name in DENIED_NAMES or any(x in name for x in ("credential", "secret", "private-key", "token-file", ".env")) or name.endswith((".pem", ".key"))


def resolve_source(root, relative):
    p = relative_path(relative)
    current = root
    for piece in p.parts:
        current = current / piece
        if current.is_symlink():
            raise ValueError("Symbolic link rejected: " + relative)
    try:
        current.resolve().relative_to(root)
    except ValueError:
        raise ValueError("Source path escapes the supplied root")
    return current


def read_source(root, path):
    relative = path.relative_to(root).as_posix()
    resolve_source(root, relative)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
            raise ValueError("Not a bounded regular source file: " + relative)
        raw = handle.read(MAX_FILE + 1)
        after = os.fstat(handle.fileno())
    if len(raw) > MAX_FILE or (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino):
        raise ValueError("Source changed while reading: " + relative)
    text = raw.decode("utf-8")
    if "\x00" in text or any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError("Potential secret or binary content rejected in " + relative + "; review locally and select a clean source path")
    return {"path": relative, "bytes": len(raw), "sha256": digest(raw), "text": text}


def collect(root, includes):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Root must be a directory")
    paths, skipped = set(), []
    for include in includes:
        p = relative_path(include)
        if denied(p):
            raise ValueError("Private/runtime include rejected: " + include)
        source = resolve_source(root, include)
        if not source.exists():
            raise ValueError("Include does not exist: " + include)
        if source.is_file():
            if p.suffix.lower() not in TEXT_SUFFIXES:
                raise ValueError("Unsupported source file: " + include)
            paths.add(source)
            continue
        for directory, dirs, files in os.walk(source, followlinks=False):
            allowed = []
            for name in sorted(dirs):
                child = Path(directory) / name
                rel = child.relative_to(root)
                if child.is_symlink() or denied(rel):
                    skipped.append({"path": rel.as_posix(), "reason": "excluded directory or symlink"})
                else:
                    allowed.append(name)
            dirs[:] = allowed
            for name in files:
                child = Path(directory) / name
                rel = child.relative_to(root)
                if child.is_symlink() or denied(rel) or child.suffix.lower() not in TEXT_SUFFIXES:
                    skipped.append({"path": rel.as_posix(), "reason": "excluded file or symlink"})
                else:
                    paths.add(child)
    records = [read_source(root, p) for p in sorted(paths)]
    if not records:
        raise ValueError("No eligible source files")
    return records, sorted(skipped, key=lambda row: row["path"])


def note_id(transfer_id, label):
    return str(uuid5(UUID(transfer_id), label))


def make_note(identity, title, content):
    text = encoded(content).decode("utf-8")
    if len(text) > MAX_NOTE:
        raise ValueError("Note exceeds bounded content limit")
    return {"note_id": identity, "title": title, "content": text,
            "author": "Intel source transfer helper", "evidence": "Exact UTF-8 source snapshot with SHA-256; source is not executed or adopted.", "status": "handoff"}


def prepare(root, includes, request_id, transfer_id, output):
    request_id, transfer_id = str(UUID(request_id)), str(UUID(transfer_id))
    if output.exists():
        raise ValueError("Outbox exists; use verify/send to retry the frozen snapshot")
    records, skipped = collect(root, includes)
    bundle = {"schemaVersion": SCHEMA, "kind": "morph-source-bundle", "requestId": request_id,
              "transferId": transfer_id, "createdAt": datetime.now(timezone.utc).isoformat(),
              "sourceRoot": str(root.resolve()), "includes": includes, "files": records, "skipped": skipped}
    raw = encoded(bundle)
    if len(raw) > MAX_BUNDLE:
        raise ValueError("Bundle exceeds 20 MB; select fewer source paths")
    bundle_hash = digest(raw)
    text = raw.decode("utf-8")
    chunks = []
    while text:
        size = min(12_000, len(text))
        while len(encoded({"text": text[:size]}).decode()) > 21_000:
            size //= 2
        chunks.append(text[:size])
        text = text[size:]
    notes = []
    for index, chunk in enumerate(chunks, 1):
        payload = {"schemaVersion": SCHEMA, "kind": "morph-source-chunk", "requestId": request_id,
                   "transferId": transfer_id, "part": index, "partCount": len(chunks),
                   "bundleSha256": bundle_hash, "chunkSha256": digest(chunk.encode()), "text": chunk}
        notes.append(make_note(note_id(transfer_id, "part:" + str(index)), "Intel source | " + transfer_id + " | part " + str(index), payload))
    manifest = {"schemaVersion": SCHEMA, "kind": "morph-source-manifest", "requestId": request_id,
                "transferId": transfer_id, "createdAt": bundle["createdAt"], "bundleSha256": bundle_hash,
                "bundleBytes": len(raw), "fileCount": len(records), "fileBytes": sum(row["bytes"] for row in records),
                "partCount": len(chunks), "partNoteIdRule": "UUID5(namespace=transferId, name='part:' + oneBasedPartNumber)",
                "skippedCount": len(skipped)}
    first = make_note(note_id(transfer_id, "manifest"), "Intel source manifest | " + transfer_id, manifest)
    output.mkdir(parents=True, mode=0o700)
    (output / "notes").mkdir(mode=0o700)
    (output / "bundle.json").write_bytes(raw)
    (output / "manifest.json").write_bytes(encoded(manifest))
    for row in [first, *notes]:
        (output / "notes" / (row["note_id"] + ".json")).write_bytes(encoded(row))
    verify(output)
    return manifest


def verify(output):
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest.get("kind") != "morph-source-manifest" or manifest.get("schemaVersion") != SCHEMA:
        raise ValueError("Unknown manifest")
    transfer_id, request_id = str(UUID(manifest["transferId"])), str(UUID(manifest["requestId"]))
    first = json.loads((output / "notes" / (note_id(transfer_id, "manifest") + ".json")).read_text())
    if first != make_note(note_id(transfer_id, "manifest"), "Intel source manifest | " + transfer_id, manifest):
        raise ValueError("Manifest note differs from frozen manifest")
    notes, parts = [first], []
    for part in range(1, manifest["partCount"] + 1):
        identity = note_id(transfer_id, "part:" + str(part))
        note = json.loads((output / "notes" / (identity + ".json")).read_text())
        value = json.loads(note["content"])
        if note != make_note(identity, "Intel source | " + transfer_id + " | part " + str(part), value):
            raise ValueError("Chunk note fields differ from frozen protocol")
        if (note["note_id"] != identity or value.get("kind") != "morph-source-chunk" or value.get("transferId") != transfer_id
                or value.get("requestId") != request_id or value.get("part") != part or value.get("partCount") != manifest["partCount"]
                or value.get("bundleSha256") != manifest["bundleSha256"] or digest(value["text"].encode()) != value["chunkSha256"]):
            raise ValueError("Chunk identity or hash mismatch")
        notes.append(note)
        parts.append(value["text"])
    raw = "".join(parts).encode()
    if len(raw) != manifest["bundleBytes"] or digest(raw) != manifest["bundleSha256"] or raw != (output / "bundle.json").read_bytes():
        raise ValueError("Bundle size or hash mismatch")
    bundle = json.loads(raw)
    if (bundle.get("transferId") != transfer_id or bundle.get("requestId") != request_id
            or bundle.get("kind") != "morph-source-bundle" or bundle.get("schemaVersion") != SCHEMA
            or len(bundle["files"]) != manifest["fileCount"] or sum(row["bytes"] for row in bundle["files"]) != manifest["fileBytes"]):
        raise ValueError("Bundle identity mismatch")
    seen = set()
    for row in bundle["files"]:
        p = relative_path(row["path"])
        if row["path"] in seen or denied(p) or p.suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError("Invalid or duplicate source path in bundle")
        seen.add(row["path"])
        raw_file = row["text"].encode()
        if len(raw_file) != row["bytes"] or digest(raw_file) != row["sha256"] or any(x.search(row["text"]) for x in SECRET_PATTERNS):
            raise ValueError("File hash or secret validation failed")
    return manifest, notes


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("MCP redirect rejected; no token forwarded")


class MCP:
    def __init__(self, pairing):
        connection = json.loads((pairing / "connection.json").read_text())
        self.url = connection["url"]
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Pairing must specify a direct HTTPS MCP endpoint")
        token = connection["token"]
        if not isinstance(token, str) or len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError("Pairing token is invalid")
        tls = ssl.create_default_context(cafile=str(pairing / "morph-ca.pem"))
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=tls))
        self.headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        self.counter = 0
        hello = self.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "morph-source-transfer", "version": "1.0"}})
        self.headers["MCP-Protocol-Version"] = hello["protocolVersion"]
        self.request("notifications/initialized", None, notification=True)

    def request(self, method, params, notification=False):
        self.counter += 1
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notification:
            body["id"] = self.counter
        request = urllib.request.Request(self.url, data=encoded(body), headers=self.headers)
        with self.opener.open(request, timeout=20) as response:
            if response.headers.get("Mcp-Session-Id"):
                self.headers["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("MCP response exceeds limit")
        if not raw and notification:
            return {}
        result = json.loads(raw)
        if "error" in result:
            raise ValueError("MCP rejected the request; frozen outbox retained")
        return result.get("result", {})

    def call(self, tool, arguments):
        result = self.request("tools/call", {"name": tool, "arguments": arguments})
        if result.get("isError"):
            raise ValueError("MCP tool failed: " + tool + "; frozen outbox retained")
        value = result.get("structuredContent")
        if value is None:
            texts = [row["text"] for row in result.get("content", []) if row.get("type") == "text"]
            value = json.loads("".join(texts))
        return value


def publish_notes(output, client):
    manifest, notes = verify(output)
    receipt_dir = output / "receipts"
    receipt_dir.mkdir(exist_ok=True, mode=0o700)
    for note in notes:
        saved = client.call("save_handoff", note)
        expected_path = "context/notes/" + note["note_id"] + ".json"
        if saved.get("path") != expected_path or any(saved.get("note", {}).get(k) != v for k, v in note.items()):
            raise ValueError("Saved source note differs, possibly redacted; transfer not verified")
        offset, pieces = 0, []
        while True:
            read = client.call("read_context", {"path": expected_path, "offset": offset, "limit": 24000})
            if read.get("redacted"):
                raise ValueError("Source readback was redacted")
            content = read["content"]
            pieces.append(content)
            offset += len(content)
            if offset >= read["total_characters"]:
                break
            if not content:
                raise ValueError("Empty paginated source readback")
        raw = "".join(pieces).encode()
        parsed = json.loads(raw)
        if any(parsed.get(k) != v for k, v in note.items()):
            raise ValueError("Source readback differs from frozen payload")
        receipt = {"noteId": note["note_id"], "path": expected_path, "sha256": digest(raw),
                   "checkedAt": datetime.now(timezone.utc).isoformat(), "created": saved.get("created"), "verified": True}
        (receipt_dir / (note["note_id"] + ".json")).write_bytes(encoded(receipt))
        print("Verified note " + note["note_id"], flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("prepare", help="Offline: freeze explicit source includes into a new outbox")
    pack.add_argument("--root", type=Path, required=True)
    pack.add_argument("--include", action="append", required=True)
    pack.add_argument("--request-id", required=True)
    pack.add_argument("--transfer-id", required=True)
    pack.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("verify", help="Offline: verify every byte and note in an existing outbox")
    check.add_argument("--output", type=Path, required=True)
    send = commands.add_parser("send", help="Send the frozen outbox through the existing TLS pairing, with readback")
    send.add_argument("--output", type=Path, required=True)
    send.add_argument("--pairing", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.root, args.include, args.request_id, args.transfer_id, args.output)
        elif args.command == "verify":
            result, _ = verify(args.output)
        else:
            result = publish_notes(args.output, MCP(args.pairing))
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # HTTP errors are rendered by type only: no response body or credentials.
        detail = type(exc).__name__ if isinstance(exc, urllib.error.URLError) else str(exc)
        print("Source transfer stopped: " + detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
