# Bounded Station event-stream shutdown

**Mac package annotation — 2026-11-15T07:17:33.712630+00:00.** The following report records the producing Intel team's test on November 15. Its final pending list describes that earlier moment. Delivery `60fff35b-12d2-4efd-a97e-e224b8199cb6` subsequently supplied the exact CLI, original regression, this report and structured result. The omitted XML/diff references are labeled below. A separate Mac regression against committed package `daab4b41420f8d035153e402a8bb7c69e31bddee` reproduced the timeout before the change and passed afterward in 10.231 seconds, preserving the synthetic ledger. These Mac results are separate from the Intel measurements. Publication does not deploy or recover the main Intel service. Original and adopted hashes are retained in the package provenance.

At 2026-11-15T06:44:04.708817+00:00, `/root/adoption_station` completed a narrow CLI repair for request `d5315791-6749-4b01-97b5-1b9357306487`. Root owns real-service recovery and the shared Mac report/source delivery.

The Station's event stream can stay open while Uvicorn waits for responses to drain. The existing `serve` branch now passes `timeout_graceful_shutdown=10` to Uvicorn. After that deadline Uvicorn cancels outstanding connection tasks and continues application shutdown. No CLI argument, authentication source, database setting, provider setting or environment contract changes.

Added `station/tests/test_cli_shutdown.py`. It starts the actual CLI in an isolated subprocess with a temporary database containing two synthetic simulation records, an ephemeral token and an explicitly limited environment. It opens an authenticated real HTTP event stream, reads an event, keeps the response open, and sends SIGTERM only to the owned subprocess. A complete SQLite dump must remain unchanged after exit. No analysis request, provider credential or hardware enters the test.

The test reproduced the pre-fix failure: the process remained alive beyond the 15-second wait while SSE stayed open. Cleanup closed the owned client and reaped the process without SIGKILL. With the repair, the identical test passed: measured SIGTERM-to-exit **10.195 seconds**, process return code **-15**, and unchanged canonical records. The passing test run took 10.544 seconds overall. The before/after XML hashes, structured measured results and exact commands are preserved in [result.json](result.json); the original XML files remain on Intel.

| File | Decision | SHA-256 |
| --- | --- | --- |
| `station/morph_station/__main__.py` | edit | `a01ca16760d38fa1fa1b1bb9f7e67b33eea6290ec799c8149b54551aaa5a7298` |
| `station/tests/test_cli_shutdown.py` | add | `633b1fb34721f00f3d9bccb149702bfd4da71d59a439a5b88645a435f8893e47` |
| `before.xml` (Intel-local, not transferred) | Preserve reproduced failure | `1f6dbaf2bb6b9fcae537b19ce1f1f1e23aaa05df02464b3fc945dba83664d500` |
| `after.xml` (Intel-local, not transferred) | One passing regression | `d09e024a47c8d5a7e6a54e512a9e62a02ccbd24eb143ac9298a3a095876c3ac4` |

All 31 other previously pinned application/test/fixture files retain their hashes. This agent did not run another broad backend suite: only the real CLI regression was relevant to this change. Existing v2 review tools, private backups and actual failed activation remain unchanged. The source snapshot and `main-change.diff` (Intel-local, not transferred) are frozen for root's recovery and publication review.

The ten-second deadline bounds Uvicorn connection/task draining. The existing analyst lifespan can additionally wait up to 30 seconds for an already-running bounded request; this repair preserves that behavior. The regression has no running analysis jobs. The test proves the disposable SSE behavior, not the historical host connection's identity or a completed production recovery.

**Pending:** root's real-service recovery result, verified Mac reporting and actual eligible source delivery. The temporary token/database/logs are runtime test material and must not enter source delivery. The modified CLI, new test and this operator explanation are the logical source group; baseline/final hashes are recorded in the result.
