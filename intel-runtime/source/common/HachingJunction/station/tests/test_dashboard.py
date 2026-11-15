"""Bounded coherent dashboard reads from temporary records; no physical I/O."""

from copy import deepcopy
from itertools import count

import pytest
from fastapi.testclient import TestClient

from morph_station.api import create_app
from morph_station.models import RecordWrite
from morph_station.store import DASHBOARD_MAX_RESPONSE_BYTES, StationStore
from test_store import FINISH, START, cycle_record, finished_cycle, inspection_records, session_record


@pytest.fixture
def dashboard_client(tmp_path, monkeypatch):
    monkeypatch.delenv("MORPH_CORS_ORIGINS", raising=False)
    token = "dashboard-test-only-" + "x" * 40
    app = create_app(db_path=tmp_path / "dashboard.sqlite3", token=token,
                     evidence_dir=tmp_path / "evidence")
    with TestClient(app, headers={"Authorization": "Bearer " + token}) as client:
        yield client


@pytest.fixture
def store(dashboard_client):
    return dashboard_client.app.state.store


@pytest.fixture
def put(store):
    sequence = count(1)

    def write(kind, record, *, event_id=None, expected_revision=None):
        data = deepcopy(record)
        data.pop("revision", None)
        return store.upsert(RecordWrite(eventId=event_id or f"dashboard-event-{next(sequence)}",
                                       recordType=kind, record=data, expectedRevision=expected_revision))
    return write


def read(client, **query):
    result = client.get("/api/v1/dashboard", params=query)
    assert result.status_code == 200, result.text
    return result.json()


def test_empty_source_selection_advertisement_and_no_actions(dashboard_client, store, put):
    put("session", session_record("simulation-only", source="simulation"))
    put("cycle", cycle_record("simulation-cycle", session_id="simulation-only"))
    before = store.latest_sequence()
    data = read(dashboard_client)
    assert data["sourceMode"] == "live"
    assert data["sessions"] == {"items": [], "limit": 50, "total": 0, "hasMore": False}
    assert data["selectedSessionId"] is None
    assert data["snapshot"]["session"] is None
    assert data["currentDetail"] is None
    assert data["metrics"]["cycles"]["total"] == 0
    assert data["metrics"]["endToEnd"]["value"] is None
    assert data["metrics"]["filters"]["includedSessionIds"] == []
    assert data["snapshot"]["metrics"] == data["metrics"]
    assert data["generatedAt"] == data["snapshot"]["generatedAt"]
    assert data["lastEventSequence"] == data["snapshot"]["lastEventSequence"] == before
    assert data["snapshot"]["availableActions"] == []
    assert all(not capability["verified"] for capability in data["snapshot"]["capabilities"].values())
    assert data["cameras"]["status"] == "unavailable"
    assert store.latest_sequence() == before
    schema = dashboard_client.get("/api/v1/schema").json()
    assert schema["capabilities"]["dashboardRead"]["maxResponseBytes"] == DASHBOARD_MAX_RESPONSE_BYTES
    assert "Dashboard" in schema["responses"]
    with TestClient(dashboard_client.app) as anonymous:
        assert anonymous.get("/api/v1/dashboard").status_code == 401
        assert anonymous.get("/health").json()["dashboardRead"] == schema["capabilities"]["dashboardRead"]


def test_pages_bound_source_filter_and_old_selected_session(dashboard_client, put):
    for index in range(54):
        put("session", session_record(f"live-{index:03d}"))
    put("session", session_record("zz-simulation", source="simulation"))
    for index in range(23):
        put("cycle", cycle_record(f"cycle-{index:03d}", session_id="live-000"))
    latest = read(dashboard_client)
    assert latest["selectedSessionId"] == "live-053"
    assert len(latest["sessions"]["items"]) == 50
    assert latest["sessions"]["total"] == 54
    assert latest["sessions"]["hasMore"] is True
    assert all(item["sourceMode"] == "live" for item in latest["sessions"]["items"])
    selected = read(dashboard_client, sessionId="live-000")
    assert selected["snapshot"]["session"]["id"] == "live-000"
    assert "live-000" not in {item["id"] for item in selected["sessions"]["items"]}
    assert selected["recentCycles"]["limit"] == 20
    assert selected["recentCycles"]["offset"] == 0
    assert selected["recentCycles"]["total"] == 23
    assert selected["recentCycles"]["hasMore"] is True
    assert len(selected["recentCycles"]["items"]) == 20
    assert selected["currentDetail"]["cycle"]["id"] == "cycle-022"
    focused = read(dashboard_client, sessionId="live-000", cycleId="cycle-000")
    assert focused["detail"]["cycle"]["id"] == "cycle-000"
    assert focused["currentDetail"]["cycle"]["id"] == "cycle-022"
    assert focused["detail"]["cycle"]["sessionId"] == focused["snapshot"]["session"]["id"]
    assert dashboard_client.get("/api/v1/dashboard?sessionId=live-001&cycleId=cycle-000").status_code == 409
    assert dashboard_client.get("/api/v1/dashboard?sessionId=live-000&cycleId=missing").status_code == 404
    small = read(dashboard_client, sessionId="live-000", limit=2)
    assert [item["id"] for item in small["recentCycles"]["items"]] == ["cycle-022", "cycle-021"]
    assert small["metrics"]["cycles"]["total"] == 23
    simulation = read(dashboard_client, sourceMode="simulation")
    assert simulation["selectedSessionId"] == "zz-simulation"
    assert simulation["sessions"]["total"] == 1
    assert dashboard_client.get("/api/v1/dashboard?sessionId=zz-simulation").status_code == 409
    assert dashboard_client.get("/api/v1/dashboard?sessionId=missing").status_code == 404


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=-1", "limit=2.5",
                                 "sourceMode=replay", "sessionId=", "sessionId=..", "cycleId=..", "cycleId=",
                                 "limit=1&limit=2", "sourceMode=live&sourceMode=simulation", "offset=1"])
def test_invalid_or_ambiguous_queries_rejected(dashboard_client, query):
    assert dashboard_client.get("/api/v1/dashboard?" + query).status_code == 422


def test_coherent_sqlite_read_with_concurrent_writer(dashboard_client, store, put, monkeypatch):
    put("session", session_record())
    put("cycle", cycle_record())
    before = store.latest_sequence()
    writer = StationStore(store.db_path, store.evidence_dir)
    original_metrics = store._metrics

    def write_during_read(db, *args, **kwargs):
        writer.upsert(RecordWrite(eventId="concurrent-cycle", recordType="cycle",
                                  record=cycle_record("new-cycle")))
        return original_metrics(db, *args, **kwargs)

    monkeypatch.setattr(store, "_metrics", write_during_read)
    data = read(dashboard_client)
    assert store.latest_sequence() == before + 1
    assert data["lastEventSequence"] == before
    assert data["snapshot"]["lastEventSequence"] == before
    assert data["metrics"]["cycles"]["total"] == data["recentCycles"]["total"] == 1
    assert data["snapshot"]["activeCycleIds"] == ["cycle-1"]
    assert data["currentDetail"]["cycle"]["id"] == "cycle-1"
    assert data["detail"] == data["currentDetail"]
    monkeypatch.setattr(store, "_metrics", original_metrics)
    refreshed = read(dashboard_client)
    assert refreshed["lastEventSequence"] == before + 1
    assert refreshed["metrics"]["cycles"]["total"] == 2


def test_fractional_timestamps_sort_by_time_not_the_z_suffix(dashboard_client, put):
    put("session", session_record("z-earlier"))
    later = {**session_record("a-later"), "startedAt": "2026-11-14T12:00:00.100000Z"}
    put("session", later)
    put("cycle", {**cycle_record("z-cycle-earlier", session_id="a-later"),
                  "startedAt": "2026-11-14T12:00:01Z"})
    put("cycle", {**cycle_record("a-cycle-later", session_id="a-later"),
                  "startedAt": "2026-11-14T12:00:01.000001Z"})
    result = read(dashboard_client)
    assert result["selectedSessionId"] == "a-later"
    assert result["snapshot"]["cycle"]["id"] == "a-cycle-later"
    assert [item["id"] for item in result["recentCycles"]["items"]] == ["a-cycle-later", "z-cycle-earlier"]


def test_exact_metrics_recovery_unknown_duplicate_and_late_confirmation(dashboard_client, store, put):
    finished_cycle(store, put, cycle_id="recovered", failed_attempts=1)
    unknown = finished_cycle(store, put, cycle_id="unknown", outcome="unverified", attempt_outcome="unverified")
    finished_cycle(store, put, cycle_id="simulated", session_id="simulation", source="simulation")
    before = store.latest_sequence()
    # A repeated complete record remains the same record and event.
    duplicate = put("cycle", unknown)
    assert duplicate["duplicate"] is True
    assert store.latest_sequence() == before
    data = read(dashboard_client, sessionId="session-1")
    metrics = data["metrics"]
    assert metrics == store.metrics("session-1")
    assert metrics["cycles"]["finished"] == 2
    assert metrics["cycles"]["unverified"] == 1
    assert metrics["endToEnd"]["numerator"] == 1
    assert metrics["endToEnd"]["denominator"] == 2
    assert metrics["physicalExecution"]["numerator"] == 1
    assert metrics["physicalExecution"]["denominator"] == 3
    assert metrics["recoveredCycles"] == metrics["retries"] == 1
    assert metrics["firstAttemptSuccesses"] == 0
    assert metrics["timings"]["fullCycle"]["sampleCount"] == 2
    assert len(metrics["timings"]["fullCycle"]["valuesMs"]) == 2
    confirmation = put("confirmation", {
        "id": "late-confirmation", "sessionId": "session-1", "cycleId": "unknown",
        "source": "operator", "authorId": "fixture-operator", "attemptId": "unknown-attempt-1",
        "confirmedAt": FINISH, "physicalSuccess": True, "observedDestination": "good_bin",
    })["record"]
    attempt = store.get("attempt", "unknown-attempt-1")
    put("attempt", {**attempt, "outcome": "successful", "confirmationId": confirmation["id"]},
        expected_revision=attempt["revision"])
    put("cycle", {**unknown, "outcome": "correct", "confirmationId": confirmation["id"],
                  "observedDestination": "good_bin"}, expected_revision=unknown["revision"])
    updated = read(dashboard_client, sessionId="session-1")
    assert updated["metrics"]["cycles"]["total"] == 2
    assert updated["metrics"]["endToEnd"]["numerator"] == 2
    assert updated["metrics"]["retries"] == 1
    assert any(revision["recordType"] == "cycle" and revision["record"]["outcome"] == "unverified"
               for revision in updated["currentDetail"]["revisions"])


def test_current_evidence_complete_and_images_separate(dashboard_client, store, put):
    put("session", session_record())
    put("cycle", cycle_record())
    inspection = inspection_records(store, put)
    data = read(dashboard_client)
    detail = data["currentDetail"]
    assert detail == store.cycle_detail("cycle-1")
    assert detail["inspections"][0]["id"] == inspection["id"]
    assert detail["modelRuns"][0]["id"] == inspection["modelRunId"]
    assert detail["frames"][0]["id"] in inspection["frameIds"]
    evidence = detail["evidence"][0]
    assert "contentBase64" not in evidence
    image = dashboard_client.get("/api/v1/evidence/" + evidence["id"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"


def test_oversize_detail_returns_explicit_error_without_partial_evidence(dashboard_client, store, put):
    put("session", session_record())
    put("cycle", cycle_record())
    for index in range(2):
        put("model_run", {"id": f"large-model-{index}", "sessionId": "session-1", "cycleId": "cycle-1",
                          "provider": "fixture", "modelId": "fixture-model", "requestedAt": START,
                          "input": {"savedPrompt": "a" * 800_000}})
    before = store.latest_sequence()
    result = dashboard_client.get("/api/v1/dashboard")
    assert result.status_code == 413
    assert result.json()["code"] == "dashboard_response_too_large"
    assert result.json()["maxResponseBytes"] < 4 * 1024 * 1024
    assert "currentDetail" not in result.json()
    assert result.headers["cache-control"] == "private, no-store"
    assert store.latest_sequence() == before
