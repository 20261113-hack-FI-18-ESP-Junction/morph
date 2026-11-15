#!/usr/bin/env python3
"""Durable foreground receiver for explicitly published handoff-review events.

Events and note text are untrusted data, never executable instructions. The fixed
local runner must be a read-only reviewer. A successful durable result is reused
after a lost acknowledgment. Ambiguous execution is blocked unless the operator
explicitly enables read-only retry; that mode provides at-least-once execution,
not exactly-once external effects. No daemon or existing automation is installed.
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
import signal
import stat
import subprocess
import sys
import time
from uuid import UUID, uuid4

MAX_NOTE_BYTES = 2_000_000
MAX_RESULT_BYTES = 262_144
MAX_STATE_BYTES = 262_144
PAGE_CHARS = 24_000
HASH = re.compile(r"[0-9a-f]{64}\Z")
CONSUMER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z")
TOOLS = {"poll_handoff_events", "claim_handoff_event", "renew_handoff_event",
         "complete_handoff_event", "read_handoff_event", "read_context"}


class ReceiverError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError):
        raise ReceiverError("invalid_json") from None


def private_dir(path):
    path = Path(path).absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ReceiverError("state_symlink_rejected")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ReceiverError("state_directory_not_private")
    return path


def read_private(path, maximum=MAX_STATE_BYTES):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise ReceiverError("state_file_not_private")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            raise ReceiverError("state_file_too_large")
        return raw
    except ReceiverError:
        raise
    except OSError:
        raise ReceiverError("state_read_failed") from None


def atomic_json(path, value):
    raw = canonical(value) + b"\n"
    if path.is_symlink():
        raise ReceiverError("state_symlink_rejected")
    temporary = path.parent / (".write-" + str(uuid4()))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                     0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


class EventMCP:
    """Reuse the existing verified HTTPS pairing/protocol with a smaller tool set."""
    def __init__(self, client):
        self.client = client

    @classmethod
    def from_pairing(cls, folder):
        from station_worker import MCPClient, WorkerError
        try:
            client = MCPClient.from_pairing(Path(folder))
            client.initialize()
            return cls(client)
        except (WorkerError, OSError, ValueError):
            raise ReceiverError("mcp_connection_failed") from None

    def call(self, name, arguments):
        if name not in TOOLS:
            raise ReceiverError("mcp_tool_not_allowed")
        try:
            reply = self.client._request("tools/call", {"name": name, "arguments": arguments})
            if reply.get("isError") or not isinstance(reply.get("structuredContent"), dict):
                raise ReceiverError("mcp_tool_failed")
            return reply["structuredContent"]
        except ReceiverError:
            raise
        except Exception:
            # No remote error text, URL, headers or credentials reaches logs.
            raise ReceiverError("mcp_transport_failed") from None


def validate_event(event, target):
    try:
        if not isinstance(event, dict) or event["target"] != target:
            raise ValueError
        for key in ("event_id", "note_id"):
            if str(UUID(event[key])) != event[key]:
                raise ValueError
        if type(event["seq"]) is not int or event["seq"] < 1:
            raise ValueError
        if event["origin"] not in {"mac", "intel"} or event["origin"] == target:
            raise ValueError
        if event.get("kind") != "work":
            raise ValueError
        if event["note_path"] != "context/notes/" + event["note_id"] + ".json":
            raise ValueError
        if not isinstance(event["note_sha256"], str) or not HASH.fullmatch(event["note_sha256"]):
            raise ValueError
        if type(event["note_characters"]) is not int or not 1 <= event["note_characters"] <= MAX_NOTE_BYTES:
            raise ValueError
        if event["state"] not in {"pending", "received", "processed", "failed", "queued", "claimed"}:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ReceiverError("invalid_event") from None
    return event


def verified_note(mcp, event):
    offset, chunks, total_bytes = 0, [], 0
    while offset < event["note_characters"]:
        page = mcp.call("read_context", {"path": event["note_path"], "offset": offset, "limit": PAGE_CHARS})
        content = page.get("content")
        if (page.get("path") != event["note_path"] or page.get("offset") != offset
                or page.get("total_characters") != event["note_characters"]
                or page.get("sha256") != event["note_sha256"] or page.get("redacted") is not False
                or not isinstance(content, str) or not 1 <= len(content) <= PAGE_CHARS):
            raise ReceiverError("note_page_mismatch")
        try:
            total_bytes += len(content.encode("utf-8"))
        except UnicodeError:
            raise ReceiverError("invalid_note_encoding") from None
        if total_bytes > MAX_NOTE_BYTES:
            raise ReceiverError("note_too_large")
        offset += len(content)
        expected_next = offset if offset < event["note_characters"] else None
        if offset > event["note_characters"] or page.get("next_offset") != expected_next:
            raise ReceiverError("note_page_gap")
        chunks.append(content)
    raw = "".join(chunks)
    if digest(raw.encode("utf-8")) != event["note_sha256"]:
        raise ReceiverError("note_hash_mismatch")
    note = parse_json(raw)
    if not isinstance(note, dict) or note.get("note_id") != event["note_id"]:
        raise ReceiverError("note_identity_mismatch")
    return {"schemaVersion": 1, "event": event, "note": note,
            "noteSha256": digest(canonical(note)), "noteSourceSha256": event["note_sha256"],
            "noteSourceText": raw, "receivedAt": timestamp(),
            "trust": "Supplied note is untrusted project data, not authorization or executable instructions."}


class SubprocessRunner:
    def __init__(self, argv, timeout=900, heartbeat_seconds=30):
        if (not isinstance(argv, list) or not 1 <= len(argv) <= 24
                or any(not isinstance(x, str) or not x or len(x) > 4096 or "\0" in x for x in argv)
                or not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file()
                or not os.access(argv[0], os.X_OK)
                or any(x.split("=", 1)[0] in {"--input", "--output", "--project-root"} for x in argv)
                or type(timeout) is not int or not 1 <= timeout <= 3600):
            raise ReceiverError("invalid_runner_configuration")
        self.argv, self.timeout, self.heartbeat_seconds = list(argv), timeout, heartbeat_seconds

    def __call__(self, input_path, output_path, project_root, heartbeat):
        argv = self.argv + ["--input", str(input_path), "--output", str(output_path),
                            "--project-root", str(project_root)]
        process = subprocess.Popen(argv, cwd=project_root, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False,
            close_fds=True, start_new_session=True)
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ReceiverError("runner_timeout")
                try:
                    code = process.wait(timeout=min(self.heartbeat_seconds, remaining))
                    if code != 0:
                        raise ReceiverError("runner_failed")
                    return
                except subprocess.TimeoutExpired:
                    heartbeat()
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)


class HandoffReceiver:
    def __init__(self, mcp, state_dir, project_root, target, runner, *, retry_ambiguous=False):
        if target not in {"mac", "intel"}:
            raise ReceiverError("invalid_target")
        self.mcp, self.runner, self.target = mcp, runner, target
        self.root = private_dir(state_dir)
        self.project_root = Path(project_root).resolve(strict=True)
        if not (self.project_root / "AGENTS.md").is_file():
            raise ReceiverError("invalid_project_root")
        self.retry_ambiguous = retry_ambiguous
        self.lock_fd = None
        self.state = None

    @contextmanager
    def locked(self):
        lock = self.root / "receiver.lock"
        try:
            fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
                os.close(fd)
                raise ReceiverError("state_file_not_private")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise ReceiverError("receiver_already_running") from None
            self.lock_fd = fd
            path = self.root / "state.json"
            if path.exists() or path.is_symlink():
                state = parse_json(read_private(path))
                if (not isinstance(state, dict) or state.get("schemaVersion") != 1
                        or state.get("target") != self.target
                        or state.get("projectRoot") != str(self.project_root)
                        or not isinstance(state.get("consumerId"), str)
                        or not CONSUMER.fullmatch(state["consumerId"])
                        or type(state.get("cursor")) is not int or state["cursor"] < 0):
                    raise ReceiverError("invalid_receiver_state")
                self.state = state
            else:
                self.state = {"schemaVersion": 1, "target": self.target,
                    "projectRoot": str(self.project_root), "consumerId": "receiver-" + str(uuid4()),
                    "cursor": 0, "createdAt": timestamp()}
                self._save_state()
            yield self
        finally:
            if self.lock_fd is not None:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None

    def _save_state(self):
        atomic_json(self.root / "state.json", self.state)

    def _call(self, name, **arguments):
        return self.mcp.call(name, {"target": self.target, **arguments})

    def _event_dir(self, event):
        return private_dir(private_dir(self.root / "events") / event["event_id"])

    def _result(self, directory, local, event):
        run_name = local.get("runDirectory", "")
        if not re.fullmatch(r"run-[0-9]{1,8}", run_name):
            raise ReceiverError("invalid_local_event_state")
        run_dir = private_dir(directory / run_name)
        envelope = parse_json(read_private(run_dir / "input.json", 4 * MAX_NOTE_BYTES + 65536))
        if (not isinstance(envelope, dict) or envelope.get("event", {}).get("event_id") != event["event_id"]
                or envelope.get("noteSourceSha256") != event["note_sha256"]):
            raise ReceiverError("local_event_identity_mismatch")
        path = run_dir / "result.json"
        raw = read_private(path, MAX_RESULT_BYTES)
        result_hash = digest(raw)
        if local.get("resultSha256") is not None and local["resultSha256"] != result_hash:
            raise ReceiverError("durable_result_corrupt")
        result = parse_json(raw)
        if (not isinstance(result, dict) or result.get("schemaVersion") != 1 or result.get("runnerStatus") != "processed"
                or result.get("sourceNoteId") != event["note_id"]
                or result.get("sourceNoteSha256") != envelope.get("noteSha256")
                or result.get("sourceNoteSourceSha256", event["note_sha256"]) != event["note_sha256"]):
            raise ReceiverError("invalid_runner_result")
        # Result reaches durable storage before the server receives completion.
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return result_hash

    def _complete(self, event, outcome, result_hash, error_code=""):
        saved = self._call("complete_handoff_event", consumer_id=self.state["consumerId"],
            event_id=event["event_id"], claim_id=event["claim_id"], outcome=outcome,
            result_sha256=result_hash, error_code=error_code)
        value = saved.get("event", {})
        if (value.get("event_id") != event["event_id"] or value.get("state") != outcome
                or value.get("result_sha256") != result_hash or value.get("target") != self.target
                or value.get("consumer_id") != self.state["consumerId"]
                or value.get("claim_id") != event["claim_id"]):
            raise ReceiverError("completion_readback_mismatch")

    def _process(self, incoming):
        event = validate_event(incoming, self.target)
        directory = self._event_dir(event)
        local_path = directory / "state.json"
        local = parse_json(read_private(local_path)) if local_path.exists() else {}
        if not isinstance(local, dict):
            raise ReceiverError("invalid_local_event_state")
        if event["state"] == "processed":
            # Another consumer may have completed this event. Record the server's
            # state without asserting that this machine executed its runner.
            local.update(status="acknowledged", acknowledgedAt=timestamp(), serverResultSha256=event.get("result_sha256"))
            atomic_json(local_path, local)
            return "processed"
        claim = self._call("claim_handoff_event", consumer_id=self.state["consumerId"],
                           event_id=event["event_id"], lease_seconds=300)
        if claim.get("claimed") is not True:
            return "backoff" if claim.get("reason") == "retry_backoff" else "blocked"
        claimed = validate_event(claim.get("event"), self.target)
        for key in ("event_id", "seq", "note_id", "note_sha256", "note_characters"):
            if claimed[key] != event[key]:
                raise ReceiverError("claim_identity_mismatch")
        try:
            UUID(claimed["claim_id"])
            if claimed["consumer_id"] != self.state["consumerId"]:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ReceiverError("invalid_claim") from None
        event = claimed
        if local.get("status") in {"running", "processed_pending_ack", "acknowledged"}:
            try:
                result_hash = self._result(directory, local, event)
            except ReceiverError:
                if local.get("status") in {"processed_pending_ack", "acknowledged"}:
                    raise ReceiverError("durable_result_corrupt") from None
                if not self.retry_ambiguous:
                    return "ambiguous"
            else:
                local.update(status="processed_pending_ack", resultSha256=result_hash)
                atomic_json(local_path, local)
                self._complete(event, "processed", result_hash)
                local.update(status="acknowledged", acknowledgedAt=timestamp())
                atomic_json(local_path, local)
                return "processed"
        try:
            envelope = verified_note(self.mcp, event)
            previous_number = local.get("runNumber", 0)
            if type(previous_number) is not int or not 0 <= previous_number < 99_999_999:
                raise ReceiverError("invalid_local_event_state")
            number = previous_number + 1
            # A crash after durable input but before its state receipt leaves an
            # orphan directory. Preserve it and allocate a new run, never wedge
            # retry on the same name or overwrite the original evidence.
            while (directory / ("run-" + str(number))).exists():
                number += 1
                if number > 99_999_999:
                    raise ReceiverError("run_limit_reached")
            run_dir = private_dir(directory / ("run-" + str(number)))
            if (run_dir / "input.json").exists() or (run_dir / "result.json").exists():
                raise ReceiverError("run_directory_collision")
            atomic_json(run_dir / "input.json", envelope)
            local = {"eventId": event["event_id"], "noteSha256": event["note_sha256"],
                "status": "received", "receivedAt": timestamp(), "runNumber": number,
                "runDirectory": run_dir.name, "claimId": event["claim_id"]}
            atomic_json(local_path, local)
            local.update(status="running", startedAt=timestamp())
            atomic_json(local_path, local)
            def heartbeat():
                reply = self._call("renew_handoff_event", consumer_id=self.state["consumerId"],
                    event_id=event["event_id"], claim_id=event["claim_id"], lease_seconds=300)
                if reply.get("renewed") is not True or reply.get("event", {}).get("claim_id") != event["claim_id"]:
                    raise ReceiverError("lease_renewal_failed")
            self.runner(run_dir / "input.json", run_dir / "result.json", self.project_root, heartbeat)
            result_hash = self._result(directory, local, event)
        except (ReceiverError, OSError, ValueError, TypeError) as error:
            code = error.code if isinstance(error, ReceiverError) else "runner_or_state_failed"
            # A process can finish durably just as lease renewal or exit-status
            # observation fails. Preserve a valid successful output in that case
            # instead of scheduling an unnecessary second execution.
            if local.get("status") == "running":
                try:
                    result_hash = self._result(directory, local, event)
                except ReceiverError:
                    pass
                else:
                    local.update(status="processed_pending_ack", resultSha256=result_hash,
                                 processedAt=timestamp())
                    atomic_json(local_path, local)
                    self._complete(event, "processed", result_hash)
                    local.update(status="acknowledged", acknowledgedAt=timestamp())
                    atomic_json(local_path, local)
                    return "processed"
            # Preserve any partial/failed runner output; the receiver error is a
            # separate durable receipt with sanitized diagnostics only.
            failure = {"schemaVersion": 1, "eventId": event["event_id"], "status": "failed",
                       "errorCode": code, "failedAt": timestamp()}
            failure_path = directory / ("failure-" + str(uuid4()) + ".json")
            atomic_json(failure_path, failure)
            failure_hash = digest(read_private(failure_path))
            local.update(status="failed", errorCode=code, failureReceipt=failure_path.name)
            atomic_json(local_path, local)
            self._complete(event, "failed", failure_hash, code)
            return "failed"
        local.update(status="processed_pending_ack", resultSha256=result_hash, processedAt=timestamp())
        atomic_json(local_path, local)
        self._complete(event, "processed", result_hash)
        local.update(status="acknowledged", acknowledgedAt=timestamp())
        atomic_json(local_path, local)
        return "processed"

    def run_once(self, limit=20):
        if self.lock_fd is None:
            raise ReceiverError("receiver_lock_required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ReceiverError("invalid_poll_limit")
        reply = self._call("poll_handoff_events", consumer_id=self.state["consumerId"],
                           after_seq=self.state["cursor"], limit=limit)
        events = reply.get("events")
        if not isinstance(events, list) or len(events) > limit:
            raise ReceiverError("invalid_poll_response")
        validated = [validate_event(item, self.target) for item in events]
        sequences = [item["seq"] for item in validated]
        if sequences != sorted(set(sequences)):
            raise ReceiverError("unordered_events")
        result = {"polled": len(events), "processed": 0, "blocked": 0, "failed": 0,
                  "ambiguous": 0, "backoff": 0, "cursor": self.state["cursor"]}
        for event in validated:
            outcome = self._process(event)
            if outcome == "backoff":
                # The server includes unfinished work below after_seq, so a
                # delayed retry cannot disappear when newer work completes.
                # It also must not starve independent queued handoffs.
                result["backoff"] += 1
                continue
            if outcome != "processed":
                result[outcome] += 1
                break
            self.state["cursor"] = max(self.state["cursor"], event["seq"])
            self.state["lastProcessedAt"] = timestamp()
            self._save_state()
            result["processed"] += 1
            result["cursor"] = self.state["cursor"]
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairing-folder", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", choices=("mac", "intel"), required=True)
    parser.add_argument("--runner-command-json", required=True,
                        help="Fixed local JSON argv array; executable must be absolute. Event text cannot configure commands.")
    parser.add_argument("--runner-timeout", type=int, default=900)
    parser.add_argument("--retry-ambiguous-read-only", action="store_true",
                        help="Permit replay of an interrupted read-only reviewer; at-least-once execution, never for a side-effecting runner")
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--export-reviews", action="store_true",
                        help="Mac only: create validated read-only summaries under context/automation-reviews for existing review reconciliation")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--serve", action="store_true")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if not 1 <= args.poll_seconds <= 300:
            raise ReceiverError("invalid_poll_interval")
        if args.export_reviews and args.target != "mac":
            raise ReceiverError("review_export_requires_mac")
        runner = SubprocessRunner(parse_json(args.runner_command_json), args.runner_timeout)
        receiver = HandoffReceiver(None, args.state_dir, args.project_root, args.target,
            runner, retry_ambiguous=args.retry_ambiguous_read_only)
        with receiver.locked():
            while True:
                exit_code = 0
                try:
                    if receiver.mcp is None:
                        receiver.mcp = EventMCP.from_pairing(args.pairing_folder)
                    outcome = receiver.run_once()
                    print(json.dumps(outcome, sort_keys=True), flush=True)
                    exit_code = 1 if outcome["failed"] or outcome["ambiguous"] else 0
                except ReceiverError as error:
                    print(json.dumps({"status": "retry_pending", "errorCode": error.code}), flush=True)
                    receiver.mcp = None
                    exit_code = 1
                if args.export_reviews:
                    try:
                        from handoff_review_export import export_reviews
                        exported = export_reviews(receiver.root, receiver.project_root)
                        print(json.dumps({"reviewExports": exported}, sort_keys=True), flush=True)
                        if exported["failed"]:
                            exit_code = 1
                    except (ReceiverError, OSError, ValueError) as error:
                        code = error.code if isinstance(error, ReceiverError) else "review_export_failed"
                        print(json.dumps({"reviewExports": "retry_pending", "errorCode": code}), flush=True)
                        exit_code = 1
                if args.once:
                    return exit_code
                time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 130
    except (ReceiverError, OSError, ValueError) as error:
        code = error.code if isinstance(error, ReceiverError) else "receiver_configuration_failed"
        print(json.dumps({"status": "failed", "errorCode": code}), flush=True)
        return 1


if __name__ == "__main__":
    # The optional exporter imports these helpers. Keep one exception/type
    # identity when this receiver is launched as a script rather than a module.
    sys.modules.setdefault("handoff_receiver", sys.modules[__name__])
    raise SystemExit(main())
