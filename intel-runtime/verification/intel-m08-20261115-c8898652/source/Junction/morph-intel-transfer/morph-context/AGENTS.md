# Workspace instructions

**Current Intel controller identities — owner confirmation on November 15, 2026 UTC:** **leader `5B91027633`**, **follower `5AE6075066`**. The owner confirmed replacement of the former leader controller `5B91030668` after the 07:37:40 UTC host USB inventory. Use [the current Junction connection map](../../robot-connections.json). Preserve earlier measurements with their original serials. USB serials are not automatically LeRobot calibration IDs. Controller identification does not establish calibration acceptance, exclusive access or successful teleoperation; physical launch requires the operator's explicit readiness confirmation.

These instructions apply to all work in this folder and its subfolders. Every human contributor and AI agent should read this file before making changes. More specific instructions in a subfolder add context for that area. Explicit instructions from the project owner take precedence over these project defaults.

**Later M08 owner stop, November 15, 2026 UTC:** the leader became unavailable. Three follower points were manually captured, then the owner reported a table collision during authorized playback. The program stopped at 08:07:42 UTC and verified torque off on all six motors. The owner explicitly ended the experiments. Current replay is blocked in code before serial access with no CLI bypass. Do not resume hardware operations using earlier authorization or execute archived pre-hold scripts. See the [current Intel M08 report](../../reviews/intel-m08-teleop-20261115T073603Z/README.md). M08 stays In progress; no successful physical replay or leader/follower teleoperation is claimed.

## Language

- Write all new and updated project-owned Markdown files in English. This includes headings, prose, tables, checklists, diagram labels, and explanatory comments in documentation examples.
- Keep existing project documentation in English when extending it. Do not introduce untranslated Slovenian sections.
- Preserve executable commands, identifiers, file paths, URLs, version numbers, and source references. Keep exact quotations or original data intact when their original wording matters, and explain them in English.
- This rule applies to our documentation, not to third-party files in installed tools, dependencies, caches, or virtual environments. Do not rewrite vendor documentation.
- Chat replies may follow the user's language. English documentation does not require switching a Slovenian conversation to English.

## Project context and sources

This is the shared Junction 2026 workspace for the Ignite Next × Intel Physical AI challenge. Our project combines a physical robot workflow with a live dashboard for quality control and reliability tracking.

Read these documents as relevant to the task:

- [IGNITE_INTEL_PHYSICAL_AI.md](IGNITE_INTEL_PHYSICAL_AI.md): challenge scope, source material, required technologies, evaluation criteria, equipment, implementation plan, and unresolved questions.
- [PHYSICAL_AI_WORKFLOW.md](PHYSICAL_AI_WORKFLOW.md): selected primary workflow, voice commands, implementation stages, acceptance evidence and open questions.
- [PHYSICAL_AI_ORCHESTRATION.md](PHYSICAL_AI_ORCHESTRATION.md): selected architecture for online Gemini task selection, Nemotron perception, ElevenLabs voice input, learned skills, recovery and operator goal changes.
- [PHYSICAL_AI_EXTENSIONS.md](PHYSICAL_AI_EXTENSIONS.md): optional extensions and their compatibility, added work and evidence requirements.
- [PHYSICAL_AI_CHALLENGE_COMBINATIONS.md](PHYSICAL_AI_CHALLENGE_COMBINATIONS.md): verified challenge combinations, the selected NVIDIA/Gemini workflow, acceptance criteria, and sponsor-specific submission requirements.
- [PHYSICAL_AI_TASK_PLAN.md](PHYSICAL_AI_TASK_PLAN.md): delivery sequence, existing Notion task links, dependencies, and mandatory task-update workflow.
- [NOTION_SYNC.md](NOTION_SYNC.md): confirmed Notion publication state and the procedure for preserving and retrying failed task updates.
- [JUNCTION.md](JUNCTION.md): event logistics, submission requirements, partner resources, and the prepared local development environment.

The challenge brief describes an autonomous SO-101 workflow: pick up a Duplo brick, present it to the inspection camera, inspect it with Anomalib, and place it in the appropriate good or defective bin. Demonstrations and VLA policy training use Physical AI Studio; supported inference is optimized with OpenVINO on the target Intel Core Ultra Series 3 system.

Treat this as the project context recorded in the brief, not proof that hardware, models, training, or integration are already working. Inspect the current implementation and available equipment before making claims about their status.

The brief records conflicting evaluation rubrics and some older unresolved notes. Preserve those distinctions until a dated organizer or mentor clarification resolves them. Do not silently select a rubric, invent a requirement, or treat a proposal as an official rule. When a task depends on current rules, deadlines, or software support, verify the relevant source and record the verification date.

## Mandatory integrations — team decision on November 14, 2026

- The project owner requires **NVIDIA, Google Gemini and ElevenLabs voice input** in the project. Preserve all three in scope unless the owner changes this decision. These are team requirements in addition to the Intel challenge requirements. The adaptive workflow is the selected primary approach; all other researched partner integrations are optional extensions.
- The selected NVIDIA integration is **Nemotron 3.5 Super VL**, the model named in the reviewed Best Use of Nemotron minimum requirements. NVIDIA hardware or cloud GPU use alone does not fulfill this selected integration. Verify the exact model endpoint before implementation; the challenge's starter example has a documented model-name discrepancy.
- Use the **Gemini API in the working product**. Gemma and use of Gemini only as a development assistant do not replace this requirement.
- Updated owner direction on November 14: Gemini should participate in online task orchestration, supporting both recovery from problems and operator goal changes. The intended model is `gemini-decision-1` through the Decisions API; access is unverified. Nemotron supplies frame-linked visual observations, Anomalib supplies defect measurements, and Gemini selects among currently permitted learned tasks. The local application validates and dispatches the selection. This supersedes the earlier retrospective-query-only proposal. Each model must make a distinct, demonstrated contribution.
- Preserve a substantive local Studio/VLA/Anomalib/OpenVINO workflow. Cloud task decisions may be evaluated at defined execution boundaries; a validated local dispatcher controls skill execution. Do not send cloud-generated joint commands or silently change outcome records. Check state/goal versions, evidence freshness, preconditions, timeouts and duplicate execution IDs. Include cloud waiting time in full-cycle duration whenever the cycle waits for a response.
- Decision 1 selects from defined options; it does not generate function-call arguments, plans or explanations. Do not implement it as if it were a generative Gemini model. See the current architecture document for verified API references.
- Use ElevenLabs speech recognition to give Decision 1 actual spoken operator commands. The selected initial service is Scribe v3 Live (`scribe_v3_live`), with account access unverified. Finalize and deduplicate a complete utterance before selecting a goal; provisional text and later timestamp enrichment must not issue commands. Validate the goal, commit its version at the defined boundary, then build a new snapshot for task selection. Keep provider keys server-side. Spoken acknowledgments are optional and must reflect actual application state.
- Keep model observations, causal hypotheses, independent reference labels and measured outcomes distinct. Compute metrics from persisted records; a model's explanation is not proof of a correct detection or physical result.
- Record actual model IDs, inputs, outputs, tool results, latency and errors without credentials. Mark proposed, implemented and verified capabilities separately. If model access is blocked, record and resolve the blocker rather than silently substituting a different provider.

## Development priorities

- Prioritize a reliable end-to-end physical cycle, observable results, and measurable improvements.
- Build the dashboard around the current object: what the system sees, detects, decides, executes, and verifies.
- Keep live operation, detailed robot/system telemetry, and quality/reliability history as distinct views of the same underlying records.
- Implement the session, cycle, attempt, and outcome records before deriving counters and charts from them.
- Keep proposed capabilities clearly separate from implemented and verified capabilities. A mockup, simulated run, or successful build is not evidence of a successful physical test.
- Avoid unrelated refactors and additional infrastructure unless they are needed for the task. Reuse established project conventions and the prepared environment where practical.

## Mandatory Notion task updates — owner instruction on November 14, 2026

- Keep the existing project tasks in [Morph — Tasks](https://app.notion.com/p/418d87e344588104be78f7dafd69a4d4) current whenever project work is performed. Use the stable task IDs and canonical page links in [PHYSICAL_AI_TASK_PLAN.md](PHYSICAL_AI_TASK_PLAN.md); update the existing record rather than creating a duplicate.
- Set a task to **In progress** when work actually starts.
- After each meaningful work session and before reporting completion, update the task with the work summary, verification results and evidence links, a timezone-qualified date/time, and remaining work or blockers. Distinguish simulation, provider tests and physical verification; documentation or a successful build alone does not prove a working physical result.
- Mark **Done** only when the task's acceptance criteria are met and closure evidence is saved. Check the saved Notion result before claiming the task update succeeded.
- Review dependent tasks after completion and manually promote **Waiting → Ready** only when all their prerequisites are met.
- If a Notion write fails, preserve the pending update locally in [NOTION_SYNC.md](NOTION_SYNC.md), including the task ID/link, intended status, update content, evidence, timestamp and error. Report the synchronization failure separately from the actual implementation status, and retry when access returns. Never claim that a failed or unverified write succeeded.
- This is a standing instruction for this project. Routine task updates within this scope need no additional confirmation. It is part of the active work workflow, not a background automation or a promise to monitor tasks between work sessions.

## Shared definitions for robot repetitions

Use these team conventions consistently in the backend, dashboard, tests, exports, and documentation. They define our dashboard metrics, not the organizers' scoring rules:

- **Session:** one named test or demonstration run, with its own ID, start/end times, and robot/model/configuration metadata.
- **Cycle:** one started task for one object, ending in a recorded outcome. A new independent test is a new cycle, even when the same physical object is reused.
- **Attempt:** one physical execution attempt within a cycle. Retrying a failed grasp or placement creates a new attempt in the same cycle.
- **Additional inspection:** another image or analysis of the same object. It does not automatically create a new physical attempt or cycle.
- **First-attempt success:** a confirmed end-to-end correct cycle completed on its first physical attempt. Count additional inspections separately.
- **Recovered success:** a confirmed end-to-end correct cycle completed after at least one failed physical attempt. Keep the preceding failures in the record.

Example: a failed grasp followed by a successful retry is one cycle, two attempts, one failed attempt, one successful attempt, and one recovered cycle. It is not a first-attempt success.

## Outcome and quality rules

- Track detection correctness, physical execution success, and end-to-end task correctness separately.
- Detection correctness requires a reference label independent of the model's prediction.
- Physical execution success means the robot achieved the commanded physical result with suitable confirmation.
- End-to-end correctness also requires the classification and actual destination to be correct for the object's reference quality. Successful placement in a wrongly selected bin is not a correct end-to-end result.
- Store the commanded destination and observed destination separately where available.
- Distinguish command sent, command acknowledged, execution finished, and physical outcome verified. A controller's completion message alone does not establish a verified physical outcome.
- Record the outcome confirmation source, such as camera, sensor, or operator, and the evidence available. Use an unverified outcome when confirmation is missing.
- Preserve successful, failed, aborted, unverified, and in-progress records. A connection loss is not proof of physical failure.
- Display anomaly scores and thresholds as such. Do not label an anomaly score as a probability or confidence percentage without a justified calibration.
- Show unavailable telemetry as unavailable, not as zero. Do not invent joint forces, motor currents, temperatures, power measurements, or device utilization.

## Counters and reliability history

- The main end-to-end result is **confirmed correct cycles / all finished cycles**. Finished cycles include failed, aborted, and unverified outcomes; show those counts separately. Exclude cycles still in progress.
- The corresponding physical execution result is **confirmed successful attempts / all finished attempts**, with outcome categories visible.
- Show first-attempt successes, recovered cycles, retries, and additional inspections separately. A successful retry must not hide earlier failures.
- Detection quality uses reference-labeled examples only. Show the number checked and the total population, for example: `18 correct / 20 checked; 27 objects total`.
- Every percentage must have a defined denominator and visible sample counts. With no eligible records, show `No data yet` instead of `0%` or `100%`.
- Consecutive success streaks count only confirmed correct cycles. A failed, aborted, or unverified result ends the streak.
- Derive counters from uniquely identified persisted records. Duplicate events, page refreshes, reconnects, and repeated completion messages must not add repetitions.
- Use stable identifiers for sessions, cycles, attempts, events, and analyzed frames. Link each detection and decision to the actual frame and object it used.
- A late outcome confirmation updates the original record. A manual correction must retain its previous value, new value, author, timestamp, and reason.
- Starting a new session resets that session's displayed totals, not the saved history. Do not silently turn open cycles into successes when a session ends.
- Keep live, simulated, and replayed data distinguishable and exclude simulated runs from real hardware reliability results by default.
- Replaying recorded telemetry must not create new sessions, cycles, or attempts, or increment live reliability counters. Display the existing historical records.

## Dashboard evidence and measurements

- Show the analyzed snapshot as well as live video, with timestamps and clear stale/disconnected states.
- Display actual task instructions, model/policy inputs and outputs, chosen actions, and recorded outcomes. Do not invent internal reasoning or explanations that were not produced by the system.
- Preserve per-cycle history: images, inspections, decisions, attempts, timings, errors, confirmation sources, and final outcome.
- Separate model inference latency, robot motion time, verification time, and full cycle duration. Define timing boundaries and use them consistently.
- Compare baseline and optimized configurations on comparable inputs. Record model/configuration, device, precision where relevant, sample count, timing method, and quality alongside speed.
- Report both first-pass reliability and recovery behavior. Include failed and uncertain cases in the evidence.
- Store timestamps with an unambiguous timezone and label display timezones explicitly. Do not mix event time with receipt time or Finland time with Ljubljana time.

## Physical robot behavior

- Respect the actual calibration, workspace limits, stop behavior, and hardware operating instructions.
- Opening the dashboard, refreshing it, or reconnecting must not start a robot movement. Movement must follow an intentional control action or an already active, explicitly started run.
- Define whether pause waits for the current cycle or interrupts execution, and show the robot's acknowledgment.
- Do not present a software stop as a verified physical emergency stop.
- Validate UI and data behavior with clearly labeled simulation where appropriate, and explicitly identify which behavior was tested on physical hardware.

## Working in this folder

### Shared context across the Mac and Intel computer

- Every agent and delegated subagent must follow the [workspace-wide reporting rule](../../AGENTS.md#mandatory-mac-reporting-for-every-agent). Assign a reporter when delegating; the parent must publish attributed subagent results and verify delivery before its final handoff unless the subagent provides its own confirmed receipt. Local replies alone do not establish shared delivery.
- Codex running on the Linux Intel computer must follow [context/INTEL_CODEX.md](context/INTEL_CODEX.md): publish session starts, meaningful changes/test results, blockers and final handoffs to the shared Mac MCP; verify each saved note, and preserve unsynchronized payloads for idempotent retry. Mac review uses those notes and confirmed Notion status to track completed and remaining work. Writing only to an Intel-local copy does not update the Mac.
- Start cross-computer continuation with [context/START_HERE.md](context/START_HERE.md), [context/CHAT_CONTEXT.md](context/CHAT_CONTEXT.md), recent `context/notes/`, and the current task's source files. [CONTEXT_SHARING.md](CONTEXT_SHARING.md) documents the MCP connection and portable handoff.
- After meaningful project work, save an English handoff with the actual changes, verification evidence, remaining work, source references and a timezone-qualified timestamp. Save the exact six-field payload in `context/outbox/<UUID>.json`, publish it through the shared Mac's `morph_context.save_handoff`, read it back and retain its receipt. If sending or read-back fails on Intel, keep that unchanged outbox payload as **pending sync** and retry the same UUID; writing to an Intel-local `context/notes/` is not remote delivery. Keep status claims separate from independent evidence. Preserve prior notes and reference them when correcting a previous conclusion.
- The server reads project files live, but conversation summaries are explicit snapshots. Do not claim automatic access to later chats, external attachments or another computer's private accounts. A copied portable bundle has independent history until updates are reconciled. Continue mandatory Notion task updates separately.

### Files and implementation

- Inspect current files and applicable instructions before editing. Preserve other contributors' work and coordinate ownership when editing in parallel.
- Check whether the directory being changed is a Git repository; do not assume the workspace root or every subfolder is one. Inspect status and diffs when Git is available.
- `.junction-setup/` contains prepared runtimes, tools, dependencies, and caches. Use the activation instructions in `JUNCTION.md`; keep application source and project documentation outside dependency/cache directories.
- Keep credentials out of source, documentation, screenshots, and logs. Use local environment configuration and placeholder-only examples. Preserve relevant ignore rules for secrets, dependencies, generated output, and large artifacts.
- Preserve exact commands, links, source labels, dates, and stated uncertainty during translations. A translation is not a factual re-verification. Flag pre-existing broken references or contradictions instead of inventing missing evidence.
- Run verification appropriate to the change. For documentation, check completeness, links, commands, and formatting. For repetition logic, cover duplicate events, retries, late confirmation, unknown outcomes, session changes, and manual corrections. For integration changes, exercise the relevant workflow.
- Update affected English documentation when behavior or shared definitions change. Report what changed, what was checked, and any unresolved limitations accurately.

## Browser coordination

- The user owns the native Safari windows for their own work. Use a separate in-app browser surface for agent browsing so the user can continue browsing independently.
- Do not switch, navigate, or type into the user's Safari windows unless the user explicitly hands over Safari for that particular operation. Separate Safari windows still share focus under native app control and do not provide reliable concurrent use.
- A handover for one operation is not permission to use every Safari window or to keep controlling Safari after that operation ends.
