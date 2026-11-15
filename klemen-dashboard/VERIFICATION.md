# Klemen publication verification

## Current integration checkpoint — November 15, 2026

The later [workflow integration evidence](verification/workflow-integration-20261115/) records 116 passing dashboard tests and 114 passing dependency checks: 19 compact backend API, 18 relay, 24 worker and 53 shared-client tests. Seventeen distinct launcher/readiness regressions passed: seven lifecycle/configuration tests plus ten final checker tests. The dashboard production build and TypeScript check passed. Authenticated reads through the actual Mac MCP/Intel worker verified the restored API, one five-cycle simulation session, original retry image and analyst context, and no live session. The browser's saved-history JSON retained its displayed generation time and record identities. Native browser navigation also confirmed retry detail and read-only replay of the original 50 events.

The complete disposable launcher showed 640×480 H.264 at 30 FPS in the browser and passed the 13-read, two-export history/replay check. Ctrl+C closed a real open event-stream client, stopped all seven observed owned processes and removed the temporary runtime. A malformed private configuration failed with a fixed diagnostic without exposing its secret sentinel. Actual Intel camera playback and optical latency were not measured.

These results supersede the earlier claim below that the Mac–Intel read roundtrip was still open. Real camera delivery, physical execution and a completed product analyst request remain separate checks. The historical sections and their original source hashes are preserved. See [WORKING_SYSTEM.md](../WORKING_SYSTEM.md) for the operational boundary and remaining target work.

Checked on November 15, 2026, Europe/Ljubljana (UTC+01:00). The owner-approved dashboard upgrade follows the source-reconciliation checks retained below. These results do not certify an updated Intel deployment, a real model response or physical operation.

## Dashboard upgrade checks

| Check | Result | Evidence |
| --- | --- | --- |
| Dashboard, projection, history/replay, analyst, proxy and MCP transport | **76 passed**, no failures or skips | [JUnit](verification/dashboard-upgrade-20261115/dashboard-tests.xml) |
| Shared typed client and store | **53 passed**, no failures or skips | [JUnit](verification/dashboard-upgrade-20261115/client-tests.xml) |
| Staged Intel backend | **149 passed**, including 19 new compact-dashboard cases | [Backend result and source hashes](../intel-runtime/source/common/HachingJunction/station/verification/dashboard-read-20261115/verification.json) |
| Communication relay/worker | **67 passed**, no failures | [Saved result and command](../intel-runtime/source/common/HachingJunction/station/verification/dashboard-read-20261115/verification.json) |
| Shared-client build, dashboard TypeScript and production build | Passed | [Upgrade result](verification/dashboard-upgrade-20261115/result.json) |
| Actual temporary backend → proxy → shared client → dashboard wrapper | Passed; simulation only, 13 GETs and two explicit history/replay exports | [Demo result](verification/local-demo-20261115/result.json), [reproduction](LOCAL_DEMO.md) |
| Browser interaction and layout | Desktop and narrow views checked against the temporary simulation backend | [Browser evidence](verification/dashboard-upgrade-20261115/browser-review.json) |

The current changed-layer software total is **345 passing tests**. It does not add the older analytics count below: analytics code was unchanged and that older result retains its date/scope. The new cases cover aggregate scope/revision/sequence validation, a changing event cursor, old-API fallback, stale/disconnected retention, on-demand exports, older-session discovery, delayed history completion and concurrent replay activation. The proxy test verifies the new route through the actual MCP adapter with a synthetic queue and rejects unknown/duplicate parameters and writes. Backend cases cover atomic concurrent reads, bounds, source isolation and mixed timestamp precision.

The disposable local demo uses the actual modified API/store with fixture records and synthetic imagery, the same-origin proxy and canonical client/store. It verifies no full exports during ordinary refresh, on-demand history/replay, unchanged event sequence/metrics and rejected writes. It is separate from the existing real MCP network. A second owned demo supplied the browser review and was stopped after screenshots; no private configuration or real record database was used. Full result timestamps and cleanup evidence are saved with the reports.

Actual Intel adoption, the live worker/MCP roundtrip, camera capture, useful provider behavior, learned policies, measured telemetry and physical execution remain open. Vite's existing configuration compatibility warning does not prevent the recorded build. The frozen source-reconciliation manifests are unchanged; [upgrade hashes](verification/dashboard-upgrade-20261115/source-hashes.json) record the later source separately.

## Earlier reconciliation checks

| Check | Result | Evidence |
| --- | --- | --- |
| Dashboard, history, analyst, proxy and MCP regressions | **69 passed**, no failures or skips | [JUnit](verification/reconciled-dashboard-tests.xml) |
| Shared client and store | **47 passed**, no failures or skips | [JUnit](verification/reconciled-client-tests.xml) |
| Offline export analyzer | **58 passed**, no failures or skips | [JUnit](verification/reconciled-analytics-tests.xml) |
| Shared-client TypeScript build | Passed | `npm exec tsc -- -p ../station-client/tsconfig.json`, from `dashboard/` |
| Dashboard TypeScript | Passed | `npm run typecheck` |
| Vite production build | Passed | `npm run build`; 38 modules, 403.01 kB JavaScript before compression |
| Isolated authenticated TLS MCP integration | **Passed** | [Exact result](verification/reconciled-mcp-roundtrip.json), [runner](verification/check_reconciled_mcp.py) |

The earlier reconciliation unit/software total was **174 passed**. The proxy count includes the explicitly named older `stationProxy.mac-baseline.test.ts` and the then-new `stationProxy.mcp.test.ts`. The exact current Intel proxy test was not transferred. No complete current Intel proxy/backend analyst test result is claimed.

The TLS integration creates a temporary MCP service, credentials, queue and synthetic local API; it uses the adjacent communication package's actual relay and worker. Seven worker operations completed exactly once. JSON (91,040 bytes) crossed three base64 pages and retained its exact SHA-256; CSV and finite SSE retained their exact bodies. A comparison retained both ordered `sessionIds`. Review returned HTTP 200, analysis submission 202 and a structured conflict 409 with its exact JSON body. Missing-worker GET and POST both returned 503, with the mutation outcome explicitly unknown and no automatic repeat. The result records the hashes of the relay, worker, server and Node adapter actually exercised.

This test never connected to the existing MCP, Intel, a provider or a robot. It did not verify a live browser, deploy a service or create a real report. The temporary relay state and credentials were removed when the runner finished.

To reproduce after installing dashboard and communication dependencies, from this package root:

```bash
../communication/.junction-setup/context-mcp/bin/python verification/check_reconciled_mcp.py --node node
```

The runner also requires `openssl` on PATH to create a temporary localhost certificate. `--communication /path/to/communication` can select another staged copy. Use the communication package's MCP environment; a generic station Python environment does not contain the MCP SDK.

## Verification boundaries

The proxy permits authoritative reads plus only two explicit JSON POST intents: an audited cycle review and an evidence-analysis request. It validates local Host/Origin, route, intent, valid UTF-8, object JSON and a 64 KiB request limit. The relay and worker validate again. Application IDs and exact body bytes survive the transport. Only an intentional human submission or identical explicit retry can send a mutation; load, refresh, view selection and reconnect do not.

The relay uses a fresh request UUID, 30-second expiry, a 35-second adapter deadline and a 40-second browser deadline. Complete responses are capped at 4 MiB and must pass offset, immutable-metadata and SHA-256 checks. Oversized responses fail instead of being truncated. There is no stale response cache. Browser SSE advances the original event cursor and ends on worker loss; events invalidate reads without creating records or incrementing counters.

The complete current synthetic CSV fixture is included. Fixtures and provider replies in these tests are simulated. Export integrity, persisted metric denominators, review/retry IDs, history/replay isolation and error behavior are software checks. No trained policy, live camera, voice utterance, useful Gemma response or physical cycle was verified here.

`npm ci` used the package's existing lockfile. Validation dependencies and build output are excluded from the final source inventory. Vite still reports the existing `__dirname` configuration compatibility warning; the checked build succeeds.

## Earlier evidence

The other reports already present under `verification/`, including `check-results.json`, `mcp-https-roundtrip.json`, `local-startup.json` and the `*-mcp-final.txt` logs, belong to the earlier Mac GET-only handoff. Their 129-test total and runtime observations are historical and do not describe this reconciled package. They are retained unchanged for provenance. The old `check_mcp_https.py` runner also belongs to that earlier package layout; use the isolated runner above for this publication.

[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json) retains the original snapshot. [SOURCE_RECONCILIATION.json](SOURCE_RECONCILIATION.json) records the frozen reconciliation receipt, source hashes and adaptations before the dashboard upgrade. Source receipt is separate from execution evidence.
