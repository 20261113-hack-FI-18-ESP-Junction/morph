#!/usr/bin/env python3
"""Foreground Intel worker for bounded station data over the Mac MCP.

Reads are the default. --allow-record-writes additionally accepts explicit
audited reviews and evidence analysis; the latter can call Intel's configured
model. No robot, microphone or lifecycle routes are allowed. No daemon is
installed, and private pairing/token files are read but never modified.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import stat
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import uuid


MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_REQUEST_BODY = 65_536
MAX_CHUNK_CHARACTERS = 60_000
HTTP_TIMEOUT_SECONDS = 15
MCP_PROTOCOL = "2025-11-25"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z")
CONTENT_TYPES = frozenset({"application/json", "text/event-stream", "text/csv", "text/plain",
    "image/png", "image/jpeg", "image/webp", "application/octet-stream"})
CYCLE_QUERY = frozenset({"sessionId", "objectId", "outcome", "sourceMode", "includeSimulation",
    "hasRetry", "errorCode", "modelId", "referenceStatus", "startedAfter", "startedBefore", "offset", "limit"})
STATIC_QUERY = {
    "/api/v1/schema": frozenset(),
    "/api/v1/station/snapshot": frozenset({"sessionId"}),
    "/api/v1/dashboard": frozenset({"sessionId", "cycleId", "sourceMode", "limit"}),
    "/api/v1/sessions": frozenset(),
    "/api/v1/metrics": frozenset({"includeSimulation"}),
    "/api/v1/cycles": CYCLE_QUERY,
    "/api/v1/cameras": frozenset(),
    "/api/v1/events": frozenset({"after", "once", "limit"}),
    "/api/v1/analysis/context": frozenset({"kind", "sessionIds", "cycleId", "sourceMode",
        "comparisonSpecId", "baselineSessionId", "adaptiveSessionId"}),
    "/api/v1/analysis/reports": frozenset({"sessionId", "cycleId", "limit"}),
}


class WorkerError(ValueError):
    """Fixed non-secret error category. Never include raw remote error text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def aware_time(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise WorkerError("invalid_timestamp") from None


def safe_id(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise WorkerError("invalid_identifier")
    return value


def token_value(value: Any) -> str:
    if not isinstance(value, str) or not 32 <= len(value) <= 8192 or not value.isascii() or any(
            char.isspace() or ord(char) < 33 or ord(char) == 127 for char in value):
        raise WorkerError("invalid_token_configuration")
    return value


def private_text(path: Path, max_bytes: int = 16_384) -> str:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > max_bytes:
            raise WorkerError("private_file_permissions")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise WorkerError("private_file_owner")
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise WorkerError("private_file_unavailable") from None


def checked_url(value: Any, *, mcp: bool = False) -> str:
    try:
        if not isinstance(value, str) or len(value) > 2048 or any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError
        parts = urllib.parse.urlsplit(value)
        if parts.scheme not in ({"https"} if mcp else {"http", "https"}) or not parts.hostname:
            raise ValueError
        if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
            raise ValueError
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError
        if parts.path not in ({"/mcp"} if mcp else {"", "/"}):
            raise ValueError
        if "\\" in value or "%" in parts.netloc:
            raise ValueError
        return value if mcp else value.rstrip("/")
    except (TypeError, ValueError):
        raise WorkerError("invalid_endpoint_configuration") from None


def validated_read(path: Any, query: Any) -> tuple[str, dict]:
    """Independent route allowlist; remote requests cannot change the host/method."""
    if not isinstance(path, str) or len(path) > 512 or any(char in path for char in "%?#\\"):
        raise WorkerError("read_path_not_allowed")
    allowed = STATIC_QUERY.get(path)
    if allowed is None:
        parts = path.split("/")
        if len(parts) == 6 and parts[:4] == ["", "api", "v1", "sessions"] and SAFE_ID.fullmatch(parts[4]):
            allowed = {"metrics": frozenset({"includeSimulation"}), "export": frozenset({"format"})}.get(parts[5])
        elif len(parts) == 5 and parts[:3] == ["", "api", "v1"] and parts[3] in {"cycles", "evidence"} and SAFE_ID.fullmatch(parts[4]):
            allowed = frozenset()
        elif len(parts) == 6 and parts[:5] == ["", "api", "v1", "analysis", "reports"] and SAFE_ID.fullmatch(parts[5]):
            allowed = frozenset()
    if allowed is None:
        raise WorkerError("read_path_not_allowed")
    if not isinstance(query, dict) or len(query) > 20 or any(not isinstance(key, str) or key not in allowed for key in query):
        raise WorkerError("read_query_not_allowed")
    normalized = {}
    for key, value in query.items():
        if key == "sessionIds":
            values = value if isinstance(value, list) else [value]
            if not 1 <= len(values) <= 2:
                raise WorkerError("invalid_query_value")
            normalized[key] = [safe_id(item) for item in values]
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, int):
            value = str(value)
        if not isinstance(value, str) or len(value) > 2048 or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise WorkerError("invalid_query_value")
        if key in {"limit", "offset", "after"}:
            if not re.fullmatch(r"\d{1,16}", value) or (key == "limit" and int(value) == 0):
                raise WorkerError("invalid_query_value")
            if key == "limit" and int(value) > 1000:
                raise WorkerError("invalid_query_value")
        if key in {"includeSimulation", "hasRetry", "once"} and value not in {"true", "false"}:
            raise WorkerError("invalid_query_value")
        if key == "format" and value not in {"json", "csv"}:
            raise WorkerError("invalid_query_value")
        normalized[key] = value
    if path == "/api/v1/dashboard":
        for key in {"sessionId", "cycleId"} & normalized.keys():
            safe_id(normalized[key])
        if "sourceMode" in normalized and normalized["sourceMode"] not in {"live", "simulation"}:
            raise WorkerError("invalid_query_value")
        if int(normalized.get("limit", "20")) > 100:
            raise WorkerError("invalid_query_value")
    if path == "/api/v1/events":
        normalized["once"] = "true"
        normalized["limit"] = str(min(int(normalized.get("limit", "100")), 500))
    return path, normalized


def validated_request(method, path, query, body=None, intent=None):
    """Validate forged claims independently of the Mac queue."""
    if method == "GET":
        if body is not None or intent is not None:
            raise WorkerError("invalid_read_body")
        path, query = validated_read(path, query)
        return path, query, None, None
    if method != "POST" or not isinstance(query, dict) or query or not isinstance(path, str):
        raise WorkerError("write_path_not_allowed")
    if path == "/api/v1/analysis/reports":
        expected, ids = "evidence-analysis", ("requestId",)
    else:
        match = re.fullmatch(r"/api/v1/cycles/([^/]+)/review", path)
        if not match:
            raise WorkerError("write_path_not_allowed")
        safe_id(match[1])
        expected, ids = "record-review", ("id", "eventId")
    if intent != expected:
        raise WorkerError("explicit_write_intent_required")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError
            value[key] = item
        return value
    def invalid_constant(_):
        raise ValueError
    try:
        if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_REQUEST_BODY:
            raise ValueError
        parsed = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid_constant)
        if not isinstance(parsed, dict):
            raise ValueError
        for key in ids:
            safe_id(parsed.get(key))
    except (ValueError, UnicodeError, RecursionError):
        raise WorkerError("invalid_write_body") from None
    return path, {}, body, intent


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise WorkerError("redirect_rejected")


def bounded_read(response, max_bytes: int, deadline: float) -> bytes:
    chunks = []
    size = 0
    reader = getattr(response, "read1", response.read)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WorkerError("response_timeout")
        # HTTPResponse.read1 performs one underlying read. Apply the remaining
        # total budget to the socket when urllib exposes it.
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            sock.settimeout(remaining)
        chunk = reader(min(65_536, max_bytes + 1 - size))
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if size > max_bytes:
            raise WorkerError("response_too_large")
        chunks.append(chunk)


@dataclass(frozen=True)
class ReadResult:
    status_code: int
    content_type: str
    body: bytes
    captured_at: str


def error_result(code: str, status: int = 502) -> ReadResult:
    return ReadResult(status, "application/json", json.dumps({"error": code}, separators=(",", ":")).encode(), timestamp())


class StationHTTP:
    def __init__(self, base_url: str, token: str, *, opener=None):
        self.base_url = checked_url(base_url)
        self.token = token_value(token)
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def read(self, path: str, query: dict) -> ReadResult:
        return self.request("GET", path, query)

    def request(self, method, path, query, body=None, intent=None) -> ReadResult:
        attempted = False
        try:
            path, query, body, intent = validated_request(method, path, query, body, intent)
            url = self.base_url + path
            if query:
                url += "?" + urllib.parse.urlencode(query, doseq=True)
            headers = {
                "Authorization": "Bearer " + self.token,
                "Accept": "application/json, text/event-stream, text/csv, text/plain, image/png, image/jpeg, image/webp, application/octet-stream",
                "Accept-Encoding": "identity"}
            if method == "POST":
                headers.update({"Content-Type": "application/json", "X-Morph-Intent": intent})
            request = urllib.request.Request(url, method=method,
                data=body.encode("utf-8") if body is not None else None, headers=headers)
            deadline = time.monotonic() + HTTP_TIMEOUT_SECONDS
            try:
                attempted = True
                response = self.opener.open(request, timeout=HTTP_TIMEOUT_SECONDS)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status_code = response.status if hasattr(response, "status") else response.code
                if 300 <= status_code < 400:
                    raise WorkerError("redirect_rejected")
                if not 200 <= status_code <= 599:
                    raise WorkerError("invalid_http_status")
                content_type = response.headers.get("Content-Type", "application/octet-stream")
                if len(content_type) > 150 or any(ord(char) < 32 or ord(char) == 127 for char in content_type) or content_type.split(";", 1)[0].strip().lower() not in CONTENT_TYPES:
                    raise WorkerError("unsupported_content_type")
                body = bounded_read(response, MAX_BODY_BYTES, deadline)
                return ReadResult(status_code, content_type, body, timestamp())
        except WorkerError as error:
            return error_result("station_write_outcome_unknown" if method == "POST" and attempted else error.code)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            return error_result("station_write_outcome_unknown" if method == "POST" and attempted else "station_transport_error")


class MCPClient:
    def __init__(self, url: str, token: str, *, opener):
        self.url = checked_url(url, mcp=True)
        self.headers = {"Authorization": "Bearer " + token_value(token), "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"}
        self.opener = opener
        self.next_id = 1

    @classmethod
    def from_pairing(cls, folder: Path):
        try:
            connection = json.loads(private_text(folder / "connection.json"))
            if not isinstance(connection, dict):
                raise WorkerError("invalid_pairing_configuration")
            if connection.get("expires_at") and aware_time(connection["expires_at"]) <= datetime.now(timezone.utc):
                raise WorkerError("pairing_expired")
            tls = ssl.create_default_context(cafile=str(folder / "morph-ca.pem"))
            opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=tls))
            return cls(connection["url"], connection["token"], opener=opener)
        except WorkerError:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise WorkerError("invalid_pairing_configuration") from None

    def _request(self, method: str, params: dict | None = None, *, notification=False) -> dict:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        expected_id = None
        if not notification:
            expected_id = self.next_id
            payload["id"] = expected_id
            self.next_id += 1
        if params is not None:
            payload["params"] = params
        try:
            request = urllib.request.Request(self.url, method="POST", data=json.dumps(payload, separators=(",", ":"), allow_nan=False).encode(), headers=self.headers)
            deadline = time.monotonic() + HTTP_TIMEOUT_SECONDS
            with self.opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                if not 200 <= response.status < 300:
                    raise WorkerError("mcp_http_error")
                raw = bounded_read(response, 1_000_000, deadline)
                session = response.headers.get("Mcp-Session-Id")
                if session:
                    if len(session) > 256 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", session):
                        raise WorkerError("mcp_invalid_session")
                    self.headers["Mcp-Session-Id"] = session
            if notification:
                return {}
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("jsonrpc") != "2.0" or result.get("id") != expected_id or "error" in result:
                raise WorkerError("mcp_rpc_error")
            value = result.get("result")
            if not isinstance(value, dict):
                raise WorkerError("mcp_invalid_response")
            return value
        except WorkerError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError, ValueError, TypeError):
            raise WorkerError("mcp_transport_error") from None

    def initialize(self) -> None:
        result = self._request("initialize", {"protocolVersion": MCP_PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "morph-intel-station-read-worker", "version": "1.0"}})
        protocol = result.get("protocolVersion")
        if protocol != MCP_PROTOCOL:
            raise WorkerError("mcp_protocol_mismatch")
        self.headers["MCP-Protocol-Version"] = protocol
        self._request("notifications/initialized", notification=True)

    def call(self, name: str, arguments: dict) -> dict:
        if name not in {"claim_station_reads", "claim_station_requests", "submit_station_read_chunk"}:
            raise WorkerError("mcp_tool_not_allowed")
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise WorkerError("mcp_tool_error")
        value = result.get("structuredContent")
        if not isinstance(value, dict):
            raise WorkerError("mcp_missing_structured_result")
        return value


class StationWorker:
    def __init__(self, mcp, station, *, station_id="intel-main", worker_id=None, clock=None, allow_writes=False):
        self.mcp, self.station = mcp, station
        self.station_id = safe_id(station_id)
        self.worker_id = safe_id(worker_id or "intel-worker-" + str(uuid.uuid4()))
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if type(allow_writes) is not bool:
            raise WorkerError("invalid_worker_configuration")
        self.allow_writes = allow_writes

    def _active(self, request: dict) -> bool:
        return aware_time(request["expires_at"]) > self.clock()

    def run_once(self, limit: int = 1) -> dict:
        if type(limit) is not int or not 1 <= limit <= 8:
            raise WorkerError("invalid_claim_limit")
        arguments = {"station_id": self.station_id, "worker_id": self.worker_id, "limit": limit}
        if self.allow_writes:
            arguments["supports_writes"] = True
        result = self.mcp.call("claim_station_requests" if self.allow_writes else "claim_station_reads", arguments)
        requests = result.get("requests")
        if not isinstance(requests, list) or len(requests) > limit:
            raise WorkerError("invalid_claim_response")
        summary = {"claimed": len(requests), "completed": 0, "expired": 0, "failed": 0}
        for request in requests:
            try:
                if not isinstance(request, dict):
                    raise WorkerError("invalid_claim_response")
                request_id = safe_id(request["request_id"])
                claim_id = str(uuid.UUID(request["claim_id"]))
                if not self._active(request):
                    summary["expired"] += 1
                    continue
                # The worker validates even when a fake/custom StationHTTP is
                # supplied. The station client independently validates again.
                try:
                    method = request.get("method", "GET")
                    if method != "GET" and not self.allow_writes:
                        raise WorkerError("worker_writes_disabled")
                    path, query, body, intent = validated_request(method, request["path"], request["query"],
                        request.get("body"), request.get("intent"))
                    response = self.station.read(path, query) if method == "GET" else self.station.request(method, path, query, body, intent)
                except WorkerError as error:
                    response = error_result(error.code)
                if len(response.body) > MAX_BODY_BYTES:
                    response = error_result("response_too_large")
                encoded = base64.b64encode(response.body).decode("ascii")
                chunks = [encoded[index:index + MAX_CHUNK_CHARACTERS] for index in range(0, len(encoded), MAX_CHUNK_CHARACTERS)] or [""]
                digest = hashlib.sha256(response.body).hexdigest()
                metadata = {"station_id": self.station_id, "request_id": request_id,
                    "worker_id": self.worker_id, "claim_id": claim_id,
                    "part_count": len(chunks), "status_code": response.status_code,
                    "content_type": response.content_type, "response_sha256": digest,
                    "captured_at": response.captured_at}
                completed = False
                for index, chunk in enumerate(chunks):
                    if not self._active(request):
                        summary["expired"] += 1
                        break
                    arguments = {**metadata, "part_index": index, "body_base64": chunk}
                    try:
                        saved = self.mcp.call("submit_station_read_chunk", arguments)
                    except WorkerError as error:
                        # A lost reply must not trigger a second station read.
                        # The server accepts the same chunk/claim idempotently.
                        if error.code not in {"mcp_transport_error", "response_timeout"} or not self._active(request):
                            raise
                        saved = self.mcp.call("submit_station_read_chunk", arguments)
                    if saved.get("state") not in {"claimed", "ready"}:
                        raise WorkerError("invalid_submit_response")
                    if index == len(chunks) - 1:
                        if saved["state"] != "ready":
                            raise WorkerError("incomplete_submit_response")
                        completed = True
                if completed:
                    summary["completed"] += 1
            except (WorkerError, KeyError, ValueError, TypeError):
                summary["failed"] += 1
        return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairing-folder", type=Path, default=os.environ.get("MORPH_PAIRING_FOLDER"), help="Existing private folder containing connection.json and morph-ca.pem")
    parser.add_argument("--station-url", default=os.environ.get("MORPH_STATION_URL", "http://127.0.0.1:8000"), help="Fixed trusted records API origin; defaults to Intel loopback")
    parser.add_argument("--token-file", type=Path, default=os.environ.get("MORPH_TOKEN_FILE"), help="Existing private station token file; MORPH_API_TOKEN takes precedence")
    parser.add_argument("--station-id", default="intel-main")
    parser.add_argument("--allow-record-writes", action="store_true", help="Opt into explicit audited review and evidence-analysis POSTs; analysis may invoke Intel's configured provider")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Serve one bounded claim round and exit")
    mode.add_argument("--serve", action="store_true", help="Poll in this foreground process; Ctrl-C stops it")
    parser.add_argument("--limit", type=int, default=1, help="Claims per round, 1–8; one avoids aging queued leases during sequential reads")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        if not args.pairing_folder or not 0.25 <= args.poll_seconds <= 60 or not 1 <= args.limit <= 8:
            raise WorkerError("invalid_worker_configuration")
        token = os.environ.get("MORPH_API_TOKEN")
        if not token and args.token_file:
            token = private_text(Path(args.token_file)).strip()
        station = StationHTTP(args.station_url, token_value(token))
        mcp = MCPClient.from_pairing(Path(args.pairing_folder))
        mcp.initialize()
        worker = StationWorker(mcp, station, station_id=args.station_id, allow_writes=args.allow_record_writes)
        while True:
            try:
                summary = worker.run_once(args.limit)
                if args.once or summary["claimed"]:
                    print(json.dumps({"checked_at": timestamp(), **summary}), flush=True)
                if args.once:
                    return 0 if summary["failed"] == 0 and summary["expired"] == 0 else 2
            except WorkerError as error:
                print(json.dumps({"checked_at": timestamp(), "error": error.code}), flush=True)
                if args.once:
                    return 2
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        return 0
    except WorkerError as error:
        print(json.dumps({"error": error.code}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
