# Intel source closeout request

Prepared November 15, 2026, Europe/Ljubljana (UTC+01:00).

Request ID: `cb294a07-e4bb-4381-89a5-9a29d9ddec36`. Mac publication baseline: `2f7efc2a3badecefab278c76a515738ffc2a09e0`.

The owner asked Mac to reconcile all source currently available on the shared MCP, request missing full files, publish reviewed changes in small commits, then stop the Mac project servers for now. Please take up this request manually in the existing Intel environment. The automatic Intel receiver remains revoked; saving this note does not start Codex.

## Required full current originals

These six exact originals are missing from otherwise validated source transports. The related groups remain incomplete. Please verify the current Intel files against the recorded bytes and hashes before preparing a complete source correction. If a newer revision is now required, preserve the listed snapshot, report the new hash/revision and explain which delivery it supersedes.

### 1. current analyst-backend original

- Full source path: `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/station/tests/test_analysis.py`
- Bytes: `59218`
- SHA-256: `3bb5a23a91f8a89a00f220c126f18396fd100278b380adab6cd490ddd333d671`
- Incomplete delivery: `3764e3c7-2536-53c5-b75d-5a2dc1d560c5`

### 2. closing-intel-review-source-and-dated-document-supplement

- Full source path: `/home/intel/Documents/Junction/reviews/intel-dashboard-20261115T052333Z-d5315791/closing-shared-review-20261115T075045Z/closing-review-result.json`
- Bytes: `32123`
- SHA-256: `7f5a32176ba0870dd06650438134c8503326f041d46df69fcec5e4257f32bbcb`
- Incomplete delivery: `97c7ec3e-dd59-47e6-a450-014bad41151a`

### 3. closing-intel-review-source-and-dated-document-supplement

- Full source path: `/home/intel/Documents/Junction/reviews/intel-dashboard-20261115T052333Z-d5315791/closing-shared-review-20261115T075045Z/verify_closing_review.py`
- Bytes: `12694`
- SHA-256: `4ca8ee9b247dae16042bf198a3e96383c4d1b244f9f8a1dccc3416f661ff0730`
- Incomplete delivery: `97c7ec3e-dd59-47e6-a450-014bad41151a`

### 4. closing-intel-review-source-and-dated-document-supplement

- Full source path: `/home/intel/Documents/Junction/reviews/station-write-optin-review-20261115T075433Z-2e12edef/inspect_worker_request_v1.py`
- Bytes: `14992`
- SHA-256: `53102fe6cd4e287c12173bf262fd6e6935704567e839415e8e3db981ca444ab3`
- Incomplete delivery: `97c7ec3e-dd59-47e6-a450-014bad41151a`

### 5. closing-intel-review-source-and-dated-document-supplement

- Full source path: `/home/intel/Documents/Junction/reviews/station-write-optin-review-20261115T075433Z-2e12edef/inspection-20261115T080519285661Z.json`
- Bytes: `4089`
- SHA-256: `1d35f9a42291ff5a553e311a38ca66f06bafbaac90720042915773aab003c9ab`
- Incomplete delivery: `97c7ec3e-dd59-47e6-a450-014bad41151a`

### 6. producer-ingestion

- Full source path: `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/station/tests/test_producers.py`
- Bytes: `19772`
- SHA-256: `60d804e02c367a4bd151c2e4c62383328f9f9efcad079595c774b34ac58b81e9`
- Incomplete delivery: `831bcaf3-d30f-45cf-a30e-03b8d810d32b`

## Historical originals for archive completeness

These three older originals remain separate provenance gaps. The old analyst test is a different revision from the current analyst test above. Return the exact frozen old bytes if still available; otherwise explicitly report them unavailable. Do not replace an old hash with current bytes or invent a reconstruction.

- `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/morph-station/server/stationProxy.test.ts` — 17218 bytes; SHA-256 `552e8def4cf1f08330a2702d67e1152dd91105a6b3f578f4cbc7da2908ec7d49`.
- `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/setup/provider-check/test_check.py` — 11561 bytes; SHA-256 `ef2e01a85bec0f9d4950aabe475a0e6cc4c0dae6746a8b5d8e73cfb6a1c741c5`.
- `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/station/tests/test_analysis.py` — 52823 bytes; SHA-256 `e35d81c31bff372cc65fa10ab1c900e5174698cd67e025be73d7fa14af39e699`.

## Optional unsupported historical artifact

`/home/intel/Documents/Junction/reviews/intel-watcher-recurrence-20261115T073034Z-d5315791/watcher-log-window.jsonl` — 1111 bytes; SHA-256 `3486902d2bfc038fbda5e1e113d10f3cdeee8effd43cf95af4448e254092e4db`. This JSONL log is optional and is not a required application dependency. Preserve its unsupported status unless a separately reviewed transfer is available.

## Transfer and review requirements

1. Inspect each rejected original locally and report the exact screening reason without exposing credentials. Do not weaken screening, encode or rename content to evade it, or call a redacted copy an exact original. If a file contains real private values, retain it privately and describe the nonsecret source change and the reviewable alternative explicitly.
2. For safe exact source, use the established source-delivery workflow and an approved supported transport. If unchanged screening still rejects the original, request a separately reviewed transfer of the original file; report that concrete blocker instead of repeating the same failing sender command. No such alternative is already approved by this note.
3. Use new immutable correction transfer/delivery IDs and reference the incomplete delivery IDs above. Include full final source, tests, local dependencies and operator documentation, plus exact per-file baseline/final hashes. Existing verified dependencies may be reused only with matching current hashes and explicit references.
4. Include the SOURCE_DELIVERY.json companion with exact mappings, completeness, exclusions, source observation time, and any new revision. Preserve earlier receipts and failures. Publish a complete group only after all required files and all shared readbacks verify. If anything is still missing, send one concise ordinary blocker note with its exact status.
5. No robot, camera, model/provider request, worker flag change, process restart, or replay is requested. Preserve the M08 owner STOP and unconditional pre-I/O replay hold. Do not execute historical recovery/review scripts merely to deliver their source.
6. Mac will compare and review received bytes before publication. Source receipt, Git publication, active service adoption and physical verification remain separate checkpoints.

## Response needed before Mac shutdown

Please first state whether you are actively taking up this request and whether the six current originals can be delivered now. Report any unavailable historical revision separately. The final Intel source-lane closeout at 09:07:38 UTC said that lane had ended, so Mac cannot assume automatic pickup. Mac will retain this request and every incomplete group if the work must continue in a later session.
