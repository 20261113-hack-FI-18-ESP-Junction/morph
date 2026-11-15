# Project guide for contributors and agents

## Mandatory Mac reporting for every agent

**Owner instruction, November 14, 2026: every agent working on this Junction project, including every delegated subagent, must report its work to the shared Mac server.** This applies across this directory and all subdirectories, including hardware work, documentation, reviews, tests, the imported Morph projects, and the dashboard. Updating a local Markdown file or replying to the user or parent agent does not fulfill this requirement.

- Follow the [Intel reporting protocol](morph-intel-transfer/morph-context/context/INTEL_CODEX.md) and its [six-field payload template](morph-intel-transfer/morph-context/context/templates/PROGRESS_NOTE.json). Publish at session start, after meaningful changes/tests/findings/decisions, immediately on blockers, and before a final answer or handoff. Report actual results and remaining work, with task/session/agent identity, timezone-qualified time, evidence and synchronization state.
- Save the exact payload in the selected project's `context/outbox/<UUID>.json`, call the shared Mac's `morph_context.save_handoff`, then read the saved note back with `read_context`. Compare its UUID and content and retain the confirmation in `context/sync-receipts/<UUID>.json`. Only that verified round trip establishes delivery. For work in the Junction root, use `morph-intel-transfer/morph-context/context/` for the outbox and receipts.
- The parent must pass this rule and designate a reporter when delegating. Every subagent must either publish and return its receipt or provide the parent with the complete attributed update for publication. A parent reporting on a subagent's behalf must include that contribution and verify delivery before its own final handoff; a subagent's local response alone is not delivery. Do not publish the same contribution twice merely because it was delegated.
- If delivery or read-back fails, keep the unchanged payload in the outbox, record the sanitized error, and explicitly report **pending sync**. Retry the same UUID and payload when the connection returns. Continue independent safe work while reporting is unavailable; never claim a local save reached the Mac. A local MCP over an Intel copy is not the shared Mac server.
- Use the existing private pairing and verified connection launcher: `bash morph-intel-transfer/start-codex.sh --check` from this directory; omit `--check` to start a connected Codex session. Agents working in another project must preserve that project's working directory as described in the reporting protocol. Keep credentials out of notes and logs.
- Before the final answer, account for every delegated contribution and state whether its Mac delivery is **confirmed** or **pending**. Keep Notion status separate and preserve any pending task update. A Mac reviewer or scheduled review does not replace the originating agent's duty to publish.

This is a standing project requirement for subsequent sessions and delegation. Re-read it when resuming work; this document does not itself install an automatic uploader or verify another agent's compliance.

## Periodic incoming Mac updates

Owner instruction, November 14, 2026: check the shared Mac MCP periodically for the colleague's updates and update the relevant local files. The configured polling interval is five minutes. See [MAC_SYNC.md](MAC_SYNC.md) for the watcher, its actual running state, and the review workflow.

- At the start of work, before choosing a new implementation step, and before a final handoff, read [MAC_UPDATES.md](MAC_UPDATES.md) and its pending changes. During sustained work, review new arrivals at least every five minutes when practical.
- Fetching a note is not the same as reconciling it. Read the complete relevant note/document, resolve dated corrections against current local evidence, update the affected English files, and record the reviewed path/hash in `mac-sync/reviewed.json` only after that review.
- The watcher may update only explicitly configured shared guides when its recorded baseline proves the local file has not diverged. Conflicting local edits and initial differences stay queued for an agent to review. It does not replace source code, robot configuration, contributor instructions, or immutable evidence automatically.
- Preserve the current corrected arm identities and the user's ownership of arm diagnostics. A colleague's status report does not itself establish a new physical test, available Intel credentials, or completed acceptance.
- Report incoming changes and their local reconciliation through the existing Mac reporting protocol. Keep polling/read status, review/application status, and outgoing delivery receipts distinct.

## Required language

**Write all project files in English.** This applies to documentation, code comments and docstrings, error and status messages, generated report prose, configuration descriptions, image annotations, UI labels, test descriptions, and future updates. The language used in a conversation does not change this requirement. Translate existing authored non-English text when working on it.

Preserve device identifiers, protocol values, numeric measurements, source code identifiers, raw sensor images, and original machine output as evidence. Translate explanatory prose and generated labels, not the underlying measurements. Do not create new Slovenian versions of project documents or image annotations.

## Read first

1. [PROJECT_STATUS.md](PROJECT_STATUS.md) is the consolidated handoff: verified results, limitations, unresolved questions, and the next actions.
2. [ROBOT_GAMEPLAN.md](ROBOT_GAMEPLAN.md) describes the development sequence and historical diagnostics.
3. [camera-check-2026-11-14/README.md](camera-check-2026-11-14/README.md) contains camera measurements, artifacts, and the current depth integration limitation.
4. Read the relevant script before running it. Hardware discovery, image capture, motor reads, motor configuration, calibration, and commanded movement are different operations.

The imported [Morph project guide](morph-intel-transfer/morph-context/AGENTS.md) and [Intel handoff instructions](morph-intel-transfer/morph-context/context/INTEL_CODEX.md) provide the broader workcell and team context. Read them before changing that project. `morph-intel-pairing/` contains private connection material, not application source; do not print or include it in reports. Preserve other sessions' updates to the imported workspace.

## Project purpose and locations

**Current three-host ownership, received November 15, 2026 UTC:** Klemen's Mac owns dashboard/analytics; Jose's Mac owns interaction, coordination and expected voice input; Intel owns training, physical execution and authoritative records. Jose-to-Intel uses the NVIDIA tunnel supplied by the other team; Klemen-to-Intel uses the existing shared MCP. ElevenLabs is an undecided provider choice, superseding earlier mandatory-selection wording below; preserve its optional adapter and dated evidence. The current Intel station has no integrated mission/control API, dispatcher, skill registry or Studio execution adapter. Do not mistake its 503 command/voice routes or record-session APIs for physical control. See the [Jose takeover report](reviews/jose-takeover-20261115T022548Z-00e34e99/README.md) and its received, hash-verified architecture source. Source-transfer authorization does not authorize robot actions, provider calls, tunnel setup or service restarts.

The user is building a LeRobot workflow with one SO-101 leader and one SO-101 follower: verify hardware, calibrate, teleoperate, collect demonstrations, train a policy, and evaluate it on the follower. NVIDIA Nemotron is part of the user's intended system. Its eventual role and integration must be explicit; it is not yet connected to robot control.

The imported Morph plan specifies Duplo inspection/sorting with Studio learned skills, Anomalib, supported OpenVINO inference, Nemotron visual observations, Gemini online option selection, and ElevenLabs voice input. M03/M04 are Done for their access scopes. On November 14, 2026 at 21:09 UTC, this Intel restored the supplied private provider configuration and verified actual minimal requests to Nemotron through Verda, Gemini Decision 1, Gemma and generic Gemini. ElevenLabs still lacks a credential; microphone/Scribe acceptance remains open. The approved Gemma work is an isolated evidence analyst in Quality & history, contributing only a partial scope to M20/M21/M23/M24. Preserve the distinct provider responsibilities. An access check or software/simulation result does not establish live workcell or physical acceptance. See the [Intel provider evidence](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/verification/intel-gemma-20261114/provider-setup.json) and [analyst integration contract](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction/station/ANALYST.md).

The Mac approval report `028a574e-76f4-4874-928f-b7f20bb02aa9`, saved at 21:02:50 UTC on November 14, added Gemma for saved cycle explanations and bounded session comparisons. Intel session `f191d039-8f71-48ba-bb6a-91e15bd096c6` implemented the isolated backend/API/UI and verified actual hosted replies plus saved-simulation browser behavior. M20/M21/M23 are In progress with original criteria and dependencies retained; M24 receives a separately tracked demonstration contribution. Read the [current analyst evidence](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/verification/intel-gemma-20261114/README.md), including semantic limitations and actual task synchronization, before extending it. Coordinate edits in the shared dashboard folder and distinguish its existing running processes from the separate analyst verification preview. Gemma remains separate from Gemini orchestration and cannot dispatch tasks or alter canonical outcomes.

- Working and handoff directory: `/home/intel/Documents/Junction`.
- Existing Physical AI Studio source: `/home/intel/physical-ai-studio`.
- Running application container: `physical-ai-studio-xpu`.
- Native Studio with the registered Morph SO-101 Workstation: `http://127.0.0.1:3000`. The two robot names/types were corrected by serial identity at 20:46 UTC on November 14, 2026; UUIDs and complete payloads were preserved. See [the correction report](morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/verification/intel-studio-role-correction-20261114T204500Z/README.md).
- Separate container Studio address: `http://127.0.0.1:7860`; it had no registered projects at the correction check. Inspect both instances before concluding that Studio has no active sessions or saved configuration.
- The Junction directory is not currently a usable Git repository. Do not claim commits or a clean Git state without verifying them.

For changes to the Studio source, read its own `AGENTS.md` and relevant repository instructions. Preserve existing user changes, including the Docker localhost binding and compose backup. Follow the actual filesystem permissions of the session; a writable Junction directory does not imply write access to the separate Studio checkout.

## Confirmed context: do not ask again

- Both arms are SO-101, physically connected over USB.
- Each arm's controller has its own connected motor power supply, confirmed by the user.
- The USB hub has no external power supply. This alone does not establish the cause of a fault.
- Neither arm has been calibrated; the user explicitly confirmed this.
- Treat that as the earlier owner confirmation. A read-only native Studio check at **2026-11-14T22:31:55Z** found six stored follower calibration entries and a null leader calibration. Stored values have unverified provenance and do not establish physical calibration acceptance. Preserve them, reconcile their origin with the owner, and validate the intended arm before use or modification. See the [current physical execution record](reviews/mac-offline-evidence-20261114T222550Z-8941c757/physical-execution-record.md).
- Motor ID/baud-rate setup is separate from calibration. The user answered that they are not sure whether it was done; record it as unknown rather than asking the same question again.
- The user corrected the previously reversed serial assignment on November 14, 2026: **leader `5B91030668`**, **follower `5AE6075066`**. This supersedes all earlier role mappings. Use [robot-connections.json](robot-connections.json) as the current map; retain historical USB/probe evidence with its actual serial numbers and never infer roles from `ttyACM0` or `ttyACM1`.
- At the latest owner update, the follower works according to the user and the user is investigating leader communication. Treat this as a user report, not new independent motor/calibration/teleoperation evidence. The user owns current arm diagnostics; coordinate before opening either port.
- RealSense D415 native SDK serial: `243622061552`. The observed USB descriptor identifier `344223023467` is different; use the SDK serial for native capture.
- RealSense, the webcam, and an additional USB2.0_CAM1 have passed short image-transfer checks. The additional camera's image is substantially out of focus.

Continue authorized, reversible work without repeatedly requesting confirmation of these facts. Ask focused questions only when missing physical information or a task choice actually affects the next operation.

## Hardware operation rules

Use stable device identity and recheck current paths before opening hardware. Only one process should own a serial port or a native camera capture pipeline at a time. Inspect active application sessions before restarting the container or taking exclusive ownership of a device.

`scripts/check_robot_usb.py` only inventories metadata. It does not open serial ports or capture frames. Camera scripts do capture images and must close their clients/pipelines. A JPEG preview verifies RGB delivery; it does not by itself verify depth or recording.

The existing motor probe is audited for LeRobot `0.6.0`. Its low-level path uses `FeetechMotorsBus.connect(handshake=False)` and must close with `disconnect(disable_torque=False)` in a `finally` block. Default disconnect behavior writes registers. Opening/reopening serial ports can change DTR/RTS. Keep diagnostic operations bounded and record failures honestly.

Do not use the high-level SO101 plugin's connect/disconnect or Studio's Identify action as passive diagnostics: the reviewed implementation can write motor settings or cause movement. Motor setup writes IDs and baud rates; do not run it on a fully connected arm as a speculative fix for missing responses. Follow the documented one-motor setup procedure when setup is actually required.

Before calibration or commanded movement, establish the intended arm, the required physical setup, an operator at the hardware, and the applicable stop method and motion limits. Do not infer that successful USB enumeration proves motor communication or that successful motor reads prove safe calibration.

## Camera and depth rules

- Prefer the native RealSense driver over its duplicate UVC entry. Internal Intel IPU7 video nodes are not extra external cameras.
- The verified starting profile is 640 × 480 at 30 frames/s.
- Preserve raw Z16 depth and its scale factor. Convert to meters using `raw_depth * depth_units_m`; zero means unavailable depth. A colored depth visualization is a display artifact, not a substitute for metric depth data.
- Equal RGB/depth dimensions do not imply pixel alignment. Camera-to-robot coordinates require an additional known or calibrated transform.
- Allow publisher shutdown to finish before reopening the same camera. The diagnostic preview script defaults to a 10-second release wait because a previous rapid reopen timed out. This is an operational precaution, not a proven application bug fix.
- The inspected Studio version previews and records RGB. Native depth capture works, but Studio depth recording remains unimplemented. Verify the capture, transport, preview, storage, and metadata paths before claiming depth integration is complete.

## Evidence and validation

Keep previous successful and failed diagnostic reports. Use new output directories for new capture runs. Do not overwrite original frames or numeric reports during translation. Derived overview images may be regenerated from the originals with English labels.

Distinguish measured results, source-code observations, user confirmations, hypotheses, and planned work. Include dates and relevant versions. Short tests establish only what they measured; depth coverage is not depth accuracy, preview FPS is not necessarily native FPS, and an XPU tensor test is not a successful policy training run.

Use the existing environment and dependencies when suitable. Run checks appropriate to the change. For documentation and derived illustrations, validate links, identifiers, JSON readability, English text, and rendering. For hardware or data-path changes, verify meaningful behavior and cleanup; do not rerun hardware tests merely because prose changed.

At the end of a material work session, update `PROJECT_STATUS.md`, the relevant technical report or gameplan section, and any affected connection/configuration notes. Record unresolved issues and a concrete next step. Keep all new and updated file content in English.

For imported Morph task reporting, preserve a local outbox payload when the shared Mac/Notion connectors are unavailable. Never label local files as remotely synchronized without a confirmed write and read-back. The present camera work contributes to M08, whose full acceptance also requires calibration and teleoperation.
