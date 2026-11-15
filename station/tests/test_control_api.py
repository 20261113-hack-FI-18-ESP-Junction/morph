"""Authenticated simulation-lab integration; no external provider or robot calls."""
from datetime import datetime, timedelta, timezone
import re

from fastapi.testclient import TestClient
import pytest

from morph_station.control_api import create_control_app
from morph_station.store import StoreError


TOKEN = "test-lab-token-" + "x" * 40


@pytest.fixture
def lab(tmp_path, monkeypatch):
    # Tests never inspect credentials or contact configured accounts.
    monkeypatch.setattr("morph_station.control_api.local_provider_keys", lambda: {})
    moment = [datetime(2026, 11, 14, 21, tzinfo=timezone.utc)]
    app = create_control_app(tmp_path / "lab.sqlite3", TOKEN, clock=lambda: moment[0])
    with TestClient(app, headers={"Authorization": "Bearer " + TOKEN}) as client:
        yield client, app, moment


def records(store, session):
    exported = store.export_session(session)
    exported.pop("exportedAt")
    return exported


def require_ok(response):
    assert 200 <= response.status_code < 300, response.text
    return response.json()


def make_demo(lab, identity="test"):
    client, app, moment = lab
    return require_ok(client.post("/api/v1/control/demo", json={"requestId": identity}))


def start_demo(lab, identity="test"):
    client, app, moment = lab
    ids = make_demo(lab, identity)
    state = app.state.dispatcher.snapshot()
    require_ok(client.post("/api/v1/control/commands", json={"commandId": identity + "-start", "action": "start",
        "sessionId": ids["session"], "expectedStateVersion": state["stateVersion"]}))
    checkpoint(lab, ids)
    return ids


def checkpoint(lab, ids, **changes):
    client, app, moment = lab
    state = app.state.dispatcher.snapshot()
    payload = {"eventId": "checkpoint-" + str(state["stateVersion"]), "sessionId": ids["session"],
        "cycleId": ids["cycle"], "objectId": ids["object"], "phase": "object_ready",
        "conditions": {"workspace_ready": True, "object_visible": True}, "frameIds": [ids["frame"]],
        "expectedStateVersion": state["stateVersion"]}
    payload.update(changes)
    return client.post("/api/v1/control/checkpoints", json=payload)


def dispatch_body(lab, ids, identity="execution"):
    client, app, moment = lab
    state = app.state.dispatcher.snapshot()
    return {"requestId": identity + "-request", "executionId": identity, "sessionId": ids["session"],
        "cycleId": ids["cycle"], "objectId": ids["object"], "attemptId": ids["attempt"], "taskId": "pick",
        "expectedStateVersion": state["stateVersion"], "expectedGoalVersion": state["goalVersion"],
        "frameIds": [ids["frame"]], "deadlineAt": (moment[0] + timedelta(seconds=5)).isoformat()}


def test_creation_read_refresh_and_policy_never_seed_records(lab):
    client, app, moment = lab
    before = app.state.store.latest_sequence()
    for path in ("/api/v1/control/snapshot", "/api/v1/control/policy", "/api/v1/control/decision-context",
                 "/api/v1/control/journal", "/api/v1/lab/providers", "/api/v1/lab/voice/options"):
        assert client.get(path).status_code == 200
    assert app.state.store.list_records("session") == []
    assert app.state.store.latest_sequence() == before == 0
    assert app.state.dispatcher.adapter.submissions == []
    state = client.get("/api/v1/control/snapshot").json()
    assert state["sourceMode"] == "simulation"
    assert state["mode"] == "stopped"
    assert state["hardwareIntegrated"] is False
    assert client.get("/lab").status_code == 404
    for path in ("/api/v1/commands", "/api/v1/voice/token", "/api/v1/voice/utterances"):
        assert client.post(path, json={}).status_code == 503


def test_every_installed_control_voice_and_provider_route_requires_authentication(lab):
    client, app, moment = lab
    checked = []
    for route in app.routes:
        if not route.path.startswith(("/api/v1/control", "/api/v1/lab")):
            continue
        path = re.sub(r"\{[^}]+\}", "missing", route.path)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            response = client.request(method, path, headers={"Authorization": "Bearer invalid"},
                                      **({"json": {}} if method == "POST" else {}))
            assert response.status_code == 401, (method, path, response.text)
            checked.append((method, path))
    assert any("/voice/token" in path for _, path in checked)
    assert len(checked) >= 19
    assert app.state.store.latest_sequence() == 0
    assert app.state.dispatcher.export_journal()["executions"] == []
    assert client.get("/api/v1/control/snapshot", headers={"Host": "attacker.example"}).status_code == 400


def test_demo_retry_after_partial_save_is_complete_idempotent_and_simulated(lab, monkeypatch):
    client, app, moment = lab
    original = app.state.store.put_evidence
    def fail_upload(_body):
        raise StoreError(503, "Temporary fixture upload failure")
    monkeypatch.setattr(app.state.store, "put_evidence", fail_upload)
    assert client.post("/api/v1/control/demo", json={"requestId": "partial"}).status_code == 503
    assert len(app.state.store.list_records("session")) == 1
    assert len(app.state.store.list_records("attempt")) == 1
    assert app.state.store.list_records("frame") == []
    moment[0] += timedelta(seconds=1)
    monkeypatch.setattr(app.state.store, "put_evidence", original)
    ids = make_demo(lab, "partial")
    assert ids["duplicate"] is True
    assert app.state.store.get("session", ids["session"])["sourceMode"] == "simulation"
    assert len(app.state.store.list_records("session")) == 1
    assert len(app.state.store.list_records("cycle")) == 1
    assert len(app.state.store.list_records("attempt")) == 1
    assert len(app.state.store.list_records("frame")) == 1
    before = records(app.state.store, ids["session"])
    assert make_demo(lab, "partial")["duplicate"] is True
    assert records(app.state.store, ids["session"]) == before
    assert app.state.dispatcher.adapter.submissions == []


def test_control_http_lifecycle_preserves_attempts_and_unknown_physical_outcome(lab):
    client, app, moment = lab
    ids = start_demo(lab)
    before = records(app.state.store, ids["session"])
    request = dispatch_body(lab, ids)
    result = require_ok(client.post("/api/v1/control/dispatch", json=request))
    assert result["accepted"] is True
    assert result["execution"]["status"] == "requested"
    assert require_ok(client.post("/api/v1/control/dispatch", json=request))["duplicate"] is True
    assert len(app.state.dispatcher.adapter.submissions) == 1
    assert client.post("/api/v1/control/executions/execution/finish", json={"success": True}).status_code == 409
    assert require_ok(client.post("/api/v1/control/executions/execution/acknowledge"))["execution"]["status"] == "acknowledged"
    result = require_ok(client.post("/api/v1/control/executions/execution/finish", json={"success": True}))
    assert result["execution"]["status"] == "finished"
    assert result["execution"]["physicalOutcome"] == "unverified"
    assert require_ok(client.post("/api/v1/control/executions/execution/finish", json={"success": True}))["duplicate"] is True
    assert client.post("/api/v1/control/executions/execution/finish", json={"success": False}).status_code == 409
    assert records(app.state.store, ids["session"]) == before
    assert app.state.store.get("cycle", ids["cycle"])["outcome"] == "in_progress"
    assert app.state.store.get("attempt", ids["attempt"])["outcome"] == "in_progress"


@pytest.mark.parametrize("acknowledged", [False, True])
def test_http_restart_retains_uncertainty_and_repeated_request_never_reexecutes(lab, acknowledged):
    client, app, moment = lab
    ids = start_demo(lab)
    request = dispatch_body(lab, ids)
    require_ok(client.post("/api/v1/control/dispatch", json=request))
    if acknowledged:
        require_ok(client.post("/api/v1/control/executions/execution/acknowledge"))
    before = records(app.state.store, ids["session"])
    reopened = create_control_app(app.state.store.db_path, TOKEN, clock=lambda: moment[0])
    with TestClient(reopened, headers={"Authorization": "Bearer " + TOKEN}) as next_client:
        state = require_ok(next_client.get("/api/v1/control/snapshot"))
        assert state["mode"] == "reconciliation_required"
        result = require_ok(next_client.post("/api/v1/control/dispatch", json=request))
        assert result["duplicate"] is True
        assert result["execution"]["status"] == "reconciliation_required"
        assert next_client.post("/api/v1/control/dispatch", json={**request, "taskId": "hold"}).status_code == 409
        assert reopened.state.dispatcher.adapter.submissions == []
        result = require_ok(next_client.post("/api/v1/control/executions/execution/reconcile", json={
            "status": "unverified", "authorId": "test-operator", "reason": "Simulated restart cannot establish completion"}))
        assert result["execution"]["physicalOutcome"] == "unverified"
        assert records(reopened.state.store, ids["session"]) == before
    assert len(app.state.dispatcher.adapter.submissions) == 1


def test_live_sessions_and_cross_session_checkpoints_are_rejected(lab):
    client, app, moment = lab
    require_ok(client.post("/api/v1/sessions", json={"eventId": "live-create", "session": {
        "id": "live-session", "name": "Live unavailable", "sourceMode": "live",
        "startedAt": moment[0].isoformat(), "configId": "live-config"}}))
    response = client.post("/api/v1/control/commands", json={"commandId": "live-start", "action": "start",
        "sessionId": "live-session", "expectedStateVersion": 0})
    assert response.status_code == 409
    ids = start_demo(lab)
    wrong = {"eventId": "wrong-checkpoint", "sessionId": "live-session", "cycleId": ids["cycle"],
        "objectId": ids["object"], "phase": "object_ready", "conditions": {}, "frameIds": [ids["frame"]],
        "expectedStateVersion": app.state.dispatcher.snapshot()["stateVersion"]}
    assert client.post("/api/v1/control/checkpoints", json=wrong).status_code == 409
    assert app.state.dispatcher.adapter.submissions == []


def test_refresh_frame_retry_keeps_one_image_and_frame(lab, monkeypatch):
    client, app, moment = lab
    ids = start_demo(lab)
    payload = {"requestId": "fresh", "sessionId": ids["session"], "cycleId": ids["cycle"]}
    original = app.state.store.upsert
    def fail_frame(body):
        if body.recordType == "frame":
            raise StoreError(503, "Temporary frame persistence failure")
        return original(body)
    monkeypatch.setattr(app.state.store, "upsert", fail_frame)
    assert client.post("/api/v1/control/demo-frame", json=payload).status_code == 503
    image = app.state.store.get("evidence", "fresh:image")
    moment[0] += timedelta(seconds=1)
    monkeypatch.setattr(app.state.store, "upsert", original)
    result = require_ok(client.post("/api/v1/control/demo-frame", json=payload))
    assert result["frame"] == "fresh:frame"
    assert app.state.store.get("frame", "fresh:frame")["capturedAt"] == image["capturedAt"]
    before = records(app.state.store, ids["session"])
    assert require_ok(client.post("/api/v1/control/demo-frame", json=payload))["duplicate"] is True
    assert records(app.state.store, ids["session"]) == before


def test_missing_scribe_credential_stays_explicit_without_canonical_or_control_changes(lab):
    client, app, moment = lab
    ids = start_demo(lab)
    before = records(app.state.store, ids["session"])
    state = app.state.dispatcher.snapshot()
    result = client.post("/api/v1/lab/voice/token")
    assert result.status_code == 503
    assert result.json()["code"] == "missing_credential"
    assert records(app.state.store, ids["session"]) == before
    assert app.state.dispatcher.snapshot() == state
    assert app.state.dispatcher.adapter.submissions == []
