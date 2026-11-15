"""Domain regressions for the persistent station ledger, without robot I/O."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from itertools import count

import pytest

from morph_station.models import CorrectionRequest, EvidenceUpload, RecordWrite
from morph_station.store import StationStore, StoreError


START = "2026-11-14T12:00:00Z"
FINISH = "2026-11-14T12:00:10Z"
LATER = "2026-11-14T12:00:20Z"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+j9VEAAAAASUVORK5CYII="
)


@pytest.fixture
def store(tmp_path):
    return StationStore(tmp_path / "station.sqlite3", tmp_path / "evidence")


@pytest.fixture
def put(store):
    serial = count(1)

    def write(record_type, record, *, event_id=None, expected_revision=None):
        payload = deepcopy(record)
        payload.pop("revision", None)
        return store.upsert(
            RecordWrite(
                eventId=event_id or f"event-{next(serial)}",
                recordType=record_type,
                record=payload,
                expectedRevision=expected_revision,
            )
        )

    return write


def session_record(session_id="session-1", *, source="live"):
    return {
        "id": session_id,
        "name": f"Run {session_id}",
        "sourceMode": source,
        "startedAt": START,
        "endedAt": None,
        "configId": "configuration-1",
        "robotId": None,
        "modelRuns": [],
    }


def cycle_record(cycle_id="cycle-1", *, session_id="session-1", object_id="brick-1"):
    return {
        "id": cycle_id,
        "sessionId": session_id,
        "objectId": object_id,
        "startedAt": START,
        "endedAt": None,
        "outcome": "in_progress",
        "commandedDestination": None,
        "observedDestination": None,
        "referenceLabelId": None,
        "inspectionId": None,
        "confirmationId": None,
    }


def start_cycle(put, *, session_id="session-1", cycle_id="cycle-1", source="live"):
    put("session", session_record(session_id, source=source))
    return put("cycle", cycle_record(cycle_id, session_id=session_id))["record"]


def assert_store_error(status_code, operation):
    with pytest.raises(StoreError) as error:
        operation()
    assert error.value.status_code == status_code


def image_evidence(store, cycle_id="cycle-1", session_id="session-1", *, evidence_id=None):
    evidence_id = evidence_id or f"{cycle_id}-image"
    return store.put_evidence(
        EvidenceUpload(
            id=evidence_id,
            eventId=f"event-{evidence_id}",
            sessionId=session_id,
            cycleId=cycle_id,
            mediaType="image/png",
            contentBase64=base64.b64encode(PNG).decode(),
            capturedAt=START,
        )
    )["record"]


def inspection_records(store, put, cycle_id="cycle-1", session_id="session-1", *, prediction="good"):
    scope = {"sessionId": session_id, "cycleId": cycle_id}
    evidence = image_evidence(store, cycle_id, session_id)
    frame = put(
        "frame",
        {
            "id": f"{cycle_id}-frame",
            **scope,
            "objectId": "brick-1",
            "cameraId": "inspection-camera",
            "capturedAt": START,
            "receivedAt": START,
            "width": 1,
            "height": 1,
            "evidenceId": evidence["id"],
        },
    )["record"]
    model = put(
        "model_run",
        {
            "id": f"{cycle_id}-model-run",
            **scope,
            "provider": "local-test-fixture",
            "modelId": "fixture-detector",
            "requestedAt": START,
            "completedAt": FINISH,
            "frameIds": [frame["id"]],
            "input": {"fixture": True},
            "output": {"classification": prediction},
        },
    )["record"]
    return put(
        "inspection",
        {
            "id": f"{cycle_id}-inspection",
            **scope,
            "objectId": "brick-1",
            "frameIds": [frame["id"]],
            "modelRunId": model["id"],
            "score": 0.2 if prediction == "good" else 0.8,
            "threshold": 0.5,
            "classification": prediction,
            "requestedAt": START,
            "completedAt": FINISH,
        },
    )["record"]


def finished_cycle(
    store,
    put,
    *,
    cycle_id="cycle-1",
    session_id="session-1",
    source="live",
    failed_attempts=0,
    reference="good",
    prediction="good",
    commanded="good_bin",
    observed="good_bin",
    outcome="correct",
    attempt_outcome="successful",
):
    """Build explicit independent evidence rather than importing the demo fixture."""
    cycle = start_cycle(put, session_id=session_id, cycle_id=cycle_id, source=source)
    scope = {"sessionId": session_id, "cycleId": cycle_id}
    inspection = inspection_records(store, put, cycle_id, session_id, prediction=prediction)
    label = put(
        "reference_label",
        {
            "id": f"{cycle_id}-reference",
            **scope,
            "objectId": "brick-1",
            "quality": reference,
            "authorId": "test-operator",
            "method": "Independent fixture label",
            "createdAt": START,
        },
    )["record"]
    previous_id = None
    for ordinal in range(1, failed_attempts + 2):
        attempt_id = f"{cycle_id}-attempt-{ordinal}"
        retry = (
            {"retryOfAttemptId": previous_id, "retryReason": "Previous grasp failed"}
            if previous_id else {}
        )
        attempt = put(
            "attempt",
            {
                "id": attempt_id,
                **scope,
                "ordinal": ordinal,
                "startedAt": START,
                "endedAt": FINISH if ordinal <= failed_attempts else None,
                "outcome": "failed" if ordinal <= failed_attempts else "in_progress",
                **retry,
            },
        )["record"]
        previous_id = attempt_id
    confirmation = None
    if attempt_outcome == "successful" or outcome != "unverified":
        confirmation = put(
            "confirmation",
            {
                "id": f"{cycle_id}-confirmation",
                **scope,
                "source": "operator",
                "authorId": "test-operator",
                "attemptId": attempt["id"],
                "confirmedAt": FINISH,
                "physicalSuccess": True,
                "observedDestination": observed,
            },
        )["record"]
    put(
        "attempt",
        {
            **attempt,
            "outcome": attempt_outcome,
            "endedAt": FINISH,
            "confirmationId": confirmation["id"] if attempt_outcome == "successful" else None,
        },
        expected_revision=attempt["revision"],
    )
    return put(
        "cycle",
        {
            **cycle,
            "outcome": outcome,
            "endedAt": FINISH,
            "commandedDestination": commanded,
            "observedDestination": observed if outcome != "unverified" else None,
            "inspectionId": inspection["id"],
            "referenceLabelId": label["id"],
            "confirmationId": confirmation["id"] if outcome != "unverified" else None,
        },
        expected_revision=cycle["revision"],
    )["record"]


def assert_ratio(metric, numerator, denominator):
    assert metric["numerator"] == numerator
    assert metric["denominator"] == denominator
    if denominator == 0:
        assert metric["value"] is None


def correction_request(**overrides):
    return CorrectionRequest(
        **{
            "id": "correction-1",
            "eventId": "correction-event",
            "entityType": "session",
            "entityId": "session-1",
            "expectedRevision": 1,
            "field": "name",
            "previousValue": "Run session-1",
            "newValue": "Operator-reviewed session",
            "authorId": "test-operator",
            "reason": "Correct the recorded run name",
            "createdAt": LATER,
            **overrides,
        }
    )


def test_records_survive_a_fresh_store_instance(store, put, tmp_path):
    saved = start_cycle(put)
    sequence = store.latest_sequence()

    reopened = StationStore(tmp_path / "station.sqlite3", tmp_path / "evidence")

    assert reopened.get("cycle", saved["id"]) == saved
    assert reopened.latest_sequence() == sequence
    assert len(reopened.list_records("session")) == 1


def test_replayed_event_returns_original_result_without_another_event(store, put):
    record = session_record()
    first = put("session", record, event_id="session-created")
    sequence = store.latest_sequence()

    replayed = put("session", record, event_id="session-created")

    assert replayed["duplicate"] is True
    assert replayed["record"] == first["record"]
    assert replayed["event"] == first["event"]
    assert store.latest_sequence() == sequence
    assert len(store.list_records("session")) == 1


def test_reusing_an_event_id_for_different_content_is_rejected(store, put):
    put("session", session_record(), event_id="reserved-event")
    sequence = store.latest_sequence()
    changed = session_record("unrelated-session")

    assert_store_error(
        409, lambda: put("session", changed, event_id="reserved-event")
    )

    assert store.latest_sequence() == sequence
    assert len(store.list_records("session")) == 1


def test_semantic_duplicate_with_new_event_id_does_not_increment_revision(store, put):
    record = session_record()
    first = put("session", record)
    sequence = store.latest_sequence()

    duplicate = put("session", record, event_id="same-record-received-again")

    assert duplicate["duplicate"] is True
    assert duplicate["record"]["revision"] == first["record"]["revision"]
    assert store.latest_sequence() == sequence


def test_stale_revision_cannot_overwrite_a_newer_record(store, put):
    initial = put("session", session_record())["record"]
    updated = {**initial, "name": "Reviewed run name"}
    current = put("session", updated, expected_revision=initial["revision"])["record"]
    sequence = store.latest_sequence()

    assert_store_error(
        409,
        lambda: put(
            "session",
            {**initial, "name": "Outdated edit"},
            expected_revision=initial["revision"],
        ),
    )

    assert store.get("session", initial["id"]) == current
    assert store.latest_sequence() == sequence


def test_session_end_refuses_an_open_cycle_and_preserves_its_state(store, put):
    initial_cycle = start_cycle(put)
    initial_session = store.get("session", "session-1")
    sequence = store.latest_sequence()

    assert_store_error(
        409,
        lambda: store.end_session(
            "session-1", "end-session", FINISH, initial_session["revision"]
        ),
    )

    assert store.get("cycle", "cycle-1") == initial_cycle
    assert store.get("session", "session-1")["endedAt"] is None
    assert store.latest_sequence() == sequence


def test_cycle_cannot_be_reassigned_to_another_session(store, put):
    original = start_cycle(put)
    put("session", session_record("session-2"))
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put(
            "cycle",
            {**original, "sessionId": "session-2"},
            expected_revision=original["revision"],
        )

    assert store.get("cycle", "cycle-1")["sessionId"] == "session-1"
    assert store.latest_sequence() == sequence


def test_missing_parent_rejection_is_atomic(store, put):
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put("cycle", cycle_record(session_id="missing-session"))

    assert store.list_records("cycle") == []
    assert store.latest_sequence() == sequence


def test_event_catch_up_is_ordered_exclusive_and_read_only(store, put):
    start_cycle(put)
    first_page = store.events(after=0, limit=1)
    boundary = first_page[0]["sequence"]
    sequence = store.latest_sequence()
    before = store.list_records("cycle")

    remainder = store.events(after=boundary, limit=100)
    replay = store.events(after=boundary, limit=100)

    assert remainder == replay
    assert all(event["sequence"] > boundary for event in remainder)
    assert [event["sequence"] for event in remainder] == sorted(
        event["sequence"] for event in remainder
    )
    assert len({event["eventId"] for event in first_page + remainder}) == 2
    assert store.events(after=sequence) == []
    assert store.latest_sequence() == sequence
    assert store.list_records("cycle") == before


def test_failed_grasp_then_success_is_one_recovered_cycle_with_two_attempts(store, put):
    finished_cycle(store, put, failed_attempts=1)

    metrics = store.metrics("session-1")

    assert_ratio(metrics["endToEnd"], 1, 1)
    assert_ratio(metrics["physicalExecution"], 1, 2)
    assert metrics["cycles"]["total"] == 1
    assert metrics["attempts"]["total"] == 2
    assert metrics["attempts"]["failed"] == 1
    assert metrics["firstAttemptSuccesses"] == 0
    assert metrics["recoveredCycles"] == 1
    assert metrics["retries"] == 1
    assert store.get("attempt", "cycle-1-attempt-1")["outcome"] == "failed"


def test_two_failed_attempts_are_retained_after_recovery(store, put):
    finished_cycle(store, put, failed_attempts=2)

    metrics = store.metrics("session-1")

    assert_ratio(metrics["endToEnd"], 1, 1)
    assert_ratio(metrics["physicalExecution"], 1, 3)
    assert metrics["retries"] == 2
    assert metrics["recoveredCycles"] == 1
    assert [item["outcome"] for item in store.list_records("attempt", cycle_id="cycle-1")] == [
        "failed", "failed", "successful"
    ]


def test_additional_inspection_neither_adds_attempts_nor_inflates_detection_population(store, put):
    finished_cycle(store, put)
    original = store.get("inspection", "cycle-1-inspection")
    put(
        "inspection",
        {
            **original,
            "id": "cycle-1-additional-inspection",
            "additionalInspectionOfId": original["id"],
            "requestedAt": FINISH,
            "completedAt": LATER,
        },
    )

    metrics = store.metrics("session-1")

    assert metrics["cycles"]["total"] == 1
    assert metrics["attempts"]["total"] == 1
    assert metrics["additionalInspections"] == 1
    assert metrics["firstAttemptSuccesses"] == 1
    assert metrics["retries"] == 0
    assert metrics["detection"]["checked"] == 1
    assert metrics["detection"]["totalPopulation"] == 1


def test_late_confirmation_updates_original_cycle_and_attempt_revisions(store, put):
    old_cycle = finished_cycle(
        store, put, outcome="unverified", attempt_outcome="unverified"
    )
    old_attempt = store.get("attempt", "cycle-1-attempt-1")
    assert_ratio(store.metrics("session-1")["endToEnd"], 0, 1)
    confirmation = put(
        "confirmation",
        {
            "id": "delayed-confirmation",
            "sessionId": "session-1",
            "cycleId": "cycle-1",
            "attemptId": old_attempt["id"],
            "source": "operator",
            "authorId": "test-operator",
            "confirmedAt": LATER,
            "physicalSuccess": True,
            "observedDestination": "good_bin",
        },
    )["record"]
    attempt = put(
        "attempt",
        {**old_attempt, "outcome": "successful", "confirmationId": confirmation["id"]},
        expected_revision=old_attempt["revision"],
    )["record"]
    cycle = put(
        "cycle",
        {
            **old_cycle,
            "outcome": "correct",
            "confirmationId": confirmation["id"],
            "observedDestination": "good_bin",
        },
        expected_revision=old_cycle["revision"],
    )["record"]

    assert cycle["id"] == old_cycle["id"]
    assert cycle["revision"] == old_cycle["revision"] + 1
    assert attempt["revision"] == old_attempt["revision"] + 1
    assert len(store.list_records("cycle")) == 1
    assert len(store.list_records("attempt")) == 1
    assert_ratio(store.metrics("session-1")["endToEnd"], 1, 1)
    assert_ratio(store.metrics("session-1")["physicalExecution"], 1, 1)


def test_unverified_aborted_and_failed_cycles_stay_in_finished_denominator(store, put):
    finished_cycle(store, put)
    for outcome in ("unverified", "aborted", "failed", "in_progress"):
        cycle = put("cycle", cycle_record(f"cycle-{outcome}"))["record"]
        put(
            "attempt",
            {"id": f"attempt-{outcome}", "sessionId": "session-1", "cycleId": cycle["id"],
             "ordinal": 1, "startedAt": START,
             "endedAt": None if outcome == "in_progress" else FINISH, "outcome": outcome},
        )
        if outcome != "in_progress":
            put("cycle", {**cycle, "outcome": outcome, "endedAt": FINISH},
                expected_revision=cycle["revision"])

    metrics = store.metrics("session-1")

    assert_ratio(metrics["endToEnd"], 1, 4)
    assert_ratio(metrics["physicalExecution"], 1, 4)
    assert metrics["cycles"]["total"] == 5
    assert metrics["cycles"]["finished"] == 4
    assert metrics["cycles"]["inProgress"] == 1
    assert metrics["attempts"]["inProgress"] == 1
    for outcome in ("unverified", "aborted", "failed"):
        assert metrics["cycles"][outcome] == 1
    assert store.get("cycle", "cycle-unverified")["outcome"] == "unverified"


def test_simulated_results_are_excluded_from_default_hardware_metrics(store, put):
    finished_cycle(store, put, cycle_id="live-cycle")
    finished_cycle(
        store, put, cycle_id="sim-cycle", session_id="sim-session", source="simulation"
    )

    assert_ratio(store.metrics()["endToEnd"], 1, 1)
    assert_ratio(store.metrics(include_simulation=True)["endToEnd"], 2, 2)
    assert_ratio(store.metrics("sim-session")["endToEnd"], 0, 0)
    assert_ratio(store.metrics("sim-session", include_simulation=True)["endToEnd"], 1, 1)
    assert len(store.list_records("cycle")) == 2


def test_wrong_bin_can_be_physical_success_but_is_not_end_to_end_correct(store, put):
    cycle = finished_cycle(
        store,
        put,
        reference="defective",
        prediction="good",
        commanded="good_bin",
        observed="good_bin",
        outcome="failed",
    )

    metrics = store.metrics("session-1")

    assert_ratio(metrics["physicalExecution"], 1, 1)
    assert_ratio(metrics["endToEnd"], 0, 1)
    assert metrics["detection"]["correct"] == 0
    assert metrics["detection"]["checked"] == 1
    assert cycle["commandedDestination"] == cycle["observedDestination"] == "good_bin"
    assert store.get("reference_label", cycle["referenceLabelId"])["quality"] == "defective"
    sequence = store.latest_sequence()
    with pytest.raises(StoreError):
        store.correct(
            correction_request(
                entityType="cycle", entityId=cycle["id"], expectedRevision=cycle["revision"],
                field="outcome", previousValue="failed", newValue="correct",
                reason="Attempt to count commanded placement as overall correctness",
            )
        )
    assert store.latest_sequence() == sequence
    assert store.get("cycle", cycle["id"])["outcome"] == "failed"


def test_new_session_has_fresh_totals_without_erasing_closed_history(store, put):
    finished_cycle(store, put)
    original = store.get("session", "session-1")
    store.end_session("session-1", "close-session-1", LATER, original["revision"])
    put("session", session_record("session-2"))

    assert_ratio(store.metrics("session-1")["endToEnd"], 1, 1)
    assert_ratio(store.metrics("session-2")["endToEnd"], 0, 0)
    assert store.get("session", "session-1")["endedAt"] is not None
    assert len(store.list_records("session")) == 2
    assert len(store.list_records("cycle")) == 1


def test_manual_correction_preserves_full_audit_and_is_idempotent(store, put):
    original = put("session", session_record())["record"]
    request = correction_request(expectedRevision=original["revision"])

    result = store.correct(request)
    sequence = store.latest_sequence()
    repeated = store.correct(request)

    audit = result["correction"]
    for key in ("previousValue", "newValue", "authorId", "reason", "entityId", "field"):
        assert audit[key] == getattr(request, key)
    assert datetime.fromisoformat(audit["createdAt"].replace("Z", "+00:00")) == request.createdAt
    assert result["record"]["name"] == request.newValue
    assert result["record"]["revision"] == original["revision"] + 1
    assert repeated["duplicate"] is True
    assert repeated["correction"] == audit
    assert store.latest_sequence() == sequence


def test_stale_or_conflicting_corrections_do_not_replace_history(store, put):
    original = put("session", session_record())["record"]
    sequence = store.latest_sequence()
    assert_store_error(
        409, lambda: store.correct(correction_request(previousValue="A value never stored"))
    )
    assert store.get("session", "session-1") == original
    assert store.latest_sequence() == sequence
    store.correct(correction_request())
    sequence = store.latest_sequence()
    current = store.get("session", "session-1")

    assert_store_error(
        409,
        lambda: store.correct(
            correction_request(eventId="different-correction-event", newValue="Conflicting edit")
        ),
    )

    assert store.get("session", "session-1") == current
    assert store.latest_sequence() == sequence


def test_replaying_saved_views_never_creates_new_records_or_events(store, put):
    finished_cycle(store, put, failed_attempts=1)
    sequence = store.latest_sequence()
    expected = store.metrics("session-1")
    entities = {
        kind: store.list_records(kind)
        for kind in ("session", "cycle", "attempt", "inspection", "execution")
    }

    for _ in range(3):
        store.snapshot("session-1")
        store.cycle_detail("cycle-1")
        store.events(after=0, limit=100)
        assert store.metrics("session-1") == expected

    assert store.latest_sequence() == sequence
    for kind, records in entities.items():
        assert store.list_records(kind) == records


def test_evidence_is_immutable_and_cannot_be_reassigned_to_a_different_cycle(store, put):
    start_cycle(put)
    put("cycle", cycle_record("cycle-2"))
    evidence = image_evidence(store)
    file_path, media_type = store.evidence_file(evidence["id"])
    sequence = store.latest_sequence()

    assert file_path.read_bytes() == PNG
    assert media_type == "image/png"
    with pytest.raises(StoreError):
        store.put_evidence(
            EvidenceUpload(
                id=evidence["id"],
                eventId="reassign-evidence",
                sessionId="session-1",
                cycleId="cycle-2",
                mediaType="image/png",
                contentBase64=base64.b64encode(PNG).decode(),
                capturedAt=START,
            )
        )
    assert store.latest_sequence() == sequence
    assert file_path.read_bytes() == PNG


def test_attempt_cannot_claim_cycle_from_another_session(store, put):
    start_cycle(put)
    put("session", session_record("session-2"))
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put(
            "attempt",
            {
                "id": "wrong-session-attempt",
                "sessionId": "session-2",
                "cycleId": "cycle-1",
                "ordinal": 1,
                "startedAt": START,
            },
        )

    assert store.list_records("attempt") == []
    assert store.latest_sequence() == sequence


def test_inspection_cannot_borrow_evidence_from_another_cycle(store, put):
    start_cycle(put)
    original = inspection_records(store, put)
    put("cycle", cycle_record("cycle-2"))
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put(
            "inspection",
            {**original, "id": "cross-cycle-inspection", "cycleId": "cycle-2"},
        )

    assert len(store.list_records("inspection")) == 1
    assert store.latest_sequence() == sequence


def test_controller_completion_without_confirmation_cannot_be_success(store, put):
    cycle = start_cycle(put)
    attempt = put(
        "attempt",
        {"id": "attempt-1", "sessionId": "session-1", "cycleId": "cycle-1",
         "ordinal": 1, "startedAt": START},
    )["record"]
    put(
        "execution",
        {"id": "execution-1", "sessionId": "session-1", "cycleId": "cycle-1",
         "attemptId": "attempt-1", "taskId": "pick", "policyId": "fixture-policy",
         "status": "finished", "requestedAt": START, "finishedAt": FINISH},
    )
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put("attempt", {**attempt, "outcome": "successful", "endedAt": FINISH},
            expected_revision=attempt["revision"])
    with pytest.raises(StoreError):
        put("cycle", {**cycle, "outcome": "correct", "endedAt": FINISH},
            expected_revision=cycle["revision"])

    assert store.latest_sequence() == sequence
    assert store.get("attempt", "attempt-1")["outcome"] == "in_progress"
    assert store.get("cycle", "cycle-1")["outcome"] == "in_progress"


def test_empty_or_unlabeled_data_never_reports_perfect_quality(store, put):
    empty = store.metrics()
    assert_ratio(empty["endToEnd"], 0, 0)
    assert_ratio(empty["physicalExecution"], 0, 0)
    assert_ratio(empty["detection"]["rate"], 0, 0)
    start_cycle(put)
    inspection_records(store, put)

    unlabeled = store.metrics("session-1")

    assert unlabeled["detection"]["checked"] == 0
    assert unlabeled["detection"]["totalPopulation"] == 1
    assert_ratio(unlabeled["detection"]["rate"], 0, 0)


def test_reference_correction_cannot_silently_invalidate_a_confirmed_correct_cycle(store, put):
    cycle = finished_cycle(store, put)
    label = store.get("reference_label", cycle["referenceLabelId"])
    sequence = store.latest_sequence()

    assert_store_error(
        409,
        lambda: store.correct(
            correction_request(
                entityType="reference_label",
                entityId=label["id"],
                expectedRevision=label["revision"],
                field="quality",
                previousValue="good",
                newValue="defective",
                reason="New independent review changes the reference label",
            )
        ),
    )

    assert store.get("reference_label", label["id"]) == label
    assert store.get("cycle", cycle["id"]) == cycle
    assert store.list_records("correction") == []
    assert store.latest_sequence() == sequence
    assert_ratio(store.metrics("session-1")["endToEnd"], 1, 1)


def test_session_scoped_model_and_goal_cannot_use_another_sessions_evidence(store, put):
    start_cycle(put)
    inspection = inspection_records(store, put)
    put("session", session_record("session-2"))
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put(
            "model_run",
            {"id": "foreign-frame-model", "sessionId": "session-2", "cycleId": None,
             "provider": "fixture", "modelId": "fixture-model", "requestedAt": START,
             "completedAt": FINISH, "frameIds": inspection["frameIds"]},
        )
    with pytest.raises(StoreError):
        put(
            "decision",
            {"id": "foreign-model-goal", "sessionId": "session-2", "cycleId": None,
             "kind": "goal", "modelRunId": inspection["modelRunId"],
             "offeredChoices": ["standard_sorting", "hold"], "selectedChoice": "hold",
             "stateVersion": 1, "goalVersion": 1, "requestedAt": START,
             "completedAt": FINISH},
        )

    assert store.latest_sequence() == sequence
    assert store.list_records("model_run", session_id="session-2") == []
    assert store.list_records("decision", session_id="session-2") == []


def test_ended_session_rejects_new_cycles_and_attempts_without_changing_history(store, put):
    finished_cycle(store, put)
    session = store.get("session", "session-1")
    store.end_session("session-1", "close-session", LATER, session["revision"])
    sequence = store.latest_sequence()

    with pytest.raises(StoreError):
        put("cycle", cycle_record("after-session-cycle"))
    with pytest.raises(StoreError):
        put(
            "attempt",
            {"id": "after-session-attempt", "sessionId": "session-1", "cycleId": "cycle-1",
             "ordinal": 2, "startedAt": LATER, "retryOfAttemptId": "cycle-1-attempt-1",
             "retryReason": "An unintentional reconnect attempted to start new work"},
        )

    assert store.latest_sequence() == sequence
    assert len(store.list_records("cycle")) == 1
    assert len(store.list_records("attempt")) == 1
    assert_ratio(store.metrics("session-1")["endToEnd"], 1, 1)


@pytest.mark.parametrize("semantic_duplicate", [False, True])
def test_correction_target_cannot_reuse_an_event_id_reserved_by_another_request(
    store, put, semantic_duplicate
):
    original = put("session", session_record())["record"]
    # Both persisted events and duplicate-request receipts reserve a caller's ID.
    reservation = session_record() if semantic_duplicate else session_record("other-session")
    put("session", reservation, event_id="correction-event:target")
    sequence = store.latest_sequence()

    assert_store_error(409, lambda: store.correct(correction_request()))

    assert store.get("session", "session-1") == original
    assert store.list_records("correction") == []
    assert store.latest_sequence() == sequence


@pytest.mark.parametrize("distinct_event_ids", [False, True])
def test_concurrent_duplicate_requests_create_one_record_revision_and_event(store, distinct_event_ids):
    writes = [
        RecordWrite(
            eventId=f"concurrent-{index}" if distinct_event_ids else "concurrent-event",
            recordType="session",
            record=session_record(),
        )
        for index in range(8)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(store.upsert, writes))

    assert sum(not result["duplicate"] for result in results) == 1
    assert all(result["record"]["revision"] == 1 for result in results)
    assert len(store.list_records("session")) == 1
    assert len(store.events(after=0)) == 1
    assert store.latest_sequence() == 1
