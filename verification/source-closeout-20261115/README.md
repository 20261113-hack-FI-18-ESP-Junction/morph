# Source reconciliation checkpoint — November 15, 2026

This folder records the Mac source reconciliation after the owner requested a final shared-server review, small GitHub commits and shutdown of the Mac project servers. Source publication, target adoption and physical acceptance are separate checkpoints.

The [complete delivery reconciliation](source-disposition.json) accounts for all 13 complete groups: 151 received files totaling 2,460,082 bytes. Every group maps to verified published commits and its original receipt. Seven newly reconciled mutable ledgers were updated; all six previously published ledgers and immutable intake records were preserved. The incomplete source and separate station-guide mapping exception remain explicit.

## Dashboard verification

The saved-correction UI preserves typed before/after values, the author, an explicitly zoned timestamp and the exact captured source revision. Inconsistent or incomplete records remain in the generic evidence ledger. Application-owned v12 wording is identified only under its exact reviewed contract. Existing media, record transport, history and request handling are preserved.

The [UI reconciliation](../../klemen-dashboard/verification/analyst-ui-r2-20261115/RECONCILIATION.json) records 39 analyst tests within the full 122-test dashboard suite, all passing, plus successful TypeScript checking. The [production build result](dashboard-production-build.json) and [original log](dashboard-production-build.txt) record a successful build of those same frozen source hashes. The original workspace paths in that result describe the verification environment. These checks used software fixtures and establish no new provider or physical result.

The [published Intel package integrity check](package-integrity.json) passed for all 338 sealed files and 299 source-provenance entries in a clean Git export. Running the same strict checker in the development workspace also reported 14 ignored local media test logs as unlisted extras. Those logs were preserved; they are absent from Git, and no source hash, verifier or ignore rule was changed to hide the distinction.

## Missing exact source

The [original request](../../INTEL_SOURCE_REQUEST.md), ID `cb294a07-e4bb-4381-89a5-9a29d9ddec36`, lists six current originals and three historical originals. Intel manually reviewed them and published [response `aee44be4-a19f-41ee-9676-f4b8a5db9f3b`](intel-response-20261115T092949Z.json) at `2026-11-15T09:29:49.574851+00:00` (10:29:49 Europe/Ljubljana). Its [authenticated readback](intel-response-20261115T092949Z-readback.json) confirms the full saved note, without redaction; that verifies receipt of the report, not its undelivered source files.

Intel reports all nine originals present with the exact requested bytes and hashes. Its unchanged sender rejects the files because the credential screening also matches synthetic authorization tests and English permission metadata. Intel classified these occurrences as false positives after static review; Mac has not received the exact files and cannot independently inspect them. No replacement, redacted copy or metadata note closes an original-source gap. The source transport and its screening were not changed.

After the owner's later message that the files had probably been sent, a [fresh full-server check](latest-source-check-20261115T093702Z.json) completed at 09:37:02 UTC (10:37:02 Europe/Ljubljana). It inspected the authenticated 3,303-file catalog across 17 pages, found no new source manifest after the 09:29:49 response and found none of the nine requested original file hashes. The existing inventory still contained 29 manifests and 13 complete groups. This is the last verified delivery state at this checkpoint.

The old 52,823-byte analyst test was found in the preserved `verification/intel-reliability-20261114/audit-language-v12-20261115/before/tests/test_analysis.py` snapshot beneath Intel's continuation bundle, rather than at the current test path. Its requested hash is unchanged. This corrects the location in the original request without rewriting that historical request.

The following delivery groups remain incomplete:

| Delivery | Remaining exact originals |
| --- | --- |
| `3764e3c7-2536-53c5-b75d-5a2dc1d560c5` | Current analyst test |
| `831bcaf3-d30f-45cf-a30e-03b8d810d32b` | Producer ingestion test |
| `97c7ec3e-dd59-47e6-a450-014bad41151a` | Four closing review source/report files |

The three historical originals remain separate archive gaps. The optional 1,111-byte watcher JSONL exists on Intel but remains unsupported; it is not an application dependency. After reviewing this blocker, the owner explicitly authorized shutdown with the recorded gaps and requested a manual ZIP for attachment in this chat. That human-mediated transfer will preserve original bytes, hashes and all earlier receipts. It does not change the shared sender or turn this metadata response into a complete source delivery. No automatic continuation was requested by Intel's final response.

## Operating state

The [operating guide](../../WORKING_SYSTEM.md) records the current application boundary and the M08 owner STOP. Physical experiments and replay remain held after the reported collision. Offline tests, source receipt and a successful build do not establish physical clearance. The automatic Intel receiver remains revoked and the Mac review automation remains paused.

At 09:48:35 UTC, the [dashboard shutdown check](dashboard-shutdown.json) confirmed that all 11 recorded dashboard/demo processes had exited, ports 3000 and 3101 were closed and the known disposable demo runtime was removed. The demo supervisor returned an inspection error; the independent process and listener check confirmed cleanup without an additional signal. Shared MCP remained running at that check for the final handoff. Its later shutdown is a separate verification step.
