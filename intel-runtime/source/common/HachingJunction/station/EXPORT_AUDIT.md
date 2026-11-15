# Offline export integrity and evidence reports

Implemented on November 14, 2026 as the Mac-feasible portions of M21 and M23, and integrated into the current Intel project on the same date. The command checks a complete saved station export and produces a Markdown report plus structured JSON. It does not open a station database, call providers, retrieve media or operate hardware. No additional package is required beyond the station's existing Python dependencies.

## Run from the Intel project root

Run these commands from the `HachingJunction` project directory containing `station/`. Use Intel's existing station interpreter and the exact acceptance-export copies packaged under `station/tests/fixtures/export-audit/`. The original exports remain unchanged in the separate package review directory. Each command must use a new output directory. The example creates a fresh result parent outside both the active project and the extracted package:

```bash
MORPH_PYTHON=/home/intel/Documents/Junction/morph-intel-transfer/morph-context/.junction-setup/python/bin/python
MORPH_REVIEW_ROOT=/home/intel/Documents/Junction/reviews/mac-offline-evidence-20261114T222550Z-8941c757
export MORPH_AUDIT_FIXTURE_ROOT="$PWD/station/tests/fixtures/export-audit"
MORPH_M16_FIXTURES="$MORPH_AUDIT_FIXTURE_ROOT/context/verification/m16-closure-1cf186e8-ce90-4cbb-a953-6611e0bdcb98"
MORPH_AUDIT_OUTPUT_ROOT="$(mktemp -d "$MORPH_REVIEW_ROOT/manual-check-XXXXXX")"

PYTHONPATH=station "$MORPH_PYTHON" -m morph_station.export_audit audit \
  "$MORPH_M16_FIXTURES/recovered-session-export.json" \
  --output-dir "$MORPH_AUDIT_OUTPUT_ROOT/m16-audit"

PYTHONPATH=station "$MORPH_PYTHON" -m morph_station.export_audit audit \
  "$MORPH_AUDIT_FIXTURE_ROOT/station/verification/sample-export.json" \
  --output-dir "$MORPH_AUDIT_OUTPUT_ROOT/sample-audit"

PYTHONPATH=station "$MORPH_PYTHON" -m morph_station.export_audit replay \
  "$MORPH_M16_FIXTURES/recovered-session-export.json" \
  "$MORPH_M16_FIXTURES/browser-replay-export.json" \
  --output-dir "$MORPH_AUDIT_OUTPUT_ROOT/m16-paired-exports"

PYTHONPATH=station "$MORPH_PYTHON" -m pytest station/tests/test_export_audit.py -q
```

Each command creates `report.json` and `report.md`. Exit code `0` means the metadata checks passed; `1` means integrity failed; `2` means input or output could not be processed. Existing output directories are refused. Input hashes are checked before and after the audit. JSON provenance includes the check time, resolved source paths, input hashes and hashes of the audit, model and store modules. Treat absolute paths as local provenance when preparing a public copy.

The Python interface exposes `load_export(path)`, `audit_export(document)`, `compare_replay(left, right)` and `render_markdown(report)`. Prefer `load_export` for file input: it rejects duplicate JSON keys, invalid UTF-8, nonfinite numbers, excessive integers and files larger than 32 MiB. All schema timestamps require explicit timezones. Numeric and boolean fields are validated strictly without silently converting strings or booleans into numeric values.

## What is checked

- Schema version 1 and all seven export sections, with complete typed record groups. Unknown top-level fields, record fields and envelope fields fail validation.
- Unique typed record identities, event IDs, global event sequences and typed revision identities. Global event sequences may have gaps because other sessions share the ledger; each entity must still have every revision from one through its current revision.
- Agreement between current records, the final revision, every event payload and its matching revision. Event and revision order must agree.
- Current references and outcome preconditions through the existing station validator: session/object/frame associations, valid attempt chains, independent reference labels and confirmations for successful results. Additional-inspection links must not loop.
- Historical typed references must exist in the supplied complete record population and agree on session, cycle and object where applicable. This does not establish when the referenced record first existed or reconstruct its value at that past instant.
- Ordinary update transitions preserve immutable fields. Corrected transitions require exact old/new values and attributed audit records for every changed field. Multiple audit fields may share one Intel target transition; optional `reviewId` is retained.
- Canonical metrics recomputed through the existing station calculator using in-memory reads. Any mismatch with the saved metrics fails the report and withholds derived results.
- Paired export equivalence after each export passes its own checks. Only the top-level `exportedAt` field is ignored. All persisted record, event, revision, configuration and metric changes make the pair unequal.

The offline evidence policy requires an attributed correction for changes after **any finished cycle or attempt**, including a result recorded as `unverified`. The older ingestion API also permits ordinary updates from `unverified`; this utility flags such history for explicit audit reconciliation. This is a deliberate evidence check, not a change to ingestion or accepted M16. Preserve the original export when reconciling it; do not rewrite history to force a passing result.

## Report meaning

Reports retain the denominators for correct cycles and successful attempts, show failed/aborted/unverified/in-progress categories, and separate first-attempt successes, recovered cycles, retries and additional inspections. Detection correctness uses independently labeled examples and shows the checked count and total cycle population. Empty eligible populations show `No data yet`.

Simulation is visibly labeled and excluded from the report's default live aggregate. The report exposes saved cycle-to-reference/inspection/confirmation links and model/provider/device/precision metadata. A recorded latency is not a newly measured benchmark. Full-cycle durations use the canonical persisted start/end boundary; missing telemetry is not replaced with zero. Raw prompts, model outputs, utterances, audit reasons and author prose are omitted from the generated report.

`physicalVerification` is always `not_performed`, and `evidenceFilesVerified` is always `false`. A passing result establishes consistency of the supplied metadata. It does not establish that the robot moved, that supplied records are authentic, that media hashes match actual files, that reference labels are physically correct, or that a provider response is useful. A coherently fabricated or altered history cannot be detected without an independent trusted source. Historical payload schemas, reference identities and update/audit consistency are checked; the entire past database is not reconstructed at every event.

The `replay` command compares two saved snapshots. It does not run browser replay, prove that a browser created those snapshots, or measure a live counter before and after replay. Cross-session performance comparisons, statistical significance and Intel/OpenVINO speed or quality conclusions remain outside this utility.

## Integration and ownership

The additive implementation is [export_audit.py](morph_station/export_audit.py), with independent checks in [test_export_audit.py](tests/test_export_audit.py). It reuses [models.py](morph_station/models.py) and the pure validation/metric methods in [store.py](morph_station/store.py), without invoking the database constructor.

The original November 14 integration added only this utility, its tests and this guide to Intel active source. On November 15 UTC, three byte-identical, manifest-verified acceptance exports were additionally packaged as test fixtures so the default test run is self-contained. Their [fixture provenance](tests/fixtures/export-audit/README.md) records hashes and original paths. The sealed package inputs and earlier verification reports remain unchanged. Do not copy the Mac store, dashboard, dispatcher, providers, voice modules or older Gemma implementation over newer Intel source. If Intel adds export fields, reconcile the validator against that newer contract; an unsupported export must not trigger a source downgrade.

The November 14 Intel compatibility review confirmed that `MODELS`, `CorrectionRequest`, `MUTABLE`, `CORRECTABLE`, `StoreError`, `without_revision`, `_get`, `_list`, `_ref`, `_validate` and `_correct_cycle` retain the reviewed contracts. Intel's additional review request models do not add export record types. Its `_metrics` method adds an optional `cycle_ids=None` filter; this audit uses the unchanged default full-session calculation. The in-memory adapter still avoids the database constructor. The audit module and its 58 tests were accepted unchanged from the package after all 58 passed against Intel's existing environment. All three CLI checks above also passed with preserved fixture hashes; neither source downgrades nor relaxed checks were needed.

The tests still accept an explicit `MORPH_AUDIT_FIXTURE_ROOT` override. Its folder must contain `station/verification/sample-export.json` and both `recovered-session-export.json` and `browser-replay-export.json` under `context/verification/m16-closure-1cf186e8-ce90-4cbb-a953-6611e0bdcb98/`. Without the variable, the tests use their packaged `fixtures/export-audit` directory relative to the test file, independently of the working directory or an external Mac checkout. No existing Intel evidence is overwritten. The previous workspace-relative default failed when the Mac M16 directory was absent; the earlier passing integration had explicitly supplied the external fixture override. Only fixture selection changed in the test source; all 58 audit tests and their assertions and the audit implementation remain unchanged. Run tests with Intel's existing station interpreter and installed dependencies; Mac runtime folders are not transferable.

The original dated verification, demo preparation and remaining acceptance work remain in the [preserved Mac evidence handoff](../../../../reviews/mac-offline-evidence-20261114T222550Z-8941c757/extracted/Morph-Mac-Offline-Evidence-20261114-01a1dbfa/payload/context/verification/mac-offline-evidence-20261114/HANDOFF.md). Intel results and report hashes are recorded in the [audit integration report](../../../../reviews/mac-offline-evidence-20261114T222550Z-8941c757/audit-merge/RESULT.md). M21/M23/M24 retain their existing acceptance requirements; these offline checks do not complete physical or demonstration acceptance.
