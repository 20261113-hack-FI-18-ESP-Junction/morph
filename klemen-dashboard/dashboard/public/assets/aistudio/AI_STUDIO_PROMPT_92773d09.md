# Morph — Google AI Studio build prompt

**Handoff prepared November 14, 2026.** This is a prompt for building the proposed product, not a claim that the dashboard, model connections or robot already work. Use it with the reference package. The screenshots show illustrative simulation data.

## How to hand this to the builder

Follow [HANDOVER_GUIDE.md](HANDOVER_GUIDE.md) for the exact sequence. Give AI Studio the eight reference images below, the graphic assets, [DESIGN_SPEC.md](DESIGN_SPEC.md) and [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md). Include [PROJECT_AUDIT.md](PROJECT_AUDIT.md) when explaining the current implementation status. Keep these files together when exporting the project or sharing it with the teammate. [AI_STUDIO_MASTER_PROMPT.txt](AI_STUDIO_MASTER_PROMPT.txt) contains only the master prompt, ready to copy in full.

| Reference | Purpose |
| --- | --- |
| [01-live.png](references/01-live.png) | Main operational hierarchy, camera and current object |
| [02-system.png](references/02-system.png) | Robot, component and model status |
| [03-quality.png](references/03-quality.png) | Reliability, reference-label quality and history |
| [04-cycle-detail.png](references/04-cycle-detail.png) | A complete cycle trace and evidence |
| [05-stop.png](references/05-stop.png) | Software-stop request and acknowledgment states |
| [06-design-system.png](references/06-design-system.png) | Typography, palette, spacing and graphic treatment |
| [07-disconnected.png](references/07-disconnected.png) | Empty hardware state and unavailable controls |
| [08-mobile.png](references/08-mobile.png) | Responsive reflow and reachable stop control |

Paste the following brief into AI Studio. The staged follow-ups at the end keep implementation reviewable. For live hardware, export and run beside the Intel station API, or deliberately implement a secured bridge; a hosted preview does not automatically reach the robot or the station's `localhost`.

---

## Paste-ready master prompt

Build **Morph**, a professional dashboard for a voice-directed Physical AI quality-inspection and sorting station. The physical subject is a **Duplo brick** handled by an **SO-101** robot. The application must explain what the station observed, measured, selected, executed and independently verified for each object. Use the attached references as a visual specification and the attached integration contract as the behavioral specification.

The current project contains planning and setup work. Robot calibration, trained skills, actual camera characteristics, cloud-model access and successful autonomous cycles remain unverified. Implement truthful capability states: **Proposed**, **Implemented**, **Verified**, plus current connection/operation state. A working UI does not verify a robot integration.

### 1. Visual direction

Create a restrained **Tech Renaissance** interface inspired by Junction's combination of historical scientific imagery and contemporary engineering. It should feel like a precise instrument with an editorial identity. Keep all interface text and project documentation in English.

Use these tokens: application `#080808`; panels `#101010`; borders `#252421`; primary text `#F2EEE6`; secondary text `#A7A39A`; bronze accent `#C7A477`; confirmed-success sage `#91B99C`; warning `#D6B775`; error text `#E36363`. The prominent stop action uses `#B72F35` with white text. Status meaning must also be expressed with text or icons. Do not introduce blue-black panels, neon glows or decorative gradients that compete with evidence.

Use **Inter** for interface text and **Space Mono** for IDs, timestamps and numeric readings. Use **Cormorant Garamond italic** only for an occasional restrained display heading, never operational labels. Preserve legible body text and tabular numeric alignment. Favor whitespace, clear alignment, small radii and thin separators over nested cards or dense badges.

At desktop width use a 212px sidebar, an 84px ornamental masthead at the absolute top, a 76px operational header and 32px content padding. Reflow gracefully on smaller screens. Keep the red stop action accessible without searching. The masthead contains the supplied orbital graphic with very slow rotation and a subdued engraving near the upper right. Honor reduced-motion preferences. The engraving is decoration, never camera evidence; omit the large Copernicus side card from the old concepts. Use the supplied Morph mark and wordmark consistently.

### 2. Product structure

Provide three real navigation destinations: **Live inspection**, **Robot & system**, and **Quality & history**. A cycle opens a detail drawer with a full-screen option. A software-stop status dialog is available across all views. Every view reads the same underlying records.

The header shows session, source/view mode, connection state and relevant controls. Distinguish **Live**, **Simulation**, and **Replay** persistently. Default the hardware view to disconnected/empty until connected. Provide an intentional **Open simulation** action; never present seeded fixtures as hardware results. Replay reads an existing session and retains its original source mode.

### 3. Records before counters

Use React and TypeScript with a typed `StationClient` boundary, a simulation adapter, and a real station adapter. Follow the proposed API and types in `INTEGRATION_CONTRACT.md`; those are Morph endpoints to implement, not existing vendor endpoints. Prefer one authoritative local station API, transactional SQLite persistence and immutable evidence files. Keep specialized Studio and Anomalib environments separate. If the AI Studio preview uses its server runtime, keep that adapter replaceable rather than creating a competing production source of truth.

Persist sessions, cycles, attempts, inspections, frames, voice utterances, goals, decisions, skill executions, confirmations and corrections with stable IDs and timestamps. Keep event occurrence time separate from receipt time. Preserve frame/object/cycle association, state and goal versions, model/configuration metadata and record revisions. Use `null` for absent telemetry and render **Unavailable**.

A cycle is one started task for one object. A retry after a failed physical execution creates another attempt in the same cycle. An additional inspection does not automatically create an attempt. Several learned skill calls can belong to one attempt. A new independent test of the same brick creates a new cycle.

### 4. Live inspection

Lead with the current object and its process. Make the camera the largest functional area, with available-camera selection and capture time, frame age, actual FPS and connection state. Keep the exact analyzed snapshot beside or immediately below the stream. Show anomaly overlays on their source frame; never attach an old map to an unrelated moving frame. Frozen footage stays visible with a clear stale state.

Show object/cycle IDs, active phase and elapsed phase time, attempt number, anomaly score, threshold, classification and planned destination. Display **Anomaly score**, not confidence percent. Keep reference quality, model classification, commanded destination and observed destination distinct. The illustrative camera fixture may be a Duplo schematic explicitly marked **Simulation**; replace it with actual frames only when the camera adapter works.

Use the real process order: observe → pick → verify grasp → present → inspect → choose response → place → verify outcome. Visually group phases if needed while retaining the exact active phase and the failure location. Present the latest important events in a compact list, with full history one click away.

Expose four concise metric summaries: confirmed correct cycles/all finished cycles; confirmed successful attempts/all finished attempts; first-attempt/recovered behavior and streak; full-cycle time with sample count. Keep failed, aborted, unverified and in-progress totals visible in an expandable summary, along with retries and additional inspections. The user must understand the current object without leaving this view.

### 5. Make each model's contribution observable

Use **ElevenLabs Scribe v3 Live (`scribe_v3_live`)** for deliberately captured speech. Show the original transcript, selected supported goal, effective boundary and queued/active/rejected state. Keep microphone activation intentional. Partial transcripts are display-only. Assemble committed segments into one complete utterance, finalize it once, and deduplicate by utterance ID. Later timestamp enrichment updates that transcript and must never issue another command.

Use **Anomalib** for the frame-linked anomaly score/map, threshold and classification. Use **NVIDIA Nemotron 3.5 Super VL** for frame-linked visual observations, uncertainty and separately labeled hypotheses. The published reference is `nvidia/nemotron-3.5-super-vl-120b-a12b`; verify the available endpoint and returned identity with the team's account before marking it connected. NVIDIA hosting alone does not replace this integration.

Use **Gemini Decision 1 (`gemini-decision-1`) through the Decisions API** for a supported goal choice, then a permitted task choice from a fresh snapshot after local goal commit. It returns typed decisions/probabilities with no generated explanation. Do not invent prose reasoning, function-call arguments or a plan. Keep provider answers separate from the local validator's acceptance or rejection.

The local dispatcher checks IDs, state/goal versions, evidence freshness, deadlines, allowed tasks, preconditions, retry limits and execution IDs. It resolves known parameters and invokes an existing Studio-trained policy. Cloud output must never become arbitrary joint commands. Show the selected task, actual policy/version, validator result and execution status. Keep substantive local Studio/VLA/Anomalib/OpenVINO behavior in scope. Blocked provider access remains a visible blocker; do not silently swap providers.

### 6. Controls and outcome truth

Provide **Start session**, **Start cycle**, **Pause after cycle**, **Resume** and a large red **Stop process** action where the real adapter supports them. Label the latter **Software stop**. Starting a session is bookkeeping only. Opening, refreshing, reconnecting or navigating the application must never start movement.

Pause after cycle prevents admission of new cycles after the active cycle reaches its defined end. Show request and acknowledgment separately. A supported urgent stop sends the controller-defined idempotent stop request immediately, then opens the status dialog; the dialog must not delay that request. Do not let a stale UI version block the controller's necessary stop path. If no supported stop operation exists, disable the control and explain why.

The dialog distinguishes **Requested**, **Acknowledged**, controller execution state and **Physical stop verified / Unverified**. It does not invent power-bus, brake or safety-certification claims. Closing it or acknowledging an incident cannot resume movement. Resume remains a separate intentional action subject to actual restart conditions.

For ordinary execution, keep **Command sent**, **Acknowledged**, **Execution finished**, and **Physical outcome verified** distinct. Controller completion alone never establishes physical success. A connection loss preserves the last known state and an unverified outcome. Ending a session must preserve an open cycle's real status.

### 7. Robot & system

Show connection, readiness, active task, calibration and latest error for the robot, cameras, backend, learned policy, Anomalib and required cloud services. Separate deployment location and configured model identity from verification status. Telemetry tables show measured/commanded joints, deviation, units and measurement age when available. Missing currents, temperatures, forces, utilization and device allocation read **Unavailable**. Keep active faults visible in Live inspection too.

### 8. Quality & history

Compute reliability from unique persisted records: correct cycles/all finished cycles, including failed, aborted and unverified; exclude in-progress cycles. Physical execution uses successful attempts/all finished attempts. Every percentage has numerator, denominator, source and scope. No eligible records renders **No data yet**. A failed, aborted or unverified cycle ends a confirmed-success streak.

Keep detection metrics separate. Use independently reference-labeled examples only, with coverage and total population. Define positive as defective: TP defective/rejected, TN good/accepted, FN defective/accepted, FP good/rejected. Highlight defect escapes. Keep review-required classifications separate and document which inspection contributes to each cycle's metric. Extra images cannot inflate the object population.

Provide session/time/outcome/model/object filters and quick filters for failures, retries and unverified results. The cycle drawer shows frames, inspections, decisions, ordered attempts, times, commanded/observed destinations, errors, confirmation sources and final outcome. Reference-label entry and corrections require author and reason; preserve old/new values and time. Late confirmation updates the original record and recomputes its metrics.

Support CSV session export and full JSON trace export, including schema version, IDs, source mode and revisions. Replay is read-only over these saved records. It must not create new sessions, cycles, attempts, executions or live counter increments.

### 9. Timing, states and validation

Separate transcription, goal selection, Anomalib, Nemotron, Gemini, motion, verification and full-cycle timing. Full-cycle duration includes cloud waiting, retries and extra inspections whenever they delay the cycle. Use measured boundaries and sample counts. Do not sum parallel spans as if serial. Persist UTC and label display timezone explicitly.

The OpenVINO comparison reads **Benchmark not recorded** until comparable measurements exist. Each comparison needs model, device, precision, configuration, input set, threshold, warm-up/method, sample count and quality. Separate model speedup from full-cycle improvement. Do not copy the old Stitch benchmark numbers or unsupported camera/force/crack measurements.

Create simulation fixtures for empty/disconnected, normal success, failed grasp then recovered success, extra inspection without physical retry, wrong-bin outcome, provider timeout, stale evidence, queued voice goal, unverified connection loss and audited correction. Keep all demo records isolated from real reliability history. Use keyboard-accessible controls, visible focus, readable contrast, responsive reflow and reduced motion. Test interactions rather than rendering dead controls.

Keep provider keys on the server, with placeholder-only configuration examples. The browser may receive a short-lived single-use transcription token. Never expose long-lived secrets in client bundles, logs, screenshots or exports. Use actual installed SDK documentation and tested adapters; do not fabricate Studio methods.

### 10. Deliver in stages

First implement domain types, persistence, fixture isolation, metric queries and correction/event handling. Then build the three views against `StationClient`, matching the supplied visual references. Next add cycle detail, exports, replay, voice UI states and software controls using simulation. After that, connect real camera/station/model adapters as each interface is verified. Report exactly which checks ran and which capabilities remain unverified.

Acceptance must demonstrate duplicate event/execution protection; two failed attempts followed by recovery; extra inspection without another attempt; stale selection after a goal change; partial/committed/enriched transcript deduplication; timeout and event-gap recovery; refresh/reconnect without counter changes; late confirmation; audited manual correction; new session totals without erased history; session end with an open cycle; empty metrics; read-only replay; and no movement triggered by mount/navigation/reconnect. Keep simulation acceptance separate from physical test evidence.

---

## Short follow-up prompts

1. **Data review:** “Show the domain model, fixture population and exact metric denominators. Demonstrate one failed grasp followed by a successful retry as one cycle and two attempts. List the invariants your tests cover before expanding the UI.”
2. **Visual review:** “Match the reference hierarchy and DESIGN_SPEC.md. Reduce visual noise, retain the neutral black palette, put ornament only in the top masthead, and prioritize the current brick, source frame, selected task and outcome. Show Live inspection at desktop and narrow widths.”
3. **Interaction review:** “Exercise navigation, cycle detail, filters, reference corrections, CSV/JSON, read-only replay, finalized voice goal states and stop acknowledgment. Report behavior and test evidence; keep unimplemented adapters visibly unavailable.”
4. **Integration review:** “Connect one verified adapter at a time using INTEGRATION_CONTRACT.md. Preserve simulation isolation and persisted evidence. Show a real frame-linked input/output and returned model identity before calling a provider integration verified.”

The master prompt deliberately specifies the end product. The current handoff remains a design reference; only the builder's subsequently verified implementation and physical evidence establish working capabilities.
