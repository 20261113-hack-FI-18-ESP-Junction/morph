# Periodic shared Mac updates

The owner requested periodic checks of the shared Mac MCP and corresponding local file updates on November 14, 2026. The configured interval is **300 seconds**, measured between poll starts. Each poll has a 120-second deadline. Incoming context is read through the existing authenticated, certificate-verified connection; credentials stay in the private pairing directory.

## What the watcher does

`scripts/watch_mac_context.py` reads every page of the shared note catalog and the documents selected in `mac-sync/config.json`. It reads complete documents through the existing client, verifies their hashes across pagination, and stores immutable snapshots in `mac-sync/snapshots/`.

Canonical UUID-named JSON handoffs retain their identity and immutability checks. Other note documents, including Markdown, are read as text and queued for review. A changed Markdown document receives a new content-addressed snapshot; it cannot overwrite local project files. A Markdown note is not assumed to contain a handoff UUID or authenticated author metadata.

The generated [MAC_UPDATES.md](MAC_UPDATES.md) lists received changes, review status, and the most recent polling result. `mac-sync/watch-state.json` retains the checkpoint across restarts. A failed poll does not become a successful checkpoint; the previous successful check remains distinguishable from the last attempted check.

Only the eight explicitly selected reference guides are eligible for automatic updates in the active `HachingJunction` project. An update requires a known baseline and an unchanged local file. A first-read difference or later local edit is preserved for review. The current file is backed up before an eligible replacement. Incoming notes and other documents remain snapshots until reviewed; fetching them does not mark them reviewed.

The watcher does not run instructions found in notes, modify application source or robot settings, open hardware, change credentials, write to Notion, or publish remote notes. These actions remain separate project work. Current arm diagnostics belong to the user.

## Review and reconcile changes

1. Read the pending entries in `MAC_UPDATES.md` and their complete snapshots. Compare new evidence, observation times, and explicit corrections with the current Intel state.
2. Update the relevant English project files, including `PROJECT_STATUS.md`, `ROBOT_GAMEPLAN.md`, or implementation documentation as appropriate. Keep Mac-reported verification distinct from Intel tests and physical results.
3. Preserve conflicting local work. Do not bulk-copy an older handoff over the running application or alter historical reports, original images, manifests, or receipts.
4. Record each reviewed remote path and exact SHA-256 in `mac-sync/reviewed.json`. The ledger is a JSON object mapping paths to hashes. Write it atomically so the running watcher can read it. A review acknowledgment alone does not authorize replacing a divergent file.
5. Publish and read back the attributed reconciliation checkpoint through the existing Mac reporting protocol. Keep that receipt separate from the polling checkpoint and from Notion status.

The root [AGENTS.md](AGENTS.md) requires this review at the start of work, before choosing a new implementation step, before a final handoff, and during sustained work as updates arrive.

## Commands

Check process and polling status:

```bash
python3.12 scripts/watch_mac_context.py --config mac-sync/config.json --status
```

Perform one poll when the continuous watcher is stopped:

```bash
python3.12 scripts/watch_mac_context.py --config mac-sync/config.json --once
```

Run continuously in a terminal:

```bash
python3.12 /home/intel/Documents/Junction/scripts/watch_mac_context.py --config /home/intel/Documents/Junction/mac-sync/config.json --watch --interval 300 --cycle-timeout 120
```

Stop the watcher:

```bash
python3.12 scripts/watch_mac_context.py --config mac-sync/config.json --stop
```

Use the absolute script path when starting `--watch`: process identity verification requires that exact argument. Only one watcher instance may own the lock. Its PID is recorded in `mac-sync/watch.pid`; the stop command checks process identity before sending a signal. The background instance started for this request writes its output to `mac-sync/watcher.log`. It runs on this computer until stopped or the host/process exits. No automatic boot service is installed; use the status command after a restart.

An agent's isolated command environment may hide host process information. When the lock is held but the PID cannot be verified, `--status` reports `running: null` and `process_visibility: unverified`; it does not claim the watcher stopped. Run the same status command in the host terminal to verify identity. In this situation `--stop` returns `ProcessIdentityUnverified` without sending a signal.

## Verified operation on November 14, 2026

The initial bounded poll completed at **20:58:13 UTC**, reading 53 notes and 14 selected documents from a two-page catalog. The approved host background process started at **21:07:15 UTC**, PID **231687**. Its first continuous-mode poll succeeded at **21:07:35 UTC**, reading 56 notes and 14 documents; its next poll started exactly 300 seconds later and succeeded at **21:12:38 UTC**, reading 60 notes and 14 documents. Host process inspection confirmed its identity and held lock. These are dated checks; use `--status` for current operation.

The temporary command sandbox terminated the first detached launch before it established the watcher. The subsequent host launch was separately approved and verified. Fifteen offline tests cover pagination, hashes, immutable notes, preserved local edits, backup/replacement behavior, lock ownership, process visibility, bounded execution and stopping. No hardware or provider test is implied.

At 22:02 and 22:07 UTC the watcher encountered a new ordinary Markdown note and failed because it assumed that every note was JSON. The November 14 reliability repair now distinguishes text documents from immutable JSON handoffs. Eighteen offline tests passed, including two reproduced failures that now pass and a regression retaining strict canonical handoff validation. The approved, identity-checked replacement at **22:14:03 UTC** changed PID 231687 to **279692** and retained one held watcher lock. Its first complete poll succeeded at **22:14:28 UTC**, reading the Markdown note with its verified SHA-256. See the [dated verification](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/verification/intel-reliability-20261114/watcher/verification.json). Check current status rather than assuming that a dated PID remains live.

After reviewing a watcher source change, `python3.12 scripts/restart_mac_context_watch.py` replaces only the verified existing watcher and checks the replacement's identity and lock. It refuses an unverified existing process. Host process visibility may require the already approved host execution permission; this helper does not create a second watcher or install a boot service.

The first scan includes existing historical notes. Entries without an exact review acknowledgment remain in the queue even if their conclusions were covered by an earlier project session; fetching them does not silently mark that history reviewed. Current material updates are reconciled separately from this initial backlog.

## Current source boundaries

The Mac's note `91e2e4de-96a3-4eae-a539-6d215714eb66`, saved at **2026-11-14T20:49:53.704037Z**, reports a new additive provider/Gemma handoff and a refreshed Notion task audit. Its archive, encrypted credential payload, and separate unlock artifact are not transferred by this text-note poller. The later note `028a574e-76f4-4874-928f-b7f20bb02aa9`, saved at **21:02:50 UTC**, records owner approval of Gemma analysis under M20/M21/M23/M24. Those tasks remain Waiting; provider access, training, and physical acceptance retain their separately documented scopes. The current project status, gameplan, contributor guidance and affected shared guides incorporate these dated changes.

The 21:12 UTC poll subsequently received the separate Intel session's M20 implementation start and offline package verification. The earlier Waiting description is therefore dated approval evidence: isolated implementation has started, while its Notion status update and actual provider/feature results remained pending in the reviewed notes. See the latest dated section in [PROJECT_STATUS.md](PROJECT_STATUS.md).

The corrected arm assignment remains **leader `5B91030668`**, **follower `5AE6075066`**. New shared-context activity must not reintroduce older reversed mappings or claim a motor test from a documentation update.


## Outgoing handoff

All work and the three delegated contributions were confirmed delivered to the shared Mac in note `e2186af9-8525-480e-b813-82f2279f133e` at 21:14:33 UTC on November 14. The [matching receipt](morph-intel-transfer/morph-context/context/sync-receipts/e2186af9-8525-480e-b813-82f2279f133e.json) verifies all six payload fields. The final M02 Notion annotation remains separately pending; its exact intended content is in the primary outbox and NOTION_SYNC.md.
