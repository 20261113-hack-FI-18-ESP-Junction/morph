# Working-system integration verification

Recorded November 15, 2026, Europe/Ljubljana (UTC+01:00). [result.json](result.json) separates software checks, actual Intel record reads, native browser observations, a synthetic media demonstration and remaining target acceptance. [Current source hashes](current-source-hashes.json) describe the final implementation before this evidence commit; older manifests remain unchanged.

## Checks and evidence

| Scope | Result | Evidence |
| --- | --- | --- |
| Dashboard, media, proxy, history and analyst state | 116 tests passed | [Test log](dashboard-tests.txt) |
| Backend compact API, relay, worker and shared client | 19 + 18 + 24 + 53 tests passed | [Dependency result and tested source](dependency-closure-20261115T073444Z-result.json) |
| Local launcher and checker | 17 distinct tests passed: seven launcher/lifecycle and ten final readiness tests | [16-test run](launcher-tests-final.txt), [final ten checker tests](readiness-tests-final.txt) |
| Build and TypeScript | Passed; the existing Vite compatibility warning remains | [Build](final-build.txt), [TypeScript](final-typecheck.txt) |
| Actual Intel after browser history/replay | One simulation session, five cycles, event cursor 50, compact v1 API | [Final GET-only check](station-check-after-replay.json) |
| Exact history JSON | Export retained the UI snapshot's generation timestamp and record identities | [Download audit](browser-json-export.json) |
| Complete disposable demo | Actual HTTP schema/detail/image/history/replay, 13 reads and two explicit exports | [Demo regression](unified-demo-check.txt) |
| Changing synthetic browser video | 640×480 configured, 30 decoded FPS, H.264 | [Screenshot](synthetic-video.jpg), [launch report](unified-demo-launch-and-stop.json) |
| Shutdown with open event stream | The HTTP 200 stream closed; all seven owned processes stopped; private temporary runtime removed | [Supervisor result](unified-demo-launch-and-stop.json) |
| Malformed private media configuration | Fixed diagnostic, no secret-sentinel disclosure, no service started | [Configuration check](malformed-config-check.json) |
| Source publication review | Exact paths, baseline/final hashes and reviewed dependency closure | [Groups 1–3](publication-ready-groups-1-3-20261115T0751Z.json), [groups 4–7](publication-ready-groups-4-7-20261115T080429Z.json) |

The 16-test launcher run preceded one final missing-selection-field guard. All ten checker tests then passed with that guard; the unchanged seven launcher/lifecycle tests remain valid. The earlier intermediate failure log is preserved as diagnostic history and is superseded by these results. The earlier `station-tools-20261115` hashes precede the TCP restart and missing-field fixes; the current hashes above record those intentional changes.

The production build was repeated after the final header wording change and passed (1,689 transformed modules; `index-CCvcuG6W.js`). The saved earlier final-build log has the immediately preceding wording-only revision; neither result verifies hardware.

## Actual Intel and application boundaries

The [history screenshot](intel-history.jpg) shows actual records received through the existing Mac MCP from Intel. Those records are labeled simulation. The browser showed the original failed grasp and successful second attempt, then browsed original replay sequences 1 and 2 of 50 without changing the session totals. The final GET preserved cursor 50. The selected saved image is a synthetic 1×1 PNG, not a camera capture.

One explicit Gemma analysis submission used application ID `a3ba92b8-1a25-4a14-8e0e-809c7a7af382`; its relay request expired without a worker claim. The browser retains that same request across reload and shows its ID. It was not retried and no provider invocation or completed report is inferred. The active Intel owner received the exact lookup and constrained worker-adoption handoff; authoritative lookup remains pending.

Intel's separately read-back prerequisite note reports 25 original bridge tests passing in a reviewed environment. It also identifies Studio capture ownership and potentially settings-changing preview subscription, absent verified MediaMTX/media routing, and untested actual encoding. These are target reports, not Mac physical verification. See [the operating guide](../../../WORKING_SYSTEM.md) for the concrete remaining non-Jose work.

No actual camera subscription, robot movement, physical baseline/recovery, useful product explanation or optical camera-to-display latency was established. Private pairing, credentials, databases and raw captures are not included. Whitespace warnings are limited to unchanged third-party font licenses and two verbatim lines in the preserved historical replay accessibility log.
