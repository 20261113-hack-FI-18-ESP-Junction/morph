# Actual Intel Station recovery and Mac MCP relay

At 2026-11-15T07:08:31Z the reviewed main Station API was restored on 127.0.0.1:8000. The old exact process required one approved pidfd SIGKILL after retained failed SIGTERM/SIGINT attempts. Fresh private SQLite, evidence and analyst backups preceded the unclean termination; exact original arguments/environment were retained in memory. New PID 476229/startTicks 14924157 serves the integrated dashboard and analyst routes. Canonical records/evidence remained unchanged, event cursor 50, with 41 records and 50 events. There was no database restore, seed, provider call or hardware operation. Existing GET worker 417036, five-minute watcher 279692 and dashboard 188283 retained identities. Automatic Intel Codex receiver remains intentionally stopped/logged out under the owner's 06:18 correction; coordination belongs to Jose Mac.

At 07:09:01–07:09:22 UTC the actual Intel agent -> shared Mac MCP queue -> existing GET-only Intel worker -> main API -> shared Mac MCP response connection passed all nine requests/eight logical checks. Verified schema, empty live view, saved simulation view, two selected-cycle reads, missing session 404, source mismatch 409, exact analyzed-image bytes, and repeated coherent state. All response bodies were fully retrieved and hashed; direct GET JSON matched except declared generatedAt fields. The 68-byte 1x1 saved simulated PNG matched relay/direct/local bytes and SHA-256 3afd67627c9ad149a848aed228fe2884d4a696d74f5beb27d1e4d57ef1767fa9. This is actual cross-host transport of simulation evidence, not a camera capture, real model output, physical acceptance or Klemen UI rendering. No records were created; live sessions remain zero, saved simulation has one session/five cycles.

Final integrated Station suite: 309 passed, zero failures/errors/skips, using existing Python and the original MORPH_AUDIT_FIXTURE_ROOT. Modules: analyst123/API16/CLI1/dashboard19/export-audit58/producers36/reviews24/store32. The real disposable CLI/open-SSE regression exits in 10.140 seconds with its complete canonical database unchanged. Prior failures remain retained; no checks were weakened. Current source includes focused dashboard API/store, explicit input producer adapter, and ten-second CLI graceful-shutdown bound, while preserving newer Gemma v12/context v7.

Remaining: Klemen must verify the actual UI against intel-main; real camera/detector/dispatcher producer callbacks and original physical acceptance remain open. User explicitly says arm diagnostics continue, so no arm/camera access. Preserve M03/M04/M06/M15/M16 accepted scopes; M20/M21 stay In progress with original criteria and dependencies. Initial environment/camera/calibration -> mentor/pilot -> demonstrations/skills/real detector -> physical cycle -> existing Gemma -> M22 baseline-first ordering stays unchanged.

## Actual request ledger

| Check | Request ID | HTTP | Body SHA-256 |
| --- | --- | --- | --- |
| 01-schema | `ac104e46-76aa-454c-9486-46ace2723be2` | 200 | `4e935aa8b1bcd78eb9d4daa2153475cdf0a0d430fee8979b45cbb92fbd80280d` |
| 02-dashboard-live | `09450d05-a059-49d9-887e-da1a3ed9cbbc` | 200 | `1204c38d7d1e6c0fe4ef0de4faf923e92e51485ec29ca337d8501e16b290829c` |
| 03-dashboard-simulation | `b4cf6c07-6287-4061-be3b-52751023cbe6` | 200 | `012e781f5d147c5c0a98473d216a7f3e4221febcb0588f7c22250678dabfa233` |
| 04-selected-cycle-00 | `73a3353e-9924-4aa1-a17e-5ffd1e440b42` | 200 | `7f7bfc7b22fa7ba6edef7a2099153cdbdef16617b6ea2f78b0e427bee6f78666` |
| 04-selected-cycle-01 | `905617a4-422b-4d39-a34e-961b8e15bb8a` | 200 | `617c1bd1bf3353e68eb1498caf2636360892fd4ab3222c76bcd71126f79a6e4e` |
| 05-missing-session | `bc657fc0-4246-464f-98a1-223d5be68f52` | 404 | `9cacfd4e290c06186ec60db4cfdafa33bc32abac703258f674eff230163a8190` |
| 06-source-conflict | `11a4b20c-837d-4a8e-bbe8-ec8f63f1c4bf` | 409 | `5a616ee301e41f51d3d17772f42ad7738e4eafc1b1799a095578dc106f8d3d70` |
| 07-saved-analyzed-image | `f1d4588d-10ca-4eb8-a9dc-b2badcb9af2c` | 200 | `3afd67627c9ad149a848aed228fe2884d4a696d74f5beb27d1e4d57ef1767fa9` |
| 08-repeat-selected-cycle | `806de9db-631a-4fa3-9d33-d92533626a61` | 200 | `d053eb455c2a203cceb93548d3919cf1e678c732eedacf8b1402303997eae8a5` |

## Immutable evidence

- [recovery-result.json](transition-v4-20261115T065901Z/station-recovery-20261115T070831253122Z/recovery-result.json) — SHA-256 `f8c57a404a09a55b4a116832583028411f6c211afadc9a0725059100d882e904`
- [result.json](relay-verification-20261115T070901Z-8bce8491/result.json) — SHA-256 `5dcff5ed0e1f56615da7f3d41afa8cc009906cab48df6f4b6bdf02b4d024ab4e`
- [result.json](final-integrated-20261115T065834Z/result.json) — SHA-256 `1ae3c68a805d06cde2d3e3ca5ffe3bd3a3664e83f2bcb4fba9ecb372ed655e1f`

All nine logical request receipts include complete response-page metadata, request/source identities, direct comparisons and body hashes. Only permitted GET paths were queued. The saved image is explicitly a one-pixel simulated-camera fixture. No timing measurement here is a physical-cycle benchmark or M22 result.

Source delivery: dashboard-adoption manifest context/notes/84ebe925-0e49-5476-9183-dda33cf79e1c.json SHA84921a7ec9572e4d55672f0ba6739a573d7df0ba3e857972093ca57ddbedd078, completion53d998b4-fd3e-40c1-8b7f-71ce8ecae59d/eventc9547375-e57a-5151-8421-b84b0189fdaa saved/read back. Shutdown group manifest context/notes/26f5de83-62dd-54a8-851c-c0b6f5d83d0a.json SHAccb385334b1cafb79c77630421d35fc7bb175f1ff619beb94b8b0c3d1e9edcc6, completionea3c127e-4f0a-454f-aac4-cd2745c79320/eventb4f73037-5d1c-5443-854f-d90ea46a9087 saved/read back; Mac subsequently acknowledged receipt. Producer manifest context/notes/f5ed8867-ef91-5f23-a383-1f972af4fdff.json SHA9e74ea0e67590864d6a22d585f5082e4c90af59a9848fcd7d992f0d4045816db remains INCOMPLETE because the original test_producers.py,19772bytes,SHA60d804e02c367a4bd151c2e4c62383328f9f9efcad079595c774b34ac58b81e9 is rejected by unchanged source screening. Preserve the original and no completion event. Fresh Mac correction0aca9667-60a6-51a5-a784-e6a5937fc231 is acknowledged: next companion will identify Intel-runtime common-store sibling mapping, preserving the distinct older Klemen analytics store. No published dashboard/producer/shutdown commit is claimed by these receipts.

## Reporting and acceptance

Requested EXISTING task annotations, not closures: M20 page418d87e3445881a5b926d243895df509 updateId e89ceeb8-66a3-45cc-9efe-2c4f949d1fd1; M21 page418d87e3445881b2a2afd8d2b7f306c6 updateId 26a7a590-2eb0-48ce-a853-dc10a0cceb63. Both intended In progress. Append the above dated runtime/test evidence and limitations, retain all original acceptance and dependency text and newer annotations, and return exact saved Notion readbacks. Earlier owner-correction IDs c913ec0b-13c1-45dc-a742-5a70fa30e0a6 / 0db9d8d1-724a-423c-bc57-6753ec1154c1 were reported/read as already applied at07:01:42.834Z; do not duplicate them. This NEW runtime annotation is pending until separately verified.

Attribution: /root/adoption_station implemented/reviewed dashboard/producers/CLI correction, ran final309 tests and independently peer-reviewed v4; /root/adoption_receiver_review prepared guarded v4 and27 isolated checks and reconciles the all-task TODO; /root/adoption_codex prepared the bounded real relay harness, independently verified source delivery/readbacks and fresh Mac evidence; /root reviewed, performed authorized recovery and actual relay, preserves records and publishes all contributors. The v4 peer report SHAe40195129d347e974ad534372a785bba668c888b16d4140cf563f370cda27fb2 and preparation SHA6633abf728abb592284c45b4d47e030be0c9305de0874b98e1b4f3afa88c1635 retain 33source/9metadata pins and27 passed guard tests. No child executed real recovery.


Runtime handoff delivery is **confirmed**: `context/notes/eb59a294-b174-466d-bdff-2b704ec14c43.json`, saved at `2026-11-15T07:15:59.624627+00:00`, full SHA-256 `71d49ac5e842ca2f3968f412a06ecea6495540855a7131064172c200848cebdf`. All six intended fields matched the complete readback. Event `3ba364e3-d572-5b30-b541-e90380554729` has origin `intel`, target `mac`; it was claimed at the saved readback. This confirms the attributed team report reached the Mac; it does not itself confirm the requested Notion updates or UI acceptance. See [receipt](receipts/runtime-restored-readback.json).
