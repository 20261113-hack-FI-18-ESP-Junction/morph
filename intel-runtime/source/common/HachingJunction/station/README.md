# Morph station records — M06 foundation

This application provides authenticated local record storage, session/cycle reads, ordered events, metrics, immutable evidence, independent labels, audited corrections and complete metadata exports. It is the M06 software foundation, separate from the [Morph dashboard reference](../design/morph-handoff/README.md).

The M15 [TypeScript StationClient](web-client/README.md) connects the owner's actual React dashboard in the sibling `../morph-station` project. All three views share persisted records through its GET-only same-origin proxy. Source/session selection, event reconnection, presentation models and completed software/UI acceptance are documented in the client verification report. M16's write forms/replay and later physical integration remain separate tasks.

**No robot, camera or provider adapter is connected.** Starting the service, opening a snapshot, refreshing or reconnecting to events does not create a session, seed simulation, start motion or contact Gemini, Nemotron or ElevenLabs. `/commands`, camera streaming, voice-token issuance and voice-goal submission return HTTP 503. The eventual dispatcher and physical workflow remain later tasks.

## Run using the prepared environment

Run these commands from the workspace root. `run.sh` selects the existing `.junction-setup/python/bin/python`; application source and data stay outside dependency caches.

```bash
bash station/run.sh init
bash station/run.sh serve
```

`init` creates the database and an owner-only token file at `station/.data/api-token` (mode `0600`). It prints the token file location, never the token. An existing token is preserved. `serve` binds to **127.0.0.1:8000** by default and requires a configured token. It does not initialize a new token or seed demo records.

In a second terminal:

```bash
bash station/run.sh request /api/v1/station/snapshot
bash station/run.sh request /api/v1/schema
bash station/run.sh request /api/v1/sessions
bash station/run.sh request '/api/v1/events?after=0&once=true'
```

The request command reads the token file and sends the Authorization header internally. It neither prints the token nor follows HTTP redirects. Do not paste the token into chat, a URL, source code, screenshots or logs. Use `--output /path/to/result.json` to save response bytes.

The public `/health` endpoint contains service capability metadata only. `/docs` and `/openapi.json` describe the interface without exposing data. **Every `/api` route requires `Authorization: Bearer …`, including evidence downloads and unknown paths.** The browser client should fetch evidence with the same header and display the resulting blob; an unauthenticated image URL will not work.

## Explicit simulation

Seeding is a deliberate CLI operation, separate from starting the service:

```bash
bash station/run.sh init
bash station/run.sh seed-demo --prefix demo
bash station/run.sh serve
```

The demo records are marked `sourceMode: simulation`. Reusing the same prefix is idempotent; choosing a new prefix intentionally creates another demonstration dataset. Do not treat these outcomes as hardware results. Normal reliability queries exclude simulation unless requested explicitly:

```bash
bash station/run.sh request '/api/v1/cycles?includeSimulation=true'
bash station/run.sh request '/api/v1/metrics?includeSimulation=true'
```

Use the session IDs returned by the session list or seeding command for detail and exports. GET requests and replay only read existing data.

## Configuration and remote access

| Setting | Default / purpose |
| --- | --- |
| `MORPH_DATA_DIR` | `station/.data`; local runtime data directory |
| `MORPH_DB_PATH` | `$MORPH_DATA_DIR/station.sqlite3`; file-backed SQLite database |
| `MORPH_EVIDENCE_DIR` | `evidence` beside the database; immutable uploaded content |
| `MORPH_TOKEN_FILE` | `$MORPH_DATA_DIR/api-token`; owner-only token file |
| `MORPH_API_TOKEN` | Optional server/client token supplied through the environment; overrides the token file |
| `MORPH_CORS_ORIGINS` | Empty by default; explicit comma-separated HTTP(S) origins, without paths or wildcards |
| `MORPH_PYTHON` | Optional Python executable override for the launcher |

Tokens must contain at least 32 ASCII characters without whitespace. `init` generates a random token substantially longer than that minimum. If using an environment token, provision it through the local secret configuration; the example commands intentionally contain no credential value.

For a separately served local frontend, configure the exact origin before starting the server, for example:

```bash
MORPH_CORS_ORIGINS=http://127.0.0.1:5173 bash station/run.sh serve
```

Allowed CORS preflight requests are handled without a bearer token; the corresponding data requests still require authentication. The allowlist is not a substitute for authentication. No wildcard origins or credentialed cookies are enabled.

Use an SSH tunnel to reach a station on another machine while preserving the loopback binding. The API has no built-in TLS or public deployment configuration. A non-loopback `--host` must be an intentional deployment choice with an appropriate secured network or reverse proxy; it is not needed for the initial client workflow.

On a different machine, install `requirements.txt` into an isolated application environment and select its Python with `MORPH_PYTHON`. Keep Studio and Anomalib in their own prepared environments. The versions in this file were observed in the existing environment on November 14, 2026; no new package installation is needed here.

## HTTP record contract

All mutation bodies use stable client-supplied event/entity IDs. Retransmit the same event only with the same payload. Updates require the expected stored revision; revisions are controlled by the server. Timestamps must be ISO 8601 with an explicit timezone. Store validation errors return 4xx responses and do not partially update records.

| Route | Behavior |
| --- | --- |
| `GET /api/v1/schema` | Standalone JSON Schemas for record types, request envelopes and the typed snapshot response |
| `GET /api/v1/station/snapshot?sessionId=…` | Persisted snapshot and latest event sequence |
| `GET /api/v1/events?after=…` | Ordered SSE stream, resumable by sequence |
| `GET /api/v1/sessions` | All saved session metadata, with source modes |
| `POST /api/v1/sessions` | `{eventId, session}`; creates bookkeeping only |
| `POST /api/v1/sessions/{id}/end` | `{eventId, endedAt, expectedRevision}`; rejects unresolved cycles |
| `POST /api/v1/records` | Internal authenticated adapter boundary: `{eventId, recordType, record, expectedRevision?}` |
| `GET /api/v1/metrics` | Aggregate persisted reliability; simulation excluded by default |
| `GET /api/v1/sessions/{id}/metrics` | Session metrics; use `includeSimulation=true` for an explicit simulated session |
| `GET /api/v1/cycles` | Filtered, paginated cycle summaries |
| `GET /api/v1/cycles/{id}` | Full cycle detail and audit evidence |
| `POST /api/v1/cycles/{id}/reference-labels` | `{eventId, record, expectedRevision?}`; URL and record cycle must match |
| `POST /api/v1/corrections` | Version-checked, attributed correction with previous/new value and reason |
| `POST /api/v1/cycles/{id}/review` | Atomic operator review: independent label, late confirmation, linked attempt and cycle corrections, with revisions and per-field audit |
| `POST /api/v1/evidence` | Base64 upload linked to the session/cycle; immutable after creation |
| `GET /api/v1/evidence/{id}` | Authenticated content lookup by evidence ID; never accepts a filesystem path |
| `GET /api/v1/sessions/{id}/export?format=json` | Complete session record export, including revisions, events and corrections |
| `GET /api/v1/sessions/{id}/export?format=csv` | Same sections as flat rows with lossless `dataJson` values |
| `GET /api/v1/cameras` | Empty descriptors and explicit unavailable status |
| `POST /api/v1/commands`, `POST /api/v1/voice/token`, `POST /api/v1/voice/utterances`, `GET /api/v1/cameras/{id}/stream` | HTTP 503; no hardware/provider action |

Cycle filters are `sessionId`, `objectId`, `outcome`, `sourceMode`, `includeSimulation`, `hasRetry`, `errorCode`, `modelId`, `referenceStatus=labeled|unlabeled`, `startedAfter`, `startedBefore`, `offset` and `limit`. Explicit `sourceMode=simulation` selects simulated cycles; otherwise simulation is excluded unless `includeSimulation=true`. The maximum page size is 1,000.

Use the authenticated `/api/v1/schema` response to generate or validate the dashboard's records instead of inferring fields from a fixture. Each entry under `records`, `envelopes` and `responses` is a standalone JSON Schema; resolve its `$defs` within that entry. OpenAPI also declares the snapshot's nested session/cycle revisions, nullable goal state, event cursor, unavailable integration capabilities and empty action list. M06 exposes no active goal or available robot action. Event/entity IDs share the same 120-character constraint and identifier pattern; invalid envelopes return HTTP 422 without echoing raw inputs.

## Atomic history review — Intel M16 continuation

The `CycleReview` envelope in `/api/v1/schema` defines the narrow review route. Each request supplies a stable review `id`, `eventId`, current cycle `expectedRevision`, `authorId`, nonblank `reason` and timezone-qualified `createdAt`. Optional `label` and `confirmation` records are linked to the existing cycle in the same SQLite transaction as the requested outcome/destination changes. A label edit requires its current revision and preserves its original author, time and evidence; the correction records identify the reviewer. A new label can retain its own independent evidence.

An operator confirmation supplies the actual `confirmedAt`, `physicalSuccess`, observed destination, and any evidence IDs. Linking it to an attempt also requires `expectedAttemptRevision`; the optional `attemptOutcome` changes that finished attempt. The route cannot finish active execution, invent an end time, change model outputs, or create physical attempts. It accepts operator attribution only: a manual review cannot impersonate a camera or sensor. Observation time must fall between the work's start and this review's creation time.

All changed fields retain their previous/new values, previous/new revisions, author, reason and timestamp. Validation applies to the final linked result, so changing an incorrect reference label and downgrading a previously correct cycle is possible without temporarily publishing contradictory records. Any stale revision, missing/cross-cycle evidence, incompatible destination or invalid correct-result claim rolls back the entire transaction, including events and receipts. The normal definition of a correct cycle still requires matching independent quality, inspection, commanded/observed destination and a confirmed successful final attempt.

The response is `{ "cycle": <complete cycle detail>, "duplicate": false }`. An exact retry with the same IDs and payload returns the originally saved response with `duplicate: true`, including after a process restart or a later correction. A reused event or review ID with changed content is a conflict. On an ambiguous network failure, retain the unchanged payload for retry; on a revision conflict, reload and review the current record explicitly. The additive `review_requests` table reserves review IDs; existing records, exports and schema version 1 remain compatible.

The Intel backend regression report is [the M16 JUnit result](../../verification/intel-m16-backend-tests.xml). Its 24 new review cases cover the recovered-cycle fixture (one cycle, two attempts, one retry, one recovered success, zero first-attempt successes; rates 1/1 and 1/2), atomic corrections/rollback, attribution, scoped evidence, active-execution rejection, concurrent duplicate submission and restart. These are simulation/software results, not observations of a physical robot.

The ingestion boundary saves reported facts and validates their relationships. It is **not** a robot dispatcher or proof that a sensor observation is genuine. The authenticated adapter/operator is responsible for accurate source attribution. Independent reference labels, commanded destinations and physical confirmations remain separate records.

JSON requests are limited to **1 MiB**. The evidence-upload JSON envelope is limited to **7 MiB**, and decoded evidence is limited to **5 MiB**. Supported media are PNG, JPEG, JSON and plain text. Upload original evidence bytes and retain the returned immutable ID/hash; exports include evidence metadata, while binaries remain available through the authenticated evidence endpoint.

### Create a simulated bookkeeping session

Save this example as a local JSON file, then send it with `bash station/run.sh request /api/v1/sessions --method POST --body /path/to/session.json`:

```json
{
  "eventId": "example-session-created",
  "session": {
    "id": "example-session",
    "name": "Explicit API bookkeeping example",
    "sourceMode": "simulation",
    "startedAt": "2026-11-14T15:00:00+01:00",
    "configId": "example-config",
    "robotId": null,
    "modelRuns": []
  }
}
```

This command creates no cycle and starts no movement. Use actual timezone-qualified timestamps for a real test record. Omitted measurements remain unavailable.

### Event reconnect and bounded catch-up

SSE `id` is the monotonically increasing database `sequence`; the event JSON also retains its unique `eventId`, entity revision and source information. Resume using `after=N` or the `Last-Event-ID: N` header. If both are present, the larger cursor wins. A cursor ahead of this database returns HTTP 409 so the client can refresh its snapshot rather than silently losing events.

`once=true` emits at most `limit` events up to the sequence captured at the request's start, then closes. Repeat from the last received sequence for additional pages. A caught-up response contains an SSE comment and creates no new event. The normal stream polls for subsequent committed events and emits idle comments. A browser requiring bearer headers should use a fetch-based SSE reader rather than putting the token into an EventSource URL.

### Export and audit

Both export formats read saved records without creating sessions, cycles, attempts or events. JSON preserves related entities, revisions, correction records and ordered events. CSV uses `section,recordType,id,dataJson`; the JSON cell retains nested data instead of dropping model inputs or audit values. Download referenced evidence separately when assembling a portable archive.

## Verification

From the workspace root:

```bash
PYTHONPATH=station .junction-setup/python/bin/python -m pytest station/tests
```

Tests use temporary databases and explicit fixtures. They exercise the data/API foundation only; they do not establish provider access, calibrated cameras, trained robot skills or physical success. The larger acceptance contract remains in [AGENTS.md](../AGENTS.md), the [primary workflow](../PHYSICAL_AI_WORKFLOW.md) and the [integration contract](../design/morph-handoff/INTEGRATION_CONTRACT.md).
