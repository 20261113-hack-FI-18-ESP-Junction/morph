"""M17/M18: persisted evidence, one-call reservations, typed choices and no motion."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from threading import Event

import pytest
from fastapi.testclient import TestClient

from morph_station.control_api import create_control_app
from morph_station.dispatcher import GoalRequest
from morph_station.providers import (
    DECISIONS_MODEL, DECISIONS_URL, NEMOTRON_MODEL, NEMOTRON_REPORTED_ROOT,
    NEMOTRON_URL, GoalSelectionRequest, NoRedirect, ObservationRequest,
    ProviderFailure, ProviderService, TaskSelectionRequest, load_credentials,
)
from morph_station.models import RecordWrite
from morph_station.store import StoreError
from test_dispatcher import Harness
from test_control_api import checkpoint, require_ok, start_demo


class Transport:
    def __init__(self, reply=None, callback=None):
        self.calls=[]
        self.reply=reply
        self.callback=callback

    def __call__(self,url,headers,payload,timeout):
        self.calls.append({"url":url,"headers":headers,"payload":payload,"timeout":timeout})
        if self.callback:
            self.callback()
        if isinstance(self.reply,BaseException):
            raise self.reply
        if self.reply is not None:
            return self.reply
        if url==NEMOTRON_URL:
            return {"status":200,"body":{"model":NEMOTRON_MODEL,"choices":[{"message":{"content":"A red block is visible."}}]}}
        kind=next(iter(payload["questions"]))
        choices=payload["questions"][kind]["criteria"]
        selected="pick" if "pick" in choices else "sort"
        return choice_reply(list(choices),selected,kind)


def choice_reply(choices=("inspect","pick","hold"),selected="pick",kind="task"):
    return {"status":200,"body":{"answers":{kind:{"type":"choice","choice":selected,
        "probabilities":{choice:1.0 if choice==selected else 0.0 for choice in choices},"confidence":1.0}},
        "usage":{"total_output_tokens":0,"total_input_tokens":100}}}


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path).start()


def service(h,transport=None,**kwargs):
    return ProviderService(h.store,h.engine,credentials={"GEMINI_API_KEY":"google-test-secret","VERDA_INFERENCE_KEY":"verda-test-secret"},
        transport=transport or Transport(),**kwargs)


def observe(request_id="observe",frame="frame",cycle="cycle"):
    return ObservationRequest(requestId=request_id,sessionId="session",cycleId=cycle,frameId=frame)


def task(h,request_id="select",observations=()):
    state=h.engine.snapshot()
    return TaskSelectionRequest(requestId=request_id,sessionId="session",expectedStateVersion=state["stateVersion"],
        expectedGoalVersion=state["goalVersion"],observationRunIds=list(observations))


def canonical_outcomes(h):
    return {kind:h.store.list_records(kind,"session") for kind in ("cycle","attempt","inspection","confirmation","reference_label","execution")}


def test_observation_uses_exact_blob_and_keeps_outcomes_separate(h):
    transport=Transport()
    provider=service(h,transport)
    before=canonical_outcomes(h)
    result=provider.observe(observe())
    assert result["accepted"] and result["status"]=="completed"
    assert result["decisionId"] is None
    run=h.store.get("model_run",result["modelRunId"])
    assert run["frameIds"]==["frame"]
    assert run["cycleId"]=="cycle" and run["input"]["image"]["objectId"]=="brick"
    assert run["output"]["reportedDeploymentRoot"]==NEMOTRON_REPORTED_ROOT
    assert run["output"]["requestedModel"]==run["output"]["returnedModel"]==NEMOTRON_MODEL
    image_url=transport.calls[0]["payload"]["messages"][0]["content"][1]["image_url"]["url"]
    raw=base64.b64decode(image_url.split(",",1)[1])
    assert hashlib.sha256(raw).hexdigest()==run["input"]["image"]["sha256"]
    assert transport.calls[0]["url"]==NEMOTRON_URL
    assert h.adapter.submissions==[] and canonical_outcomes(h)==before
    assert "test-secret" not in json.dumps(h.store.export_session("session"))


def test_observation_duplicate_and_conflict_never_recall_provider(h):
    t=Transport(); p=service(h,t)
    first=p.observe(observe())
    again=service(h,t).observe(observe())
    assert again["modelRunId"]==first["modelRunId"] and again["duplicate"]
    h.frame("other-frame")
    with pytest.raises(StoreError,match="reused"):
        p.observe(observe(frame="other-frame"))
    assert len(t.calls)==1 and len(h.store.list_records("model_run"))==1


def test_request_identity_is_shared_between_operation_kinds(h):
    t=Transport();p=service(h,t)
    p.observe(observe("same"))
    with pytest.raises(StoreError,match="reused"):
        p.select_task(task(h,"same"))
    assert len(t.calls)==1


def test_mismatched_cycle_and_tampered_blob_prevent_call(h):
    t=Transport();p=service(h,t)
    h.put("cycle",{"id":"other","sessionId":"session","objectId":"other-brick","startedAt":h.stamp()})
    with pytest.raises(StoreError,match="different"):
        p.observe(observe(cycle="other"))
    path,_=h.store.evidence_file("frame-image")
    path.write_bytes(b"tampered")
    with pytest.raises(StoreError,match="integrity"):
        p.observe(observe())
    assert t.calls==[] and h.store.list_records("model_run")==[]


def test_live_evidence_is_not_silently_treated_as_simulation(tmp_path):
    h=Harness(tmp_path,source="live");t=Transport();p=service(h,t)
    with pytest.raises(StoreError,match="simulated"):
        p.observe(observe())
    assert t.calls==[]


@pytest.mark.parametrize("reply,category",[
    ({"status":429,"body":{"error":{"message":"rate limited"}}},"quota_or_rate_limit"),
    ({"status":503,"body":{}},"http_error"),
    ({"status":302,"body":{}},"redirect_rejected"),
    ({"status":200,"body":"html"},"malformed_response"),
    ({"status":200,"body":{"model":"other-model","choices":[]}},"unexpected_model"),
    ({"status":200,"body":{"model":NEMOTRON_MODEL,"choices":[]}},"malformed_observation"),
    (TimeoutError("must not store private exception"),"timeout"),
    (RuntimeError("google-test-secret must never leak"),"transport_error"),
])
def test_provider_failures_persist_once_and_repeated_requests_do_not_retry(h,reply,category):
    t=Transport(reply);p=service(h,t)
    first=p.observe(observe())
    assert first["error"]==category and first["fallback"]=="hold" and not first["accepted"]
    assert p.observe(observe())["duplicate"] and len(t.calls)==1
    run=h.store.get("model_run",first["modelRunId"])
    assert run["completedAt"] and run["error"]==category
    assert "test-secret" not in json.dumps(run)
    assert "private exception" not in json.dumps(run)


def test_missing_credential_is_saved_without_network(h):
    t=Transport();p=ProviderService(h.store,h.engine,credentials={},transport=t)
    result=p.observe(observe())
    assert result["error"]=="missing_credential" and t.calls==[]


def test_partial_reservation_survives_restart_and_blocks_duplicate_network(h):
    class Crash(BaseException): pass
    entered=Event();release=Event()
    def callback():
        entered.set();release.wait(2)
        raise Crash()
    t=Transport(callback=callback);p=service(h,t)
    with ThreadPoolExecutor(max_workers=2) as pool:
        original=pool.submit(p.observe,observe())
        assert entered.wait(2)
        prior=service(h,t).observe(observe())
        assert prior["status"]=="uncertain" and not prior["retryAllowed"] and prior["duplicate"]
        release.set()
        with pytest.raises(Crash): original.result()
    after=service(h,t).observe(observe())
    assert after["status"]=="uncertain" and len(t.calls)==1
    run=h.store.get("model_run",after["modelRunId"])
    assert run["completedAt"] is None


def test_task_choice_uses_current_menu_saved_observation_and_never_dispatches(h):
    t=Transport();p=service(h,t);before=canonical_outcomes(h)
    observed=p.observe(observe())
    selected=p.select_task(task(h,observations=[observed["modelRunId"]]))
    assert selected["accepted"] and selected["selectedChoice"]=="pick"
    assert selected["deadlineAt"] and selected["attemptId"]=="attempt"
    assert selected["frameIds"]==["frame"]
    decision=h.store.get("decision",selected["decisionId"])
    assert decision["offeredChoices"]==["inspect","pick","hold"] and decision["accepted"]
    assert decision["stateVersion"]==h.engine.snapshot()["stateVersion"]
    call=t.calls[-1]
    assert call["url"]==DECISIONS_URL and call["payload"]["model"]==DECISIONS_MODEL
    inputs=json.loads(call["payload"]["input"])
    assert inputs["observations"][0]["modelRunId"]==observed["modelRunId"]
    assert inputs["frames"][0]["sha256"]==h.store.get("evidence","frame-image")["sha256"]
    assert h.adapter.submissions==[] and canonical_outcomes(h)==before
    assert p.select_task(task(h,observations=[observed["modelRunId"]]))["duplicate"] and len(t.calls)==2
    assert p.get_request("select")["decisionId"]==selected["decisionId"]
    assert p.get_decision_receipt(selected["decisionId"])["deadlineAt"]==selected["deadlineAt"]


def test_observation_for_a_different_frame_cannot_enter_choice_context(h):
    t=Transport();p=service(h,t);h.frame("other-frame")
    other=p.observe(observe(frame="other-frame"))
    with pytest.raises(StoreError,match="current valid frame"):
        p.select_task(task(h,observations=[other["modelRunId"]]))
    assert len(t.calls)==1


def test_stale_requested_version_is_rejected_before_reservation(h):
    t=Transport();p=service(h,t);request=task(h)
    h.control("pause_after_cycle")
    with pytest.raises(StoreError,match="stale"):
        p.select_task(request)
    assert t.calls==[] and h.store.list_records("model_run")==[]


def test_state_change_while_cloud_waits_persists_rejected_selection(h):
    t=Transport(callback=lambda:h.control("pause_after_cycle"));p=service(h,t)
    result=p.select_task(task(h))
    assert result["error"]=="stale_dispatcher_state" and result["selectedChoice"]=="pick"
    assert result["fallback"]=="hold" and not result["accepted"]
    assert h.store.get("decision",result["decisionId"])["accepted"] is False
    assert h.adapter.submissions==[]


def test_cloud_response_after_deadline_cannot_be_accepted(h):
    def delay(): h.time+=timedelta(seconds=10)
    t=Transport(callback=delay);p=service(h,t)
    result=p.select_task(task(h))
    assert result["error"]=="decision_deadline_expired" and not result["accepted"]


def test_expired_frame_during_cloud_wait_is_rejected(h):
    def delay(): h.time+=timedelta(milliseconds=1100)
    result=service(h,Transport(callback=delay)).select_task(task(h))
    assert result["error"]=="stale_frame_evidence" and not result["accepted"]


@pytest.mark.parametrize("mutation",["unsupported","bad_probabilities","generated_tokens","other_model","nan"])
def test_invalid_fixed_choice_preserves_raw_response_but_records_local_hold(h,mutation):
    reply=choice_reply()
    answer=reply["body"]["answers"]["task"]
    if mutation=="unsupported":answer["choice"]="invented_joint_command"
    elif mutation=="bad_probabilities":answer["probabilities"]={"pick":1.0}
    elif mutation=="generated_tokens":reply["body"]["usage"]["total_output_tokens"]=7
    elif mutation=="other_model":reply["body"]["model"]="gemini-generative-model"
    else:answer["confidence"]=float("nan")
    t=Transport(reply);p=service(h,t)
    result=p.select_task(task(h))
    assert not result["accepted"] and result["selectedChoice"]=="hold" and result["fallback"]=="hold"
    decision=h.store.get("decision",result["decisionId"])
    assert decision["selectedChoice"]=="hold" and not decision["accepted"]
    assert p.select_task(task(h))["duplicate"] and len(t.calls)==1


def test_no_permitted_task_records_local_fallback_without_cloud(h):
    h.checkpoint(conditions={"workspace_ready":False})
    t=Transport();result=service(h,t).select_task(task(h))
    assert result["error"]=="no_permitted_tasks" and result["selectedChoice"]=="hold"
    assert t.calls==[]


def test_provider_hold_is_not_motion(h):
    result=service(h,Transport(choice_reply(selected="hold"))).select_task(task(h))
    assert not result["accepted"] and result["error"]=="provider_selected_fallback"
    assert h.adapter.submissions==[]


def test_goal_selection_only_reads_finalized_utterance_and_does_not_commit(h):
    h.put("utterance",{"id":"speech","sessionId":"session","cycleId":"cycle","text":"Sort the bricks.","source":"typed",
        "startedAt":h.stamp(),"completedAt":h.stamp(),"status":"partial"})
    state=h.engine.snapshot()
    request=GoalSelectionRequest(requestId="goal",sessionId="session",utteranceId="speech",
        expectedStateVersion=state["stateVersion"],expectedGoalVersion=state["goalVersion"])
    t=Transport();p=service(h,t)
    with pytest.raises(StoreError,match="finalized"):
        p.select_goal(request)
    utterance=h.store.get("utterance","speech")
    h.put("utterance",{**utterance,"status":"finalized"})
    result=p.select_goal(request)
    assert result["accepted"] and result["selectedChoice"]=="sort"
    assert h.store.get("decision",result["decisionId"])["kind"]=="goal"
    assert h.engine.snapshot()==state and h.adapter.submissions==[]
    assert len(t.calls)==1


@pytest.mark.parametrize("goal_id", ["sort", "inspect_more"])
def test_task_request_describes_goal_and_missing_fulfillment_without_changing_menu(tmp_path, monkeypatch, goal_id):
    monkeypatch.setattr("morph_station.control_api.local_provider_keys", lambda: {})
    moment = [datetime(2026, 11, 15, 1, tzinfo=timezone.utc)]
    token = "goal-criteria-test-token-" + "x" * 40
    app = create_control_app(tmp_path / "criteria.sqlite3", token, clock=lambda: moment[0])
    engine = app.state.dispatcher
    with TestClient(app, headers={"Authorization": "Bearer " + token}) as client:
        lab = client, app, moment
        ids = start_demo(lab)
        require_ok(checkpoint(lab, ids, phase="inspected", conditions={"workspace_ready": True,
            "object_presented": True, "object_held": True, "classification_good": True}))
        if goal_id == "inspect_more":
            state = engine.snapshot()
            engine.select_goal(GoalRequest(requestId="extra-view", sessionId=ids["session"], goalId=goal_id,
                expectedStateVersion=state["stateVersion"], expectedGoalVersion=state["goalVersion"]))
        before = engine.snapshot()
        policy_hash = engine.policy_hash
        offered = ["place_good", "reinspect_other_view", "hold"]
        transport = Transport(choice_reply(offered, "hold"))
        provider = ProviderService(app.state.store, engine, credentials={"GEMINI_API_KEY": "test-only"}, transport=transport)
        result = provider.select_task(TaskSelectionRequest(requestId="described-task", sessionId=ids["session"],
            expectedStateVersion=before["stateVersion"], expectedGoalVersion=before["goalVersion"]))
    payload = transport.calls[0]["payload"]
    context = json.loads(payload["input"])
    criteria = payload["questions"]["task"]["criteria"]
    assert set(criteria) == set(engine.allowed_tasks()) == set(offered)
    assert context["activeGoal"]["id"] == goal_id
    assert context["activeGoal"]["extraInspectionFulfillment"] == "not_tracked"
    assert context["activeGoal"]["automaticGoalConsumptionImplemented"] is False
    assert ("one additional inspection" if goal_id == "inspect_more" else "normal inspection") in context["activeGoal"]["description"]
    assert "execution budget" in criteria["reinspect_other_view"]
    assert "unmet extra-inspection requirement" in criteria["place_good"]
    assert "Never derive defect classification from a Nemotron" in criteria["place_good"]
    assert "fulfillment" in criteria["hold"] and "uncertain" in criteria["hold"]
    assert context["sourceMode"] == "simulation" and context["anomalibMeasurements"] == []
    assert "synthetic lab declarations" in context["evidenceMeaning"]
    assert "no generated arguments or plan" in payload["questions"]["task"]["instructions"]
    assert result["selectedChoice"] == "hold" and result["accepted"] is False
    assert engine.snapshot() == before and engine.policy_hash == policy_hash
    assert engine.adapter.submissions == []


def test_ambiguous_goal_fallback_preserves_descriptive_fixed_choices_without_guessing(h):
    utterance = h.put("utterance", {"id": "ambiguous-speech", "sessionId": "session", "text": "Please continue with object placement.",
        "source": "typed", "startedAt": h.stamp(), "completedAt": h.stamp(), "status": "finalized"})
    state = h.engine.snapshot()
    transport = Transport(choice_reply(["inspect_more", "sort", "unsupported"], "unsupported", "goal"))
    provider = service(h, transport)
    result = provider.select_goal(GoalSelectionRequest(requestId="ambiguous-goal", sessionId="session", utteranceId=utterance["id"],
        expectedStateVersion=state["stateVersion"], expectedGoalVersion=state["goalVersion"]))
    payload = transport.calls[0]["payload"]
    criteria = payload["questions"]["goal"]["criteria"]
    assert set(criteria) == {"sort", "inspect_more", "unsupported"}
    assert "normal inspection and good/defective sorting" in criteria["sort"]
    assert "one additional inspection" in criteria["inspect_more"]
    assert "not continuous or repeated inspection" in criteria["inspect_more"]
    assert "instead of guessing" in criteria["unsupported"]
    assert "do not guess from vague movement or placement wording" in payload["questions"]["goal"]["instructions"]
    context = json.loads(payload["input"])
    assert context["utterance"] == utterance and context["currentGoal"]["id"] == "sort"
    assert result["selectedChoice"] == "unsupported" and result["accepted"] is False and result["fallback"] == "hold"
    assert h.engine.snapshot() == state and h.adapter.submissions == []


def test_credential_response_echo_is_redacted(h):
    reply={"status":200,"body":{"model":NEMOTRON_MODEL,"choices":[{"message":{"content":"google-test-secret"}}],
        "api_key":"verda-test-secret","authorization":"Bearer verda-test-secret"}}
    result=service(h,Transport(reply)).observe(observe())
    exported=json.dumps(h.store.export_session("session"))
    assert "test-secret" not in exported and "[REDACTED]" in exported
    assert result["observation"]=="[REDACTED]"


def test_completed_canonical_run_cannot_be_overwritten_by_late_provider(h):
    def external_completion():
        run=h.store.list_records("model_run")[0]
        h.put("model_run",{**run,"completedAt":h.stamp(),"output":{"prior":"preserve"},"error":"external_completion"})
    t=Transport(callback=external_completion);p=service(h,t)
    with pytest.raises(StoreError,match="completed outside"):
        p.observe(observe())
    prior=h.store.list_records("model_run")[0]
    assert prior["output"]=={"prior":"preserve"}
    assert p.observe(observe())["status"]=="uncertain" and len(t.calls)==1


def test_oversized_and_nonfinite_transport_results_are_bounded(h):
    t=Transport({"status":200,"body":{"content":"x"*1_000_001}})
    result=service(h,t).observe(observe())
    assert result["error"]=="response_too_large"
    assert h.store.get("model_run",result["modelRunId"])["output"]["response"] is None


def test_literal_config_permissions_and_redirect_rejection(tmp_path,monkeypatch):
    for key in ("GEMINI_API_KEY","GOOGLE_API_KEY","VERDA_INFERENCE_KEY"):
        monkeypatch.delenv(key,raising=False)
    config=tmp_path/"providers.env"
    config.write_text("GEMINI_API_KEY='literal$(not-executed)'\n")
    config.chmod(0o600)
    assert load_credentials(config)["GEMINI_API_KEY"]=="literal$(not-executed)"
    config.chmod(0o644)
    with pytest.raises(ValueError,match="owner-only"):load_credentials(config)
    link=tmp_path/"linked.env";link.symlink_to(config)
    with pytest.raises(ValueError,match="symlink"):load_credentials(link)
    with pytest.raises(ProviderFailure,match="redirect_rejected"):
        NoRedirect().redirect_request(None,None,302,"redirect",{},"https://other.invalid")
