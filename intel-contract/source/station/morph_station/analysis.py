"""Explicit asynchronous evidence reports stored outside the canonical event stream."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import queue
import re
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from pydantic import ValidationError

from .analysis_context import ContextBuilder
from .analysis_models import CONTRACT_VERSION, MODEL, PROMPT_VERSION, AnalysisRequest, EvidenceBriefResponse, Selection
from .analysis_provider import GemmaProvider, ProviderError, sanitize, strict_json_loads, validate_reply
from .store import StoreError, canonical, fingerprint, now

TERMINAL = {"ready", "rejected", "failed", "interrupted"}
MAX_STORED_JSON_BYTES = 1024 * 1024
STORAGE_WARNING = {"code": "analysis_storage_unavailable", "message": "Some saved analysis evidence cannot be read or saved. New analysis is unavailable until storage is repaired and the analysis service is restarted."}


def atomic_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class AnalysisService:
    def __init__(self, store, directory: Path, provider=None):
        self.directory = Path(directory)
        self.reports_dir = self.directory / "reports"
        self.requests_dir = self.directory / "requests"
        self.builder = ContextBuilder(store, self.directory)
        self.provider = provider if provider is not None else GemmaProvider()
        self.lock = threading.RLock()
        self.jobs = queue.Queue(maxsize=4)
        self.closed = False
        self.storage_issues = set()
        self.unsaved_errors = {}
        self.owner_file = None
        self.owns_worker = False
        self.worker = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.reports_dir.mkdir(exist_ok=True, mode=0o700)
            self.requests_dir.mkdir(exist_ok=True, mode=0o700)
            self.owner_file = os.open(self.directory / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(self.owner_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.owns_worker = True
        except BlockingIOError:
            pass
        except OSError:
            self._storage_issue(self.directory)
        if self.owns_worker:
            self._recover()
            self.worker = threading.Thread(target=self._work, name="morph-evidence-analyst", daemon=True)
            self.worker.start()

    def _recover(self):
        for path in self._paths(self.requests_dir):
            try:
                self._read_index(path)
            except StoreError:
                self._storage_issue(path)
        for report in self._stored_reports():
            path = self._path(report["reportId"])
            request = report["request"]
            index = self.requests_dir / (fingerprint(request["requestId"]) + ".json")
            try:
                if not index.exists():
                    atomic_json(index, {"fingerprint": report.get("requestFingerprint", fingerprint(request)), "reportId": report["reportId"]})
                if report["status"] not in TERMINAL:
                    self._interrupt(report, "The station stopped before this report completed. Retry explicitly with a new request identifier.")
                    atomic_json(path, report)
            except OSError:
                self._storage_issue(path, report["reportId"])

    def _storage_issue(self, path, report_id=None):
        with self.lock:
            self.storage_issues.add(str(path))
            if report_id:
                self.unsaved_errors[report_id] = dict(STORAGE_WARNING)

    def _paths(self, directory):
        try:
            return list(directory.glob("*.json"))
        except OSError:
            self._storage_issue(directory)
            return []

    def _stored_reports(self):
        for path in self._paths(self.reports_dir):
            try:
                yield self._read_report(path)
            except StoreError:
                self._storage_issue(path)

    def _read_index(self, path):
        try:
            index = self._read(path)
            if not isinstance(index, dict) or not isinstance(index.get("fingerprint"), str) or not re.fullmatch(r"[a-f0-9]{64}", index["fingerprint"]):
                raise ValueError("Invalid request index")
            self._read_report(self._path(index["reportId"]))
            return index
        except (KeyError, TypeError, ValueError, StoreError):
            self._storage_issue(path)
            raise StoreError(503, STORAGE_WARNING["message"])

    def _read_report(self, path):
        try:
            report = self._read(path)
            if not isinstance(report, dict) or report.get("reportId") != path.stem or report.get("status") not in TERMINAL | {"queued", "running"}:
                raise ValueError("Invalid report identity or state")
            self._path(report["reportId"])
            AnalysisRequest.model_validate(report["request"])
            for key in ("context", "timestamps", "timings", "provenance", "validation"):
                if not isinstance(report[key], dict):
                    raise ValueError("Invalid report field")
            if not isinstance(report["timestamps"]["queuedAt"], str) or not isinstance(report["context"]["contentDigest"], str):
                raise ValueError("Invalid report metadata")
            for key in ("facts", "metrics", "knownGaps", "recordRevisions", "untrustedExcerpts", "reviewTargets"):
                if not isinstance(report["context"][key], list):
                    raise ValueError("Invalid captured context")
            if report["status"] == "ready":
                EvidenceBriefResponse.model_validate(report["output"])
            return report
        except StoreError as exc:
            if exc.status_code == 404:
                raise
            self._storage_issue(path)
            raise
        except (KeyError, TypeError, ValueError, ValidationError):
            self._storage_issue(path)
            raise StoreError(503, STORAGE_WARNING["message"])

    @staticmethod
    def _interrupt(report, message):
        report.update(status="interrupted", error={"code": "interrupted", "message": message})
        report["timestamps"]["interruptedAt"] = now()

    @staticmethod
    def _read(path):
        try:
            if path.stat().st_size > MAX_STORED_JSON_BYTES:
                raise ValueError("Stored analysis exceeds its read bound")
            return strict_json_loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise StoreError(404, "Analysis report was not found")
        except (ValueError, OSError, RecursionError):
            raise StoreError(503, "Stored analysis evidence cannot be read")

    def _path(self, report_id):
        if not re.fullmatch(r"[a-f0-9-]{36}", report_id):
            raise StoreError(404, "Analysis report was not found")
        return self.reports_dir / (report_id + ".json")

    def context(self, selection):
        return self.builder.build(selection)

    def get(self, report_id):
        with self.lock:
            report = copy.deepcopy(self._read_report(self._path(report_id)))
            if report_id in self.unsaved_errors:
                report.update(status="failed", error=self.unsaved_errors[report_id], persistenceState="unavailable")
        try:
            current = self.builder.build(AnalysisRequest.model_validate(report["request"]).selection())
            report["freshness"] = "current" if current["contentDigest"] == report["context"]["contentDigest"] else "stale"
        except StoreError:
            report["freshness"] = "stale"
        return report

    def list(self, session_id=None, cycle_id=None, limit=50):
        rows = []
        for report in self._stored_reports():
            if session_id and session_id not in report["request"]["sessionIds"]:
                continue
            if cycle_id and cycle_id != report["request"].get("cycleId"):
                continue
            rows.append(report)
        rows.sort(key=lambda report: (report["timestamps"]["queuedAt"], report["reportId"]), reverse=True)
        reports = []
        for report in rows[:limit]:
            try:
                reports.append(self.get(report["reportId"]))
            except StoreError:
                self._storage_issue(self._path(report["reportId"]))
        return {"reports": reports, **({"warnings": [dict(STORAGE_WARNING)]} if self.storage_issues else {})}

    def submit(self, request: AnalysisRequest):
        request_payload = request.model_dump()
        request_fingerprint = fingerprint(request_payload)
        index_path = self.requests_dir / (fingerprint(request.requestId) + ".json")
        with self.lock:
            if index_path.exists():
                prior = self._read_index(index_path)
                if prior["fingerprint"] != request_fingerprint:
                    raise StoreError(409, "The request identifier was already used for different input")
                try:
                    return self.get(prior["reportId"])
                except StoreError:
                    self._storage_issue(index_path)
                    raise StoreError(503, STORAGE_WARNING["message"])
            if self.storage_issues:
                raise StoreError(503, STORAGE_WARNING["message"])
            if not self.owns_worker or self.closed:
                raise StoreError(503, "The station analysis worker is unavailable")
            context = self.builder.build(request.selection())
            if context["contentDigest"] != request.expectedSelectionDigest:
                raise StoreError(409, "The selected evidence changed; refresh it before requesting analysis")
            if not any(metric.get("denominator", 0) > 0 for metric in context["metrics"]):
                raise StoreError(422, "No data yet: no finished cycles or attempts are eligible for analysis")
            cache_key = fingerprint({"digest": context["contentDigest"], "question": request.question,
                                     "model": MODEL, "prompt": PROMPT_VERSION, "contract": CONTRACT_VERSION})
            reports = list(self._stored_reports())
            if self.storage_issues:
                raise StoreError(503, STORAGE_WARNING["message"])
            for report in reports:
                if report["status"] == "ready" and report.get("cacheKey") == cache_key:
                    try:
                        atomic_json(index_path, {"fingerprint": request_fingerprint, "reportId": report["reportId"]})
                    except OSError:
                        self._storage_issue(index_path)
                        raise StoreError(503, STORAGE_WARNING["message"])
                    result = self.get(report["reportId"])
                    result["cacheReused"] = True
                    return result
            if self.jobs.full():
                raise StoreError(429, "The bounded analysis queue is full; retry explicitly later")
            report_id = str(uuid.uuid4())
            captured_at = now()
            report = {
                "reportId": report_id, "status": "queued", "request": sanitize(request_payload), "requestFingerprint": request_fingerprint,
                "context": context, "output": None, "cacheKey": cache_key,
                "validation": {"accepted": False, "reasons": [], "scope": "Schema, supplied citation IDs, prose constraints and comparison policy; semantic usefulness requires evaluation."},
                "provenance": {"requestedModel": MODEL, "returnedModel": None, "responseId": None,
                               "promptVersion": PROMPT_VERSION, "contractVersion": CONTRACT_VERSION,
                               "sourceDigest": context["contentDigest"]},
                "timestamps": {"queuedAt": captured_at, "contextCapturedAt": context["asOf"], "startedAt": None,
                               "providerRequestedAt": None, "providerCompletedAt": None, "validatedAt": None, "readyAt": None},
                "timings": {"providerLatencyMs": None, "validationMs": None, "reportTotalMs": None},
                "providerEvidence": None, "error": None,
            }
            try:
                atomic_json(self._path(report_id), report)
                atomic_json(index_path, {"fingerprint": request_fingerprint, "reportId": report_id})
            except OSError:
                self._storage_issue(index_path, report_id)
                raise StoreError(503, STORAGE_WARNING["message"])
            self.jobs.put_nowait((report_id, time.monotonic()))
            return self.get(report_id)

    def _work(self):
        while True:
            job = self.jobs.get()
            if job is None:
                self.jobs.task_done()
                return
            report_id, queued_clock = job
            provider_clock = None
            report = None
            try:
                report = self._read_report(self._path(report_id))
                with self.lock:
                    # Closing can race a dequeue. Only an already-started invocation may finish.
                    if self.closed or self.storage_issues:
                        self._interrupt(report, "The analysis service became unavailable before this report started. Retry explicitly after recovery.")
                        continue
                    report["status"] = "running"
                    report["timestamps"]["startedAt"] = now()
                    report["timestamps"]["providerRequestedAt"] = now()
                    atomic_json(self._path(report_id), report)
                provider_clock = time.monotonic()
                evidence = self.provider(report["context"], report["request"]["question"])
                report["timestamps"]["providerCompletedAt"] = now()
                report["timings"]["providerLatencyMs"] = evidence.get("providerLatencyMs", (time.monotonic() - provider_clock) * 1000)
                report["providerEvidence"] = sanitize(evidence)
                response = evidence.get("response", {})
                response = response if isinstance(response, dict) else {}
                report["provenance"].update(returnedModel=response.get("modelVersion"), responseId=response.get("responseId"),
                                            usage=response.get("usageMetadata"), httpStatus=evidence.get("httpStatus"))
                validation_clock = time.monotonic()
                try:
                    report["output"] = validate_reply(evidence, report["context"])
                finally:
                    report["timings"]["validationMs"] = (time.monotonic() - validation_clock) * 1000
                    report["timestamps"]["validatedAt"] = now()
                report["validation"]["accepted"] = True
                report["status"] = "ready"
                report["timestamps"]["readyAt"] = now()
            except ProviderError as exc:
                report["status"] = "rejected" if (exc.evidence or report.get("providerEvidence") or {}).get("httpStatus") == 200 else "failed"
                report["error"] = {"code": exc.code, "message": sanitize(exc.message)}
                report["validation"]["reasons"] = [exc.code]
                if exc.evidence:
                    report["providerEvidence"] = sanitize(exc.evidence)
                    response = exc.evidence.get("response", {})
                    response = response if isinstance(response, dict) else {}
                    report["provenance"].update(returnedModel=response.get("modelVersion"), responseId=response.get("responseId"),
                                                usage=response.get("usageMetadata"), httpStatus=exc.evidence.get("httpStatus"))
            except (StoreError, OSError):
                self._storage_issue(self._path(report_id))
                if report is not None:
                    report.update(status="failed", error=dict(STORAGE_WARNING))
                    report["validation"]["reasons"] = [STORAGE_WARNING["code"]]
            except Exception:
                # Unexpected exception details can contain provider or credential input; retain only a stable code.
                if report is not None:
                    report["status"] = "failed"
                    report["error"] = {"code": "analysis_internal_error", "message": "The evidence report could not be completed."}
                    report["validation"]["reasons"] = ["analysis_internal_error"]
                else:
                    self._storage_issue(self._path(report_id))
            finally:
                try:
                    if report is not None:
                        if provider_clock is not None:
                            if report["timings"]["providerLatencyMs"] is None:
                                report["timings"]["providerLatencyMs"] = (time.monotonic() - provider_clock) * 1000
                            if report["timestamps"]["providerCompletedAt"] is None:
                                report["timestamps"]["providerCompletedAt"] = now()
                        report["timings"]["reportTotalMs"] = (time.monotonic() - queued_clock) * 1000
                        with self.lock:
                            atomic_json(self._path(report_id), report)
                except OSError:
                    self._storage_issue(self._path(report_id), report_id)
                finally:
                    self.jobs.task_done()

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        if self.worker:
            # Cancel queued work; allow only the already-running bounded request to finish.
            while True:
                try:
                    pending = self.jobs.get_nowait()
                except queue.Empty:
                    break
                if pending is not None:
                    report_id, queued_clock = pending
                    try:
                        report = self._read_report(self._path(report_id))
                        self._interrupt(report, "Station shutdown interrupted this queued report. Retry explicitly with a new request identifier.")
                        report["timings"]["reportTotalMs"] = (time.monotonic() - queued_clock) * 1000
                        atomic_json(self._path(report_id), report)
                    except (StoreError, OSError):
                        self._storage_issue(self._path(report_id), report_id)
                self.jobs.task_done()
            self.jobs.put(None)
            self.worker.join(timeout=30)
        if self.worker is None or not self.worker.is_alive():
            if self.owns_worker:
                fcntl.flock(self.owner_file, fcntl.LOCK_UN)
            if self.owner_file is not None:
                os.close(self.owner_file)


def register_analysis_routes(app: FastAPI, store, directory: Path, provider=None):
    service = AnalysisService(store, directory, provider)
    app.state.analysis = service
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application) as state:
            try:
                yield state
            finally:
                service.close()

    app.router.lifespan_context = lifespan

    @app.get("/api/v1/analysis/context")
    def context(kind: str, sessionIds: list[str] = Query(...), cycleId: str | None = None,
                sourceMode: str = "simulation", comparisonSpecId: str | None = None,
                baselineSessionId: str | None = None, adaptiveSessionId: str | None = None):
        return service.context(Selection.model_validate({"kind": kind, "sessionIds": sessionIds, "cycleId": cycleId,
                               "sourceMode": sourceMode, "comparisonSpecId": comparisonSpecId,
                               "baselineSessionId": baselineSessionId, "adaptiveSessionId": adaptiveSessionId}))

    @app.post("/api/v1/analysis/reports", status_code=202)
    def create_report(body: AnalysisRequest):
        return service.submit(body)

    @app.get("/api/v1/analysis/reports")
    def list_reports(sessionId: str | None = None, cycleId: str | None = None, limit: int = Query(50, ge=1, le=100)):
        return service.list(sessionId, cycleId, limit)

    @app.get("/api/v1/analysis/reports/{report_id}")
    def get_report(report_id: str):
        return service.get(report_id)
