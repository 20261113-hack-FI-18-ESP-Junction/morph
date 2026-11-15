"""HTTP boundary checks using temporary persisted records, never real hardware."""

import base64
import csv
import io
import json
import re
import stat

import pytest
from fastapi.testclient import TestClient

from morph_station.api import MAX_JSON_BYTES, create_app

TOKEN = "test-only-token-" + "x" * 40
START = "2026-11-14T14:00:00Z"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("MORPH_CORS_ORIGINS", raising=False)
    app = create_app(db_path=tmp_path / "test.sqlite3", token=TOKEN, evidence_dir=tmp_path / "evidence")
    with TestClient(app, headers={"Authorization": "Bearer " + TOKEN}) as result:
        yield result


def session(client, identity="api-session", mode="simulation"):
    body = {"eventId": identity + "-create", "session": {
        "id": identity, "name": "API test", "sourceMode": mode, "startedAt": START,
        "configId": "api-test-config", "robotId": None, "modelRuns": [],
    }}
    response = client.post("/api/v1/sessions", json=body)
    assert response.status_code == 201, response.text
    return response.json()["record"], body


def cycle(client, session_id="api-session", identity="api-cycle"):
    body = {"eventId": identity + "-create", "recordType": "cycle", "record": {
        "id": identity, "sessionId": session_id, "objectId": "api-object", "startedAt": START,
    }}
    response = client.post("/api/v1/records", json=body)
    assert response.status_code == 200, response.text
    return response.json()["record"]


def test_authentication_covers_every_api_path_and_data_free_health(client):
    for route in ["/api/v1/station/snapshot", "/api/v1/sessions", "/api/v1/events?once=true",
                  "/api/v1/evidence/unknown", "/api/v1/schema", "/api/unknown"]:
        response = client.get(route, headers={"Authorization": "Bearer incorrect"})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    with TestClient(client.app) as unauthenticated:
        assert unauthenticated.get("/api/v1/sessions").status_code == 401
        health = unauthenticated.get("/health")
        assert health.status_code == 200
        assert health.json()["hardwareIntegrated"] is False
        assert "session" not in health.json()


def test_startup_reads_and_unavailable_controls_never_seed_or_dispatch(client):
    assert client.get("/api/v1/sessions").json() == []
    before = client.app.state.store.latest_sequence()
    assert client.get("/api/v1/station/snapshot").status_code == 200
    assert client.get("/api/v1/events?once=true").text == ": caught-up\n\n"
    assert client.get("/api/v1/cameras").json()["cameras"] == []
    assert client.get("/api/v1/cameras/missing/stream").status_code == 503
    for path in ["/api/v1/commands", "/api/v1/voice/token", "/api/v1/voice/utterances"]:
        assert client.post(path, json={}).status_code == 503
    assert client.app.state.store.latest_sequence() == before
    assert client.get("/api/v1/sessions").json() == []


def test_sessions_idempotence_open_cycle_end_and_store_error_translation(client):
    record, body = session(client)
    repeated = client.post("/api/v1/sessions", json=body)
    assert repeated.status_code == 200
    assert repeated.json()["duplicate"] is True
    cycle(client)
    response = client.post("/api/v1/sessions/api-session/end", json={
        "eventId": "end-open-session", "endedAt": "2026-11-14T14:05:00Z", "expectedRevision": record["revision"]})
    assert response.status_code == 409, response.text
    assert client.get("/api/v1/cycles/api-cycle").status_code == 200
    assert client.get("/api/v1/cycles/missing").status_code == 404
    assert client.get("/api/v1/sessions/missing/metrics").status_code == 404


def test_ending_empty_session_and_explicit_timezone(client):
    record, _ = session(client)
    response = client.post("/api/v1/sessions/api-session/end", json={
        "eventId": "end-no-timezone", "endedAt": "2026-11-14T14:05:00", "expectedRevision": record["revision"]})
    assert response.status_code == 422
    response = client.post("/api/v1/sessions/api-session/end", json={
        "eventId": "end-empty-session", "endedAt": "2026-11-14T14:05:00Z", "expectedRevision": record["revision"]})
    assert response.status_code == 200, response.text
    assert response.json()["record"]["endedAt"] is not None


def test_cycle_listing_keeps_simulation_explicit_and_paginates(client):
    session(client)
    cycle(client)
    assert client.get("/api/v1/cycles").json()["total"] == 0
    selected = client.get("/api/v1/cycles?sourceMode=simulation&limit=1").json()
    assert selected["total"] == 1
    assert selected["items"][0]["id"] == "api-cycle"
    assert client.get("/api/v1/cycles?includeSimulation=true&offset=1").json()["items"] == []
    assert client.get("/api/v1/cycles?limit=1001").status_code == 422


def test_sse_reconnect_uses_sequence_and_does_not_mutate(client):
    session(client)
    cycle(client)
    before = client.app.state.store.latest_sequence()
    response = client.get("/api/v1/events?after=0&once=true&limit=1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    initial = [int(value) for value in re.findall(r"^id: (\d+)$", response.text, re.MULTILINE)]
    assert len(initial) == 1
    resumed = client.get("/api/v1/events?after=0&once=true", headers={"Last-Event-ID": str(initial[0])})
    remaining = [int(value) for value in re.findall(r"^id: (\d+)$", resumed.text, re.MULTILINE)]
    assert remaining and all(value > initial[0] for value in remaining)
    assert remaining == sorted(remaining)
    assert client.get("/api/v1/events?once=true", headers={"Last-Event-ID": "invalid"}).status_code == 400
    assert client.get(f"/api/v1/events?after={before + 1}&once=true").status_code == 409
    assert client.app.state.store.latest_sequence() == before


def test_reference_labels_corrections_exports_retain_audit_without_mutation(client):
    record, _ = session(client)
    cycle(client)
    label = {"eventId": "label-create", "record": {
        "id": "api-label", "objectId": "api-object", "quality": "good", "authorId": "operator-test",
        "method": "Independent operator reference for an API fixture", "evidenceIds": [], "createdAt": START,
    }}
    response = client.post("/api/v1/cycles/api-cycle/reference-labels", json=label)
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/cycles?includeSimulation=true&referenceStatus=labeled").json()["total"] == 1
    invalid_label = {"eventId": "label-wrong-cycle", "record": dict(label["record"], cycleId="wrong-cycle")}
    assert client.post("/api/v1/cycles/api-cycle/reference-labels", json=invalid_label).status_code == 422
    correction = {
        "id": "api-correction", "eventId": "correct-session-name", "entityType": "session",
        "entityId": "api-session", "expectedRevision": record["revision"], "field": "name",
        "previousValue": "API test", "newValue": "API test corrected", "authorId": "operator-test",
        "reason": "Correct fixture title while retaining its prior value", "createdAt": "2026-11-14T14:01:00Z",
    }
    response = client.post("/api/v1/corrections", json=correction)
    assert response.status_code == 200, response.text
    before = client.app.state.store.latest_sequence()
    exported = client.get("/api/v1/sessions/api-session/export?format=json")
    assert exported.status_code == 200, exported.text
    text = json.dumps(exported.json())
    for value in ["api-label", "api-correction", "API test corrected", "previousValue", "correct-session-name"]:
        assert value in text
    exported_csv = client.get("/api/v1/sessions/api-session/export?format=csv")
    assert exported_csv.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    assert rows and all("dataJson" in row for row in rows)
    for row in rows:
        json.loads(row["dataJson"])
    assert "api-correction" in exported_csv.text
    json_records = exported.json()["records"]
    assert {(row["recordType"], row["id"]) for row in rows if row["section"] == "records"} == {
        (kind, record["id"]) for kind, records in json_records.items() for record in records}
    assert client.app.state.store.latest_sequence() == before


def test_evidence_is_authenticated_immutable_and_bounded(client):
    session(client)
    cycle(client)
    body = {"id": "api-evidence", "eventId": "api-evidence-created", "sessionId": "api-session",
            "cycleId": "api-cycle", "mediaType": "text/plain", "capturedAt": START,
            "contentBase64": base64.b64encode(b"Explicit simulated evidence").decode("ascii")}
    response = client.post("/api/v1/evidence", json=body)
    assert response.status_code == 200, response.text
    downloaded = client.get("/api/v1/evidence/api-evidence")
    assert downloaded.content == b"Explicit simulated evidence"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    changed = dict(body, eventId="api-evidence-changed", contentBase64=base64.b64encode(b"Changed").decode("ascii"))
    assert client.post("/api/v1/evidence", json=changed).status_code == 409
    oversized = dict(body, id="too-large", eventId="large-evidence", contentBase64=base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode("ascii"))
    assert client.post("/api/v1/evidence", json=oversized).status_code in {413, 422}
    assert client.get("/api/v1/evidence/too-large").status_code == 404
    assert client.post("/api/v1/records", content=b"x" * (MAX_JSON_BYTES + 1),
                       headers={"Content-Type": "application/json"}).status_code == 413


def test_cors_is_explicit_and_data_still_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("MORPH_CORS_ORIGINS", "http://127.0.0.1:5173")
    with TestClient(create_app(tmp_path / "cors.sqlite3", token=TOKEN)) as client:
        preflight = client.options("/api/v1/sessions", headers={"Origin": "http://127.0.0.1:5173",
                                   "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"})
        assert preflight.status_code == 200
        data = client.get("/api/v1/sessions", headers={"Origin": "http://127.0.0.1:5173"})
        assert data.status_code == 401
        assert data.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        other = client.options("/api/v1/sessions", headers={"Origin": "https://untrusted.example",
                               "Access-Control-Request-Method": "GET"})
        assert other.status_code == 400
    monkeypatch.setenv("MORPH_CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="explicit"):
        create_app(tmp_path / "invalid-cors.sqlite3", token=TOKEN)


def test_cli_init_private_token_is_preserved_and_never_printed(tmp_path, monkeypatch, capsys):
    from morph_station.__main__ import main

    monkeypatch.setenv("MORPH_DATA_DIR", str(tmp_path / "local-data"))
    monkeypatch.delenv("MORPH_API_TOKEN", raising=False)
    monkeypatch.delenv("MORPH_TOKEN_FILE", raising=False)
    monkeypatch.delenv("MORPH_DB_PATH", raising=False)
    assert main(["init"]) == 0
    token_path = tmp_path / "local-data" / "api-token"
    saved_token = token_path.read_text().strip()
    assert len(saved_token) >= 32
    assert stat.S_IMODE(token_path.stat().st_mode) == 0o600
    assert saved_token not in capsys.readouterr().out
    assert main(["init"]) == 0
    assert token_path.read_text().strip() == saved_token
    assert saved_token not in capsys.readouterr().out


def test_factory_requires_auth_configuration_and_never_generates_token(tmp_path, monkeypatch):
    monkeypatch.setenv("MORPH_DATA_DIR", str(tmp_path / "not-initialized"))
    monkeypatch.delenv("MORPH_API_TOKEN", raising=False)
    monkeypatch.delenv("MORPH_TOKEN_FILE", raising=False)
    with pytest.raises(ValueError, match="not configured"):
        create_app(tmp_path / "missing-token.sqlite3")
    assert not (tmp_path / "not-initialized" / "api-token").exists()


@pytest.mark.parametrize("invalid_id", ["invalid event id", "x" * 121, "../invalid", ""])
def test_request_envelopes_reject_invalid_event_ids_without_server_errors(client, invalid_id):
    record, original = session(client)
    cycle(client)
    before = client.app.state.store.latest_sequence()
    invalid_session = dict(original, eventId=invalid_id)
    invalid_end = {"eventId": invalid_id, "endedAt": "2026-11-14T14:05:00Z", "expectedRevision": record["revision"]}
    invalid_label = {"eventId": invalid_id, "record": {"id": "unused-label"}}
    for path, body in [("/api/v1/sessions", invalid_session),
                       ("/api/v1/sessions/api-session/end", invalid_end),
                       ("/api/v1/cycles/api-cycle/reference-labels", invalid_label)]:
        response = client.post(path, json=body)
        assert response.status_code == 422, response.text
        assert all("input" not in error for error in response.json()["detail"])
    assert client.app.state.store.latest_sequence() == before


def test_authenticated_schema_and_typed_snapshot_cover_persisted_shape(client):
    schemas = client.get("/api/v1/schema")
    assert schemas.status_code == 200
    data = schemas.json()
    assert data["schemaVersion"] == 1
    assert {"session", "cycle", "attempt", "frame", "inspection", "model_run", "utterance", "decision",
            "execution", "reference_label", "confirmation", "evidence"} <= set(data["records"])
    assert data["envelopes"]["SessionCreate"]["properties"]["eventId"]["maxLength"] == 120
    assert data["envelopes"]["SessionEnd"]["properties"]["eventId"]["pattern"] == data["records"]["session"]["properties"]["id"]["pattern"]
    snapshot_schema = data["responses"]["Snapshot"]
    assert snapshot_schema["properties"]["goalVersion"]["type"] == "null"
    assert snapshot_schema["properties"]["availableActions"]["maxItems"] == 0
    assert {"SessionView", "CycleView", "StationCapabilities", "UnavailableCapability"} <= set(snapshot_schema["$defs"])
    openapi = client.get("/openapi.json").json()
    response_schema = openapi["paths"]["/api/v1/station/snapshot"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/Snapshot")
    empty = client.get("/api/v1/station/snapshot").json()
    assert empty["session"] is None and empty["cycle"] is None and empty["sourceMode"] is None
    session(client)
    cycle(client)
    populated = client.get("/api/v1/station/snapshot?sessionId=api-session")
    assert populated.status_code == 200, populated.text
    result = populated.json()
    assert result["session"]["revision"] == 1 and result["cycle"]["revision"] == 1
    assert result["sourceMode"] == "simulation"
    assert result["lastEventSequence"] == client.app.state.store.latest_sequence()
    assert result["goalVersion"] is None and result["goal"] is None and result["availableActions"] == []
    assert all(item == {"status": "unavailable", "verified": False} for item in result["capabilities"].values())
