# Klemen publication verification

Checked on November 15, 2026, Europe/Ljubljana (UTC+01:00), after reconciling the current Intel M16/Gemma frontend and shared client with the Mac MCP transport. These results describe this publication package. They do not certify an updated Intel deployment, a model response or physical operation.

## Current checks

| Check | Result | Evidence |
| --- | --- | --- |
| Dashboard, history, analyst, proxy and MCP regressions | **69 passed**, no failures or skips | [JUnit](verification/reconciled-dashboard-tests.xml) |
| Shared client and store | **47 passed**, no failures or skips | [JUnit](verification/reconciled-client-tests.xml) |
| Offline export analyzer | **58 passed**, no failures or skips | [JUnit](verification/reconciled-analytics-tests.xml) |
| Shared-client TypeScript build | Passed | `npm exec tsc -- -p ../station-client/tsconfig.json`, from `dashboard/` |
| Dashboard TypeScript | Passed | `npm run typecheck` |
| Vite production build | Passed | `npm run build`; 38 modules, 403.01 kB JavaScript before compression |
| Isolated authenticated TLS MCP integration | **Passed** | [Exact result](verification/reconciled-mcp-roundtrip.json), [runner](verification/check_reconciled_mcp.py) |

The current unit/software total is **174 passed**. The proxy count includes the explicitly named older `stationProxy.mac-baseline.test.ts` and the new `stationProxy.mcp.test.ts`. The exact current Intel proxy test was not transferred. No complete current Intel proxy/backend analyst test result is claimed.

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

[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json) retains the original snapshot. [SOURCE_RECONCILIATION.json](SOURCE_RECONCILIATION.json) records current source receipt, exact source hashes, local adaptations and the final package inventory. Source receipt is separate from execution evidence.
