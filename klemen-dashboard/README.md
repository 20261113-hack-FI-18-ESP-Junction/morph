# Klemen Mac — dashboard and analytics

This package combines the current Intel M16 history/review/replay and Gemma analyst frontend with the existing Mac MCP connection. The source was reconciled on November 15, 2026 in this new publication directory. The earlier handoff and pre-change archive remain separate. [SOURCE_RECONCILIATION.json](SOURCE_RECONCILIATION.json) records received/reused source and package adaptations; [SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json) retains the original Mac package history.

The runnable UI includes Live inspection, Robot & system, Quality & history, audited operator reviews, frozen record replay, saved Gemma reports and explicit report requests. It also includes the shared records client and an offline export analyzer. These source features do not establish a current Intel deployment, live connectivity, provider availability or a working physical robot. [VERIFICATION.md](VERIFICATION.md) records the checks actually performed on this package.

## Ownership and connection

| Part | Responsibility |
| --- | --- |
| `dashboard/` | Klemen's React views, history/review workflow, Gemma evidence UI and local MCP proxy |
| `station-client/` | Shared records client/store and explicit, idempotent operator review submission |
| `analytics/` | Offline integrity and metrics checks on complete saved session exports |
| Intel station | Authoritative records, review validation, saved analyst contexts/reports, explicit Gemma requests and physical runtime ownership |
| Jose Mac | Operator chat, coordination and permitted mission selection; likely voice host, with ElevenLabs undecided |

The connection is **Klemen dashboard → existing Mac MCP service → Intel relay worker → Intel's local records API**. This package does not connect directly from the Mac to Intel HTTP. Jose's separate NVIDIA tunnel belongs to the other team.

Opening, refreshing, switching views and reconnecting read existing records and reports. The operator must explicitly submit a history review or request a Gemma explanation. Replay cannot submit reviews or generate reports. No route here creates a robot mission or sends motion commands. A saved operator confirmation remains attributed evidence; cloud prose is not a physical outcome.

## Run the dashboard

Use Node 24. From this package:

```bash
cd dashboard
npm ci
npm exec tsc -- -p ../station-client/tsconfig.json
cp .env.example .env
```

Set `MORPH_CONTEXT_PAIRING_DIR` in the private local `.env` to the existing pairing directory containing `connection.json` and `morph-ca.pem`. Set `MORPH_STATION_ID` to the Intel worker's configured station ID, normally `intel-main`. `connection.json` must belong to the current user and have mode `0600`. Its token stays on the server; it never enters frontend variables, URLs or browser storage. TLS certificate verification uses the supplied CA.

The accompanying updated communication/runtime package must be deployed before the new write paths can work. It provides `enqueue_station_request` and an upgraded worker that claims supported writes only when explicitly started with `--allow-record-writes`. The worker defaults to reads; use `--poll-seconds 0.25 --limit 1` for bounded sequential work. The earlier GET-only worker can continue reads but cannot claim review/analyst jobs. Starting this dashboard does not install or restart either service.

```bash
npm run dev
```

Open `http://127.0.0.1:3000`. The server binds to loopback and rejects foreign Host/Origin requests. For the local production build:

```bash
npm run build
npm start
```

An unavailable/stale state is expected when the pairing, matching relay, worker or selected Intel service is unavailable. The dated Intel runtime report found main port 8000 lacked analyst routes while isolated port 52197 had them. Verify the intended Intel service separately; source receipt does not establish that either running process loaded these files.

## MCP request behavior

GET requests use `enqueue_station_read`; responses are read in base64 pages through `read_station_response`. Each request has a fresh relay UUID. The adapter checks offsets, immutable response metadata, byte bounds and the complete SHA-256 before forwarding the response. Repeated `sessionIds` values remain ordered for two-session comparisons.

Only these POST requests are supported:

| Route | Required browser and MCP intent | Application identity retained |
| --- | --- | --- |
| `/api/v1/cycles/{cycle_id}/review` | `record-review` | Review `id` and `eventId`, expected revisions, attribution and exact original body |
| `/api/v1/analysis/reports` | `evidence-analysis` | `requestId`, selected evidence digest and exact original body |

POST bodies must be JSON objects encoded as valid UTF-8, at most **64 KiB**. Both routes use `enqueue_station_request`; the proxy, relay and worker independently enforce their boundaries. Backend JSON error statuses and bodies remain visible. No mutation is automatically retried. A missing reply can leave the submission outcome unknown: retain the original application identifiers for an explicit retry through the UI. A fresh transport UUID does not create a new application submission identity.

The relay request expires after 30 seconds; the adapter waits at most 35 seconds and browser requests allow 40 seconds. It never serves a stale cache as current. The complete response limit is **4 MiB**, including exports or evidence; larger replies fail without truncation. Larger file transport remains separate work.

Browser SSE repeatedly requests bounded `once=true` reads, preserves actual event bytes and advances the event cursor. A bridge heartbeat follows only an actual newly received response. Worker loss ends the stream, and the UI marks the connection stale. No records or counters are synthesized.

## Run offline analytics

Use Python 3.12. The analyzer checks saved data without importing it into a running station or calling providers:

```bash
python3.12 -m venv analytics/.venv
analytics/.venv/bin/python -m pip install -r analytics/requirements.txt
cd analytics
.venv/bin/python -m morph_station.export_audit audit ../verification/fixtures/sample-export.json --output-dir reports/example-audit
```

Use a new output directory each time. The supplied fixture is labeled simulation. For actual session analysis, supply the complete exported JSON and retain its original bytes and provenance. The `replay` command compares existing exports while ignoring only the export timestamp; it does not replay robot motion:

```bash
.venv/bin/python -m morph_station.export_audit replay ../verification/fixtures/recovered-session-export.json ../verification/fixtures/browser-replay-export.json --output-dir reports/example-equivalence
```

## Check this package

Verify the source inventory without installing dependencies:

```bash
python3 tools/verify_package.py
```

From `dashboard/`, after dependency installation and the shared-client build:

```bash
npm run typecheck
npm test
npm run build
node --test ../station-client/tests/client.test.ts ../station-client/tests/store.test.ts
```

From the package root:

```bash
analytics/.venv/bin/python -m pip install -r analytics/requirements-dev.txt
PYTHONPATH=analytics analytics/.venv/bin/python -m pytest analytics/tests -q
```

The current Intel proxy test file was rejected by the source sender and is not included. `stationProxy.mac-baseline.test.ts` is explicitly the older Mac regression set; `stationProxy.mcp.test.ts` adds local coverage for the new transport boundary. These do not constitute a reconstructed complete Intel test suite. The Intel backend analyst test file is also unavailable; frontend/controller checks are a separate scope. The exact current synthetic CSV dependency is included.

Model keys and the live Gemma service remain on the service host. The retained design assets and `src/domain/` prototype files are historical source material; active UI records use the shared station client. Do not replace absent telemetry with prototype values or describe simulated outcomes as physical verification.
