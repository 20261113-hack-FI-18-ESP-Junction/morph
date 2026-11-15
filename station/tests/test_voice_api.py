"""Authenticated speech lab API tests with simulated provider events."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from morph_station.api import create_app
from morph_station.models import RecordWrite
from morph_station.voice import SCRIBE_MODEL
from morph_station.voice_api import install_voice_routes

TOKEN = "voice-test-only-token-" + "x" * 40
PREFIX = "/api/v1/lab/voice"


@pytest.fixture
def lab(tmp_path):
    now = [datetime(2026, 11, 14, 20, 0, 0, tzinfo=timezone.utc)]
    app = create_app(db_path=tmp_path / "lab.sqlite3", token=TOKEN)
    install_voice_routes(app, lambda: {}, clock=lambda: now[0])
    with TestClient(app, headers={"Authorization": "Bearer " + TOKEN}) as client:
        for sid, mode in (("sim1", "simulation"), ("sim2", "simulation"), ("real", "live")):
            response = client.post("/api/v1/sessions", json={"eventId": "create-" + sid, "session": {
                "id": sid, "name": sid, "sourceMode": mode, "startedAt": now[0].isoformat(), "configId": "test"}})
            assert response.status_code == 201, response.text
        yield client, now


def set_time(now, second):
    now[0] = now[0].replace(second=second)


def begin(client, uid="u1"):
    response = client.post(PREFIX + "/start", json={"utteranceId": uid, "sessionId": "sim1"})
    assert response.status_code == 200, response.text
    return response.json()


def feed(client, uid, event_id, event, index=None):
    body = {"eventId": event_id, "event": event}
    if index is not None:
        body["segmentIndex"] = index
    return client.post(PREFIX + f"/{uid}/events", json=body)


def finish(client, now, uid="u1"):
    begin(client, uid)
    set_time(now, 1)
    assert feed(client, uid, uid + "-session", {"message_type": "session_started", "session_id": uid + "-provider",
                "config": {"model_id": SCRIBE_MODEL, "commit_strategy": "manual"}}).status_code == 200
    set_time(now, 2)
    assert client.post(PREFIX + f"/{uid}/release").status_code == 200
    set_time(now, 3)
    assert feed(client, uid, uid + "-commit", {"message_type": "committed_transcript", "text": "Pause after this cycle"}, 0).status_code == 200
    set_time(now, 4)
    return client.post(PREFIX + f"/{uid}/finalize", json={"expectedSegmentCount": 1, "terminalCommitEventId": uid + "-commit"})


def test_routes_are_authenticated_and_token_missing_stays_nonsecret(lab):
    client, _ = lab
    before = client.app.state.store.latest_sequence()
    assert client.post(PREFIX + "/token", headers={"Authorization": "Bearer wrong"}).status_code == 401
    response = client.post(PREFIX + "/token")
    assert response.status_code == 503 and response.json()["code"] == "missing_credential"
    options = client.get(PREFIX + "/options").json()
    assert "token" not in options and options["recordingStartsAutomatically"] is False
    assert client.app.state.store.latest_sequence() == before


def test_real_sessions_and_cross_session_cycles_are_rejected(lab):
    client, now = lab
    assert client.post(PREFIX + "/start", json={"utteranceId": "bad", "sessionId": "real"}).status_code == 409
    store = client.app.state.store
    store.upsert(RecordWrite(eventId="cross-cycle", recordType="cycle", record={
        "id": "cycle2", "sessionId": "sim2", "objectId": "object", "startedAt": now[0]}))
    response = client.post(PREFIX + "/start", json={"utteranceId": "bad2", "sessionId": "sim1", "cycleId": "cycle2"})
    assert response.status_code == 409
    assert store.list_records("utterance") == []


def test_canonical_finalization_is_retry_safe_and_does_not_create_execution(lab):
    client, now = lab
    before = client.app.state.store.latest_sequence()
    response = finish(client, now)
    assert response.status_code == 200, response.text
    first = response.json()
    assert first["newlyFinalized"] is True and first["physicalActionSent"] is False
    assert first["providerProvenance"] == "browser_relay"
    assert first["utteranceRecord"]["provider"] == "elevenlabs"
    assert first["utteranceRecord"]["modelId"] == SCRIBE_MODEL
    assert client.app.state.store.latest_sequence() == before + 1
    set_time(now, 5)
    repeated = client.post(PREFIX + "/u1/finalize", json={"expectedSegmentCount": 1, "terminalCommitEventId": "u1-commit"})
    assert repeated.status_code == 200 and repeated.json()["persistenceDuplicate"] is True
    assert repeated.json()["newlyFinalized"] is False
    assert len(client.app.state.store.list_records("utterance")) == 1
    assert client.app.state.store.list_records("execution") == []
    assert client.app.state.store.list_records("cycle") == []
    assert client.app.state.store.latest_sequence() == before + 1
    stored = client.get(PREFIX + "/u1").json()
    assert stored["capture"]["status"] == "finalized" and len(stored["events"]) == 2


def test_retry_after_canonical_write_failure_finishes_persistence(lab, monkeypatch):
    client, now = lab
    store = client.app.state.store
    original = store.upsert
    failed = [False]
    def temporary_failure(write):
        if write.recordType == "utterance" and not failed[0]:
            from morph_station.store import StoreError
            failed[0] = True
            raise StoreError(503, "simulated temporary persistence failure")
        return original(write)
    monkeypatch.setattr(store, "upsert", temporary_failure)
    response = finish(client, now)
    assert response.status_code == 503
    assert client.app.state.voice_journal.get("u1")["status"] == "finalized"
    assert store.list_records("utterance") == []
    response = client.post(PREFIX + "/u1/finalize", json={"expectedSegmentCount": 1, "terminalCommitEventId": "u1-commit"})
    assert response.status_code == 200 and response.json()["newlyFinalized"] is False
    assert response.json()["persistenceDuplicate"] is False
    assert len(store.list_records("utterance")) == 1


def test_server_time_start_retry_and_enrichment_do_not_change_canonical_record(lab):
    client, now = lab
    original = begin(client)
    set_time(now, 1)
    assert begin(client)["startedAt"] == original["startedAt"]
    # Complete using the same server-owned start identity.
    response = finish(client, now)
    assert response.status_code == 200
    before = client.app.state.store.get("utterance", "u1")
    set_time(now, 6)
    result = feed(client, "u1", "timestamps", {"message_type": "committed_transcript_with_timestamps",
                  "text": "Pause after this cycle", "language_code": "sl", "words": []}, 0)
    assert result.status_code == 200 and result.json()["eventDisposition"] == "enrichment_only"
    assert client.app.state.store.get("utterance", "u1") == before
