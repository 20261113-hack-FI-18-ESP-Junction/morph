# Event-triggered handoff review

**Standing source workflow — November 15, 2026:** [SOURCE_SYNC.md](../context/SOURCE_SYNC.md) now authorizes the active and existing scheduled Mac agent to reconstruct, review, reconcile and publish source for requested Intel changes. A complete group produces one `morph-source-delivery` work note/event. The event receiver and its runner remain read-only; their acknowledgment does not apply source or publish Git. The separate local `source_intake.py` and subsequent reviewed reconciliation retain their own receipts. Older automatic-reception limitations below describe the lower-level receiver, not the newly authorized full-agent workflow.

This adds explicit work notifications and a read-only reviewer to the **existing Mac MCP server**. It reuses the current HTTPS URL, bearer pairing and trusted CA. It does not create a second server, a tunnel, a robot controller, an automatic Git synchronizer or a new Notion automation.

The implementation was prepared on November 15, 2026. This portable guide does not include private canonical history; the maintained Mac evidence location is `context/verification/mcp-adoption-20261115/`. Commands below describe the implemented interfaces; successful source tests alone do not establish that a receiver is running on either host. Dated live activation and source hashes belong in the [publication verification](../verification/events-20261115/README.md). The existing [existing review reconciliation workflow](../context/EVENT_REVIEW.md) remains the fallback and the owner of normal Notion reconciliation.

## What triggers a review

Only an intentional call to `publish_handoff_event` creates work. The preferred [publisher](handoff_publish.py) first saves the exact six-field handoff, reads the complete saved note back, verifies its hash, then publishes a `work` event for the other host. Ordinary `save_handoff` remains append-only and **does not trigger a review**.

Use this opt-in path for a substantive implementation, verification, blocker or source handoff that the other host should inspect. Continue publishing idle status receipts through the existing ordinary-note workflow. Do not turn receiving, acknowledging or reviewing an event into another work event; that would create a reciprocal loop. The publisher/store reject the exact scheduled-review author `Codex on Mac | scheduled project review` and structured `kind` or `event_type` values `ack`/`receipt`. These are concrete filters, not a general natural-language idle detector. A sentence mentioning a receipt in an otherwise substantive handoff is permitted. The caller remains responsible for selecting meaningful work.

`origin` and `target` are opposite values from `mac` and `intel`; they route work but are not independent machine identities authenticated by separate credentials. Holders of the existing shared bearer pairing remain within its existing trust boundary.

## Components and state

| Component | Responsibility |
| --- | --- |
| [server.py](server.py) | Registers six optional event tools on the current authenticated MCP when `--enable-handoff-events` is supplied. |
| [handoff_events.py](handoff_events.py) | Stores durable UUID/hash-bound events in `.junction-setup/context-share/handoff-events.sqlite3`; enforces one active lease per target. |
| [handoff_publish.py](handoff_publish.py) | Performs explicit save → complete readback → publish, with an immutable local payload and durable retry receipt. |
| [handoff_receiver.py](handoff_receiver.py) | Polls, claims, verifies note pages, renews the lease, invokes a fixed local reviewer, saves its result and completes the event. |
| [handoff_codex_runner.py](handoff_codex_runner.py) | Starts an isolated read-only Codex review and validates its English JSON result. It does not execute the note's instructions. |
| [handoff_review_export.py](handoff_review_export.py) | Optionally exports validated Mac review summaries for the existing reconciliation workflow; it creates no work events or Notion updates. |
| [station_worker.py](station_worker.py) | Supplies the existing standard-library HTTPS/MCP pairing client reused by publisher/receiver. The separate station-data worker is not launched by this feature. |

The handoff event and the station-data relay are separate queues. Enabling or receiving a handoff event does not create an analyst request, enable station writes, issue a robot command, or change the current voice/provider configuration. A Codex review itself uses the configured Codex account; it is not a Gemma, Nemotron or robot test.

| Observation | What it establishes |
| --- | --- |
| Publisher receipt `prepared` | Exact local payload path and bytes are bound before networking. |
| Publisher receipt `saved_note` | The complete shared note was read back without redaction and its full text hash was checked. No event is yet confirmed. |
| Publisher receipt `event_published` | The expected deterministic event UUID, sequence, direction and note hash were returned. This does not prove target receipt. |
| Server state `queued` | Durable work is waiting. Polling alone changes nothing. |
| Server state `claimed`, with `received_at` | A target receiver acquired a processing lease. It does not prove the note was fully read or the review finished. |
| Receiver local state `received` | The complete note snapshot was verified and saved locally. |
| Receiver `processed_pending_ack` | A successful durable result exists; the server completion may still be pending. |
| Server state `processed` | A receiver reported a durable result hash. It is not proof of source adoption, implementation, Notion synchronization or physical acceptance. |
| Runner `notionSync: pending` | Proposed M01–M24 task updates await the existing authorized task/Notion workflow and its saved readback. |

The runner may instead return `notionSync: not_required` when it proposes no task updates. It never writes Notion. It does not wake or inject a message into an existing desktop chat; it creates a separate ephemeral CLI review process.

## Enable the existing server deliberately

Adopt reviewed source into the canonical Mac workspace and verify its tests and hashes first. Preserve the current pairing, TLS files, context notes, station relay database and service arguments. Add `--enable-handoff-events` to the **existing server's** next deliberate start; retain `--enable-station-relay` if already enabled. Coordinate an explicit stop/restart of that process. Do not start a second listener on the same port, rotate pairing merely to enable this feature, or serve a stale portable snapshot as the canonical workspace.

For an already prepared Mac connection, the existing launcher accepts:

```bash
bash context_mcp/run.sh --transport http --host CURRENT_MAC_INTERFACE_IP --port 8765 \
  --token-file .junction-setup/context-share/token \
  --tls-cert .junction-setup/context-share/server-cert.pem \
  --tls-key .junction-setup/context-share/server-key.pem \
  --enable-station-relay --enable-handoff-events
```

Replace `CURRENT_MAC_INTERFACE_IP` with the interface already configured for the current pairing/certificate. Run from the canonical workspace; confirm the current process arguments instead of copying a historical IP. The launcher uses `.junction-setup/context-mcp/bin/python`, where the server SDK is installed. This is a foreground process; keep its owning session and the Mac awake. No launchd/systemd service or automatic restart is installed. Restart and service adoption remain explicit operations.

The added tools are:

| Tool | Arguments |
| --- | --- |
| `publish_handoff_event` | `note_id`, `origin`, `target`, exact saved-note `note_sha256`, `kind="work"` |
| `poll_handoff_events` | `target`, stable `consumer_id`, `after_seq=0`, `limit=20` |
| `claim_handoff_event` | `target`, `consumer_id`, `event_id`, `lease_seconds=300` |
| `renew_handoff_event` | `target`, `consumer_id`, `event_id`, current `claim_id`, `lease_seconds=300` |
| `complete_handoff_event` | `target`, `consumer_id`, `event_id`, current `claim_id`, `outcome="processed"` or `"failed"`, durable `result_sha256`, optional stable `error_code` |
| `read_handoff_event` | `target`, `event_id` |

The event UUID is deterministic for note UUID, origin and target. Repeating the same publication is idempotent; changing the hash or immutable identity is a conflict. The store checks every page of the saved note before publication. Hashes here cover the **full saved note text**, including server-added fields; the publisher's original six-field payload has a separate hash.

## Start one Mac receiver

The receiver and runner use Python 3.12 and the standard library. They do not require a separate MCP SDK installation. The runner's default Mac Codex path is `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`. It checks that the installed CLI exposes every required flag before attempting a review. The reviewed CLI is `0.169.0-alpha.11.1`; another version must pass the same compatibility check.

From the canonical workspace, prepare a fixed argv array without putting notes, tokens or event content into shell commands:

```bash
umask 077
morph_project="$(pwd -P)"
morph_python="$morph_project/.junction-setup/python/bin/python"
morph_runner_argv="$("$morph_python" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' \
  "$morph_python" "$morph_project/context_mcp/handoff_codex_runner.py")"

"$morph_python" -B "$morph_project/context_mcp/handoff_receiver.py" \
  --pairing-folder "$morph_project/.junction-setup/context-share/intel-pairing" \
  --state-dir "$morph_project/.junction-setup/event-receiver/mac" \
  --project-root "$morph_project" --target mac \
  --runner-command-json "$morph_runner_argv" \
  --runner-timeout 900 --poll-seconds 5 --serve
```

These are explicit startup commands, not an assertion that the receiver is already active. Use `--once` instead of `--serve` for one bounded polling pass. A second receiver using the same state directory is refused by its lock. The server additionally prevents simultaneous active work leases for the same target, including receivers using different state directories. Keep the state directory across restarts so the consumer ID, cursor and completed results remain available.

The configured outer runner timeout defaults to 900 seconds; the Codex wrapper's own timeout defaults to 300 seconds. To change the latter, add a fixed `--timeout-seconds` value to the JSON argv prefix. Event content cannot set it. The receiver appends only `--input`, `--output` and `--project-root`. Avoid competing foreground launchers for the same target.

The optional Mac-only flag `--export-reviews` makes validated summaries available under `context/automation-reviews/EVENT_UUID.json` after each polling pass. It also permits export of a durable successful review whose server acknowledgment remains pending. Exports contain the note/event/result hashes, dated evidence and proposed task updates, with `state: pending_reconciliation`; the private note snapshot and runtime files remain in receiver state. Validation rejects secret patterns and private configuration references. Existing identical exports are reused, conflicting files are preserved, and failed exports are retried independently without rerunning Codex or changing the event cursor. Add this flag deliberately when connecting the receiver to the existing review workflow. It is rejected for the Intel target. An exported summary still requires the normal task evidence review, authorized Notion write and saved Notion readback.

## One-time Intel bootstrap

Intel needs the reviewed receiver, runner, publisher and matching `station_worker.py`, an existing private Mac pairing folder containing `connection.json` and `morph-ca.pem`, Python **3.12**, and an already installed/authenticated Linux Codex CLI. Use the existing Intel pairing; do not copy the Mac TLS private key or install a new tunnel/server.

First inspect the current Intel checkout and compare the delivered source hashes with the dated publication manifest. Preserve dirty Git changes, locally installed Studio, calibration, datasets, keys and running services. Receiving a work event does not transfer those source files. Source adoption is a separate intentional step through Git or the established verified source package. The published `ca512b1` snapshot predates this event feature; its old manifest must not be presented as a hash verification of the new files. Use the event-feature revision/manifest supplied by the current publisher.

After that review, fill these absolute paths with the actual installed locations. The Linux Codex executable is **mandatory explicit configuration**; the Mac default path cannot work on Intel:

```bash
umask 077
morph_project="/ABSOLUTE/INTEL/PROJECT"
morph_python="/ABSOLUTE/PYTHON3.12"
morph_codex="/ABSOLUTE/LINUX/CODEX"
morph_pairing="/ABSOLUTE/EXISTING/INTEL/PAIRING"
morph_runner_argv="$("$morph_python" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' \
  "$morph_python" "$morph_project/context_mcp/handoff_codex_runner.py" \
  --codex-executable "$morph_codex")"

"$morph_python" -B "$morph_project/context_mcp/handoff_receiver.py" \
  --pairing-folder "$morph_pairing" \
  --state-dir "$morph_project/.junction-setup/event-receiver/intel" \
  --project-root "$morph_project" --target intel \
  --runner-command-json "$morph_runner_argv" --once
```

Confirm a saved actual receiver result and event state before calling the Intel path verified. Then deliberately use `--serve` if continuous foreground reception is wanted. An empty poll only verifies its own request path, not a processed review. No new account login, unattended installation or service manager is performed by these scripts. The historical Python 3.14 certificate failure in the canonical Mac `CONTEXT_SHARING.md` is a reason to retain the verified 3.12 path; do not disable TLS verification.

## Publish one substantive handoff

Save a private UTF-8 JSON payload with exactly these fields before running the publisher:

```json
{
  "note_id": "A_NEW_CANONICAL_LOWERCASE_UUID",
  "title": "Current source and verification handoff",
  "content": "English changes, exact source revision/hashes, dated verification, remaining work and source references.",
  "author": "The actual contributing host or session",
  "evidence": "Specific saved evidence, distinguishing reported, software, provider and physical results.",
  "status": "handoff"
}
```

Replace the UUID placeholder before use. Allowed status values are `proposed`, `implemented`, `verified`, `blocked` and `handoff`; title/author are bounded to 200 characters, content to 24,000 and evidence to 4,000. Include timezone-qualified observations. No credentials or private runtime dumps belong in this payload. A note's status is an attributed claim, not certification by the server.

For Intel → Mac, using the variables from the Intel setup:

```bash
"$morph_python" -B "$morph_project/context_mcp/handoff_publish.py" \
  --pairing-folder "$morph_pairing" \
  --payload /ABSOLUTE/PRIVATE/OUTBOX/NOTE_UUID.json \
  --origin intel --target mac \
  --receipt-file /ABSOLUTE/PRIVATE/RECEIPTS/NOTE_UUID.json
```

For Mac → Intel, use the Mac interpreter/project/pairing and reverse `--origin`/`--target`. Receipt directories must be owner-only mode 0700; receipts are mode 0600. Keep the same payload bytes, absolute payload path, UUID and receipt file when retrying. Do not generate a new note to conceal a connection failure. If the server saved the note or event before the connection dropped, the stable identities allow the next call to finish without duplicates. A completed local publisher receipt is reused without a network request; use `read_handoff_event` separately for a fresh target status.

## Failure, lease and offline semantics

The receiver renews its 300-second lease every 30 seconds while the runner is active. The server supports lease durations from 5 to 3,600 seconds. A lost or expired claim cannot renew or complete another receiver's work; a new claim gets a fresh claim UUID and increments attempts. Identical completion retries remain idempotent after successful completion. A failed event is retryable after exponential backoff starting at five seconds and capped at 300 seconds.

The poll cursor records discovery/progress; it is not an acknowledgment. The server includes older unfinished work even below the cursor. The receiver skips entries currently in retry backoff within a batch so later returned work can proceed, and stops on an active conflicting target lease. Poll batches are bounded; this is a small project-work queue, not a high-volume telemetry stream.

On connection failure, local payloads, inputs, results and receipts remain intact. `--serve` retries connection/polling after its configured interval. While the Mac server or a target host is offline/asleep, review is delayed; it is not marked complete. Nothing starts a new server or wakes a sleeping computer automatically.

Successful output is written and synchronized to disk **before** completion is sent to the server. If that acknowledgment is lost, the receiver validates the saved result and retries completion without invoking Codex again. A crash with an uncertain local execution outcome is blocked by default. `--retry-ambiguous-read-only` explicitly permits another read-only review attempt in a new run directory. It provides at-least-once execution and can incur another Codex request; it is not exactly-once processing and must never be used with a side-effecting runner. Preserve the original run for audit.

If lease renewal fails or the outer timeout interrupts the wrapper, its SIGTERM/SIGINT handler unwinds the separately grouped Codex process and stops descendants before saving a controlled failure. A real synthetic Python process test covers this cancellation path. It is not evidence that every OS crash or forced SIGKILL can produce a final receipt; ambiguous crash handling remains necessary.

Receiver state is local under the configured private directory:

```text
state.json                         stable consumer, target, project root, cursor
receiver.lock                      excludes a second local receiver
review-export-state.json           optional independent Mac export scan cursor
events/EVENT_UUID/state.json        received/running/processed_pending_ack/acknowledged/failed
events/EVENT_UUID/run-N/input.json  exact verified note snapshot and hashes
events/EVENT_UUID/run-N/result.json validated review result
events/EVENT_UUID/failure-UUID.json separate sanitized failure receipt
```

Do not delete this state to force a retry. Inspect its saved identities and the server event first; deliberately start a new attempt only under the documented retry policy. Keep private snapshots and Codex runtime material out of Git and published manifests.

## Review boundaries and continued development

The wrapper invokes `codex exec` with `--sandbox read-only`, `--ephemeral`, `--ignore-user-config`, `--json`, `--output-schema`, `--output-last-message`, `--skip-git-repo-check` and an isolated `/tmp` working directory. It supplies restrictive local instructions and treats the note as data. It does not set a model override. The minimal environment retains existing CLI authentication paths but removes provider credentials, proxy settings and SSH authentication variables. The CLI may still need normal write access to its own authenticated runtime outside the application-source sandbox; it does not copy those credentials into the review workspace or report.

The reviewer receives current read-only Git metadata and may inspect public project source. It preserves dirty working trees and performs no automatic fetch, pull, checkout, merge, install, test, build or deployment. It does not blindly use a note's commit claim as local truth; missing or different source is recorded as a gap. The result contains `summary`, cited `evidence`, `remaining`, `verificationClass: read_only_source_review`, `proposed_task_updates`, source note IDs/hashes and timestamps. It never labels its own read-only review as new provider or physical verification.

Automatic reception therefore **does not automatically implement future Intel code**, resolve merge conflicts or change the colleague's dashboard. An authorized contributor uses the result and verified source revision to decide the next implementation step. Existing Notion requirements still apply to that work. The five-minute review can consume pending proposals with UUID/hash deduplication, preserve acceptance criteria/dependencies, perform authorized updates and verify the returned Notion content. An event being processed is not that verification.

## Developer checks

Run local tests against the adopted source with the prepared interpreter. The runner suite uses mocked subprocesses plus synthetic Python process groups; it does not launch real Codex or make provider/network requests. Receiver/publisher tests use fake transports; server tests use temporary stores and in-process interfaces.

```bash
.junction-setup/context-mcp/bin/python -B -m unittest discover \
  -s context_mcp/tests -p 'test_handoff_*.py' -v

.junction-setup/context-mcp/bin/python -B -m unittest discover \
  -s context_mcp/tests -p 'test_context.py' -v
```

The aggregate handoff pattern includes the in-process MCP transport suite, so it uses the prepared MCP SDK interpreter. The standalone runner, receiver, publisher and event-store suites themselves need only the standard library.

Real CLI, authenticated event publication, target receiver and cross-host adoption checks must be recorded separately with exact source hashes, note/event IDs, result hashes, timestamps and limitations. The deployment owner maintains that dated evidence in the adoption directory. Never label a synthetic process or transport test as an actual Intel review or physical run.
