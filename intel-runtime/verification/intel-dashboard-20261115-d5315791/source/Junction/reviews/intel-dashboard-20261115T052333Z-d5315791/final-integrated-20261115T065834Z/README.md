# Final integrated Station regression check

`/root/adoption_station` ran the current Station suite from 2026-11-15T06:58:47.806248+00:00 to 2026-11-15T06:59:04.427854+00:00 for request `d5315791-6749-4b01-97b5-1b9357306487`, session `d0dc73a7-df82-48e6-a8c1-8a4c23c144e6`. Root is the designated shared Mac reporter.

**309 tests passed, with zero failures, errors or skips.** The existing Station Python environment and the original absolute `MORPH_AUDIT_FIXTURE_ROOT` were used. Exact commands, working directory, fixture path, source-before/source-after hashes and return code are preserved in [result.json](result.json). Every source/fixture hash remained unchanged. Earlier failed and successful reports were preserved.

| Test module | Cases |
| --- | ---: |
| `tests.test_analysis` | 123 |
| `tests.test_api` | 16 |
| `tests.test_cli_shutdown` | 1 |
| `tests.test_dashboard` | 19 |
| `tests.test_export_audit` | 58 |
| `tests.test_producers` | 36 |
| `tests.test_reviews` | 24 |
| `tests.test_store` | 32 |

The CLI regression kept a real SSE response open in an isolated child process, sent SIGTERM to that owned process, and measured 10.14 seconds to exit with return code -15. The complete temporary canonical database remained unchanged. The test uses a private temporary database, synthetic simulation records, ephemeral token and explicit environment without real-station settings or provider credentials. Other tests retain their existing fake-provider and temporary-data setup. No real service, robot, camera, provider or tunnel was operated in this test run. One existing Starlette/httpx deprecation warning remains.

This verifies the combined software change. It does not establish production recovery, delivery through MCP, provider availability or physical acceptance. Root owns actual recovery; this test run does not send another signal to the old main process.

| Evidence | SHA-256 |
| --- | --- |
| [result.json](result.json) | `1ae3c68a805d06cde2d3e3ca5ffe3bd3a3664e83f2bcb4fba9ecb372ed655e1f` |
| [station-tests.xml](station-tests.xml) | `cd7097bbf47074ed475bfd53870846cacd6629be5dd48001e6c40aeda16bc0af` |
| [station-tests.log](station-tests.log) | `1d77e603fcf8ce7fa4ffe878ca3ce3f602954160c5843e52cf7e943d51ff7b34` |

Mac delivery of this attributed result remains pending root's verified save/readback. The previously frozen CLI source group is unchanged; report the final combined result without rewriting its prior test evidence or transfer payload.
