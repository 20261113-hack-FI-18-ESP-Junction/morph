# Continue Morph on the Intel robot computer

**Current Intel arm roles — owner correction on November 14, 2026:** **leader `5B91030668`**, **follower `5AE6075066`**. Use [the current Junction connection map](../../robot-connections.json). This assignment supersedes the reversed roles and pending-identity wording in older handoffs. Dated transfer-state descriptions, original measurements, immutable notes and archives remain historical evidence. The user owns current arm diagnostics; this correction does not establish motor communication, calibration or teleoperation.

Prepared November 14, 2026. The archive manifest records the exact package creation time and source hashes. This is the entry point for Codex after extracting the ZIP. The owner wants implementation to continue from the existing work through a verified final demonstration, with concise progress updates and current Notion tasks.

## First actions

1. Read this document, [AGENTS.md](AGENTS.md), the full [project instructions](HachingJunction/AGENTS.md), and [LINUX_RUNBOOK.md](LINUX_RUNBOOK.md).
2. From this extracted directory, run `python3 verify_bundle.py`. Save the result and preserve the manifest as the original transfer baseline.
3. Locate and inspect the existing Intel project before changing anything. Read its current `AGENTS.md`, `PROJECT_STATUS.md`, `README.md`, robot gameplan, camera/motor reports, active task notes and any newer owner replies. Inspect processes, ports, source changes and physical device ownership. Do not overwrite that workspace with this ZIP.
4. Reuse the already working Intel runtime, Studio installation and private Mac pairing where suitable. Reconcile newer Intel files with this snapshot explicitly. Keep both project directories as siblings named `HachingJunction` and `morph-station`; the dashboard has a local package dependency on that path.
5. Follow [Intel reporting](HachingJunction/context/INTEL_CODEX.md): connect to the shared Mac context, read newer instructions and all relevant notes, publish and read back a session-start note, and update the existing Notion task when work starts. If a connector is unavailable, preserve an exact pending update and continue independent work.
6. Bring up the newly supplied React dashboard against the verified station service using the Linux runbook. First verify the software path using clearly labeled simulation. Then continue the actual hardware blocker, local adapters and physical baseline in the order below.

The archive extracts into a unique `Morph-Intel-Handoff-<UTCstamp>/` directory. Work from that new directory or deliberately merge reviewed changes into the existing workspace. Never use an unconditional recursive overwrite. The earlier portable transfer used `morph-context/`; that name alone does not satisfy the new dashboard's `../HachingJunction/...` dependency.

## What is in the package

| Location | Purpose |
| --- | --- |
| `HachingJunction/` | Canonical project requirements, task links, station backend/client, setup sources, evidence and shared context |
| `morph-station/` | The owner's actual React dashboard, connected to the canonical station records API |
| [LINUX_RUNBOOK.md](LINUX_RUNBOOK.md) | Runtime selection, installation only where needed, build, launch and software acceptance |
| `verify_bundle.py` and the manifest | Detect missing or altered transfer files before local edits |
| [Package verification](PACKAGE_VERIFICATION.md) | Relocated clean install/build, 121 software tests, portable HTTP checks and explicit evidence limits |
| [Shared notes](HachingJunction/context/notes/) | Dated Mac and Intel handoffs, including evidence boundaries and unresolved work |
| [Notion sync record](HachingJunction/NOTION_SYNC.md) | Confirmed task writes and any pending updates known at packaging time |
| [Notion task snapshot](HachingJunction/context/notion-snapshot/README.md) | Actual M01–M24 acceptance criteria and status captured for use when the Intel Notion connector is unavailable |

The source package intentionally excludes Mac virtual environments, dependency caches, `node_modules`, runtime databases, private pairing credentials, provider keys, account sessions and unrelated personal material. Reuse Intel's existing private pairing; create missing application configuration locally. Model weights, demonstrations, calibration files and camera captures that exist only on Intel remain in that existing workspace. Text handoffs describe those artifacts but do not transfer them.

The package includes curated project context, source documents and saved handoffs available on the Mac. It is not a raw export of every chat, attachment or later message. Read newer shared notes and the existing Intel workspace before assuming this snapshot is the newest evidence.

## The project and decisions that must survive the handoff

**Morph is a voice-directed, adaptive quality-inspection and sorting workcell for Duplo bricks.** The physical workflow is observe the object, pick it up, verify the grasp, present it to the inspection camera, inspect it with Anomalib, place it in the appropriate good/defective bin, and independently verify the result. A live dashboard connects the current object with what was observed, measured, selected, executed and confirmed.

| Required component | Distinct contribution and constraint |
| --- | --- |
| Physical AI Studio and learned VLA/policy skills | Collect the team's own demonstrations and train the manipulation behavior used in the real cycle. Retain substantive local learned execution; a sequence of hard-coded poses alone does not establish this requirement. |
| Anomalib | Produce the actual anomaly score/map and defect measurement, with a recorded threshold and independent evaluation labels. |
| Intel/OpenVINO | Run supported workloads on the assigned Intel station and measure quality alongside performance. Verify the chosen workload/device combination; package installation or a tiny synthetic operation is not a model benchmark. |
| NVIDIA Nemotron 3.5 Super VL | Supply actual frame-linked visual observations, especially visibility, ambiguous situations and recovery context. The recorded reference model ID is `nvidia/nemotron-3.5-super-vl-120b-a12b`; verify the actual available endpoint and response model before integration. The challenge starter has a documented model-name discrepancy. NVIDIA hardware/cloud use alone is insufficient. |
| Gemini Decision 1 | Use the Gemini Decisions API and intended `gemini-decision-1` model for online selection among permitted tasks and supported operator goals. Decision 1 is fixed-choice/probability output, not a generator of plans, arguments or explanations. Gemma or development-assistant use does not replace this integration. |
| ElevenLabs | Use actual spoken operator input, initially Scribe v3 Live `scribe_v3_live`, to supply a complete utterance for supported goal selection. Finalize and deduplicate before acting. Provisional text and later timestamp enrichment must not issue extra commands. |
| Local application | Own state, task parameters, allowed options, goal versions, validation, dispatch, persistence and outcome confirmation. Check freshness, deadlines, preconditions, state/goal versions and duplicate execution IDs. Cloud decisions never directly command joints. |

The selected initial demonstration is **one repeatable fixed-sequence baseline, one permitted bounded recovery, and one supported spoken goal change**. The goal change may affect a future task boundary, such as an additional inspection before placement; it cannot create an untrained skill or silently redefine correct bins. Confirm the specific supported example and recovery with the owner/mentor in M01/M09.

The owner selected this adaptive approach on November 14. It supersedes the earlier idea of using Gemini only for retrospective history queries. Spoken acknowledgments are optional and must match actual queued/active/rejected state. Other partner integrations in the extension research are optional; do not add them at the expense of the required cycle and three providers.

## Current implementation and evidence

Read the current task tracker when available. The old status column in the task index is an initial publication snapshot, not live status.

| Area | Evidence available at packaging | Remaining boundary |
| --- | --- | --- |
| M06 station foundation | Done for software acceptance. FastAPI/SQLite records, authenticated API, stable IDs/revisions, ordered events, metrics, evidence, independent labels, audit corrections and exports. Mac report: 48 tests. A later Intel handoff also reports 48 backend tests and HTTP/restart checks passed. | No actual robot, camera, policy or provider adapter is connected to this API yet. |
| M15 actual dashboard | Done on Mac, M16 Ready, confirmed in Notion at November 14, 19:43 Europe/Ljubljana (UTC+01:00). Three React views use one canonical client/store through a GET-only server proxy. | Full React dashboard was absent from the earlier Intel transfer; this package supplies it. Perform Intel UI acceptance. |
| M15 verification | 45 client/store tests, 17 projection/proxy tests, 11 retained prototype tests; TypeScript and production build; 22 client HTTP checks and 12 proxy checks. Desktop/mobile, keyboard, stale/offline recovery and exports passed on Mac. | These are software/labeled-simulation results. The evidence fixture image is a synthetic 1×1 PNG, not a live camera photograph. |
| M16 history completion | Backend correction APIs exist. Dashboard already reads traces, existing labels/audits and authentic CSV/JSON exports. | Audited write forms, late-confirmation UI, complete history filtering/pagination and explicit read-only replay still need implementation and acceptance. |
| Intel software/reporting | Intel note `bcffdadc-67d4-420e-b9a3-ed4a79415783` reports Python 3.12.16, Codex CLI 0.169.0, station dependencies, 48 backend tests, 45 client tests, TypeScript 7.0.2 compilation and HTTP checks passed. Existing Node was reported as v24.22.3 by the hardware session. | Inspect and reuse actual paths. These are attributed Intel results, not a fresh hardware verification by this archive. |
| Shared Mac connection | Intel reports launcher registration, HTTPS/MCP reads, saved-note read-back and identical-UUID retry passed. Its existing `start-codex.sh` selects Python 3.12. The Mac subsequently reconciled the pending Intel M02/M08 updates in Notion; both tasks are In progress, with physical acceptance still open. | Source files and binaries are not synchronized by this connection. Notion was unavailable to those Intel sessions; the included sync record and task snapshot distinguish later confirmed writes from historical pending notes. |
| Intel cameras | M08 handoff reports earlier individual/concurrent RGB preview tests and native D415 RGB/depth/IR frames. Exact results and limits are below. | Images/reports remain Intel-local. Reconcile camera ownership and current devices; the Morph camera adapter/live stream is still absent. |
| Intel robot | Prior expected motor IDs failed PING/READ; latest reported USB inventory had one of two controllers absent. Read-only discovery code was written and tested with a fake bus. | Discovery was not physically run. Motor setup, identities, calibration, teleoperation, demonstrations and learned autonomous cycles remain unverified. |
| Required cloud providers | Architecture and exact intended services are documented; prior Mac checks lacked configured credentials. | No successful real provider integration is established by the included application evidence. Check the actual Intel account/environment without exposing credentials. |

Canonical evidence: [backend verification](HachingJunction/station/VERIFICATION.md), [client/dashboard verification](HachingJunction/station/web-client/VERIFICATION.md), [M15 handoff](HachingJunction/context/notes/084fda51-5ff5-48d2-b547-134f8fedeb97.json), [Intel software handoff](HachingJunction/context/notes/bcffdadc-67d4-420e-b9a3-ed4a79415783.json), and [Intel hardware handoff](HachingJunction/context/notes/588a6522-04e1-42f1-a05b-8231fcef737c.json).

Older documents may still contain time-qualified descriptions of dashboard source being unknown, M15 waiting, or the Intel host being uninspected. Those statements describe earlier snapshots. Use this update, current source, the evidence above and any later confirmed notes for those facts; retain the historical documents rather than silently erasing provenance.

## Preserve and resume the real Intel hardware work

The reported host is `intel-XPS-16-DA16260`. The latest included hardware session observed at `2026-11-14T18:48:26.614929+00:00`, saved on the Mac at `2026-11-14T19:02:52.653622+00:00`. These are different observation and receipt times. Inspect current host state before acting.

- Existing Studio was reported healthy, with no projects or active runtime sessions at that check.
- USB inventory at `2026-11-14T18:41:22.572916+00:00` saw controller `5AE6075066`; controller `5B91030668` was absent from USB/sysfs despite an old `ttyACM1` node remaining in the container. Do not select a controller using the stale device node alone.
- Earlier checks opened both controllers but got no status packets from expected motor IDs 1–6 at 1 Mbaud, using PING and direct model/voltage READ. No motion, calibration or motor configuration was performed in those checks.
- The Intel agent added a `--discover` mode to an audited SO-101 read-only probe: eight supported host baud rates, broadcast PING/model READ, timeout and disconnect without torque change. Ten fake-bus software tests passed. This mode **has not been executed physically**. Locate and review the actual existing probe instead of recreating it from this description.
- The user already said they do not know whether initial motor setup was done. Do not repeat that question. Physical roles are now corrected by the owner: leader `5B91030668`, follower `5AE6075066`; use [the current Junction connection map](../../robot-connections.json). Earlier missing-controller observations are historical. Coordinate with the user before any new hardware operation instead of repeating the resolved role question.
- Earlier three-camera previews reportedly passed individually and concurrently at 640×480, approximately 29–30 FPS, with 4.952 seconds overlapping delivery. Native D415 RGB/depth/IR-left/IR-right each delivered 149 unique frames in 5.0065 seconds, with no measured gaps/timeouts. Depth unit was approximately 0.001 m; 89.56% nonzero depth is coverage, not accuracy. Original images and numerical reports remain Intel-local and should be inspected before using them as submission evidence.
- Studio currently carried RGB in preview/recording according to that note. Metric-depth recording would require additional work if the selected workflow needs it; do not add it merely because a depth sensor exists.

Finish current inventory/communication and ownership checks before motor setup or calibration. Follow the supplied SO-101 hardware procedures and operator-approved workspace/stop behavior. Do not reset motor IDs, baud rates, torque settings or calibration as a speculative connection fix.

## Implementation map: build on these components

| Path | Responsibility and next use |
| --- | --- |
| [Station README](HachingJunction/station/README.md), `station/morph_station/models.py`, `schema.sql`, `store.py` | Canonical persisted records and shared definitions; extend compatibly when live execution needs new fields. |
| `HachingJunction/station/morph_station/api.py` | Authenticated record boundary. `POST /api/v1/records` ingests validated records; evidence/session/correction endpoints exist. This is not a dispatcher. |
| [StationClient](HachingJunction/station/web-client/README.md) | Typed API reads, coherent snapshot/export, event reconnect and source/session selection. Maintain one authoritative state across views. |
| `morph-station/server.ts`, `server/stationProxy.ts` | Local UI host and explicit GET-only proxy; token stays on the server. Add only deliberately designed/validated write routes for M16/M20. Do not turn it into a generic proxy. |
| `morph-station/src/services/stationClient.ts`, `m06Projection.ts` | Canonical data adapter/projection. Preserve exact relationships, nullable unavailable fields, request-versus-command distinctions and backend metric denominators. |
| `morph-station/src/App.tsx`, `src/components/` | Existing views, cycle trace, source/session selector and UI. Inspect actual filenames before editing. Preserve the owner's design and extend the current app. |
| `morph-station/src/domain/` | Retained prototype only; its tests/types are isolated. Do not reactivate it as a fallback for live records or provider access. |
| `HachingJunction/setup/` | Prepared platform-specific setup/lockfiles and checks. Reuse the actual installed Intel profiles before considering installation. |

The current `/commands`, voice-token/utterance and camera-stream routes report unavailable. UI movement, speech, corrections and replay controls are disabled where their implementation is absent. A healthy records API is not a connected robot. A new real adapter must map actual Studio/controller/camera events to stable session/cycle/attempt/frame/inspection/execution/outcome IDs, preserve event/receipt timestamps, deduplicate retries and supply independent confirmations. Prove that boundary with software and real-device evidence before enabling control buttons.

## Execution plan through completion

The stable task IDs and canonical Notion links are in [PHYSICAL_AI_TASK_PLAN.md](HachingJunction/PHYSICAL_AI_TASK_PLAN.md). Read each actual Notion acceptance checklist when access is available; otherwise use the included [M01–M24 task snapshot](HachingJunction/context/notion-snapshot/README.md), whose index records its capture time. The following is an operational continuation plan; do not infer completed prerequisites from task numbers or a previous intended status. M08 is In progress because actual diagnostic/camera work happened, not because all M07 prerequisites or M08 acceptance criteria were confirmed.

| Stage / tasks | Work and dependency gate | Acceptance evidence to retain |
| --- | --- | --- |
| M01 — mentor decisions | Resolve the conflicting 30/30/20/20 versus 25/20/20/20/10/5 rubrics, ACT/SmolVLA expectations, cloud supervision/recovery, Studio task switching, supported voice goal and physical confirmation/stop procedure. Verify current official deadlines/submission rules. | Dated organizer/mentor answers and source links; preserve unresolved distinctions. |
| M02 — Intel identity/inventory | Finish actual host/OS/CPU/GPU/NPU and connected hardware inventory. Reuse reported software/reporting checks; close only against the full task checklist. | Host/device identities, versions, usable paths, ownership and explicit unavailable/failed checks. |
| M03 — Nemotron access | Verify exact required model with one real frame request and account endpoint. | Actual model ID, sanitized request/response, frame ID, latency/error and meaningful visual result. |
| M04 — Gemini access | Verify Decision 1 fixed-choice request/response; do not use a generative substitute. | Actual model/API, permitted options, returned probabilities/selection, latency/error and access result. |
| M05 — speech access | Verify Scribe v3 Live, actual microphone, finalization and deduplication with a complete spoken utterance. | Actual transcript/model, utterance ID, timings/errors; no command from provisional/enrichment events. |
| M06 — existing foundation | Already complete for software scope. Reuse it and run relevant regression tests when changing its behavior. | Existing reports plus evidence for any new modifications; no reclassification as physical success. |
| M07 — target runtimes | Depends on M02. Inspect existing Studio/Anomalib environments and validate the needed target execution path. Install missing pieces only; keep environments separate. | Real imports/CLI/inference checks, dependency validation and actual supported device results. |
| M08 — workcell | Depends on M07. Resolve current controller issue, verify camera/motor identities, then required setup, calibration and supervised teleoperation under actual procedures. | Camera frames, observed permitted motion, calibration/configuration provenance, stop behavior and remaining faults. |
| M09 — pilot/evaluation contract | Depends on M01/M08. Freeze object labels, training/tuning/evaluation split, scene, one supported recovery and one spoken goal change. | Versioned protocol/data inventory, independent labels and comparison rules. |
| M10 — learned skills | Depends on M09. Record the team's demonstrations through Studio and train the selected manipulation policy/skills. | Episodes, model/configuration IDs, training results, usable checkpoints and held-out physical checks. |
| M11 — real defect detector | Depends on M09. Train Anomalib on real relevant images and tune/evaluate without leaking held-out data. | Data split, actual anomaly scores/maps/thresholds, reference-labeled quality and saved model/export. |
| M12 — validated local dispatcher | Depends on M01/M06. Implement permitted task menu, preconditions, state/goal versions, deadline/freshness checks, idempotent execution and acknowledged control protocol. | Tests for stale/duplicate/unsupported/late input and interruption; explicit requested/sent/acknowledged/finished/verified distinctions. |
| M13 — live adapters/inference | Depends on M07/M10/M11/M12. Connect actual camera, detector, learned policy and controller to the dispatcher and record ingestion. Verify chosen Intel/OpenVINO workloads. | Same-object/frame links, actual device/model output, command-to-record correspondence, timings and observed results. |
| M14 — fixed-sequence baseline | Depends on M13. Execute pickup → grasp verification → presentation → inspection → correct-bin placement → independent confirmation. | Complete saved good/defective cycles, including failures and unknowns, attempts, evidence and full duration. |
| M15 — existing UI | Done on Mac. Finish Linux acceptance of the transferred actual React app; preserve one canonical record store and explicit sources. | Build/tests and actual browser checks on Intel, empty Live or genuine live data, simulation separation and no movement from reads. |
| M16 — history/corrections/replay | Depends on M06/M15. Add validated label/correction forms, late confirmations, complete filters/pagination and explicit read-only historical replay. | Prior/new values, author/time/reason, revision conflicts, duplicate submission and replay without new records/counter increments. |
| M17 — visual supervision | Depends on M03/M12/M14. Add substantive Nemotron observations at defined task checkpoints. | Real frame-linked inputs/outputs affecting the available decision context; observations remain distinct from reference labels. |
| M18 — adaptive recovery | Depends on M04/M12/M14/M17. Let Gemini select from current permitted tasks and demonstrate one bounded learned recovery. | Fresh validated decision, actual recovery execution and confirmed result, retained preceding failure and cloud wait in cycle timing. |
| M19 — spoken goal change | Depends on M05/M12/M18. Finalized ElevenLabs utterance → fixed-choice supported goal → local commit → fresh snapshot → permitted task selection. | One real spoken goal change, deduplicated utterance, goal version/boundary, queued/active/rejected UI and observed effect. |
| M20 — live integrated dashboard | Depends on M15/M16/M17/M18/M19. Expose actual camera, model and dispatcher state/controls through the existing UI. | Current-object trace across all three views, analyzed snapshot versus live video, truthful availability, acknowledged actions and physical outcomes. |
| M21 — resilience | Depends on M12/M16/M18/M19/M20. Exercise duplicate events/commands, retries, stale evidence, timeout, interruption, disconnect/restart, unknown outcomes and corrections. | Saved success/failure/aborted/unverified cases, unchanged counters after replay/reconnect, safe resume and audit integrity. |
| M22 — Intel optimization | Depends on M13/M14. Compare supported baseline/optimized execution on comparable inputs and configurations. | Model/device/precision, sample counts, timing boundaries, quality/parity and unsupported paths stated explicitly. |
| M23 — evaluate behavior | Depends on M14/M18/M19/M20/M21/M22. Compare fixed-sequence versus adaptive performance using the frozen protocol. | Persisted results, first-pass and recovered reliability, all denominators, latency components and unsuccessful cases. |
| M24 — final demo/submission | Depends on M23. Assemble the working demonstration and required evidence, verify current submission rules, prepare all artifacts and complete the owner-authorized submission workflow. | Reproducible launch, recorded demonstration, traceable results, sponsor-specific evidence and actual submission receipt when submitted. |

Run independent lanes in parallel where ownership allows: provider access and mentor clarification; hardware/data/model work; dispatcher; M16; later optimization and adaptive integration. Only one process/operator may own an arm or camera resource at a time. The suggested split was Intel for hardware/runtime/Studio/adapters/baseline and Mac for M16; this is not evidence that a Mac agent is currently working on M16. Check current notes/task ownership before overlapping edits. If no one owns a needed software task, continue it or delegate explicitly within the current authorized project.

The immediate useful milestone is **the real React UI running on Intel with persisted simulation, plus a precise current motor blocker and next action**. Then target the first recorded physical baseline; do not delay it for optional features. Start provider access checks early so unavailable required models are exposed before the demo integration stage.

## Record and UI invariants

- One independent started object task is one cycle. A failed grasp followed by a successful retry is one cycle, two attempts and one recovered success. Additional inspection does not itself create another physical attempt.
- Separate prediction correctness, commanded physical execution, observed physical success and end-to-end correctness. Independent reference quality plus actual destination is required for confirmed correct sorting.
- Primary rate: confirmed correct cycles / all finished cycles. Finished includes failed, aborted and unverified; show these counts. Exclude in-progress. Physical rate uses confirmed successful attempts / all finished attempts. Keep first-attempt, recovered, retry and extra-inspection counts separate.
- Detection quality includes only reference-labeled checked examples, with checked and total counts visible. With no eligible records, show `No data yet`; never invent 0% or 100%.
- Use stable IDs for sessions/cycles/attempts/events/frames. Reconnects, refreshes, duplicate messages and replay cannot create repetitions. Late confirmations amend the original record; manual corrections preserve previous/new values, author, timestamp and reason.
- Live, simulation and replay remain distinguishable. Exclude simulation from hardware reliability by default. Display existing records during replay.
- Preserve actual inputs/outputs, observations, errors, timestamps, confirmation source and final outcome. Do not invent reasoning, sensor telemetry, confidence percentages, state versions or command-sent timestamps.
- Keep analyzed evidence alongside actual live video with age/connection state. Missing telemetry is unavailable. Separate inference, motion, verification and full-cycle timing; include awaited cloud time.
- Timestamps must be timezone-qualified. The current dashboard labels Europe/Ljubljana; Finland is a different timezone. Some Intel notes report a `-08:00` host offset. Retain originals and normalize deliberately; never treat receipt time as observation time.

## Shared context, Notion and handoff discipline

Use [context/INTEL_CODEX.md](HachingJunction/context/INTEL_CODEX.md) as the full protocol. The existing private `morph-intel-pairing/` directory and Intel `start-codex.sh` are not bundled here. Locate them in the existing transfer workspace; inspect and reuse them with the chosen project path. The included `context_mcp/connect_intel.py` is source, not connection credentials. Do not overwrite a working `morph_context` configuration or silently substitute an Intel-local context store for the shared Mac endpoint.

Python 3.14.4 reportedly rejected the existing certificate with `Missing Authority Key Identifier`; Python 3.12.16 passed with TLS certificate and hostname verification enabled. Use the working Python 3.12 launcher while resolving any certificate issue properly. Do not disable TLS verification.

At session start, read shared instructions/current documents and paginate all relevant notes. After meaningful changes, tests, blockers and before finishing, save a concise English note with a stable new UUID, task/session/checkpoint IDs, observed time, exact work, verification class, evidence, remaining work and Notion synchronization state. Save outgoing payloads in the local outbox, use the same UUID/payload for retries, read back the shared record, and retain the receipt. Publish corrections as new notes referencing the old ones.

Notion is separate. Use existing M01–M24 pages; set In progress when work begins, save evidence/results, mark Done only on fulfilled acceptance, read back the result and promote dependents only after all prerequisites pass. When unavailable, retain the full intended update in `HachingJunction/NOTION_SYNC.md` and include it in the shared handoff for an active Mac session. Do not create duplicate tasks or claim an unsuccessful write succeeded. The Mac reconciled the included Intel M02/M08 pending notes during this packaging session; check the saved sync record before retrying historical entries. Use the included task snapshot for acceptance criteria while offline, and record that its status is a dated snapshot.

The shared MCP transfers text notes, not source patches, datasets, images, weights or account access. Transfer required files separately with a manifest/hash and review differences on the receiver. Keep local Intel artifact paths explicitly labeled as Intel-local until transferred. Do not use a bulk sync to overwrite the Mac's newer frontend or Intel's hardware changes.

## Completion and genuine blockers

Continue until each required capability has demonstrated evidence or a specific external blocker needs the owner/mentor. A working UI, build, package, camera preview or controller acknowledgment alone is not project completion. The final evidence must show the learned physical cycle, Anomalib quality decision, supported Intel execution, meaningful Nemotron input, Gemini selection/recovery, actual ElevenLabs speech goal change, reliable persisted history and measured comparison.

When blocked, state the exact failed operation, sanitized error, scope affected, evidence, required person/action and work that can continue. Do not silently swap a required provider/model, fabricate a successful physical result, repeatedly ask answered questions or call a task Done merely because the session is ending. Keep the owner informed concisely. Prepare the concrete final artifacts before asking for any final external approval that the receiving environment actually requires.

## Full context and source map

| Read when needed | Content |
| --- | --- |
| [Project instructions](HachingJunction/AGENTS.md) | Mandatory integrations, authoritative metric definitions, evidence/robot rules and standing Notion workflow |
| [Intel challenge brief](HachingJunction/IGNITE_INTEL_PHYSICAL_AI.md) | Original scope, equipment, required technology, sources and conflicting evaluation rubrics |
| [Primary workflow](HachingJunction/PHYSICAL_AI_WORKFLOW.md) | Selected approach, supported voice behavior, implementation stages and acceptance evidence |
| [Orchestration](HachingJunction/PHYSICAL_AI_ORCHESTRATION.md) | Fixed-choice Gemini API model, Nemotron role, speech boundaries, local validation and verified reference URLs |
| [Task plan](HachingJunction/PHYSICAL_AI_TASK_PLAN.md) | All canonical task URLs and exact dependencies; initial status table is historical |
| [Captured Notion tasks](HachingJunction/context/notion-snapshot/README.md) | Actual task bodies, acceptance criteria and status at capture time; usable offline and reconcilable with later live updates |
| [Challenge combinations](HachingJunction/PHYSICAL_AI_CHALLENGE_COMBINATIONS.md) | Required sponsor-specific demonstration/submission evidence and model-name discrepancy |
| [Optional extensions](HachingJunction/PHYSICAL_AI_EXTENSIONS.md) | Additional ideas, compatibility and cost; all are subordinate to the selected required workflow |
| [Setup](HachingJunction/PHYSICAL_AI_SETUP.md) and [Junction](HachingJunction/JUNCTION.md) | Prepared platform profiles, software commands, event logistics and source dates; reverify time-sensitive requirements |
| [Dashboard README](morph-station/README.md) and [capability audit](morph-station/IMPLEMENTATION_STATUS.md) | Current actual UI, proxy configuration and implemented/unavailable boundaries |
| [Design handover](HachingJunction/design/morph-handoff/HANDOVER_GUIDE.md) and [contract](HachingJunction/design/morph-handoff/INTEGRATION_CONTRACT.md) | Original visual/interaction reference and data intentions; reference mock data is not physical evidence |
| [Curated chat context](HachingJunction/context/CHAT_CONTEXT.md) and [context manifest](HachingJunction/context/CONTEXT_MANIFEST.json) | Earlier discussions, reviewed coverage, superseded ideas and historical access issues |
| [Later conversation and transfer context](HachingJunction/context/DASHBOARD_HANDOFF_CONTEXT.md) | Owner's dashboard source, implementation delivery, current ZIP request, newer Intel observations and cross-computer continuation |
| [Shared-context setup](HachingJunction/CONTEXT_SHARING.md), [reporting protocol](HachingJunction/context/INTEL_CODEX.md), [notes](HachingJunction/context/notes/) | Cross-computer connection, attributed later results, synchronization limits and required progress reporting |

The earlier Notion access trouble is historical. The authorized project destination is **Junction-Agents-Board**, with the existing Morph agreement and tasks linked by the task plan. Do not return to the old failed `Projects-Agents-Klemen` destination. The owner wants short chat updates, complete English project documentation and evidence-backed task closure.
