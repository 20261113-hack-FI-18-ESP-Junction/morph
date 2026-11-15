# Morph StationClient

This framework-independent TypeScript package supplies the Klemen dashboard's shared records client, store and presentation models. The current M16 source includes an explicit atomic cycle-review method with stable request identifiers. It does not create sessions, expose generic ingestion, dispatch motion or invoke providers. The Gemma UI uses its own explicit service client in `../dashboard/src/analysis`.

This portable layout uses `../dashboard` and `../verification/fixtures`; it does not require the original canonical workspace or a sibling checkout. [SOURCE_RECONCILIATION.json](../SOURCE_RECONCILIATION.json) records exact original source hashes and path/deadline adaptations. [Current verification](../VERIFICATION.md) is separate from [historical client evidence](VERIFICATION.md).

## Build and test

Use Node 24. From `../dashboard`, after `npm ci`:

```bash
npm exec tsc -- -p ../station-client/tsconfig.json
node --test ../station-client/tests/client.test.ts ../station-client/tests/store.test.ts
```

The source has no runtime package dependencies. Node 24 runs these TypeScript tests through built-in type stripping. Dashboard builds consume generated JavaScript and declarations from `dist/`. Generated dependencies and output are excluded from the package.

The retained `smoke_http.py`, `smoke_dashboard.py` and related smoke source belong to the historical canonical-workspace integration harness. Their backend/workspace layout and saved reports are not included here; the commands above are the portable client checks. Use `../verification/check_reconciled_mcp.py` for the current isolated communication integration.

## Dashboard connection

The supplied React app uses the explicit same-origin mode. Its loopback Node proxy holds the private Mac MCP pairing and connects to Intel through the MCP worker. No station or provider token is supplied to the browser. This package's dashboard never uses the client's historical direct-token mode.

```ts
import { StationClient, DashboardStore, projectViews } from '@morph/station-client';

const client = new StationClient({
  baseUrl: window.location.origin,
  authMode: 'same-origin-proxy',
});
const store = new DashboardStore(client, { loadSessionExport: true });
const unsubscribe = store.subscribe(() => {
  const state = store.getState();
  const views = projectViews(state);
  // Render views together with state.connection and state.stale.
});
await store.start({ sourceMode: 'live' });
// At application teardown: unsubscribe(); store.stop();
```

Create one shared client/store per station at the application boundary; changing views only changes rendering. For React, `useSyncExternalStore(store.subscribe, store.getState)` reads the stable frozen snapshot. Session/source changes abort old requests. The complete selected-session export is read within the same event-watermark bracket as the other state.

The request deadline is 40 seconds to accommodate the bounded MCP request/response cycle. Provider job deadlines remain a backend concern. Reads and refreshes are distinct from an explicit `client.reviewCycle(cycleId, request)` call. A review retains its exact payload, review ID and event ID. The client never retries a write automatically; callers offer an identical explicit retry for an uncertain result. The backend validates final evidence, revisions and the attributed transaction. The client has no motion method.

## Files

- `src/client.ts`: validated reads, explicit review, bounded requests and SSE/error handling.
- `src/types.ts`: current record, revision, metrics and API types.
- `src/store.ts`: source/session state, coherent reads, invalidation, reconnection and stale state.
- `src/views.ts`: display projections, count/ratio formatting, timestamps and frame age.
- `src/index.ts`: public exports.

## Reading state correctly

- The default source is **live**. The API's automatic newest-session selection can be simulated, so the store explicitly selects the newest eligible session or leaves the view empty. Simulation is a deliberate source switch. It reads the persisted simulation session; it does not seed data in the browser.
- All view data is bracketed by matching global event watermarks. If records change during the separate HTTP reads, the complete bundle is retried. Old and new read models are never intentionally published together.
- SSE events invalidate authoritative reads. They never increment a counter or create a record. Duplicate/out-of-order events at or below the incorporated watermark are ignored. A gap triggers a complete refresh. A cursor ahead of a replaced database causes snapshot resynchronization.
- HTTP polling also refreshes quiet sessions. `receivedAt` describes the last complete read bundle. Connection failure retains the previous bundle with `stale: true`; age-based freshness is separate from an analyzed frame's capture time.
- `connection: unauthorized` requires a valid token; `incompatible` requires checking the station/schema or selected session. Both are shown explicitly. Repeated GETs never imply that the physical robot is stopped or has failed.
- Ratios come from the backend and include `numerator`, `denominator` and definition. Empty selections/denominators display **No data yet**. Full metrics cover the selected session; the first history page contains at most 100 rows and includes its total. The M16 React UI now filters and paginates its complete selected-session export without changing these metric denominators.
- `currentDetail` follows the current cycle; `detail` follows the selected history row. Analyzed frames are chosen by inspection frame IDs. `inspectionRole` identifies the cycle's decision inspection or the latest recorded inspection while a decision link is not yet present.
- Analyzed evidence and live video remain separate. M06 has no live camera integration. `getEvidence(id)` returns an authenticated `Blob`; the UI may create and later revoke a local object URL. Never put a bearer token in an image URL.
- Missing telemetry is `null`/Unavailable. All hardware/provider capabilities remain unavailable in M06. Empty `availableActions` means no controls can be enabled.
- Timestamps display an explicit timezone. Simulation frame age is labeled simulation, not live camera freshness.

Replay belongs to the React adapter. It freezes an existing coherent snapshot, stops live polling and displays original events and revisions. It does not create a second authority, change fixed saved-session metrics or submit reviews/inference. An operator must leave replay and deliberately submit a review to amend records.
