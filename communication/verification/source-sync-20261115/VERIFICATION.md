# Source delivery, review and publication verification

Verified on November 15, 2026. The [standing policy](../../context/SOURCE_SYNC.md) now applies through both repository and communication-package contributor instructions. The existing Mac MCP remains the transport, and the existing five-minute heartbeat includes source discovery, isolated intake, review, reconciliation and small Git commits. The event receiver and runner remain read-only; source acceptance and publication are later agent decisions.

## Source and software checks

The new [source_intake.py](../../context_mcp/source_intake.py) wraps the unchanged collector. It binds delivery/request/transfer identities, verifies all declared hashes, enforces aggregate limits, reconstructs into private isolated folders and keeps durable receipts separate from acceptance. It imports only the installed project collector, never transferred code. Notes, state and incoming directories must be disjoint. Comparisons are original dated snapshots, so current work must be compared again before applying changes.

All **205 canonical communication tests**, including **24 focused intake tests**, passed. Independent review reproduced two defects in the initial implementation: receipt tampering could lose its hash constraint after a retry, and overlapping directories could overwrite an input note. Both were fixed before publication. The original reproductions now reject three repeated retries each and preserve the pinned hash/input bytes. Coverage includes missing or redacted source, partial transfers, wrong hashes, duplicate/conflicting IDs, interrupted writes, unexpected output, prohibited paths/content, locks and aggregate bounds. These are software checks, not provider or physical tests. Exact final source hashes and counts are in [verification.json](verification.json).

## Actual shared transport and source

The Mac saved and read back standing instruction `839b9dbf-9c31-4488-bb73-5c58129724a8` through authenticated MCP. Its work event `2a62f901-b0ca-5ad8-a6aa-7c387493fc1a` was processed once on Intel at **06:03:57.645210 UTC**. A later Intel report records receiver shutdown and CLI logout; the earlier successful review remains historical evidence and does not authorize restarting it.

Seven actual incoming Intel transfers passed complete source validation: **32 file entries, 826,972 file bytes and 85 manifest/chunk notes**. Five groups include completion envelopes. The new helper reconstructed those **24 files / 532,348 bytes** into private review folders and recorded `reconstructed_verified_for_review`. Two other groups remain deliberately incomplete. This active-agent run proves receipt/reconstruction, not an unattended merge or application acceptance. Sanitized IDs and receipt hashes are in [receipts.json](receipts.json).

The incoming audit-portability group is reviewed separately. Other groups require preservation of current dashboard/MCP adaptations, an excluded original analyst test, current guide wording and an explicit station-guide mapping. A precise ordinary MCP follow-up was saved and verified. An implementation-start receipt used as a source request is explicitly mapped to the standing owner instruction without rewriting immutable transfers. Omitted paths are never treated as deletions.

## Scheduled workflow and limits

The existing ACTIVE heartbeat `morph-spremljanje-napredka` was updated in place, retaining its target chat and five-minute schedule. Saved readback matches every requested field. It scans both original manifests and completion envelopes, independent of event-review and Notion ledgers; unresolved groups remain eligible. The full active/scheduled agent performs review, scoped application, tests and publication. This saved configuration is not proof that the first unattended source publication has run. The Mac/app/connectors must remain available.

The public package preserves unrelated dashboard, Intel API, media and relay/worker changes in the shared working tree. Package verification uses an isolated candidate built from the exact Git base plus only this publication's reviewed files. Credentials, private state, received application bundles and full internal task history are outside this package. Git publication, runtime deployment, Notion acceptance and physical verification remain separately recorded.
