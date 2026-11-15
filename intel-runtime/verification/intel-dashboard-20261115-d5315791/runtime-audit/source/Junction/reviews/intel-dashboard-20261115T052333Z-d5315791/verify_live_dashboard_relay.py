"""Bounded real GET relay checks. Prepared only; explicit --run is required.

Root must confirm the updated main API is ready before execution. This script
never writes station records, seeds data, invokes providers or controls devices.
Intel-initiated MCP checks are distinct from Klemen dashboard UI acceptance.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

ROOT = Path("/home/intel/Documents/Junction")
REVIEW = Path(__file__).resolve().parent
PROJECT = ROOT / "morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction"
CLIENT_SOURCE = PROJECT / "context/verification/intel-continuation/sync_shared_context.py"
TOKEN_PATH = PROJECT / "station/.data/api-token"
EVIDENCE_DIRECTORY = PROJECT / "station/.data/evidence"
ORIGIN = "http://127.0.0.1:8000"
STATION = "intel-main"
MAX_BODY = 4 * 1024 * 1024
MAX_BASE64 = 4 * ((MAX_BODY + 2) // 3)
CASE_SECONDS = 25.0
CAPABILITY = {"version": 1, "path": "/api/v1/dashboard", "maxResponseBytes": 4194303,
              "sessionLimit": 50, "defaultCycleLimit": 20, "maxCycleLimit": 100}
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z")
sys.dont_write_bytecode = True


class CheckFailure(Exception):
    pass


def require(value, code):
    if not value:
        raise CheckFailure(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value, *, binary=False):
    raw = value if binary else (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def aware(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "response_timestamp_missing_timezone")
    return parsed


def semantic(value):
    # Only generation timestamps are volatile. Preserve record timestamps,
    # event cursor, all IDs, metrics, model output and every other field.
    clone = json.loads(json.dumps(value))
    if isinstance(clone, dict):
        clone.pop("generatedAt", None)
        if isinstance(clone.get("snapshot"), dict):
            clone["snapshot"].pop("generatedAt", None)
    return clone


def image_candidates(detail):
    analyzed_ids = {ident for item in detail["inspections"] for ident in item["frameIds"]}
    evidences = {item["id"]: item for item in detail["evidence"]}
    candidates = [(frame, evidences.get(frame["evidenceId"])) for frame in detail["frames"]
                  if frame["id"] in analyzed_ids]
    return sorted(((frame, evidence) for frame, evidence in candidates
                   if evidence and evidence["mediaType"] in {"image/png", "image/jpeg"}),
                  key=lambda pair: pair[0]["id"])


def discovered_cycle_ids(aggregate, session_id):
    detail = aggregate["detail"]
    require(isinstance(detail, dict), "saved_cycle_detail_unavailable")
    recent = aggregate["recentCycles"]
    require(recent["offset"] == 0 and recent["limit"] == CAPABILITY["defaultCycleLimit"]
            and len(recent["items"]) <= CAPABILITY["defaultCycleLimit"], "cycle_discovery_page_unbounded")
    records = [detail["cycle"], *recent["items"]]
    identifiers = []
    for cycle in records:
        require(isinstance(cycle["id"], str) and SAFE_ID.fullmatch(cycle["id"])
                and cycle["sessionId"] == session_id, "saved_cycle_scope_mismatch")
        if cycle["id"] not in identifiers:
            identifiers.append(cycle["id"])
    return identifiers


def allowed_route(path, query):
    require(isinstance(query, dict) and all(isinstance(v, str) for v in query.values()), "query_type_rejected")
    if path == "/api/v1/schema":
        require(not query, "schema_query_rejected")
    elif path == "/api/v1/dashboard":
        require(not set(query) - {"sourceMode", "sessionId", "cycleId", "limit"}, "dashboard_query_rejected")
        require(query.get("sourceMode", "live") in {"live", "simulation"}, "source_mode_rejected")
        require(1 <= int(query.get("limit", "20")) <= 100, "cycle_limit_rejected")
        for name in ("sessionId", "cycleId"):
            require(name not in query or SAFE_ID.fullmatch(query[name]), "record_id_rejected")
    elif path.startswith("/api/v1/evidence/"):
        require(not query and SAFE_ID.fullmatch(path.removeprefix("/api/v1/evidence/")), "evidence_route_rejected")
    else:
        raise CheckFailure("route_not_in_harness_get_allowlist")


def read_bounded(response, maximum, deadline):
    output = bytearray()
    reader = getattr(response, "read1", response.read)
    while True:
        remaining = deadline - time.monotonic()
        require(remaining > 0, "response_deadline_exceeded")
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            sock.settimeout(min(5.0, remaining))
        block = reader(min(65536, maximum + 1 - len(output)))
        if not block:
            return bytes(output)
        output.extend(block)
        require(len(output) <= maximum, "response_byte_limit_exceeded")


class BudgetedMCPOpener:
    """Bound the existing authenticated client's response read without changing TLS."""
    def __init__(self, opener):
        self.opener = opener
        self.deadline = time.monotonic() + CASE_SECONDS

    def open(self, request, timeout=20):
        payload = json.loads(request.data)
        if payload.get("method") == "tools/call":
            params = payload["params"]
            require(params["name"] in {"enqueue_station_read", "read_station_response"}, "mcp_action_rejected")
            args = params["arguments"]
            require(args["station_id"] == STATION, "station_identity_rejected")
            if params["name"] == "enqueue_station_read":
                allowed_route(args["path"], args.get("query", {}))
        else:
            require(payload.get("method") == "tools/list", "mcp_method_rejected")
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "mcp_case_deadline_exceeded")
        with self.opener.open(request, timeout=min(float(timeout), 5.0, remaining)) as response:
            raw = read_bounded(response, 256 * 1024, self.deadline)
        return io.BytesIO(raw)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise CheckFailure("direct_api_redirect_rejected")


class Harness:
    def __init__(self, run):
        self.run = run
        self.report = {"schemaVersion": 1, "requestId": "d5315791-6749-4b01-97b5-1b9357306487",
                       "sessionId": "d0dc73a7-df82-48e6-a8c1-8a4c23c144e6",
                       "author": "/root/adoption_codex", "executedBy": "/root", "startedAt": now(),
                       "initiator": "Intel active agent through existing shared Mac MCP", "cases": [],
                       "stationOrigin": ORIGIN, "stationId": STATION, "tokenSourcePath": str(TOKEN_PATH),
                       "applicationWrites": False, "providerCalls": False, "hardwareCalls": False,
                       "workerReconfigured": False, "klemenUiAcceptance": "not tested by this harness",
                       "clockNote": "Elapsed durations use Intel monotonic time. Server expiry/completion and station capture wall clocks are retained separately and are not subtracted to infer latency."}
        self.client = None
        self.token = None

    def initialize(self):
        info = TOKEN_PATH.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) & 0o077 == 0 and info.st_size <= 16384, "private_token_file_rejected")
        self.token = TOKEN_PATH.read_text().strip()
        require(32 <= len(self.token) <= 8192 and self.token.isascii()
                and not any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in self.token), "token_syntax_rejected")
        spec = importlib.util.spec_from_file_location("existing_shared_context", CLIENT_SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.client = module.Client()
        require(self.client.server_name == "morph-context", "unexpected_shared_server_identity")
        self.budget = BudgetedMCPOpener(self.client.opener)
        self.client.opener = self.budget
        catalog = self.client.request("tools/list")
        save(self.run / "tool-catalog.json", catalog)
        tools = {tool["name"]: tool for tool in catalog["tools"]}
        for name in ("enqueue_station_read", "read_station_response"):
            require(name in tools, "required_mcp_tool_absent")
            props = tools[name]["inputSchema"]["properties"]
            require({"station_id", "request_id"}.issubset(props), "mcp_schema_incompatible")
        require({"path", "query"}.issubset(tools["enqueue_station_read"]["inputSchema"]["properties"]), "enqueue_schema_incompatible")
        require({"offset", "limit"}.issubset(tools["read_station_response"]["inputSchema"]["properties"]), "response_schema_incompatible")
        self.report["sharedServer"] = self.client.server_name
        self.direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def direct(self, directory, path, query):
        allowed_route(path, query)
        url = ORIGIN + path + ("?" + urllib.parse.urlencode(query) if query else "")
        request = urllib.request.Request(url, method="GET", headers={"Authorization": "Bearer " + self.token,
                                         "Accept": "application/json, image/png, image/jpeg", "Accept-Encoding": "identity"})
        start = time.monotonic()
        try:
            response = self.direct_opener.open(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = read_bounded(response, MAX_BODY, start + 10)
            metadata = {"httpStatus": response.code, "contentType": response.headers.get("Content-Type"),
                        "cacheControl": response.headers.get("Cache-Control"), "bytes": len(raw),
                        "sha256": digest(raw), "elapsedMonotonicSeconds": time.monotonic() - start, "receivedAt": now()}
        save(directory / "direct-body.bin", raw, binary=True)
        save(directory / "direct-metadata.json", metadata)
        return metadata, raw

    def case(self, label, path, query, expected_status=200, *, image=False):
        allowed_route(path, query)
        directory = self.run / label
        directory.mkdir(mode=0o700)
        request_id = str(uuid4())
        entry = {"label": label, "requestId": request_id, "path": path, "query": query,
                 "expectedStatus": expected_status, "requestedAt": now(), "status": "started"}
        self.report["cases"].append(entry)
        save(directory / "request.json", entry)
        start = time.monotonic()
        self.budget.deadline = start + CASE_SECONDS
        try:
            queued = self.client.call("enqueue_station_read", station_id=STATION, request_id=request_id, path=path, query=query)
            save(directory / "enqueue.json", queued)
            require(queued["request_id"] == request_id and queued["state"] == "queued", "fresh_request_not_queued")
            expires = queued["expires_at"]
            aware(expires)
            offset, fragments, common, polls = 0, [], None, 0
            while True:
                require(time.monotonic() < self.budget.deadline and polls < 100, "relay_case_deadline_exceeded")
                page = self.client.call("read_station_response", station_id=STATION, request_id=request_id, offset=offset, limit=60000)
                save(directory / f"response-{polls:03d}.json", page)
                polls += 1
                require(page["request_id"] == request_id and page["expires_at"] == expires, "relay_identity_or_expiry_changed")
                require(page["state"] != "expired", "relay_response_expired")
                if page["state"] in {"queued", "claimed"}:
                    require(offset == 0 and common is None, "ready_response_regressed")
                    time.sleep(min(0.25, max(0, self.budget.deadline - time.monotonic())))
                    continue
                require(page["state"] == "ready", "unexpected_relay_state")
                metadata = {key: page[key] for key in ("request_id", "state", "expires_at", "captured_at", "completed_at", "content_type", "response_sha256", "status_code")}
                for key in ("captured_at", "completed_at"):
                    aware(metadata[key])
                require(re.fullmatch(r"[a-f0-9]{64}", metadata["response_sha256"]), "invalid_response_hash")
                if common is None:
                    common = metadata
                require(metadata == common and page["offset"] == offset, "relay_pagination_metadata_changed")
                text = page["body_base64"]
                require(isinstance(text, str) and len(text) <= 60000 and offset + len(text) <= MAX_BASE64, "relay_base64_bound_exceeded")
                fragments.append(text)
                following = page["next_offset"]
                if following is None:
                    break
                require(type(following) is int and following == offset + len(text) and following > offset, "relay_pagination_not_contiguous")
                offset = following
            raw = base64.b64decode("".join(fragments), validate=True)
            save(directory / "relay-body.bin", raw, binary=True)
            require(len(raw) <= MAX_BODY and digest(raw) == common["response_sha256"], "relay_body_hash_or_size_mismatch")
            require(common["status_code"] == expected_status, "unexpected_http_status")
            entry.update(relayMetadata=common, bytes=len(raw), responseSha256=digest(raw), responsePages=len(fragments),
                         polls=polls, receivedAt=now(), elapsedMonotonicSeconds=time.monotonic() - start)
            direct_metadata, direct_raw = self.direct(directory, path, query)
            require(direct_metadata["httpStatus"] == expected_status, "direct_status_mismatch")
            require(direct_metadata["contentType"].split(";", 1)[0] == common["content_type"].split(";", 1)[0], "direct_content_type_mismatch")
            if image:
                require(direct_raw == raw, "direct_image_bytes_mismatch")
                value = raw
            else:
                value = json.loads(raw)
                require(semantic(value) == semantic(json.loads(direct_raw)), "direct_semantic_response_mismatch")
                if path == "/api/v1/dashboard" and expected_status == 200:
                    require(len(raw) < MAX_BODY and direct_metadata["cacheControl"] == "private, no-store", "dashboard_bound_or_cache_contract")
            entry.update(status="passed", directComparison="exact bytes" if image else "JSON equality excluding only dashboard generation timestamps",
                         directMetadata=direct_metadata)
            save(directory / "result.json", entry)
            return value
        except Exception as error:
            entry.update(status="failed", errorCode=str(error) if isinstance(error, CheckFailure) else type(error).__name__,
                         elapsedMonotonicSeconds=time.monotonic() - start, failedAt=now())
            save(directory / "failure.json", entry)
            raise

    def execute(self):
        self.initialize()
        schema = self.case("01-schema", "/api/v1/schema", {})
        require(schema.get("capabilities", {}).get("dashboardRead") == CAPABILITY
                and "Dashboard" in schema.get("responses", {}), "dashboard_capability_missing_or_incompatible")
        live = self.case("02-dashboard-live", "/api/v1/dashboard", {"sourceMode": "live"})
        require(live["sourceMode"] == "live" and live["selectedSessionId"] is None
                and live["sessions"]["total"] == 0 and live["recentCycles"]["total"] == 0
                and live["detail"] is None and live["currentDetail"] is None, "live_view_not_expected_empty_baseline")
        simulation = self.case("03-dashboard-simulation", "/api/v1/dashboard", {"sourceMode": "simulation"})
        session_id = simulation["selectedSessionId"]
        require(isinstance(session_id, str) and SAFE_ID.fullmatch(session_id), "saved_simulation_session_unavailable")
        require(simulation["snapshot"]["session"]["id"] == session_id
                and simulation["snapshot"]["session"]["sourceMode"] == "simulation", "simulation_selection_mismatch")
        cycle_ids = discovered_cycle_ids(simulation, session_id)
        self.report["imageCycleDiscovery"] = {"source": "current detail and bounded first recent-cycle page from actual aggregate",
                                               "candidateCycleIds": cycle_ids, "hasMore": simulation["recentCycles"]["hasMore"],
                                               "attemptedCycleIds": []}
        selected_reads = []
        candidates = []
        for index, cycle_id in enumerate(cycle_ids):
            query = {"sourceMode": "simulation", "sessionId": session_id, "cycleId": cycle_id}
            selected = self.case(f"04-selected-cycle-{index:02d}", "/api/v1/dashboard", query)
            selected_reads.append(selected)
            detail = selected["detail"]
            require(detail["cycle"]["id"] == cycle_id and detail["cycle"]["sessionId"] == session_id,
                    "selected_cycle_detail_mismatch")
            self.report["imageCycleDiscovery"]["attemptedCycleIds"].append(cycle_id)
            candidates = image_candidates(detail)
            if candidates:
                break
        require(candidates, "saved_analyzed_frame_image_unavailable_in_bounded_cycle_page")
        self.report["imageCycleDiscovery"]["selectedCycleId"] = cycle_id
        self.case("05-missing-session", "/api/v1/dashboard", {"sourceMode": "simulation", "sessionId": "missing-" + str(uuid4())}, 404)
        self.case("06-source-conflict", "/api/v1/dashboard", {"sourceMode": "live", "sessionId": session_id}, 409)
        frame, evidence = candidates[0]
        require(frame["sessionId"] == evidence["sessionId"] == session_id
                and frame["cycleId"] == evidence["cycleId"] == cycle_id
                and frame["objectId"] == detail["cycle"]["objectId"], "frame_evidence_scope_mismatch")
        require(SAFE_ID.fullmatch(evidence["id"]) and re.fullmatch(r"[a-f0-9]{64}", evidence["sha256"]), "evidence_identity_invalid")
        image = self.case("07-saved-analyzed-image", "/api/v1/evidence/" + evidence["id"], {}, image=True)
        require(digest(image) == evidence["sha256"] and len(image) == evidence["size"], "image_record_hash_or_size_mismatch")
        local_path = EVIDENCE_DIRECTORY / evidence["sha256"]
        require(EVIDENCE_DIRECTORY.resolve(strict=True) == EVIDENCE_DIRECTORY, "local_evidence_directory_symlink")
        fd = os.open(local_path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BODY, "local_evidence_type_or_size")
            local = handle.read(MAX_BODY + 1)
        require(local == image, "local_evidence_bytes_mismatch")
        self.report["savedAnalyzedImage"] = {"frame": frame, "evidence": evidence, "localPath": str(local_path),
                                             "relayDirectLocalBytesEqual": True, "sourceMode": "simulation"}
        repeated = self.case("08-repeat-selected-cycle", "/api/v1/dashboard", query)
        require(semantic(repeated) == semantic(selected), "records_or_cursor_changed_during_read_checks")
        require(selected["lastEventSequence"] == simulation["lastEventSequence"] == live["lastEventSequence"], "global_cursor_changed_during_read_checks")
        for value in (live, simulation, *selected_reads, repeated):
            require(value["generatedAt"] == value["snapshot"]["generatedAt"]
                    and value["lastEventSequence"] == value["snapshot"]["lastEventSequence"] == value["snapshot"]["stateVersion"]
                    and value["metrics"] == value["snapshot"]["metrics"], "dashboard_coherence_mismatch")
            require(value["lastEventSequence"] == live["lastEventSequence"], "cursor_changed_during_cycle_discovery")
        self.report.update(status="passed", discoveredSessionId=session_id, discoveredCycleId=cycle_id,
                           unchangedEventCursor=selected["lastEventSequence"], sourceMode="simulation",
                           physicalVerification=False, requiredLogicalChecksPassed=8,
                           requestedCasesPassed=len(self.report["cases"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Execute only after root confirms updated main8000 readiness.")
    args = parser.parse_args()
    require(args.run, "explicit_run_argument_required")
    os.umask(0o077)
    run = REVIEW / ("relay-verification-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    run.mkdir(mode=0o700)
    harness = Harness(run)
    try:
        harness.execute()
    except Exception as error:
        harness.report.update(status="failed", errorCode=str(error) if isinstance(error, CheckFailure) else type(error).__name__)
    finally:
        harness.report["completedAt"] = now()
        save(run / "result.json", harness.report)
    print(json.dumps({"status": harness.report["status"], "resultPath": str(run / "result.json"),
                      "resultSha256": digest((run / "result.json").read_bytes()), "cases": len(harness.report["cases"])}))
    return 0 if harness.report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
