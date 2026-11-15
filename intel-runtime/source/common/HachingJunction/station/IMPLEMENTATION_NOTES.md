# M06 implementation coordination

The root workspace is not a Git repository. Application source lives in `station/`, outside dependency caches. The existing dashboard reference remains a separate deliverable.

## Shared Python interface

- Import package: `morph_station`, under this directory. Runtime: the existing `.junction-setup/python/bin/python` with this directory on `PYTHONPATH`.
- `models.py`: `RecordWrite(eventId: str, recordType: str, record: dict, expectedRevision: int | None = None)`, `CorrectionRequest`, `EvidenceUpload` (all Pydantic models).
- `store.py`: `StoreError(status_code: int, detail: str)` and `StationStore(db_path, evidence_dir=None)`; persistent SQLite, one transactional connection per operation.
- `store.upsert(write: RecordWrite) -> {recordType, record, event, duplicate}`. The returned record includes server-controlled `revision`.
- Record types: `session`, `cycle`, `attempt`, `frame`, `inspection`, `model_run`, `utterance`, `decision`, `execution`, `reference_label`, `confirmation`. `evidence` and `correction` use dedicated methods.
- `get(record_type, record_id) -> dict`; `list_records(record_type, session_id=None, cycle_id=None) -> list[dict]`.
- `events(after=0, limit=100) -> list[dict]`, `latest_sequence() -> int`.
- `snapshot(session_id=None) -> dict`; `metrics(session_id=None, include_simulation=False) -> dict`; `cycle_detail(cycle_id) -> dict`.
- `end_session(session_id, event_id, ended_at, expected_revision) -> upsert result`; unresolved cycles cause HTTP 409, with no automatic outcome changes.
- `correct(request: CorrectionRequest) -> {correction, record, event, duplicate}`. Fields: id, eventId, entityType, entityId, expectedRevision, field, previousValue, newValue, authorId, reason, createdAt (timezone-aware).
- `put_evidence(request: EvidenceUpload) -> upsert result`. Fields: id, eventId, sessionId, cycleId, mediaType, contentBase64, capturedAt (timezone-aware). Allowed media: image/png, image/jpeg, application/json, text/plain; up to 5 MiB decoded.
- `evidence_file(evidence_id) -> (Path, media_type)`; never accepts a caller filesystem path.
- `simulation.seed_demo(store, prefix="demo") -> dict` creates deterministic labeled simulation records idempotently, never on app startup or a GET. Available to explicit CLI only for this increment.

## API ownership

The API agent owns `morph_station/api.py`, `morph_station/__main__.py`, `morph_station/client.py` if useful, `run.sh`, `requirements.txt`, `README.md`, and API tests. The root owns models, store, schema/migration, simulation and package initialization. The test agent owns domain regression tests and may request root fixes.

## Scope

Implement the M06 foundation: authenticated API, persistence, ordered event catch-up, session/cycle reads, metrics, evidence, labels and audited corrections. Hardware/provider controls remain explicitly unavailable, with no motion or provider calls on startup, refresh or reconnect. Simulation and live records remain distinct. Do not claim that M12 dispatch, M16 UI or physical integration is complete.
