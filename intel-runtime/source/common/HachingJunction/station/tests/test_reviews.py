"""Atomic operator reviews, audit preservation and retries on isolated simulation data."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

from fastapi.testclient import TestClient
import pytest

from morph_station.api import create_app
from morph_station.store import StationStore, StoreError
from test_store import (
    FINISH, LATER, START, assert_ratio, correction_request, finished_cycle,
    put, start_cycle, store,
)


def late_review(store, **overrides):
    cycle = store.get("cycle", "cycle-1")
    attempt = store.list_records("attempt", cycle_id="cycle-1")[-1]
    return {
        "id": "review-1", "eventId": "review-event-1", "expectedRevision": cycle["revision"],
        "authorId": "reviewer", "reason": "Independent observation confirms the final placement",
        "createdAt": LATER,
        "confirmation": {
            "id": "late-confirmation", "source": "operator", "confirmedAt": LATER,
            "physicalSuccess": True, "observedDestination": "good_bin", "evidenceIds": [],
            "attemptId": attempt["id"], "expectedAttemptRevision": attempt["revision"],
            "attemptOutcome": "successful",
        },
        "changes": {"outcome": "correct"}, **overrides,
    }


def unchanged_snapshot(store):
    snapshot = store.export_session("session-1")
    snapshot.pop("exportedAt")
    with sqlite3.connect(store.db_path) as db:
        snapshot["receiptCount"] = db.execute("SELECT COUNT(*) FROM request_receipts").fetchone()[0]
        snapshot["reviewCount"] = db.execute("SELECT COUNT(*) FROM review_requests").fetchone()[0]
    return snapshot


def test_late_confirmation_retains_failure_and_exact_recovered_denominators(store, put):
    finished_cycle(store, put, failed_attempts=1, outcome="unverified", attempt_outcome="unverified", source="simulation")
    before = store.cycle_detail("cycle-1")
    response = store.review_cycle("cycle-1", late_review(store))
    detail = response["cycle"]
    assert response["duplicate"] is False
    assert detail["cycle"]["outcome"] == "correct"
    assert detail["cycle"]["endedAt"] == before["cycle"]["endedAt"]
    assert detail["attempts"][0] == before["attempts"][0]
    assert detail["attempts"][1]["outcome"] == "successful"
    assert len(detail["attempts"]) == 2
    audits = {(r["entityType"], r["field"]): r for r in detail["corrections"]}
    assert audits["cycle", "outcome"]["previousValue"] == "unverified"
    assert audits["cycle", "outcome"]["newValue"] == "correct"
    assert audits["attempt", "outcome"]["previousValue"] == "unverified"
    assert all(r["authorId"] == "reviewer" and r["reason"] and r["createdAt"] for r in audits.values())
    metrics = store.metrics(include_simulation=True)
    assert_ratio(metrics["endToEnd"], 1, 1)
    assert_ratio(metrics["physicalExecution"], 1, 2)
    assert (metrics["cycles"]["total"], metrics["attempts"]["total"], metrics["retries"],
            metrics["recoveredCycles"], metrics["firstAttemptSuccesses"]) == (1, 2, 1, 1, 0)
    assert store.metrics()["cycles"]["total"] == 0


def test_review_retry_is_exact_across_concurrency_restart_and_later_correction(store, put):
    finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    body = late_review(store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.review_cycle("cycle-1", body), range(2)))
    assert sorted(r["duplicate"] for r in results) == [False, True]
    original = next(r for r in results if not r["duplicate"])
    current = store.get("cycle", "cycle-1")
    store.correct(correction_request(entityType="cycle", entityId="cycle-1", expectedRevision=current["revision"],
                                     field="outcome", previousValue="correct", newValue="unverified"))
    snapshot = unchanged_snapshot(store)
    restarted = StationStore(store.db_path, store.evidence_dir)
    assert restarted.review_cycle("cycle-1", body) == {**original, "duplicate": True}
    assert unchanged_snapshot(restarted) == snapshot


def test_label_and_correct_cycle_downgrade_commit_together_with_original_attribution(store, put):
    cycle = finished_cycle(store, put)
    label = store.get("reference_label", cycle["referenceLabelId"])
    body = late_review(store, confirmation=None, changes={"outcome": "failed"}, label={
        "id": label["id"], "expectedRevision": label["revision"], "quality": "defective",
        "method": "Independent manual review of saved evidence", "evidenceIds": label["evidenceIds"],
    })
    detail = store.review_cycle("cycle-1", body)["cycle"]
    changed = detail["referenceLabels"][0]
    assert changed["quality"] == "defective"
    assert changed["authorId"] == label["authorId"]
    assert changed["createdAt"] == label["createdAt"]
    assert {(r["entityType"], r["field"]) for r in detail["corrections"]} == {
        ("reference_label", "quality"), ("reference_label", "method"), ("cycle", "outcome")}
    assert detail["cycle"]["outcome"] == "failed"


def test_new_reference_label_is_linked_in_same_transaction(store, put):
    cycle = start_cycle(put, source="simulation")
    body = {"id": "label-review", "eventId": "label-review-event", "expectedRevision": cycle["revision"],
            "authorId": "reviewer", "reason": "Independent reference quality entry", "createdAt": LATER,
            "label": {"id": "new-label", "quality": "good", "method": "Manual inspection", "evidenceIds": []}}
    detail = store.review_cycle("cycle-1", body)["cycle"]
    assert detail["cycle"]["referenceLabelId"] == "new-label"
    assert detail["referenceLabels"][0]["authorId"] == "reviewer"
    assert detail["corrections"][0]["previousValue"] is None
    assert store.get("cycle", "cycle-1")["outcome"] == "in_progress"


@pytest.mark.parametrize("failure", ["stale_cycle", "stale_attempt", "invalid_evidence", "wrong_destination", "wrong_prediction"])
def test_review_failure_rolls_back_records_events_revisions_and_receipts(store, put, failure):
    cycle = finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    label = store.get("reference_label", cycle["referenceLabelId"])
    body = late_review(store, label={"id": label["id"], "expectedRevision": label["revision"],
                                     "quality": "good", "method": "Rechecked independently", "evidenceIds": []})
    if failure == "stale_cycle": body["expectedRevision"] = 999
    if failure == "stale_attempt": body["confirmation"]["expectedAttemptRevision"] = 999
    if failure == "invalid_evidence": body["confirmation"]["evidenceIds"] = ["missing-evidence"]
    if failure == "wrong_destination": body["changes"]["observedDestination"] = "defective_bin"
    if failure == "wrong_prediction": body["label"]["quality"] = "defective"
    before = unchanged_snapshot(store)
    with pytest.raises(StoreError):
        store.review_cycle("cycle-1", body)
    assert unchanged_snapshot(store) == before


@pytest.mark.parametrize("reuse", ["event", "review", "confirmation", "label", "label_revision"])
def test_review_rejects_reused_ids_stale_labels_and_immutable_evidence(store, put, reuse):
    finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    body = late_review(store)
    store.review_cycle("cycle-1", body)
    new_body = late_review(store, id="review-2", eventId="review-event-2", changes={"outcome": "unverified"})
    new_body["confirmation"]["id"] = "confirmation-2"
    if reuse == "event": new_body["eventId"] = body["eventId"]
    if reuse == "review": new_body["id"] = body["id"]
    if reuse == "confirmation": new_body["confirmation"]["id"] = "late-confirmation"
    if reuse in ("label", "label_revision"):
        label = store.list_records("reference_label")[0]
        new_body["label"] = {"id": label["id"], "quality": "good", "method": "Edited method",
                              "evidenceIds": ["new-evidence"] if reuse == "label" else [],
                              "expectedRevision": label["revision"] if reuse == "label" else 999}
    before = unchanged_snapshot(store)
    with pytest.raises(StoreError): store.review_cycle("cycle-1", new_body)
    assert unchanged_snapshot(store) == before


@pytest.mark.parametrize("field,value", [("reason", "  "), ("authorId", ""), ("createdAt", "2026-11-14T12:00:20"),
                                         ("changes", {"commandedDestination": "other"}), ("changes", {"outcome": None})])
def test_review_http_validates_attribution_time_and_narrow_fields(store, put, field, value):
    finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    app = create_app(store.db_path, token="t" * 40, evidence_dir=store.evidence_dir)
    body = late_review(store)
    body[field] = value
    before = unchanged_snapshot(store)
    with TestClient(app, headers={"Authorization": "Bearer " + "t" * 40}) as client:
        assert client.post("/api/v1/cycles/cycle-1/review", json=body).status_code == 422
        assert "CycleReview" in client.get("/api/v1/schema").json()["envelopes"]
    assert unchanged_snapshot(store) == before


def test_review_http_authentication_and_operator_only_confirmation(store, put):
    finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    body = late_review(store)
    app = create_app(store.db_path, token="t" * 40, evidence_dir=store.evidence_dir)
    with TestClient(app) as client:
        assert client.post("/api/v1/cycles/cycle-1/review", json=body).status_code == 401
        body["confirmation"]["source"] = "camera"
        assert client.post("/api/v1/cycles/cycle-1/review", json=body,
                           headers={"Authorization": "Bearer " + "t" * 40}).status_code == 422
        body["confirmation"]["source"] = "operator"
        result = client.post("/api/v1/cycles/cycle-1/review", json=body,
                             headers={"Authorization": "Bearer " + "t" * 40})
        assert result.status_code == 200, result.text
        assert result.json()["cycle"]["cycle"]["outcome"] == "correct"


def test_review_rejects_cross_cycle_attempt(store, put):
    finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    other = finished_cycle(store, put, cycle_id="cycle-2", session_id="session-2", outcome="unverified", attempt_outcome="unverified")
    body = late_review(store)
    body["confirmation"]["attemptId"] = "cycle-2-attempt-1"
    before = unchanged_snapshot(store)
    with pytest.raises(StoreError, match="another session"):
        store.review_cycle("cycle-1", body)
    assert unchanged_snapshot(store) == before
    assert store.get("cycle", other["id"]) == other


def test_review_cannot_finish_active_execution_or_invent_its_end(store, put):
    start_cycle(put)
    put("attempt", {"id": "active-attempt", "sessionId": "session-1", "cycleId": "cycle-1",
                    "ordinal": 1, "startedAt": START})
    body = late_review(store)
    before = unchanged_snapshot(store)
    with pytest.raises(StoreError, match="active execution"):
        store.review_cycle("cycle-1", body)
    assert unchanged_snapshot(store) == before


@pytest.mark.parametrize("confirmed_at", ["2026-11-14T11:59:59Z", "2026-11-14T12:01:00Z"])
def test_review_rejects_observation_before_work_or_after_its_recording(store, put, confirmed_at):
    finished_cycle(store, put, outcome="unverified", attempt_outcome="unverified")
    body = late_review(store)
    body["confirmation"]["confirmedAt"] = confirmed_at
    before = unchanged_snapshot(store)
    with pytest.raises(StoreError): store.review_cycle("cycle-1", body)
    assert unchanged_snapshot(store) == before

