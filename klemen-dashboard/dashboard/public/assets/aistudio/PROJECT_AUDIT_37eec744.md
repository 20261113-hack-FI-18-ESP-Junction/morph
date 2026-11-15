# Morph — project audit for the dashboard handoff

Audit date: **November 14, 2026**. This audit reconciles the supplied Stitch concepts with the current local project records. It is a document and source inspection, not a new physical test, account-access check, benchmark, or re-verification of competition rules.

## 1. What Morph is building

Morph is a **voice-directed, adaptive inspection and sorting system for Duplo bricks**, with a dashboard that connects the current object, perception evidence, selected task, physical execution, and independently confirmed outcome.

The selected primary architecture is:

1. Deliberate push-to-talk capture is transcribed by **ElevenLabs Scribe v3 Live**.
2. **Gemini Decision 1** selects a supported goal from defined options; the local application validates and commits the goal at its allowed boundary.
3. **Anomalib** supplies frame-linked defect measurements; **NVIDIA Nemotron 3.5 Super VL** supplies frame-linked visual observations.
4. Gemini selects a currently permitted high-level task using a new state snapshot.
5. The local application validates that selection and dispatches an existing **Physical AI Studio-trained policy**, preserving substantive local perception-dependent manipulation.
6. The **SO-101** executes the task; the system records the observed outcome and its confirmation source.
7. The dashboard reads those persisted records and exposes intentional controls through the same validated local application.

The target is the organizers' **Intel Core Ultra Series 3** station, with supported local inference optimized through OpenVINO. The Mac is intended as a browser/SSH client. A cloud model does not issue arbitrary joint commands, create a new learned skill, or certify a physical result.

Canonical sources: [primary workflow](../../PHYSICAL_AI_WORKFLOW.md), [orchestration](../../PHYSICAL_AI_ORCHESTRATION.md), and [Intel brief](../../IGNITE_INTEL_PHYSICAL_AI.md).

## 2. Evidence and implementation status

| Area | What is present | What the dashboard may truthfully claim now |
| --- | --- | --- |
| Product direction | Current project documents explicitly select adaptive recovery and spoken goal changes. | **Selected architecture / planned integration.** |
| Project application | The inspected application-owned files contain documentation, setup scripts, and dependency lock files. No Morph dashboard, local dispatcher, persistence model, or project API was found before this handoff. | **Design reference / implementation pending.** Installed dependencies are not a working app. |
| Source control | The workspace root reports that it is not a Git repository. No application repository was found in the inspected project-owned paths. | Create or identify the implementation repository before collaborative development. |
| Mac setup | Separate Studio 0.3.0 and Anomalib 2.7.0 profiles are recorded as installed. Studio dependency/CLI/tensor/OpenCV checks passed. | **Software preparation checked**, with the limits recorded in the setup document. |
| Anomalib test | A retained synthetic run used generated 64 × 64 images and random backbone weights. Imports, fit, Torch inference, and OpenVINO export passed. | **Synthetic installation checks only**; this is not a trained brick detector or quality benchmark. |
| OpenVINO execution | The same synthetic report has overall `status: failed` following a Mac OpenVINO internal error. No Torch/OpenVINO parity result was obtained. | **Export verified; execution unresolved in that test.** Do not display a successful speedup. |
| Intel target | Package resolution and installation dry-runs are recorded. Actual target inventory, installation, GPU/NPU execution, and workload placement remain pending. | **Target planned / device allocation unverified.** |
| Robot and cameras | No connected robot test, calibration, live camera capture, useful demonstration set, trained policy run, or complete autonomous cycle is verified. | **No hardware data yet.** A mock screen must have an unmistakable demo/simulation label. |
| Gemini | Intended model is `gemini-decision-1`; current project sources record the Decisions API interface. Account access and a real product request remain unverified. | **Configured intention / access unverified.** |
| NVIDIA | Current project sources identify `nvidia/nemotron-3.5-super-vl-120b-a12b` as the matching model reference. Real image inference and account access remain unverified. | **Configured intention / access unverified.** Confirm the endpoint before integration. |
| ElevenLabs | Selected service is `scribe_v3_live`; actual account, microphone, language, and venue-noise performance remain unverified. | **Configured intention / access unverified.** |
| Notion | A local publication attempt is documented, but successful publication into the intended WF workspace was not verified. | Use local project files as the present handoff source; do not imply a completed Notion integration. |

The synthetic report explicitly contains `data_mode: synthetic`, `backbone_pretrained: false`, and `robot_connected: false`. Its retained path is [report.json](../../.junction-setup/smoke/anomalib/20261114T122227Z-8b9a93aa/report.json). The final setup record is [PHYSICAL_AI_SETUP.md](../../PHYSICAL_AI_SETUP.md).

The audit did not start Studio, connect to a robot/camera, activate provider accounts, or run model inference.

## 3. Authoritative current direction versus historical material

| Source group | How to use it |
| --- | --- |
| `AGENTS.md`, `PHYSICAL_AI_WORKFLOW.md`, `PHYSICAL_AI_ORCHESTRATION.md` | Current owner decisions, record definitions, workflow, and model boundaries. |
| `IGNITE_INTEL_PHYSICAL_AI.md` and the supplied Intel PDF | Recorded challenge requirements, equipment descriptions, and explicitly unresolved organizer questions. |
| `PHYSICAL_AI_SETUP.md`, `setup/`, retained synthetic report | Software preparation and its actual verification limits. |
| `PHYSICAL_AI_CHALLENGE_COMBINATIONS.md`, `PHYSICAL_AI_EXTENSIONS.md` | Optional integrations and sponsor-specific conditions. Vendor availability does not make every vendor part of the product. |
| `JUNCTION.md` | Event/preparation context. Its historical pre-opening notes do not supersede the current selected project at the top of the file. |
| `tmp/docs-before-online-orchestration/`, `tmp/docs-before-voice-primary/` | Historical backups; do not revive the superseded retrospective-only Gemini architecture or make voice optional. |
| `.junction-setup/` libraries and caches | Prepared tooling and vendor code; not project implementation. Do not put application source here. |
| Supplied Stitch screenshots and conversation | Visual exploration and desired aesthetic. Their factual captions, generated metrics, controller capabilities, and benchmark claims are not evidence. |

All Markdown in this handoff and the eventual repository must remain English. The user-facing discussion may be Slovenian. Preserve the operator's original spoken language in the transcript record.

## 4. Corrections required in the supplied Stitch concepts

| Existing reference pattern | Required Morph treatment |
| --- | --- |
| A painting presented as the inspection stream; titanium bearing and microcrack captions | Show the actual robot workspace and **Duplo brick**. A synthetic illustration must say that it is illustrative. Keep Renaissance art separate from camera evidence. |
| A large Copernicus panel competing with the current object | Use a subtle decorative engraving or line motif in a brand area. It has no role in calibration, computer vision, or measured kinematics. |
| `Octo-VLA v2.4`, `DaVinci-9 NPU`, and fabricated directives | Display the actual loaded policy ID/version and real task instruction when available. Before integration, use `Policy not connected` or an explicitly labeled demo fixture. |
| `48V Power Bus: Severed`, `Pneumatic Brakes: Engaged`, `Forced Halt`, safety-standard claims | Remove unsupported hardware and certification assertions. Keep a prominent red **Software stop** control with the real request/acknowledgment state. Physical emergency-stop equipment is separate. |
| A confirmation dialog delaying the stop request | If an implemented software stop is available, dispatch it immediately on the intentional stop action and show the status dialog afterward. The dialog must not announce a verified physical halt without evidence. Dismissal must not resume execution. |
| `Acknowledge & Disarm` presented as a safety reset | Use an actual controller-supported acknowledgment/recovery protocol. Resuming a stopped workflow is a distinct intentional action with readiness checks. |
| `Heartbeat: 98.4 bpm` | Use connection state and last event age, such as `Last update 0.4 s ago`. A system heartbeat is not a biological heart rate. |
| `4K / 60 FPS`, forces, torques, servo temperatures, 0.18 mm crack measurements | Show only actual sourced measurements and units. Use `Unavailable` when absent. Camera capabilities, a connected device node, and a model-generated description do not establish a live measured value. |
| An anomaly result as a confidence percentage | Label **Anomaly score** and **Threshold**. Do not assert a universal 0–1 range unless the selected model's output is explicitly normalized that way. |
| Task accuracy calculated only over ground-truth-verified cycles | The primary operational result is **confirmed correct cycles / all finished cycles**, including failed, aborted, and unverified results in the denominator. Detection quality has its own reference-labeled denominator. |
| `Gripper precision` for all physical execution | Use **Confirmed physical attempts** or **Physical execution success**, with finished-attempt counts. A correct grasp alone does not establish successful transfer and placement. |
| All failures disappear after a retry | Keep both attempts, their separate outcomes, and one recovered cycle. Additional inspections remain separate from physical attempts. |
| Provider logos marked active without requests | Show `Not connected`, `Access unverified`, `Ready`, `Active`, or `Error` from real health/evidence records. Use brands to explain roles, not to imply tested integration. |
| A prose `AI reasoning` paragraph attributed to Decision 1 | Show offered tasks, selected option, actual returned probabilities where relevant, selection status, and validator reasons. Decision 1 generates no prose plans, explanations, or function-call arguments. |
| Hard-coded OpenVINO speedups and objects/minute | Show `No benchmark data yet` until a comparable measured experiment exists. Example chart values must be clearly labeled simulated and excluded from hardware reports. |
| `All actuators synchronized` or `ISO calibration` footer | Replace with actual component health and calibration status. No certification or numerical calibration accuracy should be inferred from decorative labels. |

The references remain useful for a near-black surface, warm bronze identity, restrained green evidence accents, editorial spacing, and an orbital motif. These are design choices, not technical measurements.

## 5. The workflow the live view should explain

Use the actual initial physical sequence:

**Observe → Pick → Verify grasp → Present → Inspect → Choose response → Place → Verify outcome**

Group these into a compact set of visual phases if needed, but preserve the underlying stages and timestamps in the record. Inspection happens after presentation to the inspection camera in the selected primary workflow. Do not imply that the first object detection is the final quality inspection.

The current object should answer five questions without opening another page:

- **Seen:** Which object, cycle, and frame are under inspection? Is the live image fresh?
- **Measured:** What did Anomalib measure, at which threshold? What did Nemotron actually observe?
- **Selected:** What goal is active and which permitted task did Gemini select? Did the local validator accept it?
- **Executed:** Which learned policy and attempt are running? Was the command sent, acknowledged, and finished?
- **Verified:** What destination was observed, who or what confirmed it, and is the full task correct?

A small voice strip should show `Listening`, `Provisional transcript`, `Finalized`, `Goal queued`, `Goal active`, or `Rejected`. A completed utterance produces one command record. Later segment or timestamp enrichment cannot create another command. A new goal version becomes active only at its defined boundary; subsequent task selection uses a newly created snapshot.

## 6. Minimum record and metric contract

Persist records before computing screen totals. Use stable session, cycle, attempt, inspection, frame, event, utterance, decision, and execution IDs.

| Concept | Rule |
| --- | --- |
| Session | Named run with start/end, data mode, robot/model/configuration metadata, and an explicit display timezone. A new session resets its displayed totals but preserves history. |
| Cycle | One started task for one object. An independent new test is a new cycle even if the object is reused. |
| Attempt | A physical execution attempt inside a cycle. A failed grasp followed by a retry creates two attempts and one cycle. |
| Additional inspection | Another image/analysis for the same object; it does not automatically create an attempt or cycle. |
| Detection result | Model prediction, anomaly score/map, threshold, and source frame; independent reference quality is a different field. |
| Physical result | Commanded destination and observed destination, confirmation source, evidence, and success/failure/aborted/unverified/in-progress status. Controller completion is not physical confirmation. |
| End-to-end result | Requires correct classification and correct actual destination for the independent reference quality, with adequate physical confirmation. |
| Correction | Retain previous value, new value, author, timestamp, and reason. Late evidence updates the original record rather than creating a second cycle. |
| Model decision | Exact model ID, inputs/snapshot/frame IDs, output, request/response times, deadline, acceptance/rejection, and validator reason. Exclude credentials. |

Required formulas and labels:

- **End-to-end reliability:** confirmed correct cycles / all finished cycles. Finished includes failed, aborted, and unverified; exclude in-progress cycles.
- **Physical execution:** confirmed successful attempts / all finished attempts. Show failed, aborted, and unverified counts.
- **First-attempt success:** a confirmed correct cycle completed on its first physical attempt. A recovered cycle requires at least one preceding failed physical attempt.
- **Detection correctness:** correct predictions / reference-labeled examples checked, with total population visible. A missing reference label is not a correct prediction.
- **Success streak:** consecutive confirmed correct cycles. Failed, aborted, and unverified results break the streak.
- **Empty sample:** show `No data yet`; never default to 0% or 100% when there is no eligible denominator.
- **Replay:** display existing records without creating sessions, cycles, or attempts. Simulation is excluded from real-hardware reliability by default.

For the confusion matrix, declare **defective = positive**. Show good/correctly accepted, defective/correctly rejected, defective/incorrectly accepted (**defect escape**), and good/incorrectly rejected. The matrix measures classification; it does not itself prove placement in a bin. If showing recall, its denominator is actual defective examples checked; if showing precision, its denominator is predicted defective examples checked. Label every rate's denominator and sample count.

## 7. What belongs in each view

| View | Primary content | Detail moved out of the live view |
| --- | --- | --- |
| **Live inspection** | Current camera, exact analyzed snapshot, object/cycle, active phase, actual selected task, active/queued voice goal, stop/pause controls, four carefully named summary metrics, compact recent events, active errors. | Large confusion matrices, full model payloads, joint tables, decorative portrait cards, and long historical tables. |
| **Robot & system** | Component health, robot mode/calibration, command acknowledgment, measured/requested joint positions and units where available, host/device/model placement, current errors, optional detailed telemetry. | No invented current/torque/temperature values; unsupported controls remain unavailable. |
| **Quality & history** | Detection matrix and label coverage, cycle/attempt outcomes, retries/reinspections, filters, correction trail, exports, baseline/adaptive and baseline/OpenVINO comparisons. | Opening a cycle reveals its complete evidence trail without requiring raw-log reading. |

Use a cycle detail drawer or full detail page for source images, all inspections, actual model outputs, task selection, commanded/observed destination, ordered attempts, verification sources, and correction history. An alert affecting the current cycle stays visible on the main screen regardless of the selected view.

## 8. Required states and checks for the implementation handoff

- Startup, refresh, and reconnect must not move the robot.
- A stop request, its acknowledgment, execution completion, and physical verification must remain distinct.
- `Pause after cycle` prevents starting another cycle after the current one ends; show whether that request was accepted. A controller-specific interruption mode needs its own explicit semantics.
- Ending a session does not convert open cycles to success.
- A connection loss preserves the last known state and can leave the physical outcome unverified; it is not automatic proof of physical failure.
- A stale frame remains visibly stale. Overlay geometry, inspection output, and decision evidence must point to the analyzed frame, not silently move onto a newer image.
- Validate session/cycle, state version, goal version, evidence age, deadline, preconditions, allowed task, and unique execution ID before dispatch.
- Cloud failure, timeout, unsupported goal, and rejected stale decision follow a defined local fallback. Never silently accept an uncertain object as good.
- Preserve original model measurements when another model disagrees. An extra inspection creates new evidence rather than overwriting the first result.
- Keep long-lived provider keys on the backend. Client voice capture uses a short-lived token if that supported provider flow is chosen.
- Verify duplicate events, retries, late confirmations, uncertain outcomes, session changes, replay, and manual corrections against record-derived counters.
- Benchmark comparable inputs/configurations with sample counts, device, precision, timing method, and quality. Include cloud waiting in full-cycle duration whenever execution waits for it. Model speedup and full-cycle speedup are separate measurements.

## 9. Open items that the design must not silently settle

The project retains two organizer rubrics: portal **30/30/20/20** and kickoff/Intel-deck **25/20/20/20/10/5**. The applicable rubric requires a dated mentor clarification. No current project source establishes a mandatory target FPS or success percentage.

ACT → Anomalib → SmolVLA appears in the deck, but the requirement to use both named policy types remains unresolved. The current Studio task-conditioning/switching API, permitted recoveries, external cloud supervision, actual device assignment, and account access also require verification. Do not encode proposed task names as if they were proven Studio API endpoints.

NVIDIA's challenge source has a documented model-name discrepancy between its minimum requirements and a starter example. Follow the selected **Nemotron 3.5 Super VL** requirement and verify the real endpoint. Gemini used only to generate the dashboard in AI Studio does not meet the selected working-product Gemini integration. Optional voice acknowledgment does not replace ElevenLabs speech recognition.

Optional databases, media services, training hosts, and sensors remain optional provider choices. Needed capabilities are durable evidence, working training, and adequate outcome confirmation; there is no requirement to add every researched sponsor logo or service.

## 10. Exact local source inventory

Workspace root: `/Users/klemensemelbauer/Desktop/MyStuff/Projects/Junction_Finska/HachingJunction`.

| File relative to that root | Audit use |
| --- | --- |
| `AGENTS.md` | Owner requirements, metrics, evidence rules, controls, working conventions. |
| `PHYSICAL_AI_WORKFLOW.md` | Canonical primary workflow, stages, voice handling, records, demo evidence. |
| `PHYSICAL_AI_ORCHESTRATION.md` | Model responsibilities, fixed-choice Decision 1, validated dispatch, recovery. |
| `IGNITE_INTEL_PHYSICAL_AI.md` | Recorded official task, offered equipment, rubric conflicts, remaining questions. |
| `Intel_Physical AI Hackathon.pdf` | Supplied 15-page primary deck; its current document summaries record its review. The audit used those summaries rather than rerendering the deck. |
| `PHYSICAL_AI_SETUP.md` | Verified software preparation versus untested runtime/hardware. |
| `PHYSICAL_AI_CHALLENGE_COMBINATIONS.md` | Mandatory sponsor scope, optional catalog, model discrepancy, separate submission rules. |
| `PHYSICAL_AI_EXTENSIONS.md` | Optional additions and the capability/provider distinction. |
| `JUNCTION.md` | Current selection, historical event notes, prepared runtimes. |
| `NOTION_SYNC.md` | Unverified publication into the intended workspace. |
| `setup/check-intel.py` | Read-only inventory and optional synthetic runtime checks; no camera/serial control. |
| `setup/run-studio.sh` | Loopback Studio launcher; starting it is not a policy run. |
| `setup/smoke-anomalib.py` | Synthetic installation test with random backbone weights, no robot/camera. |
| `.junction-setup/smoke/anomalib/20261114T122227Z-8b9a93aa/report.json` | Retained failed overall OpenVINO test and its successful intermediate checks. |

This file adds a handoff audit; it does not alter the existing canonical documents or claim that new product integrations have been built.
