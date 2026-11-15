# Intel dashboard and producer integration

Request: `d5315791-6749-4b01-97b5-1b9357306487`. Session: `d0dc73a7-df82-48e6-a8c1-8a4c23c144e6`. Reporter: `/root` on Intel, including the attributed work of `/root/adoption_station`, `/root/adoption_codex` and `/root/adoption_receiver_review`.

This report separates source integration, isolated verification, actual service activation, shared transport, source delivery and physical acceptance. All times below are UTC on November 15, 2026 unless otherwise stated. The workstation's local date remains November 14 in America/Los_Angeles during these observations.

**Current result:** the main API was restored at **07:08:31 UTC**, preserving its canonical records and evidence. The actual shared Mac MCP / existing Intel GET worker / updated API path passed **nine requests covering eight logical checks** at **07:09:22 UTC**. The final integrated suite passed **309 tests**, with zero failures, errors or skips. See [actual recovery and relay evidence](RUNTIME_VERIFICATION.md). Klemen UI acceptance, real producer callbacks and physical acceptance remain open.

## Integrated source

The received request, START_HERE and manifest were read through the shared Mac MCP with complete pagination. All 18 supplied files were independently verified against their declared hashes. Full candidate files were treated as references; only the reviewed focused API/store changes were merged. The existing Intel source matched the supplied API/store baseline at that checkpoint. No payload, reference directory, database or evidence directory was overlaid.

| Active source path | Actual decision | Final SHA-256 |
| --- | --- | --- |
| `station/morph_station/api.py` | Deliberately merged focused dashboard API/capability change | `3ab02fc234add63fc1150db6c107324dafe68266cfdaad453c554e7753e7845a` |
| `station/morph_station/store.py` | Deliberately merged coherent dashboard read using one transaction | `d099d4b67269df66be6b09a24941ac71044f3de20e6d151dcded2f3e3bc59939` |
| `station/tests/test_dashboard.py` | Added exact candidate | `574cb9b804f2e007c0fd01093f25c1d4d1b9b8b474dc0de6bec1ece50175dddd` |
| `station/morph_station/producers.py` | Added explicit ingestion module and CLI | `de9dcdb39c539e2f9ec298b29d72c85cc26580bda4be811aba3984ccdb2a94ec` |
| `station/tests/test_producers.py` | Added 36 isolated API/store cases | `60d804e02c367a4bd151c2e4c62383328f9f9efcad079595c774b34ac58b81e9` |
| `station/PRODUCERS.md` | Added English producer contract and actual integration gaps | `ad5a05fa93ddc2479a3dde13146e02a365082197a2d9395b798d8c06bfd830a5` |
| `station/morph_station/__main__.py` | Deliberately merged a ten-second Uvicorn graceful-shutdown bound | `a01ca16760d38fa1fa1b1bb9f7e67b33eea6290ec799c8149b54551aaa5a7298` |
| `station/tests/test_cli_shutdown.py` | Added actual temporary CLI/open-SSE regression with canonical-data invariance | `633b1fb34721f00f3d9bccb149702bfd4da71d59a439a5b88645a435f8893e47` |
| `station/tests/test_store.py` | Skipped identical reference | `5639bed5712bf6a74bf3ec22276a52aedc9e9ff6152c27af18f2a97a8b4219c3` |
| `station/morph_station/models.py` | Skipped identical reference | `19a63e3603a2045763aec4dfc5b4afe408cc9117b8dc1554e759411ad15ac7a3` |
| `station/requirements.txt` | Skipped identical reference; existing Python/dependencies reused | `0a491f0674b2dd255f09385a5f36386212e26621770092b4c1ebaaf2edfca00b` |

The exact baseline/final decisions and AST preservation check are in [station-merge-result.json](station-merge-result.json). The active HachingJunction directory is not a Git repository; no local commit or clean working tree is claimed. Accepted M16, current Gemma work, records, history, correction and export-audit behavior remain distinct retained scopes.

The authenticated dashboard aggregate defaults to live data, reports a coherent event cursor, includes selected/current cycle detail and computed metrics, and retains explicit unavailable camera/control state. It has bounded session/cycle selection, strict query checks and an explicit oversize error. It does not silently truncate a full selected cycle or convert simulations into live records.

The producer module requires actual caller-owned IDs, source mode, measured timestamps and exact consumed PNG/JPEG bytes. It reuses the existing authenticated record, evidence and atomic-review endpoints. Stable retry IDs and strict response checks preserve attribution and avoid duplicate records. Image upload followed by frame creation is deliberately documented as two operations: a lost response may leave uploaded evidence until the identical input is retried. No capture, inference, motion, periodic producer or implicit live record is started by this adapter.

Two compatibility details were resolved in the new adapter: omitted review fields remain omitted, and a reference-label-only correction may retain the cycle revision and original label author while still requiring its new attributed correction audit. Existing backend checks were preserved. Real camera, detector and dispatcher call sites remain absent; their required capture/receipt/consumed-image and cycle associations are documented.

## Verification and retained failures

| Scope | Result and evidence |
| --- | --- |
| Focused dashboard/store | 51 passed, including 19 new dashboard cases; [merge report](station-merge-report.md) |
| Initial combined backend | 255 passed before the producer module; includes 58 original audit cases and 106 then-current Gemma cases |
| Producer module | 36 passed; [producer report](producer-integration-review.json) |
| Combined backend with producers | 291 passed, zero failures/errors/skips at 05:41:31; [exact command and hashes](combined-backend-results.json) |
| Frozen worker isolated relay | 24 passed; [result](station-worker-tests.json) |
| Initial transition guards | 7 passed without real signals/process starts; [result](station-transition-preparation-result.json) |
| Prepared live-relay harness | 9 offline cases passed, including older-cycle image discovery and rejected bad/expired/inconsistent responses; [result](relay-harness-offline-checks-final.json) |
| Final integrated backend | **309 passed**, no failures/errors/skips; analyst 123, API 16, CLI 1, dashboard 19, export audit 58, producers 36, reviews 24, store 32; [result](final-integrated-20261115T065834Z/result.json) |
| Final recovery preparation | 27 isolated guard cases passed; nine metadata and 33 active source pins independently reviewed; [result](transition-v4-20261115T065901Z/recovery-preparation-result.json) |
| Actual service and shared transport | Six readiness GETs and nine MCP relay requests passed, with unchanged records/evidence/cursor; [runtime report](RUNTIME_VERIFICATION.md) |

Tests used the existing Station Python environment and the original package fixture directory through `MORPH_AUDIT_FIXTURE_ROOT`. They used temporary databases, saved simulation fixtures and fake providers. The one existing FastAPI/HTTPX deprecation warning did not trigger a dependency change. Later concurrent Gemma v12/context v7 and its 308-case result are separately attributed evidence; the revised activation review reconciles those newer bytes before use.

The first producer test report retains one failed case caused by serializing omitted review fields as null; the corrected 16-case and expanded 36-case reports remain alongside it. The first copied-database preflight retains a schema-cookie comparison failure: SQLite's per-file cookie was 8 in the source and 1 in its backup while full canonical rows and SQL schema matched. The corrected check requires invariance within each file and exact cross-file canonical/schema equality. It does not remove application checks or alter the source database.

The first actual activation invocation exited with a source guard before creating its activation directory or signaling a process. While host approval was pending, the concurrent Gemma lane changed `analysis_models.py`, `analysis_provider.py`, `test_analysis.py` and the portable fixture resolver in `test_export_audit.py`. API/store candidates stayed identical. The old preparation and blocked attempt remain preserved; newer source is reviewed and retained instead of restored to old hashes. See [blocked invocation](activation-attempt-01-blocked.json).

## Communication and owner decisions

The unchanged frozen GET-only worker was started at 05:22:25, PID 417036, for `intel-main` at `127.0.0.1:8000`. Three real Mac-origin schema/snapshot/session responses were fully read and independently hashed on Intel. [Transport evidence](mac-roundtrip-evidence-review.json) records all request IDs and original bodies. This earlier proof concerns the then-running API and saved simulation, not the new dashboard route.

Adoption note `a945e833-76b1-48eb-baf2-dda17da173aa` was saved and read back with SHA-256 `5485f843dc1e827707cf3f45d33485a8af00d68dd77cf63ff761f74dbc4bc6a0`. Its Intel-to-Mac event `91faa914-8253-55ca-af2a-3ed08058efab` was independently read as processed. A processed review is not deployment or physical acceptance.

The owner's later direction supersedes the earlier conditional receiver-start guide: the automatic Intel Codex receiver was stopped and standalone CLI logged out at 06:18. Automatic coordination/review belongs to Jose on Mac. Preserve its state and historical result, and do not sign in or restart it under the old request. [Stop/logout receipt](../intel-continuation-20261115T0544Z/owner-logout-receipt.json).

The existing passive five-minute watcher and GET worker remain separate processes. Historical poll failures are retained; subsequent successful polls do not retroactively diagnose their cause. No watcher cadence change is required by this integration.

Low-latency video documents were completely read and verified. They remain a proposal, including a separate authenticated media path, a single camera owner, replacement of stale queued previews and a persistent Studio subscription. The proposed p95 below 300 ms over ten minutes is unmeasured. Continuous media implementation and exact analyzed-frame evidence remain distinct tasks.

## Remaining gates and synchronization

The central [TODO](../../TODO.md) preserves all M01–M24 task scopes, the ten dashboard acceptance scenarios and prior completed transfers. The owner explicitly reconfirmed ongoing arm diagnostics. Leader remains `5B91030668`, follower `5AE6075066`; this work does not access either port, calibrate, capture images or move hardware.

Original order remains environment/cameras/calibration/teleoperation, mentor/pilot freeze, actual demonstrations and skills and real Anomalib detector, full physical cycle, existing Intel Gemma integration, then M22 measurements after the baseline works. Existing accepted software/access scopes stay accepted. No simulation result closes a physical gate.

Actual updated-service activation and dashboard/image transport verification are recorded in the subsequent runtime supplement. Klemen UI acceptance is separate from an Intel-initiated request through shared MCP. Full actual source delivery follows the new standing SOURCE_SYNC policy, with per-file baselines, frozen companion, strict manifest/chunk readbacks and one completion event per complete logical group. A descriptive progress note is not source delivery or Mac publication.

Shared checkpoint `af1e91ca-da66-4845-a05a-a06364a82868`, saved/read back at 06:28:29, has SHA-256 `b4c64439b19eec63b506547d005c0ac8758f02f891e43fead4fd05046f9c55fb`. It attributes all three contributors and records the new source guard and owner revocation. Final runtime/source/Notion receipts are retained separately; M20/M21 remain In progress with original acceptance and dependencies preserved.


## Actual shutdown failures and focused correction

At 06:36:26 root sent the reviewed single SIGTERM; the 20-second wait expired without replacement. At 06:39:33 an approved host inspection found the same old process sleeping, no port 8000 listener, one established connection and health unavailable. A separate guarded recovery captured the original environment in memory, made fresh unchanged backups and sent one SIGINT at 06:56:37. Its ten-second exit wait also timed out; the 06:57:08 host recheck confirmed the same no-listener state. No replacement or database restore occurred. Full reports remain in the v2/v3 run directories.

The installed Uvicorn/open-SSE shutdown risk was reproduced independently in a disposable actual CLI subprocess. The original failed to exit within 15 seconds while an SSE client remained open. `station/morph_station/__main__.py` now supplies `timeout_graceful_shutdown=10`; `station/tests/test_cli_shutdown.py` keeps the real test stream open until process exit and verifies the full canonical SQLite dump. The identical test passes in 10.195 seconds. This establishes the regression and fix; the exact outstanding old-host task remains unproven. The separate existing analyst shutdown join retains its own 30-second bound.

New active source: `__main__.py` merged from baseline `6fa9fec57125b6002e55641966c991a11f514db0ef7e8448ebe2c99d3d6f71ef` to `a01ca16760d38fa1fa1b1bb9f7e67b33eea6290ec799c8149b54551aaa5a7298`; added `test_cli_shutdown.py` SHA `633b1fb34721f00f3d9bccb149702bfd4da71d59a439a5b88645a435f8893e47`. The 31 other previous source pins are unchanged. See [exact before/after evidence](shutdown-fix-20261115T064128Z/result.json). Production recovery remains a separate recorded operation.

## Completed runtime recovery

Root executed the explicitly approved v4 recovery at 07:08:31. It freshly checked both failed shutdown receipts, exact old PID/start ticks, original arguments/environment, all frozen source, empty listener state and unchanged companion processes. Private SQLite and actual evidence/analyst-file backups preceded a single pidfd SIGKILL to old API PID 188282. This was an unclean termination, and no successful completion of interrupted requests is claimed. The final committed database and evidence did not change. No restore or rollback was used.

The same command, interpreter, working directory and in-memory environment launched API PID **476229**, start ticks **14924157**. Health, OpenAPI, schema, live dashboard, simulation dashboard and analyst reports returned 200. There are 41 canonical records and 50 events; the cursor is 50, live sessions are zero and the preserved simulation contains one session/five cycles. Worker 417036, watcher 279692 and dashboard 188283 retained their identities. The owner-revoked automatic Intel receiver remains disabled.

The bounded relay then made nine real requests through the existing shared Mac MCP and GET worker. Full body hashes, selection/source identity, the expected 404/409 responses and repeated coherent state all matched direct API reads. The referenced 68-byte simulated PNG matched the relay, direct endpoint and local evidence exactly. The actual transfer worked; neither real camera/model evidence nor Klemen UI rendering was tested by this harness.

| Immutable report | SHA-256 |
| --- | --- |
| [Approved recovery result](transition-v4-20261115T065901Z/station-recovery-20261115T070831253122Z/recovery-result.json) | `f8c57a404a09a55b4a116832583028411f6c211afadc9a0725059100d882e904` |
| [Actual relay result](relay-verification-20261115T070901Z-8bce8491/result.json) | `5dcff5ed0e1f56615da7f3d41afa8cc009906cab48df6f4b6bdf02b4d024ab4e` |
| [Final integrated test result](final-integrated-20261115T065834Z/result.json) | `1ae3c68a805d06cde2d3e3ca5ffe3bd3a3664e83f2bcb4fba9ecb372ed655e1f` |
| [Final JUnit report](final-integrated-20261115T065834Z/station-tests.xml) | `cd7097bbf47074ed475bfd53870846cacd6629be5dd48001e6c40aeda16bc0af` |

## Source delivery and current mapping correction

All groups retain request `d5315791-6749-4b01-97b5-1b9357306487`. Full chunk-note paths and hashes are in the [dashboard/producer ledger](source-delivery-20261115T062819Z/SOURCE_DELIVERY_REPORT.md) and [shutdown ledger](shutdown-source-delivery-20261115T064601Z/SOURCE_TRANSFER.md). Their earlier pending-event wording is a dated snapshot; the completion events below were subsequently published and read back.

| Group and state | Manifest note path | Full manifest-note SHA-256 |
| --- | --- | --- |
| Dashboard adoption — source delivery complete; completion `53d998b4-fd3e-40c1-8b7f-71ce8ecae59d` | `context/notes/84ebe925-0e49-5476-9183-dda33cf79e1c.json` | `84921a7ec9572e4d55672f0ba6739a573d7df0ba3e857972093ca57ddbedd078` |
| Producer ingestion — incomplete; no completion event | `context/notes/f5ed8867-ef91-5f23-a383-1f972af4fdff.json` | `9e74ea0e67590864d6a22d585f5082e4c90af59a9848fcd7d992f0d4045816db` |
| CLI shutdown — source delivery complete; completion `ea3c127e-4f0a-454f-aac4-cd2745c79320` | `context/notes/26f5de83-62dd-54a8-851c-c0b6f5d83d0a.json` | `ccb385334b1cafb79c77630421d35fc7bb175f1ff619beb94b8b0c3d1e9edcc6` |

The exact original `test_producers.py` remains rejected by the unchanged sender's screening of a synthetic rejection fixture. It is retained locally, 19,772 bytes with the hash in the source table above. No renaming, encoding, screening bypass or edited substitute was used. Mac correction `0aca9667-60a6-51a5-a784-e6a5937fc231`, full SHA `8662d771989f43e2835ffba8d18ab05492bb833c37eafe7994eff6cb50c6927a`, explicitly preserves this incomplete state and distinguishes it from the separate analyst-test request. A future review-only copy cannot establish exact-suite reproduction.

The same Mac correction confirms that the Intel-runtime common store already matches `d099d4b...`; the older `klemen-dashboard/analytics` store is a distinct package copy to preserve. The next companion must identify the Intel runtime sibling mapping, superseding only the earlier proposed mapping. Frozen bundles remain unchanged. A received source group or processed event does not prove Mac reconciliation, publication or UI acceptance.

The new runtime checkpoint is `eb59a294-b174-466d-bdff-2b704ec14c43`. It requests Klemen UI verification and append-only annotations to existing M20/M21 using stable update IDs `e89ceeb8-66a3-45cc-9efe-2c4f949d1fd1` and `26a7a590-2eb0-48ce-a853-dc10a0cceb63`. The exact intended updates are retained in the existing [Notion ledger](../../morph-intel-transfer/morph-context/NOTION_SYNC.md). Their synchronization is separate from MCP delivery and remains pending until exact Notion readbacks arrive. Both tasks retain In progress status and all original acceptance/dependencies; no physical task is closed.


Runtime handoff delivery is **confirmed**: `context/notes/eb59a294-b174-466d-bdff-2b704ec14c43.json`, saved at `2026-11-15T07:15:59.624627+00:00`, full SHA-256 `71d49ac5e842ca2f3968f412a06ecea6495540855a7131064172c200848cebdf`. All six intended fields matched the complete readback. Event `3ba364e3-d572-5b30-b541-e90380554729` has origin `intel`, target `mac`; it was claimed at the saved readback. This confirms the attributed team report reached the Mac; it does not itself confirm the requested Notion updates or UI acceptance. See [receipt](receipts/runtime-restored-readback.json).


## Newly reviewed passive video handoff

Mac subsequently supplied an additive live-video package in ordinary note `d7e7aa66-1470-4587-a2f9-5a37dadc7da6`. Its 60-file manifest has SHA-256 `56d265d92dda855578ea94468b46481ea5e9213ed0b7349b5b2455f1f9b2dc72`. This supersedes the proposal-only development status above: Mac implementation and synthetic evidence now exist. It does not establish Intel adoption. The complete note, README, manifest and selected evidence were read; further Intel review is separate from active installation.

Saved Mac results describe 111 dashboard tests, 25 bridge tests and 4,466 native browser frames over 148.846 seconds, plus an isolated local RTSP source-gap/jitter test. These are Mac synthetic observations. Intel package/dependency review, active capture ownership, protected signaling/media routing, owner-coordinated launch and optical ten-minute latency measurement remain open. The p95 below 300 ms remains an unmeasured target. Jose coordinates adoption; no automatic Intel receiver, camera pipeline or new media service is started by this dashboard handoff. The [shared review](shared-review-20261115T070919Z/REVIEW.md) records exact pagination and evidence limits.
