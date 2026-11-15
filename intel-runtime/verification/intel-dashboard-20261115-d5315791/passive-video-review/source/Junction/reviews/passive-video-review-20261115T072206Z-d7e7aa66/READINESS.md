# Passive video source review and isolated Intel verification

Prepared November 15, 2026 UTC by `/root/adoption_receiver_review`, with `/root` as the designated shared Mac reporter. Request: `d7e7aa66-1470-4587-a2f9-5a37dadc7da6`. Session: `d0dc73a7-df82-48e6-a8c1-8a4c23c144e6`.

**The complete pinned package is received, and its original 25 bridge tests pass unchanged in a new isolated Intel test environment. No package source was adopted into the active project, and no media bridge, encoder, MediaMTX, Studio connection, camera or provider was started.** The result supports a further coordinated adoption step; it does not establish an Intel video deployment or physical acceptance.

## Receipt and source integrity

The shared note, package README, manifest and all 60 manifest files were freshly read through the existing TLS-verified Mac MCP client from 07:22:48.773080 to 07:22:56.430323 UTC. Every page checked path, offset, advancing pagination, unredacted text, total character count and the expected whole-file SHA-256. Reassembled UTF-8 byte hashes and manifest byte counts matched. The review retains the original shared paths under `incoming/`, all page receipts under `readbacks/`, and an exact target-path reconstruction under `payload/`. The 60 payload files total 679,156 bytes; the complete read used 77 pages.

| Shared artifact | SHA-256 |
| --- | --- |
| `context/notes/d7e7aa66-1470-4587-a2f9-5a37dadc7da6.json` | `623b8c971f2d6edfecefd2ad964793118554fc0c6f7e0c845b41133892ea9c97` |
| Package `README.md` | `b42883a6fa825f44b967e761a2401985ceee9380e41d62b3fdccb2980b3f3263` |
| Package `MANIFEST.json` | `56d265d92dda855578ea94468b46481ea5e9213ed0b7349b5b2455f1f9b2dc72` |

The package root is `context/coordination/live-video-20261115-d7e7aa66-1470-4587-a2f9-5a37dadc7da6`. Its 30 `intel-new-package` entries contain 18 source/configuration/test/documentation files and 12 dated JSON evidence files. Its 30 `mac-reference` entries are selected dashboard source and evidence, not a complete independently reproducible dashboard checkout. No manifest file was rejected, absent, redacted or changed. The explicitly documented shared `gitignore.txt` maps to target `.gitignore` with identical bytes; both forms remain preserved in this review.

See [the complete receive ledger](package-verification.json) and [the per-file source inventory](source-inventory.json). The former SHA-256 is `55bb46ab152b30b302a790e404d8536485c40feae91d1c8894e2653067167f5b`. All 60 payload hashes still matched after tests. All 18 source hashes in the Mac `offline-07` result match the received Intel package.

## Reviewed implementation and boundaries

The complete Intel README, seven runtime modules, four tools, original test module, pinned requirements and three example configurations were read. The package imports do not open devices or listeners. An explicit `run` would create one Studio JPEG WebSocket subscriber, continuously drain into one replaceable pending frame, and submit at most one selected frame to an owned software `libx264` process. Viewer count does not create source connections. The private runtime-directory lock prevents another instance using that same directory; it is not a global lock across arbitrary alternative directories. The MediaMTX example separately disables publisher replacement on the fixed stream path.

The configuration requires a literal loopback Studio origin and explicit camera fingerprint/profile, refuses the placeholder Studio example, rejects synthetic input labeled live and accepts only the implemented software encoder. It constrains JPEG size, reconnect delay, receive timeout, receipt age and pipe-write budget. It does not itself prove that a configured Studio subscription reuses the intended existing capture owner; that remains an adoption prerequisite.

The status server exposes loopback GET liveness and a bearer-protected read-only status route. Token files must be owner-owned, private regular files without a final symlink. Status omits raw camera configuration, endpoint URLs, credentials and encoder stderr. `receivedAt` and `receiptAgeMs` represent bridge receipt; `captureTimestampAvailable` stays false. Header/dimension validation is not complete pixel validation. Encoded-frame progress is not browser delivery, and preview video creates no canonical frame, model-run, cycle, attempt or physical confirmation record.

The reviewed MediaMTX template is same-host preparation only: loopback RTSP/WHEP/media listeners, a placeholder viewer credential requiring private replacement, exact-path read permission, and unrelated listeners disabled. Remote HTTPS signaling and actual reachable WebRTC candidates require a separately selected topology. The shared records MCP connection does not supply this media path.

The Mac live-video contract, latest Intel requirements, verification README, final result, exact browser endpoints, pause/resume result, auth/replay results and source-hash evidence were read for coordination. Selected Mac implementation files were received and hash-verified; this review does not claim a complete independent semantic review or rerun of the Mac dashboard. The dashboard's `mediaGateway.test.ts` and `media.test.ts` are referenced by its evidence but intentionally absent from this 60-file manifest. Historical screenshots, several preliminary browser artifacts and the Intel README's broader `../source/junction/` references are also outside the selected payload. These are explicit package-scope limitations, not missing manifest files.

## Isolated tests and dependencies

The existing Station interpreter is CPython 3.12.16 at `morph-intel-transfer/morph-context/.junction-setup/python/bin/python`. Before verification it had neither Pillow nor websockets available. A final check still found neither package nor importable module there. Its environment was not modified.

The parent then authorized a new `test-env/` under this review, created from that existing CPython. Only the exact package-pinned runtime requirements, `Pillow==13.0.0` and `websockets==17.4`, were added. Binary wheels were downloaded with `--isolated --no-cache-dir --only-binary=:all: --no-deps`, inspected before installation, then installed with `--no-index --no-deps --no-compile` from this review's wheel directory. No source build or optional dependency was installed. Wheel METADATA/WHEEL identity, supported Python declaration, path safety and every file RECORD digest were checked. The websockets CLI entry point was inspected but not run. [Wheel evidence](wheel-review.json) and the [local installation report](dependency-install.json) retain versions and hashes.

| Downloaded wheel | SHA-256 |
| --- | --- |
| Pillow 13.0.0, CPython 3.12 Linux wheel | `42d63be3af4f9b951b199b0a9d23365d37ab14687e6d77b74940432c8515c4ca` |
| websockets 17.4, CPython 3.12 Linux wheel | `9ae1429ee9e52b139167ed0169757806a27ed7307e942e8c62037a9184e9843b` |

The first read-only wheel checker incorrectly counted empty ZIP directory entries as files requiring a RECORD digest and stopped before installation. The corrected reviewer validates those zero-byte directories separately and verifies every non-directory member. That inspection correction is recorded in `wheel-review.json`; no package source or original test was edited.

The exact test command was:

```text
/home/intel/Documents/Junction/reviews/passive-video-review-20261115T072206Z-d7e7aa66/test-env/bin/python -B /home/intel/Documents/Junction/reviews/passive-video-review-20261115T072206Z-d7e7aa66/run_isolated_tests.py
```

The wrapper discovers the unmodified `tests/test_bridge.py`, requires exactly 25 cases, and writes standard JUnit and text output. Its extra audit hook permits only literal IPv4 loopback connections, ephemeral port-zero fixture binds and the tests' exact inert Python sleep child commands. It does not substitute mocks for the original tests or relax their assertions. The original tests themselves replace the encoder command with those inert children.

**Result at 07:26:50.707671 UTC: 25 passed, zero failures, errors or skips; 0.830 seconds.** There were four temporary loopback fixture binds, ten loopback connections and two inert test-owned Python child starts. The original tests verified their reconnect/authentication/stall and child-cleanup behavior. Their temporary directory was empty afterward. Fourteen received Python files also passed syntax parsing without importing them. The source/fixture test SHA-256 remains `1a242920d07e845f07fa04f548e5706b8d0eb9a63560fe932799cac3efda6d42`.

| Intel test artifact | SHA-256 |
| --- | --- |
| [Result JSON](bridge-test-result.json) | `4b1387b00dea3bd3067f458a06d55dff13abefa61b23dd2e7d8025eac7249c2a` |
| [JUnit](bridge-tests.xml) | `e86d02db2588e737d75064a1473d6301d951d984dc0326ddd06fc8458aca8435` |
| [Exact test log](bridge-tests.log) | `c9e81c0729750de4bad92a03b540f3a4b7eb5835899978979737724e36a4778a` |

No actual FFmpeg/ffprobe command, bridge CLI run/preflight, MediaMTX instance or browser was used. The standalone offline/RTSP verifiers were read but not executed. Codec option tests and inert child cleanup do not establish working Intel encoding.

## Dated Mac evidence and remaining acceptance

The retained Mac results report 111 dashboard tests, 25 bridge tests and an actual software H.264/gap check. The final synthetic browser endpoints show 4,466 additional decoded frames over 148.846 seconds, with zero additional reported drops. The 120-sample disturbed RTSP run records a 400 ms source gap, alternating 25 ms scheduling jitter, one publisher and no publisher failures/restarts/write timeouts. Earlier failed jitter candidates and intermediate offline results remain intact. These are Mac synthetic/loopback measurements, not new Intel hardware or network results.

The next adoption step remains coordinated through Jose and the current owner:

1. Select a deliberate target runtime and review its required dependencies. This test venv is isolated review evidence; the active Station environment still lacks the two bridge packages. Actual Intel FFmpeg/libx264 and MediaMTX availability were not probed here.
2. Obtain the exact currently owned Studio camera configuration, actual endpoint, stable identity and accepted profile. Confirm existing capture reuse and single ownership before any connection. No arm or camera diagnostics were performed in this review.
3. Select protected WHEP HTTPS signaling, exact viewer permissions and reachable media candidates or an explicitly selected relay; separately configure protected producer-status access if needed. Do not infer media reachability from the records relay.
4. In a coordinated deployment, verify one source with multiple viewers, unauthorized-viewer rejection, changing decoded frames, source loss/restoration, stale/frozen indication and cleanup. Measure Intel CPU/resource cost under the intended workload.
5. Measure real camera-to-display delay with an optical timing method, sample count and p50/p95 over ten minutes. The p95 below 300 ms target remains unmeasured. Hardware encoding and depth require separate implementation/acceptance.
6. Continue the original physical work and dashboard producer gates separately: owner diagnostics, calibration, mentor/pilot decisions, demonstrations/skills/real detector, full physical cycle, existing Gemma responsibilities and M22 after the baseline. Video does not replace exact analyzed-image provenance or any canonical physical result.

The automatic Intel Codex receiver remains intentionally revoked/stopped and logged out since 06:18 UTC; this source review gives no restart authority. Existing applications and the GET-only Station worker were untouched. The owner retains arm diagnostics. Root `TODO.md` remains frozen at SHA-256 `fb1cee5b2aca12691bc67b3a610938b8e020d923c7f0ce19216a3578cdc546fc` (39,067 bytes).

The passive watcher was only read: at this review's last read its last successful poll was 07:20:21.057970 UTC, while its 07:24:03.877126 attempt reported `CycleTimeout`. This preserves the earlier successful recovery and the newer recurrence as distinct observations. Root owns the current watcher investigation and reporting.

Mac publication of this attributed review is pending the designated parent reporter's verified save/readback; receiving source is not outgoing delivery. No Notion update or task-acceptance change was made by this child. Root retains those responsibilities.
