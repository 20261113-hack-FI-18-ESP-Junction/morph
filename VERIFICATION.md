# Jose package verification

Verified on November 15, 2026, approximately 03:06 CET (Europe/Ljubljana, UTC+01:00), using the prepared Mac Python 3.12 environment and Node runtime. These checks ran against the copied package, not the original station folder. They use temporary databases and fake provider/media transports. No provider request, microphone capture, Intel connection or robot action occurred.

| Check | Result | Evidence |
| --- | --- | --- |
| Copied Python control/provider/voice/dispatcher suite | **124 passed**, 2.31 seconds | [JUnit result](verification/python-tests.xml) |
| Actual voice JavaScript with fake media, sockets and timers | **7 of 7 groups passed** | [Browser harness result](station/verification/voice-browser-tests.json) |
| Package/API smoke and source integrity | **11 of 11 checks passed** | [Smoke result](verification/smoke.json) |
| Portable shell launcher | `bash -n run.sh` and `MORPH_PYTHON=… bash run.sh --help` exited 0 | Command record below |
| Schema generation from the copied app | Created without credentials or sessions | [OpenAPI](verification/openapi.json), [record schema](verification/record-schema.json) |

The smoke verifies the lab page, authenticated/unauthorized API behavior, unavailable unconfigured providers, empty initial sessions/executions/events, exact copied source hashes and absence of the original machine's credential loader. It does not load any existing runtime database.

The first Python invocation omitted the exported `PYTHONPATH=station`. Its subprocess-based journal test could not import the relocated package; the other 123 cases passed. That initial result is retained in [the initial JUnit report](verification/python-tests-initial-missing-pythonpath.xml). The documented command now exports the module path for both pytest and its child process. The unchanged test/source copy then passed all 124 cases. No runtime logic was changed to make the tests pass.

Reproduce from the package root after installing the pinned requirements in `.venv`:

```bash
PYTHONPATH=station .venv/bin/python -m pytest station/tests -q
node station/tests/test_voice_browser.cjs
bash -n run.sh
MORPH_PYTHON=/absolute/path/to/python bash run.sh --help
```

The Python tests check duplicate requests, state/goal versions, stale evidence, provider-response validation, restart ownership, interrupted execution, uncertain physical outcomes, full-utterance finalization, late transcript enrichment and explicit control separation. Browser tests check capture cleanup, release/commit finalization, timeout isolation and stale socket/media handlers. These are software/simulation checks. Hosted model behavior, a production chat flow, cross-host mission transport and physical acceptance remain separate work.

The original Mac `station/` source and sibling React dashboard were not edited by this package work. Source provenance is recorded in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json). Its creation-time note about pending Intel reconciliation is historical; the focused current Intel delivery below has since arrived. All 26 original Mac copied source hashes remain unchanged.

## Received Intel source verification

All 21 transfer chunks reconstructed **17 current Intel files / 230,799 source bytes**. The 246,146-byte bundle SHA-256 is `f79c9426e361721aa63aa61038a93cbe1799d63e4a93501858a68112ea553e1b`. Transfer and per-file hashes passed; the unchanged source is included under `intel-contract/source/`, separate from the lab. The [receipt](intel-contract/report.json) records collection at **03:33:51.290670 CET**.

The subsequent [independent audit](intel-contract/verification/REVIEW.md), checked **03:35:47.871883 CET**, verified all 22 relative imports and passed **56 store/review tests** with provider credentials removed and outbound socket/provider guards. Both attempt counts remained zero. It confirmed three command/voice HTTP 503 stubs, null goal state, empty action list and zero sessions/events in temporary data. Generated [OpenAPI](intel-contract/verification/current-source-openapi.json) and [record schema](intel-contract/verification/current-source-record-schema.json) describe these received source bytes on Mac; they are not live Intel service captures.

Intel's delivery note `1717cf39-0221-4966-aafe-e5b2b963ceaf` separately reports 72 tests on its target, including 16 API tests that were not transferred. The locally verified count for the incoming source remains 56. The excluded API fixture and pytest configuration do not break the received runtime import closure. Live target deployment, mission dispatch and physical acceptance remain unverified by these software checks.

## Git repository import verification

Verified at **2026-11-15T03:52:18.535344+01:00** (Europe/Ljubljana) in a fresh local checkout of the Morph repository. All 26 Mac source entries and 17 Intel source entries still match their original manifests. The application code is unchanged from the imported handoff.

The relocated Mac suite passed **124 tests**, the separate Intel reference suite passed **56 tests**, and the offline browser harness passed **seven groups**. Launcher syntax and `--help` passed without creating runtime data. Provider credentials were removed for the Python processes. This was a software check with temporary data, not a live provider, Intel service, tunnel or physical test.

Results: [import report](verification/github-import.json), [Mac JUnit](verification/mac-import-tests.xml), [Intel JUnit](verification/intel-import-tests.xml) and [voice harness](verification/voice-import-tests.json). Original evidence remains unchanged. The import report distinguishes these checks from the earlier guarded Intel audit.

## Remaining partition publication

The original Jose and focused Intel checks above retain their scope and dates. The later [three-host handoff](REMAINING_SOURCE_HANDOFF.md) adds separately verified dashboard, Intel runtime and communication packages. Their own reports and manifests identify the exact new source and tests; no new physical or live deployment result is implied.
