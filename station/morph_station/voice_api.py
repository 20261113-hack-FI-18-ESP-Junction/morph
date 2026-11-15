"""Opt-in lab routes for Scribe; all goal/robot actions remain separate."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field

from .models import ID, RecordWrite, StrictModel
from .voice import VoiceError, VoiceJournal, issue_scribe_token, scribe_connection_options


class CaptureStart(StrictModel):
    utteranceId: ID
    sessionId: ID
    cycleId: ID | None = None


class CaptureEvent(StrictModel):
    eventId: ID
    event: dict[str, Any]
    segmentIndex: int | None = Field(default=None, ge=0, lt=128, strict=True)


class CaptureFinalize(StrictModel):
    expectedSegmentCount: int = Field(ge=1, le=128, strict=True)
    terminalCommitEventId: ID


def install_voice_routes(app, credential_loader: Callable[[], dict[str, str]], *, clock=None) -> None:
    """Install only on the authenticated, dedicated simulation control app.

    The host application owns authentication. Every route uses its existing
    ``/api`` bearer middleware; this installer never creates a public token route.
    """
    if hasattr(app.state, "voice_journal"):
        raise ValueError("Voice routes have already been installed.")
    current_time = clock or (lambda: datetime.now(timezone.utc))
    store = app.state.store
    journal = VoiceJournal(store.db_path)
    app.state.voice_journal = journal
    prefix = "/api/v1/lab/voice"

    def now() -> str:
        value = current_time()
        return value.isoformat() if isinstance(value, datetime) else value

    @app.exception_handler(VoiceError)
    async def voice_error_handler(request, error: VoiceError):
        return JSONResponse({"detail": str(error), "code": error.code},
            status_code=error.status_code, headers={"Cache-Control": "no-store"})

    def check_session(session_id: str, cycle_id: str | None = None, *, require_open=False):
        session = store.get("session", session_id)
        if session["sourceMode"] != "simulation":
            raise HTTPException(409, "Voice lab accepts simulation sessions only.")
        if require_open and session["endedAt"] is not None:
            raise HTTPException(409, "Voice capture requires an open simulation session.")
        if cycle_id:
            cycle = store.get("cycle", cycle_id)
            if cycle["sessionId"] != session_id:
                raise HTTPException(409, "Voice cycle belongs to another session.")
        return session

    def capture(identity: str) -> dict:
        record = journal.get(identity)
        check_session(record["sessionId"], record["cycleId"])
        return record

    def result(record: dict, **extra) -> dict:
        return {**record, "providerProvenance": "browser_relay",
                "physicalActionSent": False, **extra}

    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application) as state:
            journal.recover_incomplete(now())
            yield state

    app.router.lifespan_context = lifespan

    @app.get(prefix + "/options")
    def options():
        return {**scribe_connection_options(), "providerProvenance": "browser_relay",
                "physicalActionSent": False, "recordingStartsAutomatically": False}

    @app.post(prefix + "/token")
    def token():
        try:
            config = credential_loader()
        except (ValueError, OSError):
            raise HTTPException(503, "Provider credential configuration could not be loaded safely.") from None
        issued = issue_scribe_token(config.get("ELEVENLABS_API_KEY", ""))
        return JSONResponse({**issued, **scribe_connection_options()},
                            headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

    @app.post(prefix + "/start")
    def start(body: CaptureStart):
        check_session(body.sessionId, body.cycleId, require_open=True)
        try:
            previous = journal.get(body.utteranceId)
        except VoiceError as error:
            if error.code != "not_found":
                raise
            previous = None
        started = previous["startedAt"] if previous else now()
        return result(journal.start(body.utteranceId, body.sessionId, started,
                                    source_mode="simulation", cycle_id=body.cycleId))

    @app.get(prefix + "/{utterance_id}")
    def get(utterance_id: str):
        return {"capture": capture(utterance_id), "events": journal.events(utterance_id),
                "providerProvenance": "browser_relay", "physicalActionSent": False}

    @app.post(prefix + "/{utterance_id}/events")
    def event(utterance_id: str, body: CaptureEvent):
        capture(utterance_id)
        return result(journal.receive(utterance_id, body.eventId, body.event, now(), body.segmentIndex))

    @app.post(prefix + "/{utterance_id}/release")
    def release(utterance_id: str):
        capture(utterance_id)
        return result(journal.release(utterance_id, now()))

    @app.post(prefix + "/{utterance_id}/finalize")
    def finalize(utterance_id: str, body: CaptureFinalize):
        capture(utterance_id)
        finalized = journal.finalize(utterance_id, body.expectedSegmentCount,
                                     body.terminalCommitEventId, now())
        if finalized["status"] != "finalized":
            return result(finalized, utteranceRecord=None)
        # A crash after journal finalization can leave the canonical write absent.
        # Repeat this same idempotent write even when newlyFinalized is false.
        receipt_id = "voice-finalized:" + hashlib.sha256(utterance_id.encode()).hexdigest()
        canonical = {"id": utterance_id, "sessionId": finalized["sessionId"],
            "cycleId": finalized["cycleId"], "text": finalized["text"], "source": "voice",
            "provider": "elevenlabs", "modelId": finalized["modelId"],
            "startedAt": finalized["startedAt"], "completedAt": finalized["completedAt"],
            "status": "finalized", "language": None}
        saved = store.upsert(RecordWrite(eventId=receipt_id, recordType="utterance", record=canonical,
                                        occurredAt=finalized["completedAt"]))
        return result(finalized, utteranceRecord=saved["record"], persistenceDuplicate=saved["duplicate"])
