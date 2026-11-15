"""Opt-in Mac integration lab. Every dispatcher operation is explicitly simulated.

The ordinary M06 application and its control stubs remain unchanged. This factory
must use a dedicated lab database; it never loads a physical robot adapter.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import Field, StrictBool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import create_app, load_token
from .dispatcher import (CheckpointRequest, ControlRequest, DispatchRequest,
                         GoalRequest, SimulationDispatcher, demo_simulation_policy)
from .models import ID, EvidenceUpload, RecordWrite, StrictModel, Text, Time
from .providers import (GoalSelectionRequest, ObservationRequest, ProviderService,
                        TaskSelectionRequest)
from .store import StoreError


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_provider_keys() -> dict[str, str]:
    """Load existing owner-only literal configuration; never expose it in responses."""
    allowed = {"GEMINI_API_KEY", "GOOGLE_API_KEY", "VERDA_INFERENCE_KEY", "ELEVENLABS_API_KEY"}
    path = Path(__file__).resolve().parents[2] / "setup/provider-check/check.py"
    if not path.is_file():
        return {key: value for key, value in os.environ.items() if key in allowed and value}
    spec = importlib.util.spec_from_file_location("morph_local_provider_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = {**module.load_config(), **os.environ}
    return {key: value for key, value in values.items() if key in allowed and value}


class DemoRequest(StrictModel):
    requestId: ID


class FrameRequest(StrictModel):
    requestId: ID
    sessionId: ID
    cycleId: ID


class FinishRequest(StrictModel):
    success: StrictBool


class ReconcileRequest(StrictModel):
    status: Literal["finished", "failed", "unverified"]
    authorId: ID
    reason: Text


def create_control_app(db_path: str | Path, token: str, *, clock=None,
                       enable_browser_lab: bool = False):
    """Explicit construction and dedicated DB are required; reads never seed data."""
    app = create_app(db_path=db_path, token=token)
    app.title = "Morph simulation and voice lab"
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    store = app.state.store
    dispatcher = SimulationDispatcher(store, demo_simulation_policy(), clock=clock)
    app.state.dispatcher = dispatcher
    app.state.providers = ProviderService(store, dispatcher, credentials=local_provider_keys(), clock=clock)
    prefix = "/api/v1/control"

    @app.get(prefix + "/snapshot")
    def snapshot():
        return dispatcher.snapshot()

    @app.get(prefix + "/policy")
    def policy():
        return {"sourceMode": "simulation", "policy": dispatcher.policy.model_dump(mode="json"),
                "requiresMentorReview": True, "physicalAdapterImplemented": False}

    @app.get(prefix + "/decision-context")
    def decision_context():
        return dispatcher.decision_context()

    @app.get(prefix + "/journal")
    def journal():
        return dispatcher.export_journal()

    @app.post(prefix + "/commands")
    def command(body: ControlRequest):
        return dispatcher.control(body)

    @app.post(prefix + "/checkpoints")
    def checkpoint(body: CheckpointRequest):
        return dispatcher.checkpoint(body)

    @app.post(prefix + "/goals")
    def goal(body: GoalRequest):
        return dispatcher.select_goal(body)

    @app.post(prefix + "/dispatch")
    def dispatch(body: DispatchRequest):
        return dispatcher.dispatch(body)

    @app.post(prefix + "/executions/{execution_id}/acknowledge")
    def acknowledge(execution_id: str):
        return dispatcher.acknowledge(execution_id)

    @app.post(prefix + "/executions/{execution_id}/finish")
    def finish(execution_id: str, body: FinishRequest):
        return dispatcher.finish(execution_id, body.success)

    @app.post(prefix + "/executions/{execution_id}/reconcile")
    def reconcile(execution_id: str, body: ReconcileRequest):
        return dispatcher.reconcile(execution_id, body.status, body.authorId, body.reason)

    @app.post(prefix + "/demo")
    def demo(body: DemoRequest):
        """Create input records only after an intentional action, with stable IDs."""
        stem = body.requestId
        ids = {key: stem + ":" + key for key in ("session", "cycle", "object", "attempt", "frame", "image")}
        try:
            existing = store.get("session", ids["session"])
        except StoreError as exc:
            if exc.status_code != 404:
                raise
            existing = None
        if existing is None and dispatcher.snapshot()["mode"] != "stopped":
            raise HTTPException(409, "Stop and reconcile the current lab run before creating another fixture.")
        at = existing["startedAt"] if existing else dispatcher._stamp()
        fixture = Path(__file__).resolve().parents[2] / "setup/provider-check/fixtures/red-rectangle.png"
        raw = fixture.read_bytes()
        def write(kind, record):
            return store.upsert(RecordWrite(eventId=record["id"] + ":created", recordType=kind, record=record))
        write("session", {"id": ids["session"], "name": "Mac integration lab — synthetic input",
                          "sourceMode": "simulation", "startedAt": at, "configId": dispatcher.policy.id})
        write("cycle", {"id": ids["cycle"], "sessionId": ids["session"], "objectId": ids["object"], "startedAt": at})
        write("attempt", {"id": ids["attempt"], "sessionId": ids["session"], "cycleId": ids["cycle"],
                          "ordinal": 1, "startedAt": at})
        store.put_evidence(EvidenceUpload(id=ids["image"], eventId=ids["image"] + ":uploaded",
            sessionId=ids["session"], cycleId=ids["cycle"], mediaType="image/png",
            contentBase64=base64.b64encode(raw).decode(), capturedAt=at))
        # Dimensions are read from this known PNG's IHDR, not claimed camera telemetry.
        width, height = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        write("frame", {"id": ids["frame"], "sessionId": ids["session"], "cycleId": ids["cycle"],
                        "objectId": ids["object"], "cameraId": "synthetic-fixture", "capturedAt": at,
                        "receivedAt": at, "width": width, "height": height, "evidenceId": ids["image"]})
        return {"sourceMode": "simulation", "duplicate": existing is not None, **ids}

    @app.post(prefix + "/demo-frame")
    def demo_frame(body: FrameRequest):
        session = store.get("session", body.sessionId)
        cycle = store.get("cycle", body.cycleId)
        if session["sourceMode"] != "simulation" or cycle["sessionId"] != session["id"]:
            raise HTTPException(409, "Synthetic frames require a matching simulation session and cycle.")
        if cycle["endedAt"] is not None or session["endedAt"] is not None:
            raise HTTPException(409, "Synthetic refresh requires open records.")
        identity = body.requestId + ":frame"
        try:
            frame = store.get("frame", identity)
        except StoreError as exc:
            if exc.status_code != 404:
                raise
            frame = None
        if frame:
            if (frame["sessionId"], frame["cycleId"]) != (body.sessionId, body.cycleId):
                raise HTTPException(409, "Frame request ID conflict.")
            return {"frame": frame["id"], "duplicate": True, "sourceMode": "simulation"}
        image_id = body.requestId + ":image"
        try:
            image = store.get("evidence", image_id)
            at = image["capturedAt"]
        except StoreError as exc:
            if exc.status_code != 404:
                raise
            at = dispatcher._stamp()
        fixture = Path(__file__).resolve().parents[2] / "setup/provider-check/fixtures/red-rectangle.png"
        raw = fixture.read_bytes()
        store.put_evidence(EvidenceUpload(id=image_id, eventId=image_id + ":uploaded",
            sessionId=body.sessionId, cycleId=body.cycleId, mediaType="image/png",
            contentBase64=base64.b64encode(raw).decode(), capturedAt=at))
        record = {"id": identity, "sessionId": body.sessionId, "cycleId": body.cycleId,
                  "objectId": cycle["objectId"], "cameraId": "synthetic-fixture", "capturedAt": at,
                  "receivedAt": at, "width": int.from_bytes(raw[16:20], "big"),
                  "height": int.from_bytes(raw[20:24], "big"), "evidenceId": image_id}
        store.upsert(RecordWrite(eventId=identity + ":created", recordType="frame", record=record))
        return {"frame": identity, "duplicate": False, "sourceMode": "simulation"}

    @app.get("/api/v1/lab/providers")
    def provider_status():
        config = local_provider_keys()
        return {"elevenlabsConfigured": bool(config.get("ELEVENLABS_API_KEY")),
                "geminiConfigured": bool(config.get("GEMINI_API_KEY") or config.get("GOOGLE_API_KEY")),
                "nemotronConfigured": bool(config.get("VERDA_INFERENCE_KEY")),
                "physicalAdapterImplemented": False}

    @app.post("/api/v1/lab/providers/observe")
    def observe(body: ObservationRequest):
        return app.state.providers.observe(body)

    @app.post("/api/v1/lab/providers/select-task")
    def select_task(body: TaskSelectionRequest):
        return app.state.providers.select_task(body)

    @app.post("/api/v1/lab/providers/select-goal")
    def select_goal(body: GoalSelectionRequest):
        return app.state.providers.select_goal(body)

    @app.get("/api/v1/lab/providers/requests/{request_id}")
    def provider_request(request_id: str):
        return app.state.providers.get_request(request_id)

    from .voice_api import install_voice_routes
    install_voice_routes(app, local_provider_keys, clock=clock)

    if enable_browser_lab:
        @app.get("/lab", response_class=HTMLResponse)
        def browser_lab():
            # Only the private local station token enters this loopback page; no provider key.
            html = Path(__file__).with_name("lab.html").read_text()
            return HTMLResponse(html.replace("__LOCAL_API_TOKEN__", json.dumps(load_token(token))),
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    return app
