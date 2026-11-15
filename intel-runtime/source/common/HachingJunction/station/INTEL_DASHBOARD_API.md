# Bounded Intel dashboard read contract

Implementation date: November 15, 2026, Europe/Ljubljana (UTC+01:00).

This source change adds one coherent, bounded read for Klemen's dashboard. It is an intentional development change to the imported Intel source; the original source manifests remain the historical transfer baseline. No Intel service, Mac MCP process, camera, model provider, robot, or training job was started or upgraded for this change. Deployment and physical data production remain separate acceptance steps.

## Request and compatibility

`GET /api/v1/dashboard` uses the existing Station bearer authentication and accepts each query parameter at most once:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `sourceMode` | `live` | Exactly `live` or `simulation`. Selects the session population and excludes the other mode. |
| `sessionId` | Latest matching session | Optional stable session ID. The selected session must match `sourceMode`. |
| `cycleId` | Current cycle | Optional stable cycle ID for the detail panel. It must belong to the selected session. |
| `limit` | `20` | Recent-cycle page size, an integer from 1 through 100. |

Unknown or repeated parameters return HTTP 422. Missing session/cycle IDs return 404. A session/source-mode mismatch or a cycle belonging to another selected session returns 409. No matching session returns a valid empty view with null selection, null details, and no eligible metric data.

`GET /api/v1/schema` advertises this capability at `capabilities.dashboardRead` and includes the `Dashboard` response schema. The data-free `/health` route includes the same object at `dashboardRead`, but `/health` remains outside the MCP read allowlist.

```json
{
  "version": 1,
  "path": "/api/v1/dashboard",
  "maxResponseBytes": 4194303,
  "sessionLimit": 50,
  "defaultCycleLimit": 20,
  "maxCycleLimit": 100
}
```

An older backend without that capability keeps its existing read routes. A client may use its legacy read path when the capability is absent; an advertised endpoint returning an operational failure must remain visible. A failed relay, authentication error, timeout, or oversized result must not silently become a successful legacy read or cached data labeled live.

## Response

All sections are read through the same SQLite read transaction, including records, revisions, exact metrics, and the event cursor. Concurrent writers may continue; the request does not wait for a global idle interval or compare two separately read snapshots.

| Field | Contract |
| --- | --- |
| `schemaVersion`, `dashboardVersion` | Both `1`. |
| `generatedAt` | UTC response generation time, equal to `snapshot.generatedAt`. This is not a camera capture time. |
| `lastEventSequence` | Highest global event sequence visible in this transaction, equal to `snapshot.lastEventSequence` and `snapshot.stateVersion`. |
| `sourceMode`, `selectedSessionId` | Requested mode and effective selected session ID, or null ID when empty. |
| `sessions` | `{items, limit: 50, total, hasMore}` containing the newest 50 matching sessions, ordered by `startedAt` and ID descending. An explicitly selected older session is present in `snapshot.session` even when absent from this page. |
| `snapshot` | Existing Station snapshot fields for the selected session, including active cycle IDs, current cycle, unavailable component capabilities, and exact metrics. |
| `metrics` | The same metric value as `snapshot.metrics`, covering the entire selected session. Recent-cycle pagination does not change denominators. |
| `recentCycles` | `{items, offset: 0, limit, total, hasMore}` for the selected session, ordered by `startedAt` and ID descending. Includes in-progress and finished outcomes. |
| `cameras` | Existing camera-catalog result. The current source reports unavailable with an empty list. |
| `currentDetail` | Complete existing cycle-detail value for the snapshot's current cycle, or null. Current selection prefers the newest in-progress cycle, then the newest finished cycle. |
| `detail` | Complete existing cycle-detail value for `cycleId`, or `currentDetail` when no cycle is specified. |

Cycle detail retains attempts, frames, inspections, model runs, utterances, decisions, executions, independent reference labels, confirmations, corrections, evidence metadata, events, and revisions. Image bytes remain on the existing `/api/v1/evidence/{id}` route. Frame IDs, camera/object identity, capture and receipt times, inspection/model references, and evidence hashes are preserved. A saved latest image is not a continuously refreshed camera stream.

The existing metric semantics remain unchanged: failed, aborted and unverified finished outcomes remain in their denominators; retries retain prior failures; detection correctness uses independent labels; a late confirmation updates the same record; duplicate delivery and replay do not add repetitions. Full-cycle timing values remain exact and include waiting/retries. No reduced timing sample or truncated detail is silently substituted.

## Payload ceiling and freshness

The serialized UTF-8 JSON body must be **strictly smaller than 4 MiB**, including both detail fields and metric copies. If complete evidence, revisions, timing values or other records exceed that ceiling, the endpoint returns HTTP 413:

```json
{
  "code": "dashboard_response_too_large",
  "detail": "Dashboard response exceeds the bounded read limit; current evidence and exact metrics were not truncated.",
  "maxResponseBytes": 4194303
}
```

Successful and oversized responses use `Cache-Control: private, no-store`. Long sessions or unusually large model payloads can reach the v1 ceiling even with a small recent-cycle limit. A future explicitly versioned compact detail/timing contract may address that case; v1 does not sacrifice evidence or change metrics to fit.

The event cursor is global, so another session can advance it without changing the selected view. Continue finite event reads with `after=lastEventSequence`; existing duplicate/cursor protections apply. The dashboard should distinguish transport receipt time, record event time and frame capture time. An unreachable worker is unavailable, and a retained last-known view must show its age and stale state.

## Source adoption and verification

The implementation changes [api.py](morph_station/api.py), [store.py](morph_station/store.py), and [dashboard tests](tests/test_dashboard.py). The companion package adds this route and its exact query allowlist independently in [Mac relay](../../../../../communication/context_mcp/station_relay.py) and [Intel worker](../../../../../communication/context_mcp/station_worker.py). No separate `intel-runtime/transport` directory exists in this package.

To adopt the source, reconcile these changes into the actual Intel records service and the shared Mac communication deployment, preserve the existing database and private pairing, and deliberately load the updated processes. Check `/api/v1/schema` from the actual configured service, then verify a bounded dashboard read through the actual worker and Mac proxy. An older running relay or worker can reject the new route even when the backend advertises it; that is an incomplete deployment, not hardware failure.

The new tests use temporary SQLite records and in-process HTTP clients. They cover coherent reads during a concurrent write, session/cycle page limits, source filtering, focused-cycle scope, authentication and capability metadata, unavailable hardware states, exact recovery/unknown-outcome metrics, duplicate records, late confirmation, saved evidence references, and explicit oversized responses. Relay and worker tests cover the new query bounds while retaining forbidden motion/stream routes. The suite establishes software behavior only; it does not prove a live Intel-to-Mac connection, physical execution, camera publication or provider integration.

From this station directory, using an interpreter with the pinned test dependencies:

```bash
MORPH_AUDIT_FIXTURE_ROOT=../../../../fixtures/audit python -m pytest tests/test_dashboard.py tests/test_api.py tests/test_store.py tests/test_reviews.py tests/test_export_audit.py
```

The fixture root is the package's existing synthetic audit-fixture directory. The dashboard tests do not require a live database, provider credentials, camera, robot, or network listener.
