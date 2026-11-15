# Morph dashboard

This is the Klemen Mac React dashboard, reconciled with the received Intel M16 history/review/replay and Gemma analyst source on November 15, 2026. It runs beside `../station-client` and `../analytics` inside this portable package. Follow the [package setup](../README.md) for dependency installation, the private existing MCP pairing and startup commands.

From this directory, after installing dependencies:

```bash
npm exec tsc -- -p ../station-client/tsconfig.json
npm run dev
```

Open `http://127.0.0.1:3000`. For production, run `npm run build` followed by `npm start`. The server binds to loopback. It reads `MORPH_CONTEXT_PAIRING_DIR` and `MORPH_STATION_ID`; the browser never receives pairing or provider credentials. This package uses the existing Mac MCP and an Intel worker, with no direct Mac-to-Intel HTTP connection. The environment example contains placeholders only.

## Data and actions

Live inspection, Robot & system and Quality & history share one coherent records snapshot and selected session. Live is the default source. Simulation selects an existing saved simulation; it does not create records. Missing telemetry, cameras or model timing remain unavailable.

History includes complete selected-session filtering/pagination, frame-linked evidence, audited reviews, CSV/JSON exports and frozen replay. An explicit review retains author, reason, observation time, expected revisions and stable IDs. The backend owns validation and the atomic transaction. An uncertain result offers an identical explicit retry; navigation and refresh never submit it automatically. Replay shows saved records and fixed saved-session metrics without new events or review writes.

The Gemma panel reads deterministic evidence facts and saved reports. Only an explicit Generate or retry action sends a report request. It retains the original request ID, distinguishes captured from current evidence, and contains malformed responses or provider errors. The provider runs on the service host; cloud prose cannot change records or dispatch motion. See [the analyst module](src/analysis/README.md) for its contract.

The local proxy allows bounded GET requests and only two JSON POST intents: `record-review` for `/api/v1/cycles/{id}/review` and `evidence-analysis` for `/api/v1/analysis/reports`. Host/Origin, route, intent and body-size checks apply. It forwards through the MCP relay, preserving application IDs, exact bodies, response status and structured errors. No motion, mission or generic ingestion route is available. Page load, reconnect and view switches read existing data.

Times are labeled Europe/Ljubljana. Anomaly scores remain scores, ratios include their denominators, and stale/disconnected states do not rewrite outcomes. Original design assets and `src/domain/` prototype code remain provenance; they do not supply the active dashboard's reliability records.

## Checks

```bash
npm run typecheck
npm test
npm run build
```

See [current verification](../VERIFICATION.md), [capability status](IMPLEMENTATION_STATUS.md), and [source gaps](../SOURCE_GAPS.md). The exact current Intel proxy test was not transferred; the separately named Mac baseline and new MCP regressions are not a substitute for that original suite. Earlier Intel/browser evidence described in source documents is historical, separate from this package's local checks and from physical verification.
