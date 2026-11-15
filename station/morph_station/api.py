"""Authenticated HTTP boundary for the local M06 persistence foundation.

This module records observations; it does not dispatch robot motion or invoke providers.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from .models import MODELS, ID, CorrectionRequest, Cycle, EvidenceUpload, RecordWrite, Session, Time
from .store import StationStore, StoreError

MAX_JSON_BYTES = 1024 * 1024
MAX_EVIDENCE_JSON_BYTES = 7 * 1024 * 1024


def data_directory() -> Path:
    return Path(os.environ.get("MORPH_DATA_DIR", Path(__file__).resolve().parents[1] / ".data"))


def token_file() -> Path:
    return Path(os.environ.get("MORPH_TOKEN_FILE", data_directory() / "api-token"))


def load_token(explicit: str | None = None) -> str:
    value = explicit if explicit is not None else os.environ.get("MORPH_API_TOKEN")
    if value is None:
        path = token_file()
        if not path.is_file():
            raise ValueError("API token is not configured. Run 'bash station/run.sh init' first.")
        if path.stat().st_mode & 0o077:
            raise ValueError("The API token file must be readable only by its owner (mode 0600).")
        value = path.read_text(encoding="utf-8").strip()
    if not value or len(value) < 32 or not value.isascii() or any(c.isspace() for c in value):
        raise ValueError("API token must contain at least 32 ASCII characters without whitespace.")
    return value


class ApiBoundaryMiddleware:
    """Reject unauthenticated API requests and bound bodies before JSON parsing."""

    def __init__(self, app: ASGIApp, token: str):
        self.app = app
        self.token = token.encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == "/api" or path.startswith("/api/")):
            await self.app(scope, receive, send)
            return
        auth_headers = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
        valid = False
        if len(auth_headers) == 1:
            pieces = auth_headers[0].split(b" ", 1)
            valid = len(pieces) == 2 and pieces[0].lower() == b"bearer" and secrets.compare_digest(pieces[1], self.token)
        if not valid:
            await JSONResponse({"detail": "A valid bearer token is required."}, status_code=401,
                               headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})(scope, receive, send)
            return
        bound = MAX_EVIDENCE_JSON_BYTES if path == "/api/v1/evidence" else MAX_JSON_BYTES
        lengths = [v for k, v in scope.get("headers", []) if k.lower() == b"content-length"]
        try:
            if len(lengths) > 1 or (lengths and int(lengths[0]) < 0):
                raise ValueError
            too_large = bool(lengths and int(lengths[0]) > bound)
        except ValueError:
            await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(scope, receive, send)
            return
        if too_large:
            await JSONResponse({"detail": "Request body exceeds the allowed size."}, status_code=413)(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > bound:
                await JSONResponse({"detail": "Request body exceeds the allowed size."}, status_code=413)(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def buffered_receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: ID
    session: dict[str, Any]


class SessionEnd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: ID
    endedAt: Time
    expectedRevision: int = Field(ge=1)


class LabelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: ID
    record: dict[str, Any]
    expectedRevision: int | None = Field(default=None, ge=1)


class SessionView(Session):
    revision: int = Field(ge=1)


class CycleView(Cycle):
    revision: int = Field(ge=1)


class UnavailableCapability(BaseModel):
    """M06 does not assert readiness of any physical or provider integration."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["unavailable"]
    verified: Literal[False]


class StationCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    robot: UnavailableCapability
    cameras: UnavailableCapability
    anomalib: UnavailableCapability
    nemotron: UnavailableCapability
    gemini: UnavailableCapability
    elevenlabs: UnavailableCapability


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: Literal[1]
    generatedAt: Time
    lastEventSequence: int = Field(ge=0)
    session: SessionView | None
    cycle: CycleView | None
    activeCycleIds: list[ID]
    sourceMode: Literal["live", "simulation"] | None
    stateVersion: int = Field(ge=0)
    goalVersion: None
    goal: None
    availableActions: list[ID] = Field(max_length=0)
    capabilities: StationCapabilities
    metrics: dict[str, Any]


def _cors_origins() -> list[str]:
    origins = [entry.strip() for entry in os.environ.get("MORPH_CORS_ORIGINS", "").split(",") if entry.strip()]
    for origin in origins:
        parsed = urlsplit(origin)
        if (origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("MORPH_CORS_ORIGINS must be an explicit comma-separated list of HTTP(S) origins without paths.")
    return origins


def create_app(db_path: str | Path | None = None, token: str | None = None,
               evidence_dir: str | Path | None = None) -> FastAPI:
    """Create an unseeded app; dependency injection keeps test data isolated."""
    api_token = load_token(token)
    db = Path(db_path or os.environ.get("MORPH_DB_PATH", data_directory() / "station.sqlite3"))
    evidence = Path(evidence_dir or os.environ.get("MORPH_EVIDENCE_DIR", db.parent / "evidence"))
    store = StationStore(db, evidence_dir=evidence)
    app = FastAPI(title="Morph station records", version="1.0.0",
                  description="M06 persistence foundation. Hardware and provider controls are unavailable.")
    app.state.store = store
    app.add_middleware(ApiBoundaryMiddleware, token=api_token)
    origins = _cors_origins()
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                           allow_methods=["GET", "POST", "OPTIONS"],
                           allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
                           expose_headers=["Content-Disposition"])

    @app.exception_handler(StoreError)
    async def store_error(_request: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(ValidationError)
    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: ValidationError | RequestValidationError) -> JSONResponse:
        # Envelope validation inside a handler is also a 422; never echo raw input.
        errors = [{"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                  for item in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "morph-station", "schemaVersion": 1,
                "hardwareIntegrated": False, "providersIntegrated": False}

    @app.get("/api/v1/schema")
    def schema() -> dict:
        envelopes = [RecordWrite, SessionCreate, SessionEnd, LabelCreate, CorrectionRequest, EvidenceUpload]
        return {"schemaVersion": 1,
                "records": {kind: model.model_json_schema() for kind, model in MODELS.items()},
                "envelopes": {model.__name__: model.model_json_schema() for model in envelopes},
                "responses": {"Snapshot": Snapshot.model_json_schema()}}

    @app.get("/api/v1/station/snapshot", response_model=Snapshot)
    def snapshot(sessionId: str | None = None) -> dict:
        return store.snapshot(session_id=sessionId)

    @app.get("/api/v1/sessions")
    def sessions() -> list[dict]:
        return store.list_records("session")

    @app.post("/api/v1/sessions")
    def create_session(body: SessionCreate, response: Response) -> dict:
        result = store.upsert(RecordWrite(eventId=body.eventId, recordType="session", record=body.session))
        response.status_code = 200 if result.get("duplicate") else 201
        return result

    @app.post("/api/v1/sessions/{session_id}/end")
    def end_session(session_id: str, body: SessionEnd) -> dict:
        return store.end_session(session_id, body.eventId, body.endedAt.isoformat(), body.expectedRevision)

    @app.post("/api/v1/records")
    def ingest_record(body: RecordWrite) -> dict:
        return store.upsert(body)

    @app.get("/api/v1/metrics")
    def all_metrics(includeSimulation: bool = False) -> dict:
        return store.metrics(include_simulation=includeSimulation)

    @app.get("/api/v1/sessions/{session_id}/metrics")
    def session_metrics(session_id: str, includeSimulation: bool = False) -> dict:
        store.get("session", session_id)
        return store.metrics(session_id=session_id, include_simulation=includeSimulation)

    @app.get("/api/v1/cycles")
    def cycles(sessionId: str | None = None, objectId: str | None = None,
               outcome: Literal["in_progress", "correct", "failed", "aborted", "unverified"] | None = None,
               sourceMode: Literal["live", "simulation"] | None = None,
               includeSimulation: bool = False, hasRetry: bool | None = None,
               errorCode: str | None = None, modelId: str | None = None,
               referenceStatus: Literal["labeled", "unlabeled"] | None = None,
               startedAfter: AwareDatetime | None = None, startedBefore: AwareDatetime | None = None,
               offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> dict:
        if sessionId:
            store.get("session", sessionId)
        session_modes = {item["id"]: item.get("sourceMode") for item in store.list_records("session")}
        results = []
        for item in store.list_records("cycle", session_id=sessionId):
            mode = item.get("sourceMode") or session_modes.get(item.get("sessionId"))
            if sourceMode and mode != sourceMode:
                continue
            if sourceMode is None and not includeSimulation and mode == "simulation":
                continue
            if objectId and item.get("objectId") != objectId:
                continue
            if outcome and item.get("outcome") != outcome:
                continue
            started = datetime.fromisoformat(item["startedAt"].replace("Z", "+00:00"))
            if startedAfter and started < startedAfter or startedBefore and started > startedBefore:
                continue
            if referenceStatus:
                labels = store.list_records("reference_label", cycle_id=item["id"])
                if bool(labels) != (referenceStatus == "labeled"):
                    continue
            if hasRetry is not None or errorCode:
                attempts = store.list_records("attempt", cycle_id=item["id"])
                if hasRetry is not None and (len(attempts) > 1) != hasRetry:
                    continue
                if errorCode and not any(row.get("errorCode") == errorCode for row in attempts):
                    continue
            if modelId:
                runs = store.list_records("model_run", cycle_id=item["id"])
                if not any(row.get("modelId") == modelId for row in runs):
                    continue
            results.append(item)
        results.sort(key=lambda row: (row["startedAt"], row["id"]))
        return {"items": results[offset:offset + limit], "total": len(results), "offset": offset, "limit": limit}

    @app.get("/api/v1/cycles/{cycle_id}")
    def cycle_detail(cycle_id: str) -> dict:
        return store.cycle_detail(cycle_id)

    @app.post("/api/v1/cycles/{cycle_id}/reference-labels")
    def reference_label(cycle_id: str, body: LabelCreate) -> dict:
        cycle = store.get("cycle", cycle_id)
        record = dict(body.record)
        if "cycleId" in record and record["cycleId"] != cycle_id:
            raise HTTPException(422, "The reference label cycleId must match the URL.")
        record["cycleId"] = cycle_id
        record.setdefault("sessionId", cycle["sessionId"])
        return store.upsert(RecordWrite(eventId=body.eventId, recordType="reference_label", record=record,
                                       expectedRevision=body.expectedRevision))

    @app.post("/api/v1/corrections")
    def correction(body: CorrectionRequest) -> dict:
        return store.correct(body)

    @app.post("/api/v1/evidence")
    def upload_evidence(body: EvidenceUpload) -> dict:
        return store.put_evidence(body)

    @app.get("/api/v1/evidence/{evidence_id}")
    def evidence_content(evidence_id: str) -> FileResponse:
        path, media_type = store.evidence_file(evidence_id)
        return FileResponse(path, media_type=media_type,
                            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/v1/cameras")
    def cameras() -> dict:
        return {"status": "unavailable", "cameras": [], "reason": "Camera integration is not implemented in M06."}

    def unavailable(component: str) -> None:
        raise HTTPException(503, f"{component} is not integrated. No hardware action or provider request was sent.")

    @app.get("/api/v1/cameras/{camera_id}/stream")
    def camera_stream(camera_id: str) -> None:
        unavailable("Camera streaming")

    @app.post("/api/v1/commands")
    def commands() -> None:
        unavailable("Robot command dispatch")

    @app.post("/api/v1/voice/token")
    def voice_token() -> None:
        unavailable("ElevenLabs token issuance")

    @app.post("/api/v1/voice/utterances")
    def utterance_command() -> None:
        unavailable("Voice goal selection")

    @app.get("/api/v1/events")
    async def events(request: Request, after: int | None = Query(None, ge=0),
                     once: bool = False, limit: int = Query(100, ge=1, le=1000),
                     last_event_id: str | None = Header(None, alias="Last-Event-ID")) -> StreamingResponse:
        cursor = after or 0
        if last_event_id is not None:
            try:
                resumed = int(last_event_id)
                if resumed < 0:
                    raise ValueError
            except ValueError as exc:
                raise HTTPException(400, "Last-Event-ID must be a non-negative sequence number.") from exc
            cursor = max(cursor, resumed)
        ceiling = await run_in_threadpool(store.latest_sequence)
        if cursor > ceiling:
            raise HTTPException(409, "Event cursor is ahead of this station. Refresh the authoritative snapshot.")

        async def stream():
            current = cursor
            last_heartbeat = time.monotonic()
            while True:
                rows = await run_in_threadpool(store.events, after=current, limit=limit)
                if once:
                    rows = [row for row in rows if row["sequence"] <= ceiling]
                for row in rows:
                    current = row["sequence"]
                    kind = str(row.get("type", "record.updated")).replace("\r", "").replace("\n", "")
                    yield f"id: {current}\nevent: {kind}\ndata: {json.dumps(row, ensure_ascii=False, separators=(',', ':'))}\n\n"
                if once:
                    if not rows:
                        yield ": caught-up\n\n"
                    return
                if await request.is_disconnected():
                    return
                if rows:
                    continue
                if time.monotonic() - last_heartbeat >= 15:
                    yield ": keep-alive\n\n"
                    last_heartbeat = time.monotonic()
                await asyncio.sleep(0.25)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"})

    @app.get("/api/v1/sessions/{session_id}/export")
    def export_session(session_id: str, format: Literal["json", "csv"] = "json") -> Response:
        data = store.export_session(session_id)
        safe_name = "morph-session-export"
        if format == "json":
            return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"',
                                               "Cache-Control": "private, no-store"})
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["section", "recordType", "id", "dataJson"])
        for section, value in data.items():
            if section == "records" and isinstance(value, dict):
                for record_type, entities in value.items():
                    for entity in entities:
                        writer.writerow([section, record_type, entity.get("id", ""),
                                         json.dumps(entity, ensure_ascii=False, separators=(",", ":"))])
                continue
            rows = value if isinstance(value, list) else [value]
            for row in rows:
                if isinstance(row, dict):
                    record_type = row.get("recordType", row.get("entityType", "session" if section == "session" else ""))
                    record_id = row.get("id", row.get("entityId", row.get("eventId", "")))
                else:
                    record_type = record_id = ""
                writer.writerow([section, record_type, record_id, json.dumps(row, ensure_ascii=False, separators=(",", ":"))])
        return Response(output.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"',
                                 "Cache-Control": "private, no-store"})

    return app
