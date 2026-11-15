# Publication review: dashboard, records and video

Reviewed 2026-11-15T07:48:19.525458+00:00 against `main` at `cb753e9c60ad570b500ce933d10b989f6546c54a`. This is a read-only inventory of the existing accepted working tree. It applies the workspace/repository source-publication instructions; it neither applies incoming Intel deliveries nor authorizes deployment, providers or motion.

## Suggested meaningful commits

| Group | Exact candidate files | Pending freeze | Suggested subject |
| --- | ---: | ---: | --- |
| 01-records-contract | 23 | 0 | Add coherent bounded dashboard reads across the API, relay and client |
| 02-shared-chat-style | 15 | 0 | Add portable Morph chat styles and licensed assets |
| 03-media-bridge | 30 | 0 | Add a bounded Studio JPEG to H.264 media bridge |
| 04-dashboard-workflow | 87 | 16 | Integrate record views, independent video and explicit local launchers |

The accompanying [publication-review-20261115T074819Z.json](publication-review-20261115T074819Z.json) contains exact repository-relative paths, Git status, baseline SHA-256, candidate SHA-256, modes and pending reasons. The two review files are additional evidence paths for group 04; their own final hashes should be recorded outside this self-referencing inventory.

Group 01 includes both dashboard proxy allowlist files and the compact API/relay/shared-client tests, so the read contract is complete. Group 03 is the reusable video producer. Group 04 depends on groups 01 and 03. Group 02 supplies an independently portable CSS/assets/fonts package. No new dependency declaration/lockfile mismatch was found; installed runtimes and generated output stay outside Git.

## Pending freeze

The following paths have `sha256: null` plus an **observed-only** hash in JSON. They must be frozen and re-read before staging:

- `README.md`
- `WORKING_SYSTEM.md`
- `klemen-dashboard/README.md`
- `klemen-dashboard/VERIFICATION.md`
- `klemen-dashboard/dashboard/src/App.tsx`
- `klemen-dashboard/tools/check_station.py`
- `klemen-dashboard/tools/run_station.py`
- `klemen-dashboard/tools/tests/test_station_tools.py`
- `klemen-dashboard/verification/workflow-integration-20261115/browser-json-export.json`
- `klemen-dashboard/verification/workflow-integration-20261115/build.txt`
- `klemen-dashboard/verification/workflow-integration-20261115/dashboard-tests.txt`
- `klemen-dashboard/verification/workflow-integration-20261115/demo-check.txt`
- `klemen-dashboard/verification/workflow-integration-20261115/final-build.txt`
- `klemen-dashboard/verification/workflow-integration-20261115/final-typecheck.txt`
- `klemen-dashboard/verification/workflow-integration-20261115/station-check-simulation.txt`
- `klemen-dashboard/verification/workflow-integration-20261115/typecheck.txt`

New evidence or launcher files appearing after this inventory require an explicit additional review. Current HEAD already contains the heartbeat/source-delivery metadata; unrelated concurrent policy, delivery or reconciliation edits must remain outside these groups. Do not stage whole directories or use `git add .`.

## Checks and limits

- Dependency-closure suites passed: 19 backend dashboard, 18 relay, 24 worker and 53 shared-client tests (114 total). Current hashes still match their tested source: true.
- No private/runtime artifacts or real credential literals were found among 155 candidate paths. Four pattern matches are explicit synthetic test credentials. Shared UI file and source-reference hashes match; font licenses are included.
- The historical upgrade verifier checked 39 files and returned 15 expected later-source differences. Keep that snapshot intact and label the command historical; it is not the final-system verification.
- Earlier shutdown/SSE and malformed private-media diagnostic findings are fixed in source. Root owns final launcher, browser and build evidence after the remaining freeze.
- Tests use temporary SQLite and in-process/fake transports. No external network, provider, camera or robot calls occurred in this review. Local software checks and publication are separate from Intel deployment and physical acceptance.

Root must recheck HEAD/status and exact hashes, review final staged content, create the four commits, and verify remote publication separately. No source files, fixtures, services or Git state were changed by this review.

Groups 01–03 were rehashed without drift at 2026-11-15T07:50:27.155511+00:00; the exact ready-to-stage file arrays and hashes are also in [publication-ready-groups-1-3-20261115T0751Z.json](publication-ready-groups-1-3-20261115T0751Z.json). Current HEAD remains `cb753e9c60ad570b500ce933d10b989f6546c54a`.
