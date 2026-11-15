"""Authenticated provider routes over saved simulation: selections never move the arm."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from morph_station import control_api
from morph_station.control_api import create_control_app
from morph_station.models import RecordWrite
from morph_station.providers import ProviderService
from test_control_api import start_demo, require_ok
from test_providers import Transport, choice_reply


TOKEN = "provider-api-test-only-" + "x" * 40
PREFIX = "/api/v1/lab/providers"


@pytest.mark.parametrize("config_available", [False, True])
def test_local_provider_loader_excludes_ordinary_environment_values(monkeypatch, config_available):
    environment = {"GEMINI_API_KEY": "env-google-secret", "ELEVENLABS_API_KEY": "",
                   "ORDINARY_NUMBER": "1", "ORDINARY_WORD": "cat"}
    configuration = {"GEMINI_API_KEY": "file-google-secret", "GOOGLE_API_KEY": "file-alt-secret",
                     "VERDA_INFERENCE_KEY": "file-verda-secret", "ELEVENLABS_API_KEY": "file-eleven-secret",
                     "ORDINARY_NUMBER": "0", "ORDINARY_WORD": "dog"}
    loaded = []
    loader = SimpleNamespace(exec_module=lambda module: loaded.append(True))
    module = SimpleNamespace(load_config=lambda: configuration)
    monkeypatch.setattr(control_api.os, "environ", environment)
    monkeypatch.setattr(control_api.Path, "is_file", lambda path: config_available)
    monkeypatch.setattr(control_api.importlib.util, "spec_from_file_location",
                        lambda name, path: SimpleNamespace(loader=loader))
    monkeypatch.setattr(control_api.importlib.util, "module_from_spec", lambda spec: module)
    result = control_api.local_provider_keys()
    expected = {"GEMINI_API_KEY": "env-google-secret"}
    if config_available:
        expected.update(GOOGLE_API_KEY="file-alt-secret", VERDA_INFERENCE_KEY="file-verda-secret")
    assert result == expected
    assert loaded == ([True] if config_available else [])


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setattr("morph_station.control_api.local_provider_keys", lambda: {})
    moment = [datetime(2026, 11, 14, 21, tzinfo=timezone.utc)]
    app = create_control_app(tmp_path / "provider-lab.sqlite3", TOKEN, clock=lambda: moment[0])
    transport = Transport()
    app.state.providers = ProviderService(app.state.store, app.state.dispatcher,
        credentials={"GEMINI_API_KEY": "google-test-secret", "VERDA_INFERENCE_KEY": "verda-test-secret"},
        transport=transport)
    with TestClient(app, headers={"Authorization": "Bearer " + TOKEN}) as client:
        yield client, app, moment


def observation_body(ids, identity="observe"):
    return {"requestId": identity, "sessionId": ids["session"], "cycleId": ids["cycle"], "frameId": ids["frame"]}


def selection_body(lab, ids, observations=(), identity="select"):
    state = lab[1].state.dispatcher.snapshot()
    return {"requestId": identity, "sessionId": ids["session"], "expectedStateVersion": state["stateVersion"],
            "expectedGoalVersion": state["goalVersion"], "observationRunIds": list(observations)}


def explicit_dispatch(receipt, identity="execute"):
    return {"requestId": identity + "-request", "executionId": identity,
        "sessionId": receipt["sessionId"], "cycleId": receipt["cycleId"], "objectId": receipt["objectId"],
        "attemptId": receipt["attemptId"], "taskId": receipt["selectedChoice"], "decisionId": receipt["decisionId"],
        "expectedStateVersion": receipt["stateVersion"], "expectedGoalVersion": receipt["goalVersion"],
        "frameIds": receipt["frameIds"], "deadlineAt": receipt["deadlineAt"]}


def outcomes(app, session):
    return {kind: app.state.store.list_records(kind, session)
        for kind in ("cycle", "attempt", "inspection", "reference_label", "confirmation", "execution")}


def put_utterance(lab, ids, status="finalized", identity="speech"):
    client, app, moment = lab
    return app.state.store.upsert(RecordWrite(eventId=identity + "-create", recordType="utterance", record={
        "id": identity, "sessionId": ids["session"], "cycleId": ids["cycle"], "source": "typed",
        "text": "Inspect the object more closely.", "status": status,
        "startedAt": moment[0], "completedAt": moment[0]}))["record"]


def goal_body(lab, ids, identity="select-goal"):
    body = selection_body(lab, ids, identity=identity)
    body.pop("observationRunIds")
    return {**body, "utteranceId": "speech"}


def goal_commit(receipt, ids, identity="commit-goal", **changes):
    return {"requestId": identity, "sessionId": ids["session"], "goalId": receipt["selectedChoice"],
        "utteranceId": "speech", "decisionId": receipt["decisionId"],
        "expectedStateVersion": receipt["stateVersion"], "expectedGoalVersion": receipt["goalVersion"], **changes}


def test_all_provider_routes_require_authentication_before_any_side_effect(lab):
    client, app, _ = lab
    before = app.state.store.latest_sequence()
    for suffix in ("/observe", "/select-task", "/select-goal"):
        response = client.post(PREFIX + suffix, json={}, headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401, response.text
    assert client.get(PREFIX + "/requests/missing", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get(PREFIX + "/requests/missing").status_code == 404
    assert app.state.store.latest_sequence() == before == 0
    assert app.state.providers.transport.calls == []
    assert app.state.dispatcher.adapter.submissions == []


def test_observation_and_task_routes_preserve_outcomes_until_explicit_dispatch(lab):
    client, app, _ = lab
    ids = start_demo(lab)
    before = outcomes(app, ids["session"])
    observed = require_ok(client.post(PREFIX + "/observe", json=observation_body(ids)))
    selected = require_ok(client.post(PREFIX + "/select-task",
        json=selection_body(lab, ids, [observed["modelRunId"]])))
    assert observed["accepted"] and selected["accepted"]
    assert selected["selectedChoice"] == "pick"
    assert app.state.dispatcher.adapter.submissions == []
    assert outcomes(app, ids["session"]) == before
    assert require_ok(client.get(PREFIX + "/requests/select"))["decisionId"] == selected["decisionId"]
    body = explicit_dispatch(selected)
    execution = require_ok(client.post("/api/v1/control/dispatch", json=body))
    assert execution["accepted"] and execution["execution"]["status"] == "requested"
    assert execution["execution"]["physicalOutcome"] == "unverified"
    assert len(app.state.dispatcher.adapter.submissions) == 1
    repeated = require_ok(client.post("/api/v1/control/dispatch", json=body))
    assert repeated["duplicate"] and len(app.state.dispatcher.adapter.submissions) == 1


def test_retries_and_receipt_reads_do_not_repeat_provider_requests(lab):
    client, app, _ = lab
    ids = start_demo(lab)
    body = observation_body(ids)
    first = require_ok(client.post(PREFIX + "/observe", json=body))
    before = app.state.store.latest_sequence()
    for _ in range(3):
        assert require_ok(client.post(PREFIX + "/observe", json=body))["duplicate"]
        assert require_ok(client.get(PREFIX + "/requests/observe"))["modelRunId"] == first["modelRunId"]
    assert app.state.store.latest_sequence() == before
    assert len(app.state.providers.transport.calls) == 1
    assert client.post(PREFIX + "/observe", json={**body, "frameId": "different-frame"}).status_code == 409
    assert len(app.state.providers.transport.calls) == 1


def test_browser_cannot_supply_arbitrary_image_bytes_endpoint_or_choices(lab):
    client, app, _ = lab
    ids = start_demo(lab)
    for extra in ({"image": "untrusted bytes"}, {"endpoint": "https://untrusted.invalid"}):
        assert client.post(PREFIX + "/observe", json={**observation_body(ids), **extra}).status_code == 422
    assert client.post(PREFIX + "/select-task", json={**selection_body(lab, ids), "choices": ["invented"]}).status_code == 422
    assert app.state.providers.transport.calls == []


def test_original_decision_deadline_cannot_be_extended_by_http_client(lab):
    client, app, moment = lab
    ids = start_demo(lab)
    selected = require_ok(client.post(PREFIX + "/select-task", json=selection_body(lab, ids)))
    body = explicit_dispatch(selected)
    body["deadlineAt"] = (datetime.fromisoformat(selected["deadlineAt"].replace("Z", "+00:00")) + timedelta(seconds=1)).isoformat()
    rejected = require_ok(client.post("/api/v1/control/dispatch", json=body))
    assert not rejected["accepted"]
    assert app.state.dispatcher.adapter.submissions == []
    # Once the original deadline is gone, no refreshed deadline revives the selection.
    moment[0] += timedelta(seconds=31)
    body.update(requestId="expired-request", executionId="expired", deadlineAt=(moment[0] + timedelta(seconds=1)).isoformat())
    expired = require_ok(client.post("/api/v1/control/dispatch", json=body))
    assert not expired["accepted"] and app.state.dispatcher.adapter.submissions == []


def test_provider_response_after_operator_state_change_is_rejected(lab):
    client, app, _ = lab
    ids = start_demo(lab)
    def pause():
        state = app.state.dispatcher.snapshot()
        from morph_station.dispatcher import ControlRequest
        app.state.dispatcher.control(ControlRequest(commandId="pause-during-call", action="pause_after_cycle",
            sessionId=ids["session"], expectedStateVersion=state["stateVersion"]))
    app.state.providers.transport.callback = pause
    result = require_ok(client.post(PREFIX + "/select-task", json=selection_body(lab, ids)))
    assert not result["accepted"] and result["error"] == "stale_dispatcher_state"
    assert result["fallback"] == "hold"
    assert app.state.dispatcher.adapter.submissions == []


def test_goal_requires_finalized_utterance_then_explicit_bound_commit(lab):
    client, app, _ = lab
    ids = start_demo(lab)
    speech = put_utterance(lab, ids, status="partial")
    body = goal_body(lab, ids)
    assert client.post(PREFIX + "/select-goal", json=body).status_code == 409
    assert app.state.providers.transport.calls == []
    app.state.store.upsert(RecordWrite(eventId="speech-final", recordType="utterance", expectedRevision=speech["revision"],
        record={**speech, "status": "finalized"}))
    app.state.providers.transport.reply = choice_reply(["inspect_more", "sort", "unsupported"], "inspect_more", "goal")
    state = app.state.dispatcher.snapshot()
    selected = require_ok(client.post(PREFIX + "/select-goal", json=body))
    assert selected["accepted"] and selected["selectedChoice"] == "inspect_more"
    assert app.state.dispatcher.snapshot() == state and app.state.dispatcher.adapter.submissions == []
    assert require_ok(client.post(PREFIX + "/select-goal", json=body))["duplicate"]
    assert len(app.state.providers.transport.calls) == 1
    commit = goal_commit(selected, ids)
    result = require_ok(client.post("/api/v1/control/goals", json=commit))
    assert result["accepted"] and result["goalStatus"] == "active"
    assert result["state"]["goalId"] == "inspect_more"
    assert result["state"]["goalVersion"] == state["goalVersion"] + 1
    assert require_ok(client.post("/api/v1/control/goals", json=commit))["duplicate"]
    assert app.state.dispatcher.adapter.submissions == []


def test_goal_commit_cannot_substitute_choice_or_reuse_expired_receipt(lab):
    client, app, moment = lab
    ids = start_demo(lab)
    put_utterance(lab, ids)
    app.state.providers.transport.reply = choice_reply(["inspect_more", "sort", "unsupported"], "inspect_more", "goal")
    selected = require_ok(client.post(PREFIX + "/select-goal", json=goal_body(lab, ids)))
    before = app.state.dispatcher.snapshot()
    substituted = goal_commit(selected, ids, goalId="sort")
    assert client.post("/api/v1/control/goals", json=substituted).status_code == 409
    assert app.state.dispatcher.snapshot() == before
    moment[0] += timedelta(seconds=31)
    assert client.post("/api/v1/control/goals", json=goal_commit(selected, ids, identity="expired-goal")).status_code == 409
    assert app.state.dispatcher.snapshot() == before and app.state.dispatcher.adapter.submissions == []
