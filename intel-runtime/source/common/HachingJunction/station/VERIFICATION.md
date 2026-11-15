# M06 verification and handoff

Verified November 14, 2026, on the local Apple Silicon Mac. Evidence class: **software, deterministic simulation and local HTTP**. No physical robot, camera or provider request was exercised.

## Delivered

The application in `station/` implements the M06 persistence foundation with FastAPI/Pydantic and SQLite. Typed records cover sessions, cycles, attempts, frames, inspections, model requests/results, utterances, decisions, executions, independent reference labels and outcome confirmations. Immutable evidence files, revision history and attributed corrections preserve traceability.

The API provides authenticated snapshots, record ingestion, ordered event catch-up, filtered cycle history, metrics, labels, corrections, evidence downloads and JSON/CSV exports. `GET /api/v1/schema` exposes the record and response schemas for the existing dashboard. Hardware commands, camera streaming, voice goal submission and provider token issuance remain explicitly unavailable.

Application source was added outside dependency caches. The workspace root is not a Git repository. The existing dashboard reference was not rewritten; the owner's newer dashboard source has not been inspected in this workspace.

## Verification performed

- **48 pytest cases passed.** Domain and API coverage includes restart persistence, concurrent duplicate requests, semantic duplicates, conflicting event IDs, stale revisions, retries, extra inspections, late confirmations, unknown/aborted outcomes, independent labels, cross-cycle evidence, audited corrections and read-only replay/export.
- **Two real HTTP server starts passed.** A fresh server after shutdown returned the same 50 saved events, session and metrics.
- Running the deterministic seed twice with the same prefix created no additional events.
- Unauthenticated data access returned 401. Unintegrated hardware commands returned 503 without recording an execution.
- API schemas, bounded event catch-up, full exports and the token-file CLI client were exercised over local HTTP.
- Missing live records returned a zero denominator and a null percentage; simulated results did not enter default live reliability metrics.
- The server processes used by the smoke check were stopped after verification.

Reproduce from the workspace root:

```bash
.junction-setup/python/bin/python -m pytest station/tests -q
.junction-setup/python/bin/python station/tests/smoke_http.py
```

The tests exposed two persistence defects during implementation: SQLite WAL setup inside an active transaction, and a correction event colliding with an ID reserved by a duplicate-request receipt. Both were fixed and covered by passing regression cases. API validation was also aligned with the shared identifier schema so invalid IDs return 422 rather than an internal error.

## Deliberately simulated example

The fixture contains five cycles: correct first attempt, correct after one failed grasp, wrong-bin failure, unverified outcome and a cycle still in progress.

| Measure | Saved fixture result |
| --- | --- |
| Correct cycles / finished cycles | 2 / 4 |
| Successful physical-attempt records / finished attempt records | 3 / 5 |
| First-attempt successes | 1 |
| Recovered cycles | 1 |
| Retries | 1 |
| Additional inspections | 1 |
| Live reliability records | None |

The one-pixel image, policy/model IDs, timings and operator confirmations are explicitly simulation fixtures. They are not useful detection data or physical measurements.

## Evidence files

- [Pytest result](verification/pytest-results.xml)
- [HTTP/restart report](verification/smoke-report.json)
- [Sample snapshot](verification/sample-snapshot.json)
- [Sample ordered events](verification/sample-events.json)
- [Recovered cycle trace](verification/sample-cycle-retry.json)
- [Complete JSON export](verification/sample-export.json)
- [CSV export](verification/sample-export.csv)
- [API and record schemas](verification/api-schema.json)
- [Provider configuration preflight](verification/provider-preflight.json)

## Integration boundaries and next work

Use [README.md](README.md) for startup, token-file handling, CORS and the record contract. Runtime data is in ignored `station/.data/`; the private API token is not source or an artifact. Export metadata and evidence separately when transferring a saved session. Transfer source and install the application requirements on Intel; do not copy the Mac virtual environment.

M06 is complete for its stated software acceptance. The existing dashboard still needs to adopt this API or have its current data adapter reconciled with it. M15's M06 prerequisite is now satisfied; the owner's reported UI progress still needs inspection before final UI acceptance. M12 still depends on the mentor decisions in M01. Physical dispatch and M20 live integration remain separate tasks.

Provider preflight found no configured NVIDIA/NIM, Gemini/Google or ElevenLabs API keys in this process, and no project-root or station `.env` file. This is a blocker for live API checks from this Mac, not a finding about account eligibility or configuration on the Intel station. No model request or microphone capture was attempted. Configure the appropriate server-side credentials on the chosen execution host before resuming M03–M05.
