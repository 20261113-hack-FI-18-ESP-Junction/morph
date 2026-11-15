# Morph — dashboard design specification

**Design handoff · November 14, 2026 · English product UI.** The proposed direction is **a quiet scientific instrument with a Renaissance accent**. The functional center is the current physical object and its evidence. Junction's historical-scientific story informs the identity; Morph's product interface remains purpose-built for the robot workflow.

The images and interactive reference are design artifacts using a small synthetic fixture. They are not screenshots of a connected robot or measured model performance. Implementation requirements are in [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md); the paste-ready build instructions are in [AI_STUDIO_PROMPT.md](AI_STUDIO_PROMPT.md).

## 1. Visual direction

Keep the neutral black requested by the owner. Add warm off-white text, muted bronze lines and a subtle scientific engraving. Use green for confirmed outcomes, amber for pending/uncertain states and red for failures or the software-stop action. Status must also have a text label; color alone is insufficient.

The connection to Junction is its European Tech Renaissance story, historical portraiture, parchment warmth and technical typography. Morph's exact palette below is our adaptation, **not Junction's official brand palette**. The inspected official site uses warmer brown backgrounds and sand/parchment colors. Sources, CSS observations and image rights are recorded in [REFERENCES.md](REFERENCES.md).

Avoid a blue-black cockpit, neon halos, decorative telemetry, nested cards, pseudo-Latin machinery labels, large portraits alongside camera evidence and repeated project wordmarks. The product should feel calm enough to use for an entire test session.

## 2. Design tokens

| Token | Value | Intended use |
| --- | --- | --- |
| Canvas | `#080808` | Main background, neutral black |
| Panel | `#101010` | Camera, object, trace and data surfaces |
| Raised | `#171715` | Quiet selected/control surfaces |
| Hairline | `#252421` | Section and panel boundaries |
| Primary text | `#F2EEE6` | Essential labels and values |
| Secondary text | `#A7A39A` | Context, units and supporting text |
| Bronze | `#C7A477` | Morph mark, active task, primary non-stop action |
| Verified | `#91B99C` | Independently confirmed positive outcomes |
| Pending | `#D6B775` | Waiting, queued, unverified and review states |
| Fault text | `#E36363` | Failure/defect-escape emphasis |
| Stop fill | `#B72F35` | Software-stop button, with white text |

Use fills with very low opacity for status cells; avoid painting all metrics different colors. Keep normal metric values off-white, including low reliability numbers. Red identifies the actual failure or action, rather than turning the whole screen into an alarm.

The [styles.css](styles.css) file is the editable token reference. Actual input controls need a more visible boundary than a decorative hairline. Check final contrast at real rendered sizes, especially when making secondary text dimmer.

## 3. Typography

| Face | Role | Rules |
| --- | --- | --- |
| Inter | Product UI, headings, prose, navigation, large values | 400/500 normal weights; 600 only for important controls. Use tabular numbers for changing values. |
| Space Mono | IDs, timestamps, compact technical labels, scores | Use sparingly; do not set long explanations in monospace. |
| Cormorant Garamond Italic | One short editorial phrase in the masthead, optional brand line | Decorative only. Never for controls, outcome labels, telemetry or tables. |

Desktop target sizes: page title 28–32 px, primary metric 30–36 px, body 13–14 px, panel title 13–14 px, supporting operational text 11–12 px. Small ornamental captions may be 8–10 px. Keep essential content readable at 100% zoom and do not shrink the whole application to make a screenshot fit.

The prototype contains compact technical labels to communicate the visual hierarchy. The builder should increase any label that becomes hard to read on the demonstration monitor. Avoid very wide tracking except for short brand/section labels.

The supplied font files are local, so the reference works without a font CDN. Their original SIL Open Font License files are included under [assets](assets/). Keep those notices with redistributed fonts.

## 4. Identity and decorative graphics

The [Morph mark](assets/morph-mark.svg) is an articulated `M`: two upright supports meet at a central joint. It suggests a linkage, a compass construction and adaptation without impersonating a sensor diagram. Use it at 28–40 px in the product. Pair it with `MORPH` set in Inter Medium with restrained tracking. At small sizes omit the tiny tagline.

Clear space should be at least one quarter of the mark width. Use bronze on black or a single solid monochrome version. Never stretch, add bevels or wrap it in a glowing badge. `The art of adaptation` is proposed optional brand copy; it is not part of the technical product name.

The [orbital graphic](assets/orbital.svg) is an original decorative Copernican study, not calibrated geometry. Place it at the very top of the main workspace in an 84 px masthead. Keep its stroke thin and its visual weight low. The prototype slowly rotates the whole graphic between −5° and +7° over a 70-second alternate cycle. A production version may rotate one inner ring continuously over 70–100 seconds. Keep the text and portrait stationary, use CSS transforms and honor `prefers-reduced-motion`.

The [Copernicus engraving](assets/copernicus-scriven.jpg) is an existing public-domain engraving by Edward Scriven from Wellcome Collection. The reference crops and fades it in the masthead, at approximately 18% opacity. It is neither an AI-generated portrait nor a photograph. Preserve the source credit in [ASSETS.md](ASSETS.md). The portrait must not become a large parchment card beside the current object.

All decorative elements should be hidden from assistive technology where they add no content. Do not attach fictional rotation, calibration, historical coordinate or synchronization readings to the artwork.

## 5. Application shell and responsive behavior

Desktop composition uses a 212 px sidebar, 84 px decorative masthead, 76 px operational bar and 32 px content margins. Use 20–24 px gaps between major modules, 16–20 px inner padding, 6–8 px panel radii and 1 px borders. The metric row has separators rather than four heavy nested cards.

The operational bar remains sticky while scrolling. It contains the selected session, current mode/state, pause-after-cycle control and the prominent software-stop button. Its state comes from the selected session and controller; the live-disconnected state must not retain a simulated session name. The stop button is roughly 174 × 48 px on desktop and at least 44 px high on touch surfaces. It never requires a preliminary confirmation modal.

Use exactly three primary views:

1. **Live inspection** — object, scene, process, goal, task and latest evidence.
2. **Robot & system** — connections, hardware readiness, policy/model placement and measured telemetry.
3. **Quality & history** — cycle reliability, reference-label detection quality, history and measured comparisons.

At intermediate widths collapse the sidebar to a labeled/accessible icon or number rail and stack the evidence panels. On narrow screens use compact navigation at the top, then the sticky operational controls. Stack camera, object, process and goal sections. Essential fields and the stop action must not depend on hover. A mobile camera can be shorter; the analyzed image and its frame association remain accessible.

Do not prioritize fitting every historical table into one viewport. Keep the active object and the controls easy to reach, then let the user scroll into detail. The desktop references are full-page captures at a 1600 CSS-pixel viewport and exported at 2× resolution; their exact document heights vary.

## 6. Live inspection composition

Use [01-live.png](references/01-live.png) as the main visual target.

The four summary values are confirmed correct cycles, confirmed successful physical attempts, current confirmed streak and median full-cycle duration. Each fraction includes visible counts. The compact breakdown shows all cycle categories and all attempt categories, as well as retries, first-attempt successes, recovered cycles and additional inspections.

Below the summary, allocate about two thirds of the row to the camera and one third to the current object. The camera supports available-view selection and an optional anomaly overlay. It must show a real stream in production; the reference deliberately uses an [original scene illustration](assets/inspection-scene.svg), prominently labeled simulated. Replace this illustration with actual camera media through the adapter, never with a Renaissance painting.

The object panel shows object/cycle IDs, inspection/attempt index, the **exact analyzed snapshot**, frame ID, capture time, anomaly score, threshold, classification, reference label and destinations. Keep planned, commanded and observed destinations distinct. If Gemini chose another inspection and no placement command has been dispatched, show a planned destination only. The reference's 0–1 score axis is explicitly a fixture range; the production axis must match the detector's actual scoring range and normalization.

The canonical process is **Observe → Pick → Verify grasp → Present → Inspect → Choose task → Place → Verify outcome**. Map these labels to the real runtime. Highlight the current stage, preserve a faulted stage, and show a measured elapsed time. Additional views may loop through inspection without creating a new physical attempt; actual manipulation retries create another attempt in the same cycle.

Under the steps, show three short evidence blocks: Nemotron's frame-linked observation, Gemini's permitted task selection and the local policy execution state. Anomalib remains visible in the object panel. Expand exact model requests, typed outputs, inputs, errors and rejected selections on demand. Do not invent a Gemini explanation: Decision 1 supplies typed choices/probabilities rather than generative prose.

The voice row shows the finalized ElevenLabs transcript and a clear goal state. Keep queued and active goals distinct; when a goal commits at a boundary, show its version and evaluate the next task against a new snapshot. Provisional transcription may appear during deliberate capture but cannot issue a command. The reference's voice button describes states only; it does not capture audio.

## 7. Robot & system composition

Use [02-system.png](references/02-system.png). The left column lists the selected services and their verified state. The right contains measured vs requested joint values, deviation and units when supplied by the controller. Device load, control rate, memory, temperature, current and force must be `Unavailable` until a real source exists.

Show the exact policy/model IDs and actual execution device from session metadata. A selected integration is not an active connection. The reference truthfully shows the required model access and hardware state as unverified. Calibration, workspace readiness, stop acknowledgment and physical halt confirmation are separate states.

The bottom explains the local dispatch boundary: validate state/goal/evidence, dispatch one unique execution, then independently verify the physical outcome. This should become actual event status in the working product, with further implementation details inside expandable diagnostics.

## 8. Quality, history and cycle evidence

Use [03-quality.png](references/03-quality.png) and [04-cycle-detail.png](references/04-cycle-detail.png).

The main operational result remains **confirmed correct cycles / all finished cycles**. Detection agreement is a separate result over reference-labeled examples. The confusion matrix labels both axes in plain language; highlight defective objects predicted good. Do not treat correct classification as proof of correct placement.

The history view supports session/source-mode, outcome, error, object and configuration filters in production. Selecting a record opens one consistent detail panel or dialog. That panel includes all images, inspections, task choices, attempt outcomes, timestamps, independent references, actual destinations, confirmation sources and audit history. The supplied prototype has one expanded illustrative recovery trace for C-007 and summary traces for other examples; it is a layout reference.

C-007 demonstrates one cycle with two attempts: a failed grasp followed by a verified successful recovery. It is a recovered success and not a first-attempt success. C-004 deliberately demonstrates a successful physical placement into the commanded good bin with the wrong classification for a defective reference object. Its overall task outcome remains failed.

The OpenVINO panel is intentionally empty because comparable target measurements do not exist yet. When data exists, show two separate comparisons: model inference and full physical cycle. Include baseline/optimized configuration, device, precision, matched sample count, timing method and quality. Show p50/p95 only with sample counts and a stated policy for insufficient samples. Cloud waiting time cannot disappear from full-cycle time.

## 9. Stop and exceptional states

Use [05-stop.png](references/05-stop.png) and [07-disconnected.png](references/07-disconnected.png).

The large red button is **Stop process**, a software command. On an authorized connected controller, send the supported stop request immediately and open a status dialog afterward. Display request sent, controller acknowledged and physically halted separately. Closing the dialog must not resume the robot. Never claim 48 V de-energization, pneumatic brakes, certification or physical emergency-stop behavior without the actual hardware integration and evidence.

The current reference records one simulated request ID and timestamp locally in memory; repeated exports retain that timestamp. Its acknowledgment and physical halt stay unverified. It does not issue any hardware command.

Additional required production states: live with no session, connected and idle, active motion, pause requested, pause acknowledged after cycle, provider waiting/timeout, stale frame, disconnected stream, rejected stale decision, rejected voice goal, open cycle at session end, replay and corrected historical outcome. Preserve the last known evidence on connection loss and mark what is unknown. Reconnecting, refreshing, navigating or opening the application cannot start motion.

## 10. Reference fixture and implementation boundary

The synthetic population contains 12 cycles, 11 finished cycles, 8 confirmed correct cycles and 14 physical attempts. Of 13 finished attempts, 9 are successful, 2 failed, 1 aborted and 1 unverified. There are 2 retries, 2 recovered cycles, 6 first-attempt successes and 3 extra inspections. Nine examples have independent fixture reference labels; eight agree with prediction and one is a defect escape. The last three finished cycles are correct; the best streak is also three.

These values explain edge cases and visual hierarchy. They are **not Morph's measured reliability**. The HTML/JavaScript is a presentation prototype, not the backend/data implementation. Its exports contain summary fixture records. The production builder must implement persisted, uniquely identified session/cycle/attempt/evidence records first and derive every counter from them, as specified in the integration contract.

## 11. Acceptance before visual approval

- The current object, frame and analysis agree; real camera evidence has not been replaced with decoration.
- The three required cloud contributions and the substantive Intel/local policy workflow remain distinct and visible.
- Every percentage has its denominator; unknown values remain unavailable; all relevant outcome categories are accessible.
- The software stop remains reachable, its status is honest and closing its dialog does not resume execution.
- All views and exceptional states use the same records; session changes do not erase saved history.
- Keyboard focus is visible, dialogs have accessible names, controls have useful labels and reduced-motion preferences are respected.
- At the actual monitor size and mobile width, labels do not overlap, essential controls do not disappear, and technical captions remain readable.
- Visual refinement does not turn a proposed, simulated or unverified capability into a factual claim.
