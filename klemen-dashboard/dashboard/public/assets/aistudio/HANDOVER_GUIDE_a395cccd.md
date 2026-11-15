# Morph — exact handover and build instructions

**Prepared November 14, 2026.** Give the builder `Morph-dashboard-handoff-2026-11-14.zip` and the message in [MESSAGE_TO_BUILDER.md](MESSAGE_TO_BUILDER.md). The archive contains the visual target, reusable assets, implementation requirements and dated project context. It is a design and engineering handoff; the included browser reference is not a connected robot application.

## 1. What the owner sends

Send the complete ZIP, with its directory structure intact. The builder extracts it into a folder named `Morph-Handoff`. Do not send individual screenshots as the only specification. The exact archive inventory is in [PACKAGE_FILES.txt](PACKAGE_FILES.txt).

| Material inside the archive | Builder action |
| --- | --- |
| `START_HERE.md` | Open first; links to this guide. |
| `design/morph-handoff/HANDOVER_GUIDE.md` | Follow the reading order, implementation stages and acceptance checks below. |
| `design/morph-handoff/MESSAGE_TO_BUILDER.md` | Read the assigned scope and requested return package. |
| `design/morph-handoff/README.md` | Understand the reference and its implemented interactions. |
| `design/morph-handoff/DESIGN_SPEC.md` | Implement visual tokens, layout, typography, states and responsive behavior. |
| `design/morph-handoff/AI_STUDIO_MASTER_PROMPT.txt` | Copy the entire file into the initial AI Studio prompt. It contains the master prompt only. |
| `design/morph-handoff/AI_STUDIO_PROMPT.md` | Read usage notes and use its four follow-up prompts one at a time. |
| `design/morph-handoff/INTEGRATION_CONTRACT.md` | Implement records, adapter boundaries, proposed API, controls, model contributions and metrics. |
| `design/morph-handoff/PROJECT_AUDIT.md` | Check what actually exists and what is still proposed or unverified. |
| `design/morph-handoff/REFERENCES.md` | Consult dated source links and the Junction design rationale. |
| `design/morph-handoff/ASSETS.md` | Preserve artwork attribution and font licenses. |
| `design/morph-handoff/references/` | Compare generated screens with the eight primary PNG references; retain the overview and QA images for review. |
| `design/morph-handoff/assets/` | Copy the actual logo, illustration, ornament, portrait, fonts and license notices into the new app. |
| `design/morph-handoff/index.html`, `styles.css`, `app.js` | Run and inspect the offline interaction reference. Reuse appropriate design code; replace the in-memory fixture logic for the product. |
| `design/morph-handoff/tools/render-references.cjs` | Optional screenshot regeneration and reference interaction checks; requires the documented local browser/Playwright setup. |
| `design/morph-handoff/PACKAGE_FILES.txt` | Check the exact files included in this release. |

The archive root also contains `AGENTS.md`, `IGNITE_INTEL_PHYSICAL_AI.md`, `PHYSICAL_AI_WORKFLOW.md`, `PHYSICAL_AI_ORCHESTRATION.md`, `PHYSICAL_AI_CHALLENGE_COMBINATIONS.md`, `PHYSICAL_AI_EXTENSIONS.md`, `PHYSICAL_AI_SETUP.md`, `JUNCTION.md` and `Intel_Physical AI Hackathon.pdf`. These provide project rules, architecture, challenge context and setup history. Selected `setup/` scripts and dependency profiles are included for the integration developer; they are not prerequisites for viewing the design.

The sole included file under `.junction-setup/` is a retained synthetic test report. Installed environments, dependency caches, credentials and private configuration are not included. Some historical evidence references in the canonical documents point to original organizer screenshots in the owner's Downloads folder; those HEIC captures are not bundled. The included PDF and written source summaries remain available. Obtain original evidence from the owner if a disputed requirement depends on it.

## 2. Read and inspect in this order

1. Read the extracted root `AGENTS.md`, this guide and [PROJECT_AUDIT.md](PROJECT_AUDIT.md). Do not treat old Stitch captions or example numbers as measured project results.
2. Open [01-live.png](references/01-live.png), [06-design-system.png](references/06-design-system.png), then [08-mobile.png](references/08-mobile.png). These establish the desktop composition, visual language and narrow-screen behavior.
3. Open [index.html](index.html). Visit all three views, open cycle C-007, switch the illustrative camera, toggle the anomaly map and inspect the software-stop dialog.
4. Read [DESIGN_SPEC.md](DESIGN_SPEC.md), then [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md). Consult the root `PHYSICAL_AI_ORCHESTRATION.md` for the selected online decision workflow.
5. Start implementation with the master prompt and the staged procedure below.

Authority order: direct owner decisions and root `AGENTS.md`; current canonical workflow/orchestration documents; the integration contract for proposed implementation details; the design specification for presentation; screenshots and HTML for examples. Report material conflicts rather than silently changing required behavior. All new interface text and project-owned documentation must be in English.

### Open the reference without installing the robot stack

After extracting the ZIP, open `Morph-Handoff/design/morph-handoff/index.html` directly in a browser. For a local HTTP preview, open a terminal in the extracted `Morph-Handoff` folder and run:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory design/morph-handoff
```

On Windows with the Python launcher, use:

```powershell
py -3 -m http.server 4173 --bind 127.0.0.1 --directory design/morph-handoff
```

Open `http://127.0.0.1:4173` and stop the server with Ctrl+C when finished. These commands need Python 3 and serve static files only. The owner's `.junction-setup/activate.sh` is not included and is not required on the builder's machine. There is no `npm install` step for this reference. The builder must supply install/run commands for the application they create.

## 3. Exact AI Studio procedure

Google's [Build documentation](https://aistudio.google.com/docs/aistudio-build-mode), rechecked November 14, 2026, documents the Build entry point, web-app platform selection, Code preview, ZIP export and GitHub synchronization. The sequence below is our Morph implementation workflow, not a guarantee that every attachment type is accepted.

1. Open [Google AI Studio Build](https://aistudio.google.com/apps) and start a **web app**. Name the app **Morph**.
2. Supply `references/01-live.png` and `references/06-design-system.png` first. Supply `DESIGN_SPEC.md`, `INTEGRATION_CONTRACT.md` and this `HANDOVER_GUIDE.md` as text context. If a Markdown attachment is rejected, paste its contents in clearly named messages; at minimum include this guide's stage table and acceptance checklist. Never assume an unsupported archive or file has been read.
3. Copy **all text** from `AI_STUDIO_MASTER_PROMPT.txt` into the main prompt. Append the stage-one instruction below. Keep the master prompt's complete product requirements even though work will be delivered in stages.
4. Supply `PROJECT_AUDIT.md` and the remaining primary references before their relevant views are built: `02-system.png`, `03-quality.png`, `04-cycle-detail.png`, `05-stop.png`, `07-disconnected.png`, `08-mobile.png`. Ask the agent to list which references it successfully received. The overview and preview PNGs are optional duplicates; do not substitute them for the full-size primary images.
5. Add the actual `assets/` files to the generated project. If the prompt interface rejects a font, SVG or other asset, copy it into the exported source project during local work. Keep original filenames or update every reference deliberately. Do not replace the engraving, logo or fonts with unrelated generated artwork.
6. Review each completed stage using the four follow-up prompts in `AI_STUDIO_PROMPT.md`: data, visual, interaction, integration. Inspect both the preview and generated Code. Require test results and a clear list of remaining work after each stage.
7. Export the generated source as a ZIP, or synchronize it to the agreed team GitHub repository. Preserve the lockfile and assets. Continue the real station integration in the team's development environment.

Append this instruction to the first master prompt:

```text
Implement stage 1 first: typed domain records, persistence, an explicit Simulation
adapter, deterministic fixtures, metric queries, and the minimal application shell.
Use INTEGRATION_CONTRACT.md for semantics. Show the files changed, the commands run,
and the test results. Keep all remaining stages in the work plan. Do not mark
hardware or provider integrations Verified. Build no decorative metrics that are
not derived from the records. After stage 1 passes, proceed through the stages in
HANDOVER_GUIDE.md, preserving the same data model.
```

The original `AI_STUDIO_PROMPT.md` is the editable prompt source. `AI_STUDIO_MASTER_PROMPT.txt` is an exact convenience extraction of its master-prompt section; update both together if requirements change.

## 4. Visual implementation requirements

| Element | Exact direction |
| --- | --- |
| Identity | **Morph** with the supplied articulated-M mark. Use one prominent identity, not repeated small subtitles. |
| Palette | Canvas `#080808`; panel `#101010`; border `#252421`; text `#F2EEE6`; secondary `#A7A39A`; bronze `#C7A477`; success `#91B99C`; warning `#D6B775`; error `#E36363`; stop `#B72F35` with white text. |
| Typography | Inter for UI; Space Mono for IDs, timestamps and numbers; Cormorant Garamond italic only for restrained editorial accents. |
| Composition | Desktop sidebar 212px; decorative masthead 84px at the absolute top; operational header 76px; content padding 32px. Reflow at smaller sizes instead of shrinking text. |
| Renaissance detail | Subtle orbital drawing and faded Copernicus engraving in the masthead. Slow motion with reduced-motion support. No large decorative portrait beside the camera. |
| Primary content | The actual Duplo brick, live camera, exact analyzed frame, anomaly score/threshold, active task, execution state and confirmed outcome. |
| Navigation | Live inspection; Robot & system; Quality & history. Cycle detail is reachable from the current object and history. |
| Stop | Large red **Stop process**, identified as a **Software stop**, with actual request/acknowledgment state. |

The eight primary reference images are review targets for layout and state coverage. Their fixture numbers are illustrative, not required production readings. The camera SVG belongs only to Simulation. The complete asset list, provenance and license files are in `ASSETS.md` and `PACKAGE_FILES.txt`.

## 5. Implementation order and evidence required

| Stage | Build | Show before considering it complete |
| --- | --- | --- |
| 1 — Data foundation | Stable session/cycle/attempt/frame/event IDs, persistence, simulation separation, metric queries, corrections and deterministic fixtures. | Tests for duplicate events, retries, additional inspections, late confirmation and corrections; restart/refresh preserves saved totals. |
| 2 — Operational UI | The three views, shared session/source state, live/analyzed media separation, process, current object, model task selection and component status. | Desktop and mobile screenshots; keyboard navigation; no fake hardware measurements; every percentage has counts. |
| 3 — Complete interactions | Cycle trace, history filters, independent reference labels, CSV/JSON, read-only replay, voice states, pause/resume and software-stop states. | Demonstrate each interaction against persisted simulation records, including unavailable and error states. |
| 4 — Real adapters | Camera and station API; Studio-trained policy; Anomalib/OpenVINO; Nemotron; Gemini Decision 1; ElevenLabs transcription. | Verify each actual interface and account; record model identity, frame/input/output, timing and errors. Keep blocked capabilities visibly unavailable. |
| 5 — Physical validation | Deliberately started runs with the calibrated robot and actual confirmation source. | Saved cycle evidence for success, recovery and uncertain/failure outcomes; measured reliability and comparable optimization data. |

Use React/TypeScript behind a typed `StationClient`. The proposed production backend is one local station service with SQLite and immutable evidence files. The integration contract defines application endpoints to implement; it does not prove those endpoints already exist. The browser must not own authoritative hardware counters or dispatch arbitrary joint commands.

AI Studio is the development tool. The product must also use Gemini online for actual goal/task selection. Preserve all required contributions: ElevenLabs finalizes spoken input; Nemotron supplies frame-linked observations; Anomalib supplies defect measurements; Gemini Decision 1 selects among permitted choices; the local validator dispatches learned skills and records independently verified outcomes. Account access and supported model execution are integration tasks, not implied by this package.

A hosted preview does not automatically connect to the Intel station. Prefer exporting and serving the frontend beside the local station API; any alternative bridge must be implemented and tested explicitly. Avoid a second cloud database that disagrees with the station's authoritative records.

## 6. Information to obtain for live integration

The builder can finish stages 1–3 without robot or provider access. Before marking stage 4 complete, the station/integration owner must supply or verify:

| Required information | Record in the implementation handoff |
| --- | --- |
| Station connection | Actual host/origin, authenticated API route and event transport, startup procedure, one sanitized snapshot/event example. |
| Cameras | Available camera IDs, supported stream transport, captured-at timestamps, frame identifiers and freshness rules. |
| Robot and learned skills | Actual robot/calibration status, installed Studio version, policy IDs and supported task interface, command acknowledgments, pause/stop/resume behavior. |
| Outcome confirmation | Which camera, sensor or operator confirms grasp and destination; how evidence is linked to a cycle. |
| Model providers | Verified account access, actual endpoint/model IDs and returned identity, error/timeout behavior, deployment device and relevant configuration. |
| Defect evaluation | Actual detector, threshold, independent reference labels, baseline/optimized input set and measurement method. |
| Deployment and ownership | Agreed repository, target machine, person responsible for station adapters, and who resolves hardware/provider blockers. |

Keep credentials in the selected server's secret configuration. The transfer contains placeholder-only configuration examples supplied by the builder. Do not put keys into the prompt, client bundle, screenshots, export fixtures or this handoff ZIP. Missing access should be reported with a specific capability blocker while simulation work continues.

## 7. Acceptance checklist

Run these against the built application. The existing `references/verification.json` covers the smaller presentation prototype and cannot stand in for these tests.

- [ ] All three views and cycle detail share the same persisted records. Live, Simulation and Replay are clearly distinguished; fixtures do not enter real reliability totals.
- [ ] One failed grasp followed by one independently confirmed correct retry produces **1 correct cycle, 2 attempts, 1 failed attempt, 1 successful attempt, 1 retry, 1 recovered cycle and 0 first-attempt successes**. In a session containing only this example, cycle correctness is `1/1`, physical attempt success is `1/2`.
- [ ] An extra inspection without physical execution does not increment attempts. Two failed attempts followed by recovery remain one cycle with three attempts.
- [ ] Duplicate messages, page refresh, reconnect and repeated completion do not add records or counters. Late confirmation updates the existing record.
- [ ] Correct placement in a wrongly selected bin may be physical success but is overall task failure. Prediction, independent reference, commanded bin and observed bin remain separate.
- [ ] Failed, aborted and unverified cycles remain in the finished-cycle denominator. In-progress cycles are excluded. Empty denominators show `No data yet`.
- [ ] Detection quality uses only independent reference labels, shows checked/total coverage and highlights defective bricks accepted as good. A model explanation does not count as a reference label.
- [ ] Camera loss marks the last image stale, preserves its capture time and never fabricates physical failure. Anomaly overlays remain tied to their original frames.
- [ ] Partial speech and timestamp enrichment issue no duplicate commands. A finalized utterance is committed once; a queued goal becomes effective at the defined boundary.
- [ ] Stale state/goal versions, stale evidence, timeouts and repeated execution IDs are rejected or recovered according to the contract. Event gaps trigger authoritative resynchronization.
- [ ] Opening, navigating, refreshing or reconnecting does not start movement. Start-session bookkeeping does not move the robot. Pause-after-cycle and resume show actual acknowledgment.
- [ ] The supported stop request is sent before displaying its status dialog. Closing the dialog neither resumes movement nor turns a cycle into success. Physical stop remains unverified until suitable evidence exists.
- [ ] Ending a session preserves an open cycle's actual status. A new session changes displayed session totals without deleting history. Replay creates no new executions or records.
- [ ] Manual corrections retain old/new value, author, time and reason. CSV/JSON include schema version, stable IDs, source mode and revisions; the detailed JSON retains evidence relationships.
- [ ] Missing telemetry is `Unavailable`. Benchmarks remain empty until measured; model speedup and full-cycle improvement have separate timing boundaries and sample counts.
- [ ] Desktop and 390px-width layouts remain readable, with reachable stop controls, keyboard access, visible focus and reduced motion.
- [ ] Required provider and hardware verification is reported separately from UI/simulation tests. No unsupported E-stop, safety, camera, force or performance claim appears in the UI.

## 8. What the builder returns

Deliver a repository link or complete source ZIP containing:

1. Application source, reusable assets and licenses, dependency manifest and lockfile. Include the station service and database migrations when they are part of the agreed scope.
2. An English `README.md` with exact installation, simulation, development, production-build and startup commands; required runtime versions; configuration and station connection instructions.
3. A placeholder-only `.env.example`, with each variable's purpose, which process reads it and which capabilities require it. No credentials or personal runtime folders.
4. Tests and their recorded results for the checklist, plus screenshots matching the eight reference states. Identify any untested or failing check.
5. A sanitized exported simulation session with full traces, a reproducible recovery example and documented metric denominators.
6. `IMPLEMENTATION_STATUS.md` listing each feature/integration as **Proposed**, **Implemented** or **Verified**, with evidence and unresolved blockers. State whether physical tests actually ran.
7. Any real physical evidence and baseline/optimized measurements that were actually obtained, kept separate from simulation fixtures.

A visual frontend milestone can be accepted after stages 1–3 if its simulation behavior passes review and the remaining integration work is explicit. The full Morph station is complete only after the required real adapters and physical behavior are verified. A screenshot, generated source build or presentation prototype alone does not establish that result.
