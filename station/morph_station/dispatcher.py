"""Durable, explicitly simulated task dispatch. No robot SDK or physical command path.

The dispatcher journal is separate from canonical cycle/attempt/outcome records.
Only a trusted simulator supplies checkpoints; browser/model facts cannot establish
physical preconditions. Production adoption requires the separately verified adapter.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable, Literal
from uuid import uuid4

from pydantic import Field, StrictBool, model_validator

from .models import ID, Time, Text, StrictModel
from .store import StationStore, StoreError, canonical, fingerprint


class TaskRule(StrictModel):
    policyId: ID
    allowedPhases: list[ID] = Field(min_length=1)
    requiredConditions: list[ID] = Field(default_factory=list)
    nextPhase: ID
    maxExecutionsPerCycle: int = Field(default=1, ge=1, le=100)
    startsPhysicalAttempt: StrictBool = False


class DispatcherPolicy(StrictModel):
    id: ID = "unconfigured-deny-all"
    tasks: dict[ID, TaskRule] = Field(default_factory=dict)
    goalIds: list[ID] = Field(default_factory=list)
    defaultGoalId: ID | None = None
    maxEvidenceAgeMs: int = Field(default=1000, ge=1, le=600000)
    maxDecisionWindowMs: int = Field(default=5000, ge=1, le=600000)
    maxAttemptsPerCycle: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def goal_configuration(self):
        if len(set(self.goalIds)) != len(self.goalIds):
            raise ValueError("Goal identifiers must be unique")
        if self.defaultGoalId is not None and self.defaultGoalId not in self.goalIds:
            raise ValueError("Default goal must be explicitly permitted")
        return self


def demo_simulation_policy() -> DispatcherPolicy:
    """Illustrative registry for intentional simulation, not approved hardware skills."""
    def rule(phases, conditions, next_phase, limit=1, starts_attempt=False):
        return TaskRule(policyId="simulation-only-no-robot", allowedPhases=phases,
                        requiredConditions=conditions, nextPhase=next_phase, maxExecutionsPerCycle=limit,
                        startsPhysicalAttempt=starts_attempt)
    return DispatcherPolicy(
        id="m12-unfrozen-simulation-example-v1", defaultGoalId="sort",
        goalIds=["sort", "inspect_more"], maxEvidenceAgeMs=30000,
        maxDecisionWindowMs=30000, maxAttemptsPerCycle=2,
        tasks={
            "pick": rule(["object_ready"], ["workspace_ready", "object_visible"], "holding", 2, starts_attempt=True),
            "present_for_inspection": rule(["holding"], ["workspace_ready", "grasp_confirmed"], "inspecting"),
            "reinspect_other_view": rule(["inspecting", "inspected"], ["workspace_ready", "object_presented"], "inspecting", 2),
            "place_good": rule(["inspected"], ["workspace_ready", "object_held", "classification_good"], "placed"),
            "place_defective": rule(["inspected"], ["workspace_ready", "object_held", "classification_defective"], "placed"),
            "hold": rule(["object_ready", "holding", "inspecting", "inspected", "placed"], [], "held"),
        },
    )


class ControlRequest(StrictModel):
    commandId: ID
    action: Literal["start", "pause_after_cycle", "resume", "stop"]
    sessionId: ID
    expectedStateVersion: int = Field(ge=0)


class CheckpointRequest(StrictModel):
    eventId: ID
    sessionId: ID
    expectedStateVersion: int = Field(ge=0)
    cycleId: ID | None = None
    objectId: ID | None = None
    phase: ID = "idle"
    conditions: dict[ID, StrictBool] = Field(default_factory=dict, max_length=50)
    frameIds: list[ID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def scope(self):
        if (self.cycleId is None) != (self.objectId is None):
            raise ValueError("Cycle and object must be supplied together")
        if self.cycleId is None and (self.frameIds or self.conditions or self.phase != "idle"):
            raise ValueError("An empty checkpoint must be idle without evidence or conditions")
        if len(set(self.frameIds)) != len(self.frameIds):
            raise ValueError("Frame identifiers must be unique")
        return self


class GoalRequest(StrictModel):
    requestId: ID
    sessionId: ID
    goalId: ID
    expectedStateVersion: int = Field(ge=0)
    expectedGoalVersion: int = Field(ge=0)
    utteranceId: ID | None = None
    decisionId: ID | None = None


class DispatchRequest(StrictModel):
    requestId: ID
    executionId: ID
    sessionId: ID
    cycleId: ID
    objectId: ID
    attemptId: ID
    taskId: ID
    expectedStateVersion: int = Field(ge=0)
    expectedGoalVersion: int = Field(ge=0)
    frameIds: list[ID] = Field(min_length=1, max_length=20)
    deadlineAt: Time
    decisionId: ID | None = None

    @model_validator(mode="after")
    def unique_frames(self):
        if len(set(self.frameIds)) != len(self.frameIds):
            raise ValueError("Frame identifiers must be unique")
        return self


class SimulatedAdapter:
    """Observable in-memory delivery probe; never creates canonical outcomes."""

    def __init__(self):
        self.submissions: list[dict] = []
        self.stopCalls = 0
        self.failNext = False

    def submit(self, execution: dict) -> None:
        self.submissions.append(execution.copy())
        if self.failNext:
            self.failNext = False
            raise RuntimeError("Simulated delivery uncertainty")

    def stop(self) -> None:
        self.stopCalls += 1


_LOCKS: dict[str, RLock] = {}
_LOCKS_GUARD = RLock()
_UNFINISHED = {"requested", "acknowledged", "reconciliation_required"}


class SimulationDispatcher:
    """One application-owned dispatcher per database; construction reconciles restart.

    Construct once during explicit simulation-service startup, not on each request.
    All methods are synchronous; adapter submissions occur once after a durable
    reservation. Unknown delivery is retained and never automatically resubmitted.
    """

    def __init__(self, store: StationStore, policy: DispatcherPolicy | None = None,
                 adapter: SimulatedAdapter | None = None,
                 clock: Callable[[], datetime] | None = None):
        if adapter is not None and type(adapter) is not SimulatedAdapter:
            raise ValueError("Only the explicit SimulatedAdapter is supported")
        self.store = store
        self.policy = (policy or DispatcherPolicy()).model_copy(deep=True)
        self.adapter = adapter if adapter is not None else SimulatedAdapter()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.policy_hash = fingerprint(self.policy.model_dump(mode="json"))
        self.instance_id = str(uuid4())
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(store.db_path.resolve()), RLock())
        with self._lock, store._connection(write=True) as db:
            for statement in (
                "CREATE TABLE IF NOT EXISTS dispatch_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS dispatch_receipts (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS dispatch_executions (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS dispatch_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, occurred_at TEXT NOT NULL, payload TEXT NOT NULL)",
            ):
                db.execute(statement)
            row = db.execute("SELECT payload FROM dispatch_state WHERE id=1").fetchone()
            if row is None:
                state = {"sourceMode": "simulation", "stateVersion": 0, "goalVersion": 0,
                         "mode": "stopped", "sessionId": None, "activeCycleId": None,
                         "objectId": None, "phase": "idle", "conditions": {}, "frameIds": [],
                         "recordRevisions": [], "currentAttemptId": None,
                         "goalId": None, "queuedGoal": None, "activeExecutionId": None,
                         "boundaryReady": True, "policyId": self.policy.id,
                         "policyFingerprint": self.policy_hash,
                         "instanceId": self.instance_id,
                         "hardwareIntegrated": False, "physicalEmergencyStopVerified": False}
                self._save_state(db, state)
            else:
                state = self._state(db)
                if state["policyFingerprint"] != self.policy_hash:
                    raise StoreError(409, "Dispatcher policy changed; use an explicitly reconciled simulation journal")
                changed = False
                for execution in self._executions(db):
                    if execution["status"] in {"requested", "acknowledged"}:
                        execution["status"] = "reconciliation_required"
                        execution["deliveryState"] = "unknown_after_restart"
                        execution["reconciliationReason"] = "Process restarted with unfinished delivery/execution"
                        self._save_execution(db, execution)
                        self._event(db, "restart_uncertainty", {"executionId": execution["id"]})
                        changed = True
                if changed:
                    state["mode"] = "reconciliation_required"
                elif state["mode"] in {"running", "pause_pending"}:
                    state["mode"] = "paused"
                state["instanceId"] = self.instance_id
                self._advance(db, state)
                self._event(db, "dispatcher_reopened", {"instanceId": self.instance_id})

    def _now(self) -> datetime:
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Dispatcher clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc)

    def _stamp(self) -> str:
        return self._now().isoformat().replace("+00:00", "Z")

    def _lifecycle_stamp(self, execution: dict) -> str:
        current = self._now()
        previous = execution["acknowledgedAt"] or execution["requestedAt"]
        if current < datetime.fromisoformat(previous.replace("Z", "+00:00")):
            raise StoreError(409, "Clock moved backwards during execution; reconciliation is required")
        return current.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _decode(value: str) -> dict:
        import json
        return json.loads(value)

    def _state(self, db) -> dict:
        return self._decode(db.execute("SELECT payload FROM dispatch_state WHERE id=1").fetchone()[0])

    def _owner(self, state: dict) -> None:
        if state.get("instanceId") != self.instance_id:
            raise StoreError(409, "This dispatcher instance was superseded by a newer owner")
        if fingerprint(self.policy.model_dump(mode="json")) != self.policy_hash:
            raise StoreError(409, "Dispatcher policy changed in memory; use an explicitly reconciled configuration")

    @staticmethod
    def _save_state(db, state: dict) -> None:
        db.execute("INSERT OR REPLACE INTO dispatch_state VALUES (1, ?)", (canonical(state),))

    def _advance(self, db, state: dict) -> None:
        state["stateVersion"] += 1
        self._save_state(db, state)

    def _event(self, db, kind: str, payload: dict) -> None:
        db.execute("INSERT INTO dispatch_events(kind, occurred_at, payload) VALUES (?, ?, ?)",
                   (kind, self._stamp(), canonical(payload)))

    def _executions(self, db) -> list[dict]:
        return [self._decode(row[0]) for row in db.execute("SELECT payload FROM dispatch_executions ORDER BY rowid")]

    def _execution(self, db, identity: str) -> dict:
        row = db.execute("SELECT payload FROM dispatch_executions WHERE id=?", (identity,)).fetchone()
        if not row:
            raise StoreError(404, "Dispatcher execution not found")
        return self._decode(row[0])

    @staticmethod
    def _save_execution(db, execution: dict) -> None:
        db.execute("UPDATE dispatch_executions SET payload=? WHERE id=?", (canonical(execution), execution["id"]))

    def _receipt(self, db, kind: str, identity: str, body: dict) -> dict | None:
        row = db.execute("SELECT fingerprint, response FROM dispatch_receipts WHERE id=?", (kind + ":" + identity,)).fetchone()
        if row:
            if row["fingerprint"] != fingerprint(body):
                raise StoreError(409, "Request identifier was reused with a different payload")
            return {**self._decode(row["response"]), "duplicate": True, "state": self._state(db)}
        return None

    @staticmethod
    def _remember(db, kind: str, identity: str, body: dict, response: dict) -> dict:
        db.execute("INSERT INTO dispatch_receipts VALUES (?, ?, ?)",
                   (kind + ":" + identity, fingerprint(body), canonical(response)))
        return response

    def _session(self, db, session_id: str, *, allow_ended: bool = False) -> dict:
        session = self.store._get(db, "session", session_id)
        if session["sourceMode"] != "simulation":
            raise StoreError(409, "This dispatcher accepts explicitly simulated sessions only")
        if session["endedAt"] is not None and not allow_ended:
            raise StoreError(409, "Session has ended")
        return session

    @staticmethod
    def _version(state: dict, version: int, session_id: str | None = None) -> None:
        if state["stateVersion"] != version:
            raise StoreError(409, "Stale dispatcher state version")
        if session_id is not None and state["sessionId"] != session_id:
            raise StoreError(409, "Request belongs to another active session")

    def _frames(self, db, ids: list[str], session: str, cycle: str, object_id: str,
                fresh: bool = False) -> list[dict]:
        frames = []
        for identity in ids:
            frame = self.store._get(db, "frame", identity)
            if (frame["sessionId"], frame["cycleId"], frame["objectId"]) != (session, cycle, object_id):
                raise StoreError(409, "Frame does not belong to the selected session, cycle and object")
            evidence = self.store._get(db, "evidence", frame["evidenceId"])
            if (evidence["sessionId"], evidence["cycleId"]) != (session, cycle):
                raise StoreError(409, "Frame evidence scope does not match")
            if fresh:
                age = (self._now() - datetime.fromisoformat(frame["capturedAt"].replace("Z", "+00:00"))).total_seconds() * 1000
                if age < 0 or age > self.policy.maxEvidenceAgeMs:
                    raise StoreError(409, "Frame is stale or future-dated")
            frames.append(frame)
        return frames

    def snapshot(self) -> dict:
        with self.store._connection() as db:
            return self._state(db)

    def decision_context(self) -> dict:
        """One coherent read of versions, current attempt and the validated menu.

        Dispatch repeats every check after the model returns. A menu read has no
        authority to reserve an execution or to extend the returned deadline.
        """
        with self.store._connection() as db:
            state = self._state(db)
            self._owner(state)
            deadline = self._now() + timedelta(milliseconds=self.policy.maxDecisionWindowMs)
            context = {"state": state, "attemptId": None, "allowedTaskIds": [],
                       "deadlineAt": deadline.isoformat().replace("+00:00", "Z")}
            if not state["sessionId"] or not state["activeCycleId"] or not state["frameIds"]:
                return context
            attempts = [a for a in self.store._list(db, "attempt", state["sessionId"], state["activeCycleId"])
                        if a["outcome"] == "in_progress"]
            if len(attempts) != 1:
                return context
            context["attemptId"] = attempts[0]["id"]
            for task_id in self.policy.tasks:
                request = DispatchRequest(requestId="menu-validation", executionId="menu-validation",
                    sessionId=state["sessionId"], cycleId=state["activeCycleId"], objectId=state["objectId"],
                    attemptId=context["attemptId"], taskId=task_id, expectedStateVersion=state["stateVersion"],
                    expectedGoalVersion=state["goalVersion"], frameIds=state["frameIds"], deadlineAt=deadline)
                try:
                    self._validate_dispatch(db, state, request)
                except StoreError:
                    continue
                context["allowedTaskIds"].append(task_id)
            return context

    def allowed_tasks(self) -> list[str]:
        return self.decision_context()["allowedTaskIds"]

    def execution(self, execution_id: str) -> dict:
        with self.store._connection() as db:
            return self._execution(db, execution_id)

    def list_executions(self, session_id: str | None = None) -> list[dict]:
        with self.store._connection() as db:
            return [entry for entry in self._executions(db)
                    if session_id is None or entry["sessionId"] == session_id]

    def export_journal(self) -> dict:
        with self.store._connection() as db:
            return {"sourceMode": "simulation", "state": self._state(db), "executions": self._executions(db),
                    "events": [{"sequence": row["sequence"], "kind": row["kind"],
                                "occurredAt": row["occurred_at"], "payload": self._decode(row["payload"])}
                               for row in db.execute("SELECT * FROM dispatch_events ORDER BY sequence")]}

    def control(self, request: ControlRequest) -> dict:
        body = request.model_dump(mode="json")
        with self._lock, self.store._connection(write=True) as db:
            duplicate = self._receipt(db, "control", request.commandId, body)
            if duplicate:
                return duplicate
            state = self._state(db)
            self._owner(state)
            self._session(db, request.sessionId, allow_ended=request.action == "stop")
            # A stop request may come from a stale display. It still cannot stop
            # a different session; state freshness gates start/resume/motion.
            if request.action != "stop":
                self._version(state, request.expectedStateVersion)
            if request.action == "start":
                if not self.policy.tasks or self.policy.defaultGoalId is None:
                    raise StoreError(409, "No approved simulated task/goal policy is configured")
                if state["mode"] != "stopped" or state["activeExecutionId"] or state["activeCycleId"]:
                    raise StoreError(409, "Start requires a stopped, reconciled station without an open cycle")
                state.update(mode="running", sessionId=request.sessionId,
                             goalId=self.policy.defaultGoalId, queuedGoal=None, boundaryReady=True)
                state["goalVersion"] += 1
            else:
                if state["sessionId"] != request.sessionId:
                    raise StoreError(409, "Request belongs to another active session")
                if request.action == "pause_after_cycle":
                    if state["mode"] not in {"running", "pause_pending", "paused"}:
                        raise StoreError(409, "Pause requires an active or paused run")
                    state["mode"] = "pause_pending" if state["activeCycleId"] else "paused"
                elif request.action == "resume":
                    if state["mode"] != "paused" or state["activeExecutionId"]:
                        raise StoreError(409, "Resume requires an acknowledged pause without unresolved execution")
                    state["mode"] = "running"
                else:
                    if state["activeExecutionId"]:
                        execution = self._execution(db, state["activeExecutionId"])
                        if execution["status"] in _UNFINISHED:
                            execution.update(status="reconciliation_required", deliveryState="unknown_after_stop",
                                             reconciliationReason="Software stop does not establish physical outcome")
                            self._save_execution(db, execution)
                    state["mode"] = "reconciliation_required" if state["activeExecutionId"] else "stopped"
                    state["queuedGoal"] = None
                    self.adapter.stop()
            self._advance(db, state)
            self._event(db, "control", body)
            response = {"accepted": True, "duplicate": False, "state": state,
                        "acknowledgmentSource": "simulated_adapter", "physicalEmergencyStopVerified": False}
            return self._remember(db, "control", request.commandId, body, response)

    def checkpoint(self, request: CheckpointRequest) -> dict:
        body = request.model_dump(mode="json")
        with self._lock, self.store._connection(write=True) as db:
            duplicate = self._receipt(db, "checkpoint", request.eventId, body)
            if duplicate:
                return duplicate
            state = self._state(db)
            self._owner(state)
            self._session(db, request.sessionId, allow_ended=request.cycleId is None)
            self._version(state, request.expectedStateVersion, request.sessionId)
            if state["mode"] not in {"running", "pause_pending", "stopped"} or state["activeExecutionId"]:
                raise StoreError(409, "Checkpoint requires a reconciled task boundary")
            previous = state["activeCycleId"]
            if previous and previous != request.cycleId:
                if self.store._get(db, "cycle", previous)["outcome"] == "in_progress":
                    raise StoreError(409, "Previous canonical cycle remains open")
                if any(a["outcome"] == "in_progress" for a in self.store._list(db, "attempt", request.sessionId, previous)):
                    raise StoreError(409, "Previous canonical attempt remains open")
            if request.cycleId:
                if state["mode"] == "stopped" or (state["mode"] == "pause_pending" and previous != request.cycleId):
                    raise StoreError(409, "A new cycle cannot start while stopped or pausing")
                cycle = self.store._get(db, "cycle", request.cycleId)
                if (cycle["sessionId"], cycle["objectId"]) != (request.sessionId, request.objectId):
                    raise StoreError(409, "Cycle/object association does not match")
                if cycle["outcome"] != "in_progress":
                    raise StoreError(409, "Selected cycle is already finished")
                self._frames(db, request.frameIds, request.sessionId, request.cycleId, request.objectId)
            queued_goal = state["queuedGoal"]
            if queued_goal and queued_goal.get("decisionId"):
                decision = self.store._get(db, "decision", queued_goal["decisionId"])
                if decision["modelRunId"].startswith("provider-run-"):
                    self._provider_goal_utterance(db, decision["modelRunId"], queued_goal["utteranceId"])
            revisions = []
            current_attempt = None
            if request.cycleId:
                identities = {("cycle", request.cycleId)}
                attempts = self.store._list(db, "attempt", request.sessionId, request.cycleId)
                open_attempts = [entry for entry in attempts if entry["outcome"] == "in_progress"]
                current_attempt = open_attempts[0]["id"] if len(open_attempts) == 1 else None
                identities.update(("attempt", entry["id"]) for entry in attempts)
                for kind, key in (("inspection", "inspectionId"), ("reference_label", "referenceLabelId"),
                                  ("confirmation", "confirmationId")):
                    if cycle.get(key):
                        identities.add((kind, cycle[key]))
                for frame in self._frames(db, request.frameIds, request.sessionId, request.cycleId, request.objectId):
                    identities.add(("frame", frame["id"]))
                    identities.add(("evidence", frame["evidenceId"]))
                revisions = [{"kind": kind, "id": identity, "revision": self.store._get(db, kind, identity)["revision"]}
                             for kind, identity in sorted(identities)]
            state.update(activeCycleId=request.cycleId, objectId=request.objectId, phase=request.phase,
                         conditions=request.conditions, frameIds=request.frameIds, boundaryReady=True,
                         recordRevisions=revisions, currentAttemptId=current_attempt)
            if state["queuedGoal"]:
                state["goalId"] = state["queuedGoal"]["goalId"]
                state["goalVersion"] += 1
                state["queuedGoal"] = None
            if request.cycleId is None and state["mode"] == "pause_pending":
                state["mode"] = "paused"
            self._advance(db, state)
            self._event(db, "checkpoint", body)
            return self._remember(db, "checkpoint", request.eventId, body,
                                  {"accepted": True, "duplicate": False, "state": state})

    def _provider_goal_utterance(self, db, model_run_id: str, utterance_id: str | None) -> None:
        run = self.store._get(db, "model_run", model_run_id)
        if not utterance_id or run["input"].get("utteranceId") != utterance_id:
            raise StoreError(409, "Provider goal does not match the original finalized utterance")
        try:
            original = self._decode(run["input"]["request"]["input"])["utterance"]
            if not isinstance(original, dict):
                raise ValueError
            original_fingerprint = fingerprint(original)
        except (KeyError, TypeError, ValueError):
            raise StoreError(409, "Provider goal is missing its original finalized utterance snapshot") from None
        # Include the revision and all provenance fields, not only the text or ID.
        # Recheck queued goals because canonical data may be imported between boundaries.
        if original_fingerprint != fingerprint(self.store._get(db, "utterance", utterance_id)):
            raise StoreError(409, "Provider goal's original finalized utterance changed; select a new goal")

    def select_goal(self, request: GoalRequest) -> dict:
        body = request.model_dump(mode="json")
        with self._lock, self.store._connection(write=True) as db:
            duplicate = self._receipt(db, "goal", request.requestId, body)
            if duplicate:
                return duplicate
            state = self._state(db)
            self._owner(state)
            self._session(db, request.sessionId)
            self._version(state, request.expectedStateVersion, request.sessionId)
            if state["goalVersion"] != request.expectedGoalVersion:
                raise StoreError(409, "Stale goal version")
            if request.goalId not in self.policy.goalIds:
                raise StoreError(409, "Unsupported goal")
            if state["mode"] not in {"running", "pause_pending", "paused"} or state["queuedGoal"]:
                raise StoreError(409, "Goal cannot be changed in this state")
            if request.decisionId:
                decision = self.store._get(db, "decision", request.decisionId)
                if (decision["kind"], decision["accepted"], decision["sessionId"], decision["selectedChoice"],
                    decision["stateVersion"], decision["goalVersion"]) != (
                        "goal", True, request.sessionId, request.goalId,
                        request.expectedStateVersion, request.expectedGoalVersion):
                    raise StoreError(409, "Recorded goal decision does not match the accepted goal request")
                if decision["cycleId"] not in (None, state["activeCycleId"]):
                    raise StoreError(409, "Recorded goal decision belongs to another cycle")
                if decision["modelRunId"].startswith("provider-run-"):
                    table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provider_requests'").fetchone()
                    row = db.execute("SELECT payload FROM provider_requests WHERE json_extract(payload,'$.modelRunId')=?",
                                     (decision["modelRunId"],)).fetchone() if table else None
                    receipt = self._decode(row[0]) if row else None
                    if (not receipt or receipt.get("accepted") is not True or receipt.get("status") != "completed"
                        or receipt.get("decisionId") != request.decisionId or receipt.get("sessionId") != request.sessionId
                        or receipt.get("selectedChoice") != request.goalId
                        or receipt.get("stateVersion") != request.expectedStateVersion
                        or receipt.get("goalVersion") != request.expectedGoalVersion):
                        raise StoreError(409, "Provider goal has no matching accepted application receipt")
                    self._provider_goal_utterance(db, decision["modelRunId"], request.utteranceId)
                    try:
                        original_deadline = datetime.fromisoformat(receipt["deadlineAt"].replace("Z", "+00:00"))
                        if original_deadline.tzinfo is None:
                            raise ValueError
                    except (KeyError, TypeError, AttributeError, ValueError):
                        raise StoreError(409, "Provider goal receipt has no valid original deadline") from None
                    if self._now() >= original_deadline:
                        raise StoreError(409, "Provider goal decision deadline expired")
            if request.utteranceId:
                utterance = self.store._get(db, "utterance", request.utteranceId)
                if utterance["sessionId"] != request.sessionId or utterance["status"] != "finalized":
                    raise StoreError(409, "Goal requires a finalized utterance from the selected session")
                if utterance["cycleId"] not in (None, state["activeCycleId"]):
                    raise StoreError(409, "Goal utterance belongs to another cycle")
                if db.execute("SELECT 1 FROM dispatch_receipts WHERE id=?", ("utterance:" + request.utteranceId,)).fetchone():
                    raise StoreError(409, "Utterance was already used for a goal")
            queued = bool(state["activeExecutionId"] or not state["boundaryReady"])
            if queued:
                state["queuedGoal"] = {"goalId": request.goalId, "requestId": request.requestId,
                                       "utteranceId": request.utteranceId, "decisionId": request.decisionId}
            else:
                state["goalId"] = request.goalId
                state["goalVersion"] += 1
            self._advance(db, state)
            self._event(db, "goal_queued" if queued else "goal_committed", body)
            response = {"accepted": True, "duplicate": False, "goalStatus": "queued" if queued else "active", "state": state}
            if request.utteranceId:
                self._remember(db, "utterance", request.utteranceId, body, response)
            return self._remember(db, "goal", request.requestId, body, response)

    def _validate_dispatch(self, db, state: dict, request: DispatchRequest) -> TaskRule:
        self._owner(state)
        self._session(db, request.sessionId)
        self._version(state, request.expectedStateVersion, request.sessionId)
        if state["goalVersion"] != request.expectedGoalVersion:
            raise StoreError(409, "Stale goal version")
        if state["mode"] not in {"running", "pause_pending"} or state["activeExecutionId"]:
            raise StoreError(409, "Station is not available for another execution")
        if not state["boundaryReady"] or state["queuedGoal"]:
            raise StoreError(409, "A fresh checkpoint and goal commit are required")
        if (state["activeCycleId"], state["objectId"]) != (request.cycleId, request.objectId):
            raise StoreError(409, "Dispatch scope differs from the current checkpoint")
        rule = self.policy.tasks.get(request.taskId)
        if rule is None or state["phase"] not in rule.allowedPhases:
            raise StoreError(409, "Task is not permitted in the current phase")
        if any(state["conditions"].get(key) is not True for key in rule.requiredConditions):
            raise StoreError(409, "Required task precondition is not confirmed")
        window = (request.deadlineAt - self._now()).total_seconds() * 1000
        if window <= 0 or window > self.policy.maxDecisionWindowMs:
            raise StoreError(409, "Decision deadline expired or exceeds the configured window")
        cycle = self.store._get(db, "cycle", request.cycleId)
        if (cycle["sessionId"], cycle["objectId"], cycle["outcome"]) != (request.sessionId, request.objectId, "in_progress"):
            raise StoreError(409, "Cycle is finished or has a different association")
        for reference in state.get("recordRevisions", []):
            if self.store._get(db, reference["kind"], reference["id"])["revision"] != reference["revision"]:
                raise StoreError(409, "Checkpoint records changed; capture a new boundary before dispatch")
        attempt = self.store._get(db, "attempt", request.attemptId)
        attempts = self.store._list(db, "attempt", request.sessionId, request.cycleId)
        if (attempt["sessionId"], attempt["cycleId"], attempt["outcome"]) != (request.sessionId, request.cycleId, "in_progress"):
            raise StoreError(409, "Attempt is finished or belongs to another cycle")
        if attempt["ordinal"] != max(a["ordinal"] for a in attempts) or sum(a["outcome"] == "in_progress" for a in attempts) != 1:
            raise StoreError(409, "Dispatch requires the single current physical attempt")
        if len(attempts) > self.policy.maxAttemptsPerCycle or attempt["ordinal"] > self.policy.maxAttemptsPerCycle:
            raise StoreError(409, "Physical attempt budget exhausted")
        if state.get("currentAttemptId") != request.attemptId:
            raise StoreError(409, "Current attempt changed; capture a new boundary before dispatch")
        prior = [e for e in self._executions(db) if e["cycleId"] == request.cycleId and e["taskId"] == request.taskId]
        if rule.startsPhysicalAttempt and any(e["attemptId"] == request.attemptId for e in prior):
            raise StoreError(409, "A physical retry requires a new persisted attempt")
        if len(prior) >= rule.maxExecutionsPerCycle:
            raise StoreError(409, "Task execution budget exhausted")
        if set(request.frameIds) != set(state["frameIds"]):
            raise StoreError(409, "Decision frames differ from the current checkpoint")
        self._frames(db, request.frameIds, request.sessionId, request.cycleId, request.objectId, fresh=True)
        if request.decisionId:
            decision = self.store._get(db, "decision", request.decisionId)
            if (decision["sessionId"], decision["cycleId"], decision["kind"], decision["selectedChoice"],
                decision["stateVersion"], decision["goalVersion"]) != (
                    request.sessionId, request.cycleId, "task", request.taskId,
                    request.expectedStateVersion, request.expectedGoalVersion):
                raise StoreError(409, "Recorded decision does not match this task request")
            if decision["accepted"] is False or set(decision["frameIds"]) != set(request.frameIds):
                raise StoreError(409, "Recorded decision is rejected or uses different evidence")
            if decision["modelRunId"].startswith("provider-run-"):
                table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provider_requests'").fetchone()
                receipt_row = db.execute(
                    "SELECT payload FROM provider_requests WHERE json_extract(payload,'$.modelRunId')=?",
                    (decision["modelRunId"],)).fetchone() if table else None
                receipt = self._decode(receipt_row[0]) if receipt_row else None
                if (not receipt or receipt.get("accepted") is not True or receipt.get("status") != "completed"
                    or receipt.get("decisionId") != request.decisionId or receipt.get("attemptId") != request.attemptId
                    or receipt.get("sessionId") != request.sessionId or receipt.get("cycleId") != request.cycleId):
                    raise StoreError(409, "Provider decision has no matching accepted application receipt")
                try:
                    original_deadline = datetime.fromisoformat(receipt["deadlineAt"].replace("Z", "+00:00"))
                    if original_deadline.tzinfo is None:
                        raise ValueError
                except (KeyError, TypeError, AttributeError, ValueError):
                    raise StoreError(409, "Provider decision receipt has no valid original deadline") from None
                if self._now() >= original_deadline or request.deadlineAt > original_deadline:
                    raise StoreError(409, "Provider decision deadline expired or was extended")
        return rule

    def dispatch(self, request: DispatchRequest) -> dict:
        body = request.model_dump(mode="json")
        with self._lock:
            with self.store._connection(write=True) as db:
                duplicate = self._receipt(db, "dispatch", request.requestId, body)
                if duplicate:
                    if duplicate.get("execution"):
                        duplicate["execution"] = self._execution(db, request.executionId)
                    duplicate["state"] = self._state(db)
                    return duplicate
                existing = db.execute("SELECT fingerprint FROM dispatch_executions WHERE id=?", (request.executionId,)).fetchone()
                if existing:
                    if existing[0] != fingerprint(body):
                        raise StoreError(409, "Execution identifier was reused with a different payload")
                    return {"accepted": True, "duplicate": True, "execution": self._execution(db, request.executionId)}
                state = self._state(db)
                self._owner(state)
                try:
                    rule = self._validate_dispatch(db, state, request)
                except StoreError as exc:
                    self._event(db, "dispatch_rejected", {"request": body, "reason": exc.detail, "fallback": "hold"})
                    return self._remember(db, "dispatch", request.requestId, body,
                                          {"accepted": False, "duplicate": False, "reason": exc.detail,
                                           "fallback": "hold", "execution": None, "state": state})
                execution = {"id": request.executionId, "sourceMode": "simulation", **body,
                             "policyId": rule.policyId, "configurationId": self.policy.id,
                             "status": "requested", "deliveryState": "reserved", "requestedAt": self._stamp(),
                             "acknowledgedAt": None, "finishedAt": None, "controllerSuccess": None,
                             "physicalOutcome": "unverified", "confirmationId": None,
                             "nextPhase": rule.nextPhase, "reconciliation": None}
                db.execute("INSERT INTO dispatch_executions VALUES (?, ?, ?)",
                           (request.executionId, fingerprint(body), canonical(execution)))
                state.update(activeExecutionId=request.executionId, boundaryReady=False)
                self._advance(db, state)
                self._event(db, "execution_requested", {"executionId": request.executionId, "request": body})
                self._remember(db, "dispatch", request.requestId, body,
                               {"accepted": True, "duplicate": False, "execution": execution, "state": state})
            # The in-memory simulator is bounded and cannot call hardware/network.
            # Keep ownership check and submission inside one write transaction so
            # another process cannot fence this owner between the check and send.
            with self.store._connection(write=True) as db:
                state = self._state(db)
                execution = self._execution(db, request.executionId)
                if state.get("instanceId") != self.instance_id:
                    return {"accepted": True, "duplicate": False, "execution": execution, "state": state}
                self._owner(state)
                try:
                    self.adapter.submit(execution)
                except Exception:
                    execution.update(status="reconciliation_required", deliveryState="unknown_after_delivery_error",
                                     reconciliationReason="Simulated adapter delivery failed; outcome unknown")
                    self._save_execution(db, execution)
                    state["mode"] = "reconciliation_required"
                    self._advance(db, state)
                    self._event(db, "delivery_uncertain", {"executionId": request.executionId})
                else:
                    execution["deliveryState"] = "submitted_to_simulator"
                    self._save_execution(db, execution)
                    self._event(db, "simulator_submission", {"executionId": request.executionId})
            return {"accepted": True, "duplicate": False, "execution": self.execution(request.executionId), "state": self.snapshot()}

    def acknowledge(self, execution_id: str) -> dict:
        with self._lock, self.store._connection(write=True) as db:
            self._owner(self._state(db))
            execution = self._execution(db, execution_id)
            if execution["acknowledgedAt"] is not None:
                return {"duplicate": True, "execution": execution}
            if execution["status"] != "requested" or execution["deliveryState"] != "submitted_to_simulator":
                raise StoreError(409, "Execution is not awaiting an acknowledgment")
            execution.update(status="acknowledged", acknowledgedAt=self._lifecycle_stamp(execution))
            self._save_execution(db, execution)
            self._advance(db, self._state(db))
            self._event(db, "execution_acknowledged", {"executionId": execution_id})
            return {"duplicate": False, "execution": execution}

    def finish(self, execution_id: str, success: bool) -> dict:
        if type(success) is not bool:
            raise StoreError(422, "Controller success must be a boolean")
        with self._lock, self.store._connection(write=True) as db:
            self._owner(self._state(db))
            execution = self._execution(db, execution_id)
            if execution["status"] in {"finished", "failed"}:
                if execution["controllerSuccess"] != success:
                    raise StoreError(409, "Conflicting repeated completion")
                return {"duplicate": True, "execution": execution}
            if execution["status"] != "acknowledged":
                raise StoreError(409, "Completion requires acknowledgment or explicit reconciliation")
            execution.update(status="finished" if success else "failed", finishedAt=self._lifecycle_stamp(execution), controllerSuccess=success)
            self._save_execution(db, execution)
            state = self._state(db)
            state["activeExecutionId"] = None
            # A controller report never confirms a new phase/precondition or physical result.
            self._advance(db, state)
            self._event(db, "execution_finished", {"executionId": execution_id, "controllerSuccess": success})
            return {"duplicate": False, "execution": execution}

    def reconcile(self, execution_id: str, status: Literal["finished", "failed", "unverified"],
                  authorId: str, reason: str) -> dict:
        class Reconciliation(StrictModel):
            authorId: ID
            reason: Text
            status: Literal["finished", "failed", "unverified"]
        supplied = Reconciliation(authorId=authorId, reason=reason, status=status).model_dump(mode="json")
        with self._lock, self.store._connection(write=True) as db:
            self._owner(self._state(db))
            execution = self._execution(db, execution_id)
            if execution["reconciliation"]:
                if {k: execution["reconciliation"][k] for k in supplied} != supplied:
                    raise StoreError(409, "Conflicting reconciliation; preserve the original audit")
                return {"duplicate": True, "execution": execution}
            if execution["status"] != "reconciliation_required":
                raise StoreError(409, "Execution does not require reconciliation")
            execution.update(status=status, finishedAt=self._stamp(),
                             controllerSuccess=True if status == "finished" else False if status == "failed" else None,
                             reconciliation={**supplied, "at": self._stamp()})
            self._save_execution(db, execution)
            state = self._state(db)
            state.update(activeExecutionId=None, mode="stopped", boundaryReady=False, queuedGoal=None)
            self._advance(db, state)
            self._event(db, "execution_reconciled", {"executionId": execution_id, **execution["reconciliation"]})
            return {"duplicate": False, "execution": execution}
