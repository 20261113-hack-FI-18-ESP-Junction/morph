"""M12 simulated controls: durable delivery, stale rejection and truthful outcomes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from morph_station.dispatcher import (
    CheckpointRequest, ControlRequest, DispatchRequest, DispatcherPolicy,
    GoalRequest, SimulatedAdapter, SimulationDispatcher, TaskRule, demo_simulation_policy,
)
from morph_station.models import CorrectionRequest, EvidenceUpload, RecordWrite
from morph_station.simulation import PIXEL
from morph_station.store import StationStore, StoreError


def saved_records(store):
    result = store.export_session("session")
    result.pop("exportedAt")
    return result


class Harness:
    def __init__(self, tmp_path, source="simulation"):
        self.time = datetime(2026, 11, 14, 20, tzinfo=timezone.utc)
        self.serial = count(1)
        self.store = StationStore(tmp_path / "records.sqlite3")
        self.put("session", {"id": "session", "sourceMode": source, "name": "M12 simulation",
                             "startedAt": self.stamp(), "configId": "fixture"})
        self.put("cycle", {"id": "cycle", "sessionId": "session", "objectId": "brick", "startedAt": self.stamp()})
        self.put("attempt", {"id": "attempt", "sessionId": "session", "cycleId": "cycle", "ordinal": 1,
                             "startedAt": self.stamp()})
        self.frame("frame")
        rule = TaskRule(policyId="simulated-skill", allowedPhases=["observed"],
                        requiredConditions=["workspace_ready"], nextPhase="picked", maxExecutionsPerCycle=2)
        self.policy = DispatcherPolicy(id="explicit-simulation-policy", tasks={"pick": rule, "inspect": rule},
                                       goalIds=["sort", "inspect_more"], defaultGoalId="sort", maxAttemptsPerCycle=2)
        self.adapter = SimulatedAdapter()
        self.engine = SimulationDispatcher(self.store, self.policy, self.adapter, lambda: self.time)

    def stamp(self):
        return self.time.isoformat()

    def put(self, kind, record):
        data = dict(record)
        revision = data.pop("revision", None)
        return self.store.upsert(RecordWrite(eventId=f"event-{next(self.serial)}", recordType=kind,
                                            record=data, expectedRevision=revision))["record"]

    def frame(self, identity, captured=None, cycle="cycle", object_id="brick", session="session"):
        captured = captured or self.stamp()
        self.store.put_evidence(EvidenceUpload(id=identity + "-image", eventId=identity + "-upload",
            sessionId=session, cycleId=cycle, mediaType="image/png", contentBase64=PIXEL, capturedAt=captured))
        return self.put("frame", {"id": identity, "sessionId": session, "cycleId": cycle, "objectId": object_id,
            "cameraId": "simulation", "capturedAt": captured, "receivedAt": captured, "width": 1, "height": 1,
            "evidenceId": identity + "-image"})

    def control(self, action, **changes):
        return self.engine.control(ControlRequest(commandId=f"command-{next(self.serial)}", action=action,
            sessionId="session", expectedStateVersion=self.engine.snapshot()["stateVersion"], **changes))

    def checkpoint(self, **changes):
        body = dict(eventId=f"checkpoint-{next(self.serial)}", sessionId="session", cycleId="cycle", objectId="brick",
            phase="observed", conditions={"workspace_ready": True}, frameIds=["frame"],
            expectedStateVersion=self.engine.snapshot()["stateVersion"])
        body.update(changes)
        return self.engine.checkpoint(CheckpointRequest(**body))

    def request(self, **changes):
        state = self.engine.snapshot()
        body = dict(requestId=f"request-{next(self.serial)}", executionId=f"execution-{next(self.serial)}",
            sessionId="session", cycleId="cycle", objectId="brick", attemptId="attempt", taskId="pick",
            expectedStateVersion=state["stateVersion"], expectedGoalVersion=state["goalVersion"], frameIds=["frame"],
            deadlineAt=self.time + timedelta(seconds=3))
        body.update(changes)
        return DispatchRequest(**body)

    def start(self):
        self.control("start")
        self.checkpoint()
        return self

    def finish(self, execution_id, success=True):
        self.engine.acknowledge(execution_id)
        return self.engine.finish(execution_id, success)

    def close_cycle_unverified(self):
        attempt = self.store.get("attempt", "attempt")
        self.put("attempt", {**attempt, "outcome": "unverified", "endedAt": self.stamp()})
        cycle = self.store.get("cycle", "cycle")
        self.put("cycle", {**cycle, "outcome": "unverified", "endedAt": self.stamp()})


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path).start()


def test_inert_startup_reads_default_deny_and_live_rejection(tmp_path):
    fixture = Harness(tmp_path / "configured")
    before = saved_records(fixture.store)
    for _ in range(3):
        assert fixture.engine.snapshot()["mode"] == "stopped"
        assert fixture.engine.export_journal()["events"] == []
    assert fixture.adapter.submissions == []
    assert saved_records(fixture.store) == before
    disabled = SimulationDispatcher(StationStore(tmp_path / "disabled.sqlite3"))
    assert disabled.policy.tasks == {}
    fixture.engine = SimulationDispatcher(fixture.store, fixture.policy, fixture.adapter)
    live = Harness(tmp_path / "live", source="live")
    with pytest.raises(StoreError, match="simulated sessions only"):
        live.control("start")
    assert live.adapter.submissions == []


def test_no_configured_tasks_cannot_start(tmp_path):
    fixture = Harness(tmp_path)
    fixture.policy = DispatcherPolicy()
    with fixture.store._connection(write=True) as db:
        db.execute("DELETE FROM dispatch_state")
    fixture.engine = SimulationDispatcher(fixture.store, fixture.policy)
    with pytest.raises(StoreError, match="No approved"):
        fixture.control("start")


def test_lifecycle_preserves_canonical_records_and_no_physical_confirmation(h):
    before = saved_records(h.store)
    request = h.request()
    result = h.engine.dispatch(request)
    assert result["accepted"] is True
    assert result["execution"]["status"] == "requested"
    with pytest.raises(StoreError, match="requires acknowledgment"):
        h.engine.finish(request.executionId, True)
    assert h.engine.acknowledge(request.executionId)["execution"]["status"] == "acknowledged"
    assert h.engine.acknowledge(request.executionId)["duplicate"] is True
    finished = h.engine.finish(request.executionId, True)["execution"]
    assert finished["status"] == "finished"
    assert finished["physicalOutcome"] == "unverified"
    assert finished["confirmationId"] is None
    assert h.engine.finish(request.executionId, True)["duplicate"] is True
    with pytest.raises(StoreError, match="Conflicting repeated completion"):
        h.engine.finish(request.executionId, False)
    assert saved_records(h.store) == before
    assert h.engine.snapshot()["boundaryReady"] is False
    assert h.engine.dispatch(h.request())["accepted"] is False


@pytest.mark.parametrize("change,reason", [
    ({"expectedStateVersion": 0}, "Stale dispatcher"),
    ({"expectedGoalVersion": 0}, "Stale goal"),
    ({"taskId": "cloud_invented_task"}, "not permitted"),
    ({"objectId": "other-brick"}, "scope differs"),
    ({"attemptId": "unknown-attempt"}, "not found"),
    ({"frameIds": ["unknown-frame"]}, "frames differ"),
    ({"sessionId": "unknown-session"}, "not found"),
])
def test_invalid_dispatch_is_persisted_hold_without_adapter_call(h, change, reason):
    before = saved_records(h.store)
    request = h.request(**change)
    result = h.engine.dispatch(request)
    assert result["accepted"] is False
    assert result["fallback"] == "hold"
    assert reason in result["reason"]
    assert h.engine.dispatch(request)["duplicate"] is True
    assert len(h.engine.export_journal()["events"]) == 3
    assert h.adapter.submissions == []
    assert saved_records(h.store) == before


@pytest.mark.parametrize("offset,reason", [(-1, "deadline expired"), (7, "configured window")])
def test_deadlines_are_checked_at_dispatch(h, offset, reason):
    result = h.engine.dispatch(h.request(deadlineAt=h.time + timedelta(seconds=offset)))
    assert result["accepted"] is False
    assert reason in result["reason"]


@pytest.mark.parametrize("age", [-2, 2])
def test_stale_and_future_frames_fail_even_if_checkpoint_is_current(h, age):
    h.frame("aged", captured=(h.time - timedelta(seconds=age)).isoformat())
    h.checkpoint(frameIds=["aged"])
    result = h.engine.dispatch(h.request(frameIds=["aged"]))
    assert result["accepted"] is False
    assert "stale or future" in result["reason"]


def test_conditions_and_phase_are_required_and_checkpoint_scope_is_checked(h):
    h.checkpoint(conditions={"workspace_ready": False})
    assert "precondition" in h.engine.dispatch(h.request())["reason"]
    h.checkpoint(phase="unavailable")
    assert "not permitted" in h.engine.dispatch(h.request())["reason"]
    h.put("cycle", {"id": "other", "sessionId": "session", "objectId": "other-brick", "startedAt": h.stamp()})
    h.frame("other-frame", cycle="other", object_id="other-brick")
    with pytest.raises(StoreError, match="Frame does not belong"):
        h.checkpoint(frameIds=["other-frame"])
    with pytest.raises(ValidationError):
        h.checkpoint(conditions={"workspace_ready": "true"})


@pytest.mark.parametrize("acknowledged", [False, True])
def test_restart_retains_uncertainty_and_never_redispatches(h, acknowledged):
    request = h.request()
    h.engine.dispatch(request)
    if acknowledged:
        h.engine.acknowledge(request.executionId)
    next_adapter = SimulatedAdapter()
    reopened = SimulationDispatcher(h.store, h.policy, next_adapter, lambda: h.time)
    assert reopened.execution(request.executionId)["status"] == "reconciliation_required"
    assert reopened.snapshot()["mode"] == "reconciliation_required"
    result = reopened.dispatch(request)
    assert result["duplicate"] is True
    assert result["execution"]["status"] == "reconciliation_required"
    assert next_adapter.submissions == []
    with pytest.raises(StoreError, match="different payload"):
        reopened.dispatch(request.model_copy(update={"taskId": "inspect"}))
    before = saved_records(h.store)
    reconciled = reopened.reconcile(request.executionId, "unverified", "operator", "Delivery could not be confirmed")
    assert reconciled["execution"]["physicalOutcome"] == "unverified"
    assert reopened.snapshot()["mode"] == "stopped"
    assert reopened.reconcile(request.executionId, "unverified", "operator", "Delivery could not be confirmed")["duplicate"]
    assert saved_records(h.store) == before
    assert next_adapter.submissions == []


def test_delivery_error_is_unknown_and_duplicate_does_not_retry(h):
    h.adapter.failNext = True
    request = h.request()
    result = h.engine.dispatch(request)
    assert result["execution"]["status"] == "reconciliation_required"
    assert result["state"]["mode"] == "reconciliation_required"
    assert h.engine.dispatch(request)["duplicate"] is True
    assert len(h.adapter.submissions) == 1
    assert h.store.get("attempt", "attempt")["outcome"] == "in_progress"


def test_concurrent_duplicate_dispatch_submits_once(h):
    request = h.request()
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: h.engine.dispatch(request), range(10)))
    assert sum(not r["duplicate"] for r in results) == 1
    assert len(h.adapter.submissions) == 1
    assert len(h.engine.list_executions("session")) == 1


def test_competing_requests_cannot_share_one_state_version(h):
    requests = [h.request(), h.request(taskId="inspect")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(h.engine.dispatch, requests))
    assert sum(r["accepted"] for r in results) == 1
    assert len(h.adapter.submissions) == 1


def test_pause_acknowledges_only_after_current_canonical_cycle_finishes(h):
    assert h.control("pause_after_cycle")["state"]["mode"] == "pause_pending"
    request = h.request()
    h.engine.dispatch(request)
    h.finish(request.executionId)
    with pytest.raises(StoreError, match="canonical cycle remains open"):
        h.checkpoint(cycleId=None, objectId=None, phase="idle", frameIds=[], conditions={})
    assert h.engine.snapshot()["mode"] == "pause_pending"
    h.close_cycle_unverified()
    assert h.checkpoint(cycleId=None, objectId=None, phase="idle", frameIds=[], conditions={})["state"]["mode"] == "paused"
    assert h.control("resume")["state"]["mode"] == "running"
    assert h.store.get("cycle", "cycle")["outcome"] == "unverified"


def test_stop_is_idempotent_and_does_not_claim_emergency_or_outcome(h):
    request = h.request()
    h.engine.dispatch(request)
    command = ControlRequest(commandId="stop", action="stop", sessionId="session",
                             expectedStateVersion=h.engine.snapshot()["stateVersion"])
    result = h.engine.control(command)
    assert result["state"]["mode"] == "reconciliation_required"
    assert result["physicalEmergencyStopVerified"] is False
    assert h.engine.control(command)["duplicate"] is True
    assert h.adapter.stopCalls == 1
    assert h.engine.execution(request.executionId)["physicalOutcome"] == "unverified"
    with pytest.raises(StoreError, match="Resume requires"):
        h.control("resume")
    assert h.store.get("attempt", "attempt")["outcome"] == "in_progress"


def test_goal_queues_until_new_checkpoint_and_old_snapshot_is_rejected(h):
    h.put("utterance", {"id": "speech", "sessionId": "session", "text": "Inspect once more",
        "source": "voice", "provider": "simulation", "modelId": "fixture", "status": "finalized",
        "startedAt": h.stamp(), "completedAt": h.stamp()})
    request = h.request()
    h.engine.dispatch(request)
    state = h.engine.snapshot()
    goal = GoalRequest(requestId="goal", sessionId="session", goalId="inspect_more", utteranceId="speech",
        expectedStateVersion=state["stateVersion"], expectedGoalVersion=state["goalVersion"])
    queued = h.engine.select_goal(goal)
    assert queued["goalStatus"] == "queued"
    assert queued["state"]["goalVersion"] == state["goalVersion"]
    assert h.engine.select_goal(goal)["duplicate"] is True
    h.finish(request.executionId)
    assert h.engine.snapshot()["goalId"] == "sort"
    state = h.checkpoint()["state"]
    assert state["goalId"] == "inspect_more"
    assert state["goalVersion"] == goal.expectedGoalVersion + 1
    rejected = h.engine.dispatch(h.request(expectedGoalVersion=goal.expectedGoalVersion))
    assert "Stale goal" in rejected["reason"]
    duplicate_speech = goal.model_copy(update={"requestId": "new-goal", "expectedStateVersion": state["stateVersion"],
                                              "expectedGoalVersion": state["goalVersion"]})
    with pytest.raises(StoreError, match="already used"):
        h.engine.select_goal(duplicate_speech)


def test_two_skills_share_attempt_and_budget_rejects_excess_execution(h):
    before = len(h.store.list_records("attempt", "session", "cycle"))
    for _ in range(2):
        request = h.request(taskId="inspect")
        assert h.engine.dispatch(request)["accepted"]
        h.finish(request.executionId)
        h.checkpoint()
    assert len(h.store.list_records("attempt", "session", "cycle")) == before == 1
    assert "execution budget exhausted" in h.engine.dispatch(h.request(taskId="inspect"))["reason"]


def test_retry_budget_comes_from_persisted_physical_attempts(h):
    prior = "attempt"
    for ordinal in (2, 3):
        attempt = h.store.get("attempt", prior)
        h.put("attempt", {**attempt, "outcome": "failed", "endedAt": h.stamp()})
        identity = f"attempt-{ordinal}"
        h.put("attempt", {"id": identity, "sessionId": "session", "cycleId": "cycle", "ordinal": ordinal,
            "retryOfAttemptId": prior, "retryReason": "Fixture failed grasp", "startedAt": h.stamp()})
        prior = identity
    h.checkpoint()
    result = h.engine.dispatch(h.request(attemptId=prior))
    assert result["accepted"] is False
    assert "attempt budget exhausted" in result["reason"]
    assert len(h.store.list_records("attempt", "session", "cycle")) == 3
    assert h.adapter.submissions == []


def test_late_record_change_is_rechecked_at_dispatch(h):
    h.close_cycle_unverified()
    result = h.engine.dispatch(h.request())
    assert result["accepted"] is False
    assert "Cycle is finished" in result["reason"]


def test_policy_replacement_requires_explicit_reconciliation(h):
    with pytest.raises(StoreError, match="policy changed"):
        SimulationDispatcher(h.store, h.policy.model_copy(update={"maxAttemptsPerCycle": 10}))


def test_invalid_time_and_non_simulated_adapter_cannot_enter_core(h):
    with pytest.raises(ValidationError):
        h.request(deadlineAt="2026-11-14T20:00:01")
    with pytest.raises(ValueError, match="SimulatedAdapter"):
        SimulationDispatcher(h.store, h.policy, object())
    h.engine.clock = lambda: datetime(2026, 11, 14)
    with pytest.raises(ValueError, match="timezone-aware"):
        h.engine.dispatch(h.request())


def test_stale_display_can_stop_but_cannot_resume_or_stop_other_session(h):
    request = h.request()
    h.engine.dispatch(request)
    result = h.engine.control(ControlRequest(commandId="stale-stop", action="stop", sessionId="session", expectedStateVersion=0))
    assert result["accepted"] is True
    assert result["state"]["mode"] == "reconciliation_required"
    h.put("session", {"id": "other-session", "sourceMode": "simulation", "name": "Other",
                       "startedAt": h.stamp(), "configId": "fixture"})
    with pytest.raises(StoreError, match="another active session"):
        h.engine.control(ControlRequest(commandId="other-stop", action="stop", sessionId="other-session", expectedStateVersion=0))
    assert h.adapter.stopCalls == 1


def test_goal_rejects_partial_utterance_and_commits_only_finalized(h):
    utterance = h.put("utterance", {"id": "speech", "sessionId": "session", "text": "Inspect",
        "source": "voice", "provider": "simulation", "modelId": "fixture", "status": "partial",
        "startedAt": h.stamp(), "completedAt": h.stamp()})
    state = h.engine.snapshot()
    goal = GoalRequest(requestId="speech-goal", sessionId="session", goalId="inspect_more", utteranceId="speech",
                       expectedStateVersion=state["stateVersion"], expectedGoalVersion=state["goalVersion"])
    with pytest.raises(StoreError, match="finalized utterance"):
        h.engine.select_goal(goal)
    h.put("utterance", {**utterance, "status": "finalized"})
    result = h.engine.select_goal(goal)
    assert result["goalStatus"] == "active"
    assert result["state"]["goalVersion"] == state["goalVersion"] + 1
    assert h.adapter.submissions == []


def test_recorded_decision_must_match_current_choice_state_and_frames(h):
    state = h.engine.snapshot()
    h.put("model_run", {"id": "decision-run", "sessionId": "session", "cycleId": "cycle", "provider": "simulation",
        "modelId": "fixture-fixed-choice", "requestedAt": h.stamp(), "completedAt": h.stamp(), "frameIds": ["frame"]})
    h.put("decision", {"id": "decision", "sessionId": "session", "cycleId": "cycle", "kind": "task",
        "modelRunId": "decision-run", "offeredChoices": ["pick", "inspect"], "selectedChoice": "inspect",
        "stateVersion": state["stateVersion"], "goalVersion": state["goalVersion"], "frameIds": ["frame"],
        "requestedAt": h.stamp(), "completedAt": h.stamp()})
    result = h.engine.dispatch(h.request(decisionId="decision"))
    assert result["accepted"] is False
    assert "Recorded decision does not match" in result["reason"]
    result = h.engine.dispatch(h.request(taskId="inspect", decisionId="decision"))
    assert result["accepted"] is True


def test_lifecycle_rejects_clock_reversal(h):
    request = h.request()
    h.engine.dispatch(request)
    h.time -= timedelta(seconds=1)
    with pytest.raises(StoreError, match="Clock moved backwards"):
        h.engine.acknowledge(request.executionId)
    assert h.engine.execution(request.executionId)["acknowledgedAt"] is None


def test_demo_policy_is_explicit_unfrozen_and_uses_required_preconditions():
    policy = demo_simulation_policy()
    assert "unfrozen" in policy.id
    assert set(policy.tasks) == {"pick", "present_for_inspection", "reinspect_other_view", "place_good", "place_defective", "hold"}
    assert policy.tasks["pick"].allowedPhases == ["object_ready"]
    assert set(policy.tasks["pick"].requiredConditions) == {"workspace_ready", "object_visible"}
    assert "classification_good" in policy.tasks["place_good"].requiredConditions


def test_read_only_task_menu_uses_exact_dispatch_guards(h):
    before = h.engine.export_journal()
    context = h.engine.decision_context()
    assert context["allowedTaskIds"] == ["pick", "inspect"]
    assert context["attemptId"] == "attempt"
    assert context["state"]["stateVersion"] == h.engine.snapshot()["stateVersion"]
    assert h.engine.export_journal() == before
    h.checkpoint(conditions={"workspace_ready": False})
    assert h.engine.allowed_tasks() == []
    h.checkpoint()
    h.time += timedelta(seconds=2)
    assert h.engine.allowed_tasks() == []
    h.time -= timedelta(seconds=2)
    request = h.request()
    h.engine.dispatch(request)
    assert h.engine.allowed_tasks() == []


def test_second_instance_fences_old_mutations_and_pauses_idle_run(h):
    original = h.engine
    request = h.request()
    newer = SimulationDispatcher(h.store, h.policy, clock=lambda: h.time)
    assert newer.snapshot()["mode"] == "paused"
    assert newer.snapshot()["instanceId"] != original.instance_id
    with pytest.raises(StoreError, match="superseded"):
        original.dispatch(request)
    with pytest.raises(StoreError, match="superseded"):
        h.control("stop")
    assert original.adapter.submissions == []
    assert newer.list_executions() == []


def test_new_process_owns_journal_and_fences_previous_process(h):
    code = """import sys
from morph_station.store import StationStore
from morph_station.dispatcher import SimulationDispatcher, DispatcherPolicy
engine = SimulationDispatcher(StationStore(sys.argv[1]), DispatcherPolicy.model_validate_json(sys.argv[2]))
print(engine.snapshot()['instanceId'])
"""
    result = subprocess.run([sys.executable, "-c", code, str(h.store.db_path), h.policy.model_dump_json()],
                            capture_output=True, text=True, timeout=10, check=True)
    assert result.stdout.strip() != h.engine.instance_id
    with pytest.raises(StoreError, match="superseded"):
        h.engine.dispatch(h.request())
    assert h.adapter.submissions == []


def test_in_memory_policy_mutation_cannot_widen_permissions(h):
    h.engine.policy.maxAttemptsPerCycle = 99
    with pytest.raises(StoreError, match="policy changed in memory"):
        h.engine.dispatch(h.request())
    assert h.adapter.submissions == []


def test_manual_correction_invalidates_checkpoint_even_when_cycle_still_open(h):
    cycle = h.store.get("cycle", "cycle")
    h.store.correct(CorrectionRequest(id="correction", eventId="correction-event", entityType="cycle", entityId="cycle",
        expectedRevision=cycle["revision"], field="commandedDestination", previousValue=None, newValue="good_bin",
        authorId="operator", reason="Simulation review", createdAt=h.stamp()))
    result = h.engine.dispatch(h.request())
    assert result["accepted"] is False
    assert "Checkpoint records changed" in result["reason"]
    h.checkpoint()
    assert h.engine.dispatch(h.request())["accepted"] is True


def test_starting_task_cannot_hide_retry_inside_existing_attempt(tmp_path):
    fixture = Harness(tmp_path)
    fixture.policy.tasks["pick"].startsPhysicalAttempt = True
    with fixture.store._connection(write=True) as db:
        db.execute("DELETE FROM dispatch_state")
    fixture.engine = SimulationDispatcher(fixture.store, fixture.policy, clock=lambda: fixture.time)
    fixture.start()
    request = fixture.request()
    fixture.engine.dispatch(request)
    fixture.finish(request.executionId, success=False)
    fixture.checkpoint()
    assert "new persisted attempt" in fixture.engine.dispatch(fixture.request())["reason"]
    assert len(fixture.store.list_records("attempt", "session", "cycle")) == 1


def test_provider_decision_cannot_extend_its_original_deadline(h):
    state = h.engine.snapshot()
    h.put("model_run", {"id": "provider-run-test", "sessionId": "session", "cycleId": "cycle", "provider": "Google Decisions",
        "modelId": "gemini-decision-1", "requestedAt": h.stamp(), "completedAt": h.stamp(), "frameIds": ["frame"]})
    h.put("decision", {"id": "provider-decision-test", "sessionId": "session", "cycleId": "cycle", "kind": "task",
        "modelRunId": "provider-run-test", "offeredChoices": ["pick"], "selectedChoice": "pick",
        "stateVersion": state["stateVersion"], "goalVersion": state["goalVersion"], "frameIds": ["frame"],
        "requestedAt": h.stamp(), "completedAt": h.stamp(), "accepted": True})
    receipt = {"modelRunId": "provider-run-test", "decisionId": "provider-decision-test", "accepted": True,
        "status": "completed", "attemptId": "attempt", "sessionId": "session", "cycleId": "cycle",
        "deadlineAt": (h.time + timedelta(seconds=1)).isoformat()}
    with h.store._connection(write=True) as db:
        db.execute("CREATE TABLE provider_requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT INTO provider_requests VALUES (?, ?)", ("provider-request", json.dumps(receipt)))
    result = h.engine.dispatch(h.request(decisionId="provider-decision-test", deadlineAt=h.time + timedelta(seconds=2)))
    assert result["accepted"] is False
    assert "deadline expired or was extended" in result["reason"]
    result = h.engine.dispatch(h.request(decisionId="provider-decision-test", deadlineAt=h.time + timedelta(seconds=1)))
    assert result["accepted"] is True


def goal_provider_fixture(h):
    state = h.engine.snapshot()
    for identity in ("speech", "other-speech"):
        h.put("utterance", {"id": identity, "sessionId": "session", "cycleId": "cycle", "text": "Inspect once more",
            "source": "voice", "provider": "simulation", "modelId": "fixture", "status": "finalized",
            "startedAt": h.stamp(), "completedAt": h.stamp()})
    h.put("model_run", {"id": "provider-run-goal", "sessionId": "session", "cycleId": "cycle", "provider": "Google Decisions",
        "modelId": "gemini-decision-1", "requestedAt": h.stamp(), "completedAt": h.stamp(),
        "input": {"utteranceId": "speech", "request": {"input": json.dumps({
            "utterance": h.store.get("utterance", "speech"), "currentGoalId": state["goalId"], "sourceMode": "simulation"})}}})
    h.put("decision", {"id": "provider-decision-goal", "sessionId": "session", "cycleId": "cycle", "kind": "goal",
        "modelRunId": "provider-run-goal", "offeredChoices": ["sort", "inspect_more"], "selectedChoice": "inspect_more",
        "stateVersion": state["stateVersion"], "goalVersion": state["goalVersion"], "frameIds": [],
        "requestedAt": h.stamp(), "completedAt": h.stamp(), "accepted": True})
    receipt = {"modelRunId": "provider-run-goal", "decisionId": "provider-decision-goal", "accepted": True,
        "status": "completed", "sessionId": "session", "cycleId": "cycle", "selectedChoice": "inspect_more",
        "stateVersion": state["stateVersion"], "goalVersion": state["goalVersion"],
        "deadlineAt": (h.time + timedelta(seconds=2)).isoformat()}
    with h.store._connection(write=True) as db:
        db.execute("CREATE TABLE provider_requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT INTO provider_requests VALUES (?, ?)", ("provider-goal", json.dumps(receipt)))
    return GoalRequest(requestId="goal-apply", sessionId="session", goalId="inspect_more", utteranceId="speech",
        decisionId="provider-decision-goal", expectedStateVersion=state["stateVersion"], expectedGoalVersion=state["goalVersion"])


def test_provider_goal_binds_choice_original_utterance_and_versions(h):
    goal = goal_provider_fixture(h)
    before = h.engine.snapshot()
    with pytest.raises(StoreError, match="Recorded goal decision does not match"):
        h.engine.select_goal(goal.model_copy(update={"goalId": "sort"}))
    with pytest.raises(StoreError, match="original finalized utterance"):
        h.engine.select_goal(goal.model_copy(update={"utteranceId": "other-speech"}))
    with pytest.raises(StoreError, match="original finalized utterance"):
        h.engine.select_goal(goal.model_copy(update={"utteranceId": None}))
    assert h.engine.snapshot() == before
    result = h.engine.select_goal(goal)
    assert result["goalStatus"] == "active"
    assert result["state"]["goalId"] == "inspect_more"
    assert result["state"]["goalVersion"] == before["goalVersion"] + 1
    assert h.engine.select_goal(goal)["duplicate"] is True
    assert h.adapter.submissions == []


def test_provider_goal_rejects_original_deadline_expiry_and_missing_receipt(h):
    goal = goal_provider_fixture(h)
    h.time += timedelta(seconds=3)
    with pytest.raises(StoreError, match="deadline expired"):
        h.engine.select_goal(goal)
    h.time -= timedelta(seconds=3)
    with h.store._connection(write=True) as db:
        db.execute("DELETE FROM provider_requests")
    with pytest.raises(StoreError, match="no matching accepted application receipt"):
        h.engine.select_goal(goal)
    assert h.engine.snapshot()["goalId"] == "sort"


def import_utterance_revision(h, **changes):
    """Exercise the boundary against an imported revision; no public edit API is added."""
    original = h.store.get("utterance", "speech")
    revised = {**original, **changes}
    revision = revised.pop("revision") + 1
    with h.store._connection(write=True) as db:
        h.store._persist(db, "utterance", revised, revision, f"import-speech-{revision}",
                         "fixture-import", "imported_revision", h.stamp())
    return original, h.store.get("utterance", "speech")


@pytest.mark.parametrize("changes", [{"text": "Resume normal sorting"}, {}])
def test_provider_goal_rejects_imported_utterance_revision_before_apply(h, changes):
    goal = goal_provider_fixture(h)
    original = h.store.get("utterance", "speech")
    before = h.engine.snapshot()
    with pytest.raises(StoreError, match="Finalized utterance cannot be emitted or changed again"):
        h.put("utterance", {**original, "text": "Resume normal sorting"})
    assert h.store.get("utterance", "speech") == original
    old, revised = import_utterance_revision(h, **changes)
    assert revised["revision"] == old["revision"] + 1
    with pytest.raises(StoreError, match="original finalized utterance changed"):
        h.engine.select_goal(goal)
    assert h.engine.snapshot() == before
    assert h.adapter.submissions == []
    with h.store._connection() as db:
        saved = db.execute("SELECT revision, payload FROM revisions WHERE kind='utterance' AND id='speech' ORDER BY revision").fetchall()
    assert [row["revision"] for row in saved] == [1, 2]
    assert json.loads(saved[0]["payload"])["text"] == old["text"]
    assert json.loads(saved[1]["payload"])["text"] == revised["text"]


def test_queued_provider_goal_rechecks_utterance_revision_at_boundary(h):
    task = h.request()
    h.engine.dispatch(task)
    goal = goal_provider_fixture(h)
    queued = h.engine.select_goal(goal)
    assert queued["goalStatus"] == "queued"
    h.finish(task.executionId)
    import_utterance_revision(h, text="Resume normal sorting")
    before = h.engine.snapshot()
    with pytest.raises(StoreError, match="original finalized utterance changed"):
        h.checkpoint()
    assert h.engine.snapshot() == before
    assert before["goalId"] == "sort"
    assert before["goalVersion"] == goal.expectedGoalVersion
    assert before["queuedGoal"]["decisionId"] == goal.decisionId
    assert len(h.adapter.submissions) == 1
    assert h.control("stop")["state"]["queuedGoal"] is None
    assert h.store.get("cycle", "cycle")["outcome"] == "in_progress"
