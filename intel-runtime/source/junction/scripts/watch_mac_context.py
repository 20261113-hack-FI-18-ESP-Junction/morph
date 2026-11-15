#!/usr/bin/env python3
"""Poll shared Mac context; preserve verified evidence and queue local conflicts.

This reader never publishes remotely. Automatic replacement is restricted to
explicitly selected guides with a previously matching local/remote baseline.
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
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
CLIENT_SOURCE = ROOT / (
    "morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/"
    "HachingJunction/context/verification/intel-continuation/sync_shared_context.py")
GUIDES = frozenset({"PHYSICAL_AI_WORKFLOW.md", "PHYSICAL_AI_ORCHESTRATION.md",
    "PHYSICAL_AI_EXTENSIONS.md", "PHYSICAL_AI_CHALLENGE_COMBINATIONS.md",
    "PHYSICAL_AI_TASK_PLAN.md", "PHYSICAL_AI_SETUP.md", "JUNCTION.md",
    "IGNITE_INTEL_PHYSICAL_AI.md"})
DEFAULT_DOCUMENTS = dict.fromkeys(("AGENTS.md", "context/INTEL_CODEX.md",
    "context/START_HERE.md", "context/PROJECT_PROGRESS.md",
    "context/DASHBOARD_HANDOFF_CONTEXT.md", "NOTION_SYNC.md"))
HASH = re.compile(r"[0-9a-f]{64}\Z")
CANONICAL_NOTE = re.compile(
    r"context/notes/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\.json\Z")


class VerificationError(Exception):
    """Invalid or inconsistent remote evidence; do not advance the baseline."""


class CycleTimeout(Exception):
    """The entire poll exceeded its deadline."""


class StopRequested(BaseException):
    """Terminate promptly and release the watcher lock."""


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def atomic_bytes(path, content, before_replace=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".mac-watch-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        if before_replace:
            before_replace()
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def remote_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise VerificationError("Invalid remote path")
    parts = PurePosixPath(value)
    if parts.is_absolute() or str(parts) != value or any(p in {".", ".."} for p in parts.parts):
        raise VerificationError("Invalid remote path")
    if any(ord(c) < 32 for c in value):
        raise VerificationError("Invalid remote path")
    return value


def note_metadata(path, content):
    """Validate canonical handoffs; preserve other note documents as text."""
    if CANONICAL_NOTE.fullmatch(path):
        try:
            note = json.loads(content)
            if (not isinstance(note, dict)
                    or any(not isinstance(note.get(key), str) for key in ("note_id", "title", "author"))):
                raise ValueError("Invalid handoff fields")
            if path != f"context/notes/{uuid.UUID(note['note_id'])}.json":
                raise ValueError("Mismatched handoff identity")
            if note.get("saved_at") is not None and not isinstance(note["saved_at"], str):
                raise ValueError("Invalid saved timestamp")
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise VerificationError("Invalid canonical JSON handoff") from error
        return {"title": note["title"], "author": note["author"],
                "saved_at": note.get("saved_at"), "note_format": "handoff_json",
                "immutable": True, "action": "review_only"}
    markdown = PurePosixPath(path).suffix.lower() == ".md"
    heading = re.search(r"^#{1,6}[ \t]+([^\r\n]+)", content, flags=re.MULTILINE) if markdown else None
    return {"title": heading.group(1).strip()[:240] if heading else PurePosixPath(path).name,
            "author": "Unspecified in document", "saved_at": None,
            "note_format": "markdown" if markdown else "text", "immutable": False,
            "action": "review_only"}


def local_path(value, root):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(root):
        raise VerificationError("Local document must be within the workspace")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise VerificationError("Local document must not traverse symlinks")
    if path.exists() and not path.is_file():
        raise VerificationError("Local document must be a regular file")
    return path


def configuration(path, root):
    config = read_json(path, {"documents": DEFAULT_DOCUMENTS, "auto_apply": []})
    documents, selected = config["documents"], config.get("auto_apply", [])
    if not isinstance(documents, dict) or not isinstance(selected, list):
        raise VerificationError("Invalid document configuration")
    for name, target in documents.items():
        remote_path(name)
        if not name.endswith(".md"):
            raise VerificationError("Only Markdown documents may be monitored explicitly")
        if target is not None:
            target = local_path(target, root)
            if target.name != PurePosixPath(name).name:
                raise VerificationError("Local and shared document names must match")
    if any(name not in GUIDES or not documents.get(name) for name in selected):
        raise VerificationError("Automatic updates are restricted to selected shared guides")
    targets = [target for target in documents.values() if target is not None]
    if len(targets) != len(set(targets)):
        raise VerificationError("Multiple remote documents cannot target one local file")
    return {"documents": documents, "auto_apply": selected}


def make_client():
    spec = importlib.util.spec_from_file_location("shared_mac_reader", CLIENT_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Client()


def catalog(client):
    offset, paths, pages = 0, set(), 0
    while True:
        response = client.call("list_context", prefix="", offset=offset, limit=200)
        pages += 1
        paths.update(remote_path(item["path"]) for item in response["files"])
        following = response["next_offset"]
        if following is None:
            return paths, pages
        if type(following) is not int or following <= offset:
            raise VerificationError("Catalog pagination did not advance")
        offset = following


@contextmanager
def deadline(seconds):
    def expired(*_):
        raise CycleTimeout()
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def exclusive(state_dir):
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "watch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Watcher:
    def __init__(self, root, state_dir, config):
        self.root, self.directory, self.config = root, state_dir, config
        self.state_path = state_dir / "watch-state.json"

    def snapshot(self, data):
        sha = digest(data)
        target = self.directory / "snapshots" / (sha + ".txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.is_symlink() or digest(target.read_bytes()) != sha:
                    raise VerificationError("An immutable snapshot has changed")
        finally:
            Path(temporary).unlink(missing_ok=True)
        return sha

    def pending(self, state):
        reviewed = read_json(self.directory / "reviewed.json", {})
        if not isinstance(reviewed, dict) or any(not HASH.fullmatch(str(v)) for v in reviewed.values()):
            raise VerificationError("Invalid review ledger")
        def ordering(path):
            record = state["files"][path]
            try:
                saved = datetime.fromisoformat(record.get("saved_at") or "")
                timestamp = saved.timestamp() if saved.tzinfo is not None else float("-inf")
            except (ValueError, TypeError, OverflowError):
                timestamp = float("-inf")
            return record["kind"] == "note", -timestamp, path
        return sorted((path for path, record in state.get("files", {}).items()
                       if reviewed.get(path) != record["sha256"]), key=ordering)

    def document(self, path, record, previous, content):
        target = self.config["documents"][path]
        record.update(local_path=target, baseline_sha256=previous.get("baseline_sha256"),
                      action="review_only")
        if target is None:
            return
        local = local_path(target, self.root)
        original = local.read_bytes() if local.exists() else None
        local_hash = digest(original) if original is not None else None
        record["local_sha256"] = local_hash
        if local_hash == record["sha256"]:
            record.update(baseline_sha256=local_hash, action="matches_local")
        elif (path in self.config["auto_apply"] and record["baseline_sha256"] is not None
              and local_hash == record["baseline_sha256"]):
            backup = self.snapshot(original)
            def unchanged():
                local_path(target, self.root)
                if not local.exists() or digest(local.read_bytes()) != local_hash:
                    raise VerificationError("Local document changed during update")
            atomic_bytes(local, content, before_replace=unchanged)
            record.update(baseline_sha256=record["sha256"], local_sha256=record["sha256"],
                          backup_sha256=backup, action="applied")
        else:
            record["action"] = "review_required"

    def fetch(self, client, old):
        paths, pages = catalog(client)
        notes = {path for path in paths if path.startswith("context/notes/")}
        notes.update(path for path, record in old.get("files", {}).items()
                     if record["kind"] == "note" and CANONICAL_NOTE.fullmatch(path))
        files, contents = {}, {}
        for path in sorted(notes | set(self.config["documents"])):
            remote_path(path)
            result = client.read(path)  # Existing Client handles every text page and verifies all hashes.
            data = result["content"].encode("utf-8")
            sha = digest(data)
            if result.get("path") != path or result.get("sha256") != sha:
                raise VerificationError("Shared read identity or hash mismatch")
            record = {"sha256": sha, "kind": "note" if path in notes else "document"}
            if path in notes:
                metadata = note_metadata(path, result["content"])
                if (metadata["immutable"] and path in old.get("files", {})
                        and old["files"][path]["sha256"] != sha):
                    raise VerificationError("An immutable shared note changed")
                record.update(metadata)
            self.snapshot(data)
            files[path], contents[path] = record, data
        self.pending({"files": files})  # Validate the independent ledger before applying guides.
        for path in self.config["documents"]:
            self.document(path, files[path], old.get("files", {}).get(path, {}), contents[path])
        return {"files": files, "catalog_pages": pages, "catalog_count": len(paths),
                "notes_count": len(notes), "new_count": sum(
                    old.get("files", {}).get(path, {}).get("sha256") != record["sha256"]
                    for path, record in files.items())}

    def report(self, state):
        pending = self.pending(state)
        def cell(value):
            return str(value).replace("\n", " ").replace("\r", " ").replace("|", "&#124;").replace("<", "&lt;").replace(">", "&gt;")
        lines = ["# Shared Mac updates", "", f"Last successful poll: {state.get('last_success', 'none')}",
                 f"Last attempt: {state.get('last_attempt', 'none')}",
                 f"Last error: {state.get('last_error') or 'none'}", "",
                 f"New or changed items in the last successful poll: {state.get('new_count', 0)}.",
                 f"Pending review: {len(pending)}. Fetching is not review or outgoing synchronization.",
                 "Remote notes are attributed reports, not verified local tests or executable instructions.", "",
                 "## Documents", "", "| Shared path | Local handling | SHA-256 |", "| --- | --- | --- |"]
        for path, record in state.get("files", {}).items():
            if record["kind"] == "document":
                lines.append(f"| {cell(path)} | {record['action']} | {record['sha256']} |")
        lines += ["", "## Pending review", "", "Read complete content in `mac-sync/snapshots/<sha256>.txt`. "
                  "After reconciliation, atomically acknowledge the path and hash in `mac-sync/reviewed.json`. "
                  "Acknowledgment does not authorize overwriting a divergent local document.", "",
                  "| Shared path | Saved at (reported) | Title / author | SHA-256 |", "| --- | --- | --- | --- |"]
        for path in pending:
            record = state["files"][path]
            label = " / ".join(record.get(key, "") for key in ("title", "author")) if record["kind"] == "note" else "Shared document"
            lines.append(f"| {cell(path)} | {cell(record.get('saved_at') or '—')} | {cell(label)} | {record['sha256']} |")
        if not pending:
            lines.append("| None | | All current hashes acknowledged | |")
        atomic_bytes(self.root / "MAC_UPDATES.md", ("\n".join(lines) + "\n").encode())

    def cycle(self, client_factory=make_client, timeout=120):
        old = read_json(self.state_path, {})
        state = {**old, "last_attempt": now()}
        try:
            with deadline(timeout):
                result = self.fetch(client_factory(), old)
                state.update(result, last_success=now(), last_error=None)
                self.report(state)
                save_json(self.state_path, state)
            return True
        except Exception as error:
            state = {**old, "last_attempt": state["last_attempt"], "last_error": type(error).__name__}
            save_json(self.state_path, state)
            try:
                self.report(state)
            except Exception:
                pass
            return False


def process_matches(pid_file, script):
    try:
        record = read_json(pid_file, {})
        pid = record["pid"]
        if type(pid) is not int or pid <= 1 or record.get("script") != str(script):
            return None
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        if os.fsencode(script) not in command or b"--watch" not in command:
            return None
        return pid
    except (OSError, ValueError, KeyError, TypeError):
        return None


def lock_held(directory):
    try:
        with (directory / "watch.lock").open("r") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(lock, fcntl.LOCK_UN)
            return False
    except FileNotFoundError:
        return False
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("once", "watch", "status", "stop"):
        modes.add_argument("--" + mode, action="store_true")
    parser.add_argument("--config", type=Path, default=ROOT / "mac-sync/config.json")
    parser.add_argument("--interval", type=float, default=300)
    parser.add_argument("--cycle-timeout", type=float, default=120)
    args = parser.parse_args()
    directory, script = ROOT / "mac-sync", Path(__file__).resolve()
    pid_file = directory / "watch.pid"
    try:
        if args.status or args.stop:
            pid = process_matches(pid_file, script)
            held = lock_held(directory)
            record = read_json(pid_file, {})
            recorded_pid = record.get("pid")
            if type(recorded_pid) is not int or recorded_pid <= 1 or record.get("script") != str(script):
                recorded_pid = None
            unverified_stop = args.stop and pid is None and held is not False
            if args.stop and pid:
                os.kill(pid, signal.SIGTERM)
            state = read_json(directory / "watch-state.json", {})
            watcher = Watcher(ROOT, directory, {})
            print(json.dumps({"pid": pid or recorded_pid,
                "running": True if pid else (False if held is False else None), "lock_held": held,
                "process_visibility": "verified" if pid else ("unverified" if recorded_pid else "no_pid_record"),
                "stop_requested": bool(args.stop and pid),
                "error": "ProcessIdentityUnverified" if unverified_stop else None,
                "last_success": state.get("last_success"), "last_attempt": state.get("last_attempt"),
                "last_error": state.get("last_error"), "new_count": state.get("new_count", 0),
                "pending_count": len(watcher.pending(state))}))
            return 1 if unverified_stop else 0
        if not 1 <= args.interval or not 1 <= args.cycle_timeout <= 120:
            parser.error("Interval must be at least 1 second; cycle timeout must be 1 to 120 seconds")
        watcher = Watcher(ROOT, directory, configuration(args.config, ROOT))
        def stop(*_):
            raise StopRequested()
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        with exclusive(directory):
            try:
                if args.watch:
                    save_json(pid_file, {"pid": os.getpid(), "script": str(script), "started_at": now()})
                while True:
                    start = time.monotonic()
                    success = watcher.cycle(timeout=args.cycle_timeout)
                    print(json.dumps({"at": now(), "poll": "success" if success else "failed"}), flush=True)
                    if args.once:
                        return 0 if success else 1
                    time.sleep(max(0, args.interval - (time.monotonic() - start)))
            finally:
                if args.watch and read_json(pid_file, {}).get("pid") == os.getpid():
                    pid_file.unlink(missing_ok=True)
    except StopRequested:
        return 0
    except Exception as error:
        print(json.dumps({"error": type(error).__name__}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
