# Codex instructions for the Linux Intel computer

**Current Intel controller identities — owner confirmation on November 15, 2026 UTC:** **leader `5B91027633`**, **follower `5AE6075066`**. The owner confirmed replacement of the former leader controller `5B91030668` after the 07:37:40 UTC host USB inventory. Use [the current Junction connection map](../../../robot-connections.json). Preserve earlier measurements with their original serials. USB serials are not automatically LeRobot calibration IDs. Controller identification does not establish calibration acceptance, exclusive access or successful teleoperation; physical launch requires the operator's explicit readiness confirmation.

Owner direction, November 14, 2026: record the work performed on Intel in the shared Mac context so the team can review progress, completed work, evidence, blockers and remaining tasks from the Mac. These instructions extend [AGENTS.md](../AGENTS.md). They apply during active work; they do not create an unattended monitoring service.

**Later M08 owner stop, November 15, 2026 UTC:** the leader became unavailable. Three follower points were manually captured, then the owner reported a table collision during authorized playback. The program stopped at 08:07:42 UTC and verified torque off on all six motors. The owner explicitly ended the experiments. Current replay is blocked in code before serial access with no CLI bypass. Do not resume hardware operations using earlier authorization or execute archived pre-hold scripts. See the [current Intel M08 report](../../../reviews/intel-m08-teleop-20261115T073603Z/README.md). M08 stays In progress; no successful physical replay or leader/follower teleoperation is claimed.

## Every agent and delegated subagent must report

Owner clarification, November 14, 2026: this reporting requirement applies to **every agent working on the Junction project**, including root-directory work, hardware diagnostics, documentation, reviews, tests, dashboard work and delegated subagents. The [workspace rule](../../../AGENTS.md#mandatory-mac-reporting-for-every-agent) makes the requirement explicit across all local project folders.

At delegation, name the agent responsible for publication and give it this protocol. Each subagent must either publish its own update and return the confirmed receipt, or return a complete attributed update to its designated parent reporter. The parent may include a short audit or test contribution in its own checkpoint, provided it records the subagent identity, scope, results, evidence and remaining work. Substantive independent work can use its own six-field payload and UUID. The parent must actually send and read back every contribution before claiming the combined handoff is synchronized; merely receiving a subagent's response is insufficient. Reuse an existing confirmed receipt instead of duplicating an already delivered update.

The final handoff must state **confirmed** or **pending sync** for the agent's work and all delegated contributions. Follow the same outbox, receipt and unchanged-UUID retry procedure below when a tool or network connection is unavailable. An offline agent may continue independent safe work, but must preserve and disclose the outstanding delivery. Notion synchronization is tracked separately. A separate Mac progress review does not publish Intel-local work on the agent's behalf.

Select one project context directory for the session and retain it across retries. For work from `/home/intel/Documents/Junction`, the existing shared-reporting outbox is `morph-intel-transfer/morph-context/context/outbox/`, with receipts under the neighboring `sync-receipts/`. Agents working in an extracted `HachingJunction` project may use that project's context directory; identify its host-qualified path in the update so another agent can find pending payloads.

## Start in the project folder and connect to the Mac

The transfer folder contains `morph-context/` (project sources and these instructions) and `morph-intel-pairing/` (private connection material). On Linux, open a terminal in the transfer folder:

```bash
cd morph-context
python3.12 ../morph-intel-pairing/connect_intel.py --check
python3.12 ../morph-intel-pairing/connect_intel.py --project .
```

Use the installed Python 3.12 verified on this Intel host and an installed Codex CLI. From the Junction root, `bash morph-intel-transfer/start-codex.sh --check` checks the connection and the same command without `--check` opens the original Morph project. When working in another project, run `python3.12 /home/intel/Documents/Junction/morph-intel-transfer/morph-intel-pairing/connect_intel.py --project .` from its instruction-bearing workspace directory; the launcher requires that directory to contain `AGENTS.md`. For dashboard work, launch from the enclosing handoff/package root, whose instructions cover both `HachingJunction/` and `morph-station/`, then work on the dashboard from that workspace. The launcher supplies the access token and trusted certificate to its Codex child process. Keep the pairing folder private, outside Git and shared evidence. Do not display its `connection.json` or token. See [connection details](../CONTEXT_SHARING.md) for certificate expiry and troubleshooting.

The project files copied to Intel are a snapshot. For reporting back, `morph_context` must point to the **shared Mac HTTPS endpoint** configured by the pairing launcher. A separately started local stdio MCP over Intel's copied files is an independent store; saving to it does not send updates to the Mac. Never replace the shared connection with that local store as an implicit fallback.

At the beginning of a session:

1. Read local `AGENTS.md`, this file, [START_HERE.md](START_HERE.md), and the applicable task sources. Read the shared versions through `morph_context.get_project_context` and `read_context` to find newer instructions and decisions. Preserve differences instead of overwriting another contributor's work.
2. Use `list_context(prefix="context/notes/")` and follow every `next_offset`. Read relevant new notes with `read_context`; its `offset` is a character offset. Check notes after the previous session's last confirmed note ID.
3. Select the existing M01–M24 task from [PHYSICAL_AI_TASK_PLAN.md](../PHYSICAL_AI_TASK_PLAN.md). Read its actual acceptance criteria and current Notion status when the connector is available. The plan's initial status column is not live task status.
4. Inspect the actual Intel host, work directory, source revision/changed files and required hardware before making claims. Do not start robot motion or change calibration as part of connecting this context service.
5. Generate a session UUID once and publish a `session_start` note to the Mac with the task ID, intended work, actual host identity, known prerequisites and anything still unknown. Set the existing Notion task to **In progress** when its work starts.

## Publish each meaningful work update

Use `morph_context.save_handoff`. The tool appends a note to the canonical Mac workspace at `context/notes/<note_id>.json`. Save the exact outgoing payload locally before sending it, then verify the saved shared record as described below.

Publish an update:

- When starting work and selecting or changing tasks.
- After a meaningful implementation change, successful or failed test, provider check, hardware observation, experiment or decision.
- Immediately when a blocker, changed requirement, failed assumption or conflicting result is discovered.
- Before switching computers/tasks, handing work to another agent, ending a meaningful session or sending a final completion report.
- During long-running work when new observed progress or a result is available. Report that an operation is running; do not invent success or spam empty updates.

Record all substantive work and decisions, including failures. A concise evidence-based checkpoint is sufficient; do not copy hidden reasoning, every transient tool call, credentials or unscreened logs.

Use the exact six-field payload in [templates/PROGRESS_NOTE.json](templates/PROGRESS_NOTE.json). Replace every placeholder. Generate a **new note UUID once per new update**, and reuse that UUID and identical payload for every retry:

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Every `content` should state:

| Field within the content | Required information |
| --- | --- |
| Task and session | Stable task ID/canonical Notion link, session UUID, checkpoint sequence, previous note ID, host/agent identity |
| Observed time | ISO 8601 time with UTC offset; distinguish this from the server's later `saved_at` receipt time |
| Work state | `session_start`, `progress`, `blocked`, `task_complete` or `session_end`; actual task status separately |
| Completed work | Concrete behavior/changes and relevant project-relative paths; Git commit/diff when available, otherwise changed-file hashes |
| Verification | Exact command or procedure, result and sample counts, failed/uncertain cases, and evidence class: documentation, software, simulation, provider or physical |
| Remaining work | Acceptance criteria not yet met, next actions, dependencies and who needs to act |
| Blockers and decisions | Observed errors/constraints, chosen action and any owner/mentor decision; use `None observed` when appropriate |
| Source/evidence availability | Identify which evidence was included in the note, is accessible from the Mac, or exists only on Intel |
| Notion synchronization | `confirmed`, `pending` or `unavailable`, the last confirmed status and update time; do not invent a successful task update |

The tool's `status` is **not a Notion task status**. It accepts only `handoff`, `proposed`, `implemented`, `verified` or `blocked`. Use `handoff` for starts/general progress, `implemented` for code written, and `verified` only with a stated verification scope. Put `In progress`/`Done` and whether that status is confirmed in Notion inside the note's content. A software-only verification does not certify a physical task.

Keep `title` and `author` below 200 characters each, `evidence` below 4,000 characters and `content` below 24,000 characters. Split a larger report into ordered notes with new UUIDs and cross-references.

## Confirm delivery and preserve failures

1. Save the exact six-field payload to local `context/outbox/<UUID>.json` before the MCP call. Create that directory when needed. The template's placeholder UUID must be replaced; do not submit the unchanged example.
2. Call `save_handoff` using those fields. On success, retain the returned `path`, `note_id` and `saved_at`. Both `created=true` (new note) and `created=false` (matching earlier delivery) are successful acknowledgments; do not resend an exact retry under a new UUID.
3. Call the **same shared MCP's** `read_context(path=<returned path>)`, follow `next_offset` if necessary, parse the JSON and verify the note ID and intended content. The server can redact recognizable secret patterns; inspect unexpected differences and publish a correction if needed. Do not insert the redacted credential back into a later note.
4. Save a local receipt at `context/sync-receipts/<UUID>.json` with the shared path, confirmed note ID, server `saved_at`, `read_context` SHA-256 and confirmation time. Only then report **shared on the Mac**. Keep the original payload and receipt for traceability.
5. If sending or reading back fails, retain the original outbox payload, record the error without secrets and report **pending sync**. Continue independent safe work when possible. A timeout can occur after a successful write: retry the **same UUID and payload**, rather than creating a duplicate.
6. At the next successful connection, retry notes without a confirmed receipt in session/checkpoint order, verify each shared record, and then publish the new checkpoint. This is an explicit agent workflow; no automatic file watcher or retry daemon is installed.

Do not put unacknowledged Intel notes into the canonical Mac history by claiming a local file save was a remote write. The Mac cannot see a local Intel outbox until it is actually transferred. If the connection stays unavailable, preserve that outbox for manual transfer and clearly mark its contents as pending. A conflicting reused UUID is an error: inspect the existing shared note; do not overwrite it or silently change the retry payload. Correct a previous conclusion with a new note that references the original ID and reason.

## Keep the existing task tracker current

Notion is a separate integration. The pairing package does not grant access to the Mac's Notion account or copy provider credentials. Update the **existing** canonical task; never create a duplicate to work around missing access.

- Set **In progress** when work starts. Save summary, exact verification class, evidence, timestamp, remaining work and blockers after a meaningful session.
- Mark **Done** only when every acceptance criterion is met and closure evidence is retained. Read back the saved result. Review prerequisites before promoting a dependent task.
- If Notion is unavailable on Intel, retain the complete intended update locally in `NOTION_SYNC.md` and include it in the shared Mac handoff, with task ID/link, intended status, timestamp, evidence and error. The Mac agent can apply it through its available connector during an active work session under the owner's standing authorization. Until read-back succeeds, call it pending.
- If Notion later succeeds, publish a new handoff referencing the pending note and the confirmed synchronization time. Never erase the history of a failed test, failed sync or changed outcome.

## Make evidence usable from the Mac

The current MCP writes text notes only. It does not copy modified source files, binary images, model weights, robot recordings or a Git repository from Intel. A path such as `/home/operator/project/report.json` is an **Intel-local locator**, not proof that the Mac has that report.

Include concise sanitized test results, relevant measured values, sample counts, model/configuration IDs and errors directly in the note. For other artifacts, record host-qualified paths, hashes and a reachable shared location if one exists. When transferring a patch or artifact separately, record its destination and verify its hash on the receiving computer. Mark missing transfers explicitly. Do not overwrite the Mac's code with a bulk sync or claim file synchronization based only on a handoff note.

Keep independent reference labels, provider observations and confirmed physical outcomes separate. Preserve failed, aborted and unverified runs. A controller completion message or a passing build alone does not establish a physical result. Follow all repetition and operating rules in `AGENTS.md`.

## Review progress from the Mac

During an active Mac work session, read new `context/notes/` records directly or through the shared MCP. The catalog is sorted by path/UUID, not by time: follow all pages rather than assuming the first page contains the newest notes. Use task IDs, session IDs, checkpoint sequences and explicit correction references to reconstruct state. Server receipt order alone is insufficient when Intel reconnects with older notes. Do not infer that a stopped stream of updates means a task failed or finished; show its last confirmed timestamp.

Present one row per task with **last confirmed status, completed work, verification/evidence, remaining work/blockers, last Intel observation time and synchronization state**. Confirm task status against Notion where available. Keep claims that lack accessible evidence labeled as reported/unverified. Apply any pending Notion update and verify its result before reporting synchronization. Read the newest Mac direction/decision notes before the Intel agent begins a new stage; conflicting instructions require reconciliation with the owner.

The first Intel session must produce and read back a `session_start` note. Until that round trip is verified, report the connection and Intel-side reporting workflow as unverified.
