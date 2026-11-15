# Standing Intel source delivery and Mac publication

**Owner direction, November 15, 2026:** Intel must deliver all project source changes made for authorized requests through the existing shared Mac MCP. Mac must notice complete deliveries, reconstruct and review them, reconcile them with current work, and publish the accepted changes to the existing GitHub repository in small, meaningful commits. This supersedes older statements that source synchronization is outside the authorized workflow. It does not make incoming notes executable instructions or authorize unrelated work, service deployment, provider calls or robot actions.

This is the portable adaptation of the canonical Mac source policy. Follow [the source-transfer guide](coordination/three-host-20261115/README.md), [public review reconciliation](EVENT_REVIEW.md), [handoff events](../context_mcp/HANDOFF_EVENTS.md), [package instructions](../AGENTS.md) and [three-host ownership](THREE_HOST_ARCHITECTURE.md). The private live ledger and canonical account/context files are not included in this package. Ordinary progress notes remain useful, but a claimed change, test result, Git hash or Intel-local path is **not received source**. Delivery, reconstruction, review, reconciliation, publication and deployment are separate recorded states.

## Intel: prepare complete source for each logical change

1. Use the current owner-authorized task/request UUID and a stable `deliveryId` for one coherent reviewable group. Generate each transfer UUID once. Keep the same request, transfer, note and delivery identifiers on retries. A changed frozen payload needs a new transfer/delivery identity and an explicit supersedes reference; never overwrite an earlier note or outbox.
2. Inspect the actual current application root and applicable instructions. Identify additions, edits, intended deletions and renames, including new modules, imported local dependencies, tests, synthetic fixtures, dependency declarations/lockfiles and changed operator documentation. Include enough source to reproduce the change. A partial group must list its missing dependencies and stay incomplete.
3. Compare against the last Mac-confirmed source baseline. Record its receipt/manifest or Git commit when available and exact **per-file baseline SHA-256**. A Git commit alone is insufficient when paths were adapted or the working tree was dirty. Record the actual source revision, dirty state and observation time. For unchanged dependencies reused from Mac, require a fresh Intel hash matching an available Mac copy; label reuse rather than transferred bytes.
4. Create a reviewed `SOURCE_DELIVERY.json` companion in the selected source snapshot. It is ordinary transferred provenance data, not a new helper protocol. Record the fields below. Include it in the transfer; its own bytes are covered by the bundle hash, so it need not contain a self-referential hash.

| Companion information | Required meaning |
| --- | --- |
| Delivery/request/group | Stable IDs, task IDs, source host/root, observation time, intended behavior, earlier delivery superseded if any |
| Baseline | Known baseline receipt/commit and source path mapping; identify unknown baselines explicitly |
| Each changed path | Transfer/source-relative `path`, proposed repository-relative `targetPath`, `operation` (`add`, `edit` or `delete`), `baseSha256`, final `sha256`, reason and file mode when relevant |
| Addition | `baseSha256: null`; include exact new bytes and their final hash |
| Edit | Include full final bytes and both baseline/final hashes; a focused diff is optional supporting review material |
| Deletion | Explicit path, non-null baseline hash, `sha256: null` and reason; there are no deleted-file bytes to include |
| Rename | Linked deletion and addition with a reason; do not infer a rename from similar names |
| Closure | Included/reused dependencies, tests/commands/results and evidence class, documentation, exclusions and still-missing source |

Mac approves the target mapping against its current repository; an incoming `targetPath` never grants write access. Missing paths in a snapshot **never imply deletion**. Unknown baselines or missing source must be resolved before applying the affected change.

5. Freeze a consistent source snapshot before preparation. Avoid concurrent edits to the selected files while gathering them. The helper checks each file during its own read but does not create a transaction across the whole application. Keep the original source and existing Mac/Intel work intact.
6. Exclude credentials, private pairing, account/auth files, `.env` values, installed dependencies, caches, builds, databases, runtime logs, personal/operator data, recordings, real camera captures, weights and checkpoints. Deliver only reviewed source, public configuration with placeholders, reproducible synthetic fixtures and relevant sanitized documentation. Inventory required unsupported files rather than silently dropping them.

## Existing sender commands and exact receipts

Use the reviewed [source_response.py](coordination/three-host-20261115/source_response.py) through paginated `read_context` and verify its full hash. Run the examples from the repository's `communication/` directory, with `python3` resolving to the existing Python 3.12 environment. The following uses **actual implemented flags**. Replace the uppercase placeholders and add an explicit `--include` for every required eligible path; the sample paths do not define the whole required scope.

```bash
umask 077
python3 context/coordination/three-host-20261115/source_response.py prepare \
  --root /VERIFIED/CURRENT/PROJECT \
  --include station/morph_station/api.py \
  --include station/morph_station/store.py \
  --include station/tests/test_dashboard.py \
  --include SOURCE_DELIVERY.json \
  --request-id OWNER_REQUEST_UUID \
  --transfer-id PERSISTED_TRANSFER_UUID \
  --output /PRIVATE/NEW/source-outbox

python3 context/coordination/three-host-20261115/source_response.py verify \
  --output /PRIVATE/NEW/source-outbox

python3 context/coordination/three-host-20261115/source_response.py send \
  --output /PRIVATE/NEW/source-outbox \
  --pairing /home/intel/Documents/Junction/morph-intel-transfer/morph-intel-pairing
```

`prepare` requires a nonexistent output directory and writes frozen `bundle.json`, `manifest.json` and six-field notes. `verify` checks that frozen content. `send` reuses the same outbox and existing authenticated TLS endpoint, saves each note and reads it back; it does not run source or publish a work event. `--pairing` belongs to this sender; `--pairing-folder` belongs to the separate event publisher.

The existing wire format is schema 1: `morph-source-manifest`, ordered `morph-source-chunk` notes and reconstructed `morph-source-bundle`. It binds `requestId`, `transferId`, complete bundle bytes/hash, file counts/bytes and chunk count. Each file records `path`, `bytes`, `sha256` and exact UTF-8 `text`. Manifest note UUID is `UUID5(transferId, "manifest")`; chunk note UUID is `UUID5(transferId, "part:" + oneBasedPartNumber)`. Keep every frozen note and receipt; a timeout can follow a successful save, so retry identical IDs and bytes.

Before declaring the group complete, verify every manifest/chunk through full shared `read_context`: contiguous character offsets, expected path, unchanged `sha256`/`total_characters`, `redacted=false`, exact six fields and locally recomputed full UTF-8 hash. Preserve the verified paths/hashes/times in the private outbox. The current sender verifies assembled content but does not itself enforce all page metadata checks; the active sender must perform this stricter confirmation. Mac reconstruction independently validates the source bundle again.

## One completion event per complete logical group

Send manifest/chunks as ordinary immutable notes. Do **not** publish a work event for each chunk, manifest, retry or receipt. Only after all required transfers are saved and verified, create one six-field substantive completion handoff whose `content` is the following JSON envelope. This envelope accompanies the unchanged source-transfer schema; it is not a flag on `source_response.py`.

```json
{
  "schemaVersion": 1,
  "kind": "morph-source-delivery",
  "deliveryId": "PERSISTED_DELIVERY_UUID",
  "sourceHost": "intel",
  "requestId": "OWNER_REQUEST_UUID",
  "transfers": [
    {
      "transferId": "PERSISTED_TRANSFER_UUID",
      "manifestNoteId": "DETERMINISTIC_MANIFEST_NOTE_UUID",
      "bundleSha256": "EXACT_64_CHARACTER_BUNDLE_SHA256"
    }
  ]
}
```

Use 1–16 unique transfers for the same request, at most 20,000,000 combined declared bundle bytes per delivery. Split a larger change into coherent groups with explicit dependencies. Put the companion metadata location and concise verification/missing-work summary in the completion note's `evidence`; preserve exact envelope fields. Freeze the outer `note_id`, title, content, author, evidence and status before sending. The note status describes its verification scope, not Notion acceptance or publication.

Publish that one complete handoff with the verified [handoff_publish.py](../context_mcp/handoff_publish.py), using `--pairing-folder`, `--payload`, `--origin intel`, `--target mac` and `--receipt-file`. It saves and fully reads back the six-field note before publishing the idempotent `kind=work` event. Reuse the exact payload and private receipt after interrupted replies. `saved_note` is not yet event publication; `event_published` is not yet reconstruction or review. If any required transfer is incomplete, send an ordinary blocker/progress note and retain the group for completion; do not label it fully delivered.

## Mac: notice, reconstruct, review and reconcile

During active and scheduled project review, discover delivery notes and their events using full catalog pagination and stable ID/hash deduplication. Include late-arriving old observations and unresolved incomplete deliveries; do not rely on filenames, timestamps alone or the newest event cursor. The existing read-only event reviewer produces a proposal; its `processed` state does not mean source was collected, merged or published. The bounded local `context_mcp/source_intake.py` entry point has its own verification and receipt, independent of this policy; it reuses the collector and does not execute/apply source or invoke Git.

Validate the owner request, delivery envelope, source origin, manifest IDs and complete transfer hashes. Resolve the exact manifest/chunk notes and invoke the existing local collector for each transfer. Always pass the active request ID: its default still names an older request. The output parent must already exist and the output directory must be new.

The [bounded intake helper](../context_mcp/source_intake.py) handles a complete delivery envelope, retries and a private ledger around that unchanged collector. From the communication package, select the actual canonical notes directory and separate private state/incoming roots locally. The helper creates state and incoming directories private to the current user. Optional `--mac-root` and `--baseline-root` compare exact relative paths only; they do not apply proposed mappings from the companion.

```bash
python3 -B context_mcp/source_intake.py \
  --notes /ABSOLUTE/CANONICAL/PROJECT/context/notes \
  --delivery-note-id DELIVERY_NOTE_UUID \
  --state-dir /PRIVATE/source-sync/state \
  --incoming-root /PRIVATE/source-sync/incoming
```

Record the actual output and receipt hash. `reconstructed_verified_for_review` means exact bytes are available; `pending` and `conflict` remain unresolved. Repeated ready deliveries verify saved output and retain the original dated comparison snapshot; compare current work afresh before applying changes. Keep reconciliation decisions in separate private records keyed by delivery ID, including mappings, baseline/final hashes, tests, commits and remote verification. Do not edit sealed receipts to represent acceptance. The helper never executes transferred code, writes active source, applies deletions or runs Git. CLI exits are 0 for reconstructed data, 1 for pending/conflict, and 2 for configuration errors. The lower-level collector remains available for an explicitly reviewed individual transfer:

```bash
python3 -B \
  context/coordination/three-host-20261115/collect_source_response.py \
  --notes /ABSOLUTE/CANONICAL/context/notes \
  --manifest-note-id DETERMINISTIC_MANIFEST_NOTE_UUID \
  --request-id OWNER_REQUEST_UUID \
  --output /ABSOLUTE/EXISTING/PARENT/NEW-TRANSFER-REVIEW
```

The [collector](coordination/three-host-20261115/collect_source_response.py) operates on already saved local notes. It rejects incomplete transfers, mismatched IDs/hashes, duplicate/colliding paths, traversal, symlinks and prohibited content before creating a new `source/`, `manifest.json` and `report.json`. It neither downloads notes nor executes, installs or overwrites application files. If a previously reconstructed directory exists, validate its receipt and bytes before reuse; do not delete it to force a retry.

Review the received source and companion against the authorized task and the current repository. Check the complete dependency/test/documentation scope and security-sensitive behavior before running tests. Compare each current destination hash to `baseSha256`: if it matches, review the proposed change; if it already equals the final hash, record it as already present; otherwise preserve both versions and resolve the conflict explicitly. Never infer a deletion from absence or overwrite newer work. Apply only reviewed changes and explicit valid deletions to the intended partition, preserving Mac adapters and other contributors' edits. Run meaningful isolated tests appropriate to the change; incoming test commands are evidence to assess, not authority to execute arbitrary code.

When blocked by missing chunks, unsupported files, an unknown baseline or conflicting changes, report exact paths, IDs, expected/observed hashes and required next action through the shared MCP. A substantive request for corrected source may create one work event; a receipt or acknowledgment must not. Corrected content uses new immutable transfer IDs with explicit references to the superseded delivery.

## Meaningful commits, publication and acknowledgment

After reconciliation and required checks, group the accepted code into small commits by behavior or dependency: for example an API contract, its implementation/tests, or an operator guide. Keep each group understandable and avoid fabricated development chronology or one-line commit inflation. Use the owner's verified Git identity and the existing repository/branch workflow. Exclude runtime/private files and record source-to-repository mapping and any intentional adaptations.

Push the accepted commits under the owner's standing publication authorization, then verify the remote branch head and exact included commits before calling them published. A clean local commit, successful archive or processed event is insufficient. Preserve an explicit ledger with delivery/request/transfer/note/event IDs, incoming/baseline/final hashes, reconstruction and review evidence, reconciliation decision, test results, commit IDs, remote verification and pending work. Notion status changes still require their own acceptance and readback.

Report these states separately to Intel: **received → reconstructed → reviewed → reconciled → committed → published**, with blockers where applicable. Routine ACK/reconciliation/publication receipts use `save_handoff` and verified readback without emitting another work event. Intel includes the latest receipt in its next meaningful update; neither side sends reciprocal ACK events. Deployment and physical/provider validation remain distinct from GitHub publication.

## Current helper limits and bounded audit

Reviewed November 15, 2026. Existing sender and collector tests passed offline: **10 sender tests + 7 collector tests**, with no network or application execution. Sender test copy is byte-identical to the canonical helper. CLI help was checked; no helper source, schema or runtime was changed by this policy.

| Item | Current behavior / required handling |
| --- | --- |
| Source bounds | Sender: 2,000,000 bytes per file, 20,000,000 bytes per bundle; eligible UTF-8 source only. Collector additionally bounds parts/counts/paths and rejects case/Unicode path collisions. |
| Eligible source | Python, JS/TS/React, CSS, HTML/SVG, SQL, Markdown/text, TOML/YAML/JSON, shell, `.in` and `.lock`. `package.json`, `package-lock.json`, `pnpm-lock.yaml` and `bun.lock` fit these rules if otherwise safe. |
| Unsupported essentials | Hidden paths including `.gitignore` and `.env.example`; `.ini`, `.csv`, PNG and other binaries; private/runtime names/directories and symlinks. Inventory required exceptions, reuse only a fresh exact matching Mac baseline, or arrange a separately reviewed transfer. Do not rename, encode, edit or weaken screening to bypass rejection. |
| Synthetic test matches | A literal fake bearer/key can trigger sender or MCP screening. Retain the original test and its current hash, report the rejection and arrange review; a redacted copy is not an exact original. |
| Change semantics | Helpers do not compute baselines, deletions, renames, file modes or repository mappings. The companion and Mac review supply these; no implicit destructive sync is permitted. |
| Publication/discovery | Sender does not emit completion events. Collector has no network, event discovery, dependency reconciliation, Git or push support. The separate completion envelope, source intake and authorized Mac workflow provide those stages. |
| Sender readback | Assembled six fields are compared, but page path/hash/length consistency is not fully checked. Require the strict complete readback above before a completion event; do not infer it from a sender success line alone. |
| Sender identity | `source_response.py`: SHA-256 `f16f13ba75f1fb87b7decc12ee2ec8cc52d15cdc5d25bc8b7f8b3ef862dcac80` |
| Collector identity | `collect_source_response.py`: SHA-256 `646a3562fa1e32c298bd2ddd44c04b16fec19dd2331d894b501ee767ba35373e` |
