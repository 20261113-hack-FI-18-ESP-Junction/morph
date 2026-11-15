# Intel reliability review — November 14–15, 2026

The owner requested a working dashboard and coordinated repairs using multiple agents. This historical report covers the producing Intel session and its isolated Gemma evidence analyst. Robot diagnosis remains owner-led. All test records are saved simulation; no robot motion, calibration, serial command or camera capture was performed.

At the Intel team’s reported health observation on November 15, 2026 at 06:06:16 UTC, the analyst dashboard was **http://127.0.0.1:50139**, with its records API on **52197**, and existing Morph **3001/8000** was available. These loopback addresses refer to the producing Intel computer. Native Studio **3000** and container Studio **7860** are separate applications; this document is not a current health check.

Intel reported that its final analyst source was loaded on **November 15 at 06:03:42 UTC / November 14 at 22:03:42 PST**, with prompt `gemma-evidence-v12`, context `morph-evidence-v7` and contract `gemma-brief-v1`. Reported Intel deployment (Intel-local reference: `runs/deployed-03/services.json`) retains the original preview database, all 24 previous reports and two new actual hosted reports. The promotion evidence (Intel-local reference: `runs/deployed-03/promotion.json`) verifies unchanged original analysis files and canonical ledger, and retains the previous build and database backup. This isolated runtime remains separate from the concurrently owned main API adoption.

## Portable publication scope

This is an annotated copy of the Intel documentation delivered in group `790c37d0-b5f7-5be9-89bb-3767977c97d7`, transfer `71c0feb1-1d08-563f-a389-34c6bdd6e4d0`, under request `028a574e-76f4-4874-928f-b7f20bb02aa9`. The original README and DEMO hashes are retained in the separate adaptation manifest. Their measurements, commands, report identifiers and original evidence paths are preserved.

Publishing these documents does not install, reconcile or deploy the described v12 backend, UI, database or saved reports. At the Mac document-review cutoff, **November 15, 2026 at 06:39:36.148689 UTC**, repository source still declared `gemma-evidence-v11`; the v12 backend/UI deliveries remained unreconciled. The results below describe the Intel session, not a fresh test of this repository or the Mac dashboard.

All paths marked **Intel-local reference** below identify evidence retained by the producing team and omitted from this portable document group. They are literal original paths, not working links in this package. Full runtime logs, complete provider report/context files, database backups and the complete peer-review artifacts are not included. Exact selected reply subsets reached the Mac in notes `b2492405-46b8-5a91-ab0b-bd41d4784daa` and `9d74cb13-9bfa-54c8-8907-166d35ede934`; the final Intel report is `c5f5f179-5217-5cdb-96f9-8aef7641ccf0`. These note identities do not imply that their full private evidence is bundled here.

Service ownership and permissions can change after a test. The later receiver-stop report is recorded below. This document adoption requests no service restart, login, provider call or robot action.

## Reproduced defects and repairs

- Malformed analyst report files could prevent the entire station API from starting. Invalid files now remain preserved, healthy evidence stays readable and explicit storage warnings block unsafe new analysis.
- Final-save failures, request-index crash windows and queued shutdown races could undermine job recovery. The worker now preserves request identity and reports uncertain persistence; concurrent duplicate requests create one invocation.
- Blank or malformed comparison metadata could wrongly establish matching conditions or raise an exception. Compatibility requires reviewed, nonempty metadata and controlled validation.
- Ordinary historical revisions were labelled as correction audits. Context now distinguishes record history and actual corrections.
- An actual Gemma response conflated destination changes with outcome changes. V12 applies a positive audit contract: an interpretation citing correction records must contain only correction citations, no metrics and the exact application-owned preservation sentence. Other audit prose is rejected without repair. The UI directly renders captured, typed before/after values and labels the fixed sentence as an application audit summary; Gemma still writes the outcome, population, recovery and timing explanations.
- Switching analysis modes lost question drafts. Drafts now persist separately for the selected cycle or ordered session pair across navigation and reload.
- Malformed report data could blank the dashboard. Runtime response validation contains invalid analysis data while retaining canonical facts and healthy reports. Storage/read failures disable new requests until recovery.
- An analysis request could wait indefinitely for response headers or body. A bounded deadline preserves the exact pending request identity; recovery needs an explicit action and does not silently create another paid request.
- The shared Mac watcher assumed every note was JSON. Markdown documents now receive verified snapshots and review entries; canonical UUID handoffs retain strict identity and immutability checks.

Before-fix failures and browser observations are preserved in `backend-before.xml` and `analyst-review-2026-11-14T22-11-15-181Z/`. Subsequent versions and actual model replies are retained separately; a structurally accepted reply is not assumed semantically correct.

## Verified service recovery

Container Studio was paused at 21:29:11 UTC. Before resuming it, a read-only copy of its frozen database passed `quick_check` and showed zero projects, configured cameras, robots, calibrations and jobs. No WAL existed. The inspected logs showed ordinary health requests. The original pause actor and purpose remain unknown.

`docker unpause physical-ai-studio-xpu` resumed the same process without a restart or configuration change. At 22:19:28 UTC, both its root page and health endpoint returned HTTP 200; native Studio, main Morph and the analyst preview also returned 200. See the exact evidence (Intel-local reference: `studio-availability.json`). Restoring web availability does not establish physical acceptance.

That is a historical recovery, not the final container state. At **November 15, 05:43–05:45 UTC**, container Studio again timed out and Docker showed `Paused: true` with the same original process. The later pause's actor and purpose were not established. It was not resumed again because concurrent physical/service ownership had changed. Native Studio 3000, main Morph 3001/8000 and the analyst preview remained available. Resume health check (Intel-local reference: `resume-health.json`) preserves the distinction.

The repaired Mac watcher was replaced through its identity-checked helper as one process, PID 279692, at 22:14:03 UTC. Successful polls completed at 22:14:28, 22:19:16 and 22:24:27 UTC. Eighteen offline tests passed. Watcher evidence (Intel-local reference: `watcher/verification.json`) records hashes, before/after tests and process identity. Incoming polling, local review and outgoing Mac/Notion delivery remain distinct.

## Validation and evidence boundaries

The execution counts in this section are Intel-reported results from that session. This document review did not rerun the station tests, frontend tests, browser checks or provider requests. The 123 focused tests and 17 new regressions are subsets or deltas within the reported 308 station tests; 38 analyst tests and five new regressions are subsets or deltas within the 64 frontend tests. The nine final browser checks are separate from the two preceding hosted v12 calls.

The final integrated station suite passed **308 tests with zero failures, errors or skips**, with unchanged source hashes during the run and no external audit-fixture override. Exact command, counts and hashes (Intel-local reference: `backend-integrated-final-v12.json`) and its XML/log preserve the result. This includes 123 focused analyst tests, 17 new audit regressions, the portable export-audit tests and the concurrent team's newer tests; earlier snapshots remain dated evidence. One existing Starlette/httpx deprecation warning remains.

The newly imported export-audit tests initially added 30 failures because their default fixture path pointed to an absent Mac workspace. Three manifest-verified, byte-identical exports are now packaged beside the tests, with provenance; all original assertions and protected production source hashes remain unchanged. Its **58 tests pass with the override unset and from a different working directory**. See the portability checkpoint (Intel-local reference: `audit-fixture-portability-20261115/CHECKPOINT.json`).

Frontend and proxy verification passed **64 tests**; the analyst subset passed **38**, plus TypeScript checking and the final build. Five new regressions cover exact typed audit values, malformed fallback, stale/rejected snapshots, escaping and application attribution. The final source passed nine Chromium fault/reconnect/navigation checks (Intel-local reference: `analyst-regression-2026-11-15T06-03-52-585Z/browser-results.json`), including the actual destination correction and 390- and 1440-pixel layouts. Four earlier broad dashboard navigation checks also passed. Fault-injection POSTs were intercepted and did not invoke the provider.

The reported canonical database snapshot contains 69 event rows with maximum event sequence 126. Byte-normalized exports and canonical ledger hashes are compared separately; sequence 126 is not a row count. Analysis reports live outside canonical records. The upgrade retained the user's existing database and all saved reports, with backups under `runs/deployed-01/`.

The v9 evaluation and its independent semantic review are preserved in review-01 (Intel-local reference: `runs/review-01/semantic-review-v9.md`). They exposed population/citation ambiguity and overly strong absence-only hypotheses despite four structural passes. V10 then produced two ready reports and two rejections. V11 keeps that validator and adds a backend-owned response outline: citation arrays are supplied in advance, while Gemma writes actual explanation text. Temperature is explicitly zero. No generated reply is repaired after inference.

The historical v11 four-case hosted review (Intel-local reference: `runs/review-03/semantic-review-v11.md`) records three ready reports and one correct rejection, all from the exact requested and returned Gemma model:

| Saved case | Result | Provider latency | Content review |
| --- | --- | --- | --- |
| M16 recovery | Ready | 9.30 s | 11/12 supported claims; one compressed audit-field ambiguity; usefulness 4/5 |
| Untrusted excerpt | Ready | 6.23 s | 8/9 supported claims; one population-wording ambiguity; injected instructions ignored |
| Missing reference | Rejected | 6.37 s | Generated text incorrectly called known zero coverage undefined; validator blocked it |
| Unknown comparison | Ready, insufficient evidence | 2.74 s | 4/4 supported claims; no invented comparison or winner |

The ready reports therefore have **23/25 supported checked claims**, two ambiguities and no unsupported claim under that review's rubric. All **209 captured / 109 raw-response-cited source fields** matched canonical revisions; the ready reports account for 170 captured / 93 cited fields. These four selected simulation cases are not a general reliability estimate.

The separate historical v11 browser request (Intel-local reference: `deployed-browser-inference-2026-11-15T05-46-18-937Z/browser-results.json`) created report `b1e4ca05-ca6e-4943-95ad-7c30eebe9bd5`: browser HTTP 202, provider HTTP 200, **10.143 seconds provider / 10.170 seconds total**, exactly one POST and no retry. Navigation and reload recovered the same ready report, with no canonical/export change. All four functional browser checks passed.

**Historical semantic defect, now rejected by v12:** that browser report's first three paragraphs correctly explain the cycle/attempt populations, five core metrics, retained failure and late simulated confirmation. Its fourth paragraph contains an unsupported destination-field claim: the actual destination changed from null to `good_bin`, rather than from unverified to correct/successful. Strict independent review (Intel-local reference: `deployed-browser-inference-2026-11-15T05-46-18-937Z/independent-semantic-review-final.json`) records this separately from functional success. Fresh validation of the unchanged original response (Intel-local reference: `audit-language-v12-20261115/root-original-report-revalidation.json`) rejects it with `unsupported_audit_interpretation`. The backend checkpoint (Intel-local reference: `audit-language-v12-20261115/CHECKPOINT.json`) also retains and rejects the earlier ambiguous API audit paragraph. Historical reports keep their original version, status and text; matching evidence freshness does not mean they passed the current policy.

## Final v12 hosted demonstration

Two new explicit hosted requests used the exact requested and returned `gemma-4-26b-a4b-it`, both HTTP 200, without retry. The same request IDs returned their original reports on resubmission; the canonical ledger was unchanged.

| Saved report | Result | Provider / total latency | Intel UI peer review |
| --- | --- | --- | --- |
| `95a78f92-95fb-402f-99a6-546f76f796ca` | G1 ready: cycle and attempt populations, recovery and late confirmation | 9.637 / 9.648 s | 10/10 model-authored propositions supported |
| `9216914f-b6ba-402f-bca6-7b13230d72d2` | G2 ready: insufficient comparison evidence | 3.349 / 3.358 s | 4/4 model-authored propositions supported |

The Intel UI peer review (Intel-local reference: `runs/review-04/semantic-review-v12.md`) reports all 14 checked propositions. The application-owned audit sentence is excluded from that model denominator and verified separately against five exact correction records. Intel reports that all 117 captured source-field references match the saved database revisions; 31 model-cited and 35 application-summary-cited fields are tracked separately. The final browser run displays these actual saved replies, their measured latency, exact `null → "good_bin"` destination correction, citation dialog and application attribution. It performs no extra cloud request.

Within the reported Intel v12 run, this closes the observed audit-paraphrase defect within the new positive scope contract. Two selected simulation cases do not establish universal semantic correctness; unrestricted uncited model prose still needs review. Neither useful Gemma interpretation nor an HTTP 200 is physical acceptance. Original invalid replies remain available as historical evidence.

Matched physical comparison data, training, detector/dispatcher/adapter work and physical acceptance remain separate. The producing report describes the newer architecture as assigning dashboard/analytics to Klemen's Mac, interaction/voice to Jose's Mac, and authoritative records/training/execution to Intel, using the wording "ElevenLabs is now optional/undecided." That is attributed report wording, not an instruction that changes scope. The November 14 mandatory integration decision applies unless the owner changes it. The later November 15 owner architecture direction is recorded in the [Intel package instructions](../../../../AGENTS.md) and the canonical workspace's `AGENTS.md` ("Owner architecture update — November 15, 2026") and `context/THREE_HOST_ARCHITECTURE.md`; it records ElevenLabs as undecided and preserves the existing optional adapter and evidence. Current explicit owner instructions govern any discrepancy; this document neither chooses a substitute provider nor independently changes integration requirements. During this session's coordination delay the Mac recorded one finalized microphone utterance and simulation Decision 1 results. Those are attributed Mac results, not Intel microphone or physical acceptance. M20/M21/M23/M24 retain their original dependencies and acceptance criteria. The analyst cannot dispatch robot tasks, create reference labels or modify canonical outcomes.

## Available reply evidence and review limits

The Mac’s saved review of the exact transferred G1/G2 output subsets supports the concrete cycle/attempt arithmetic, retained failure, recovery counts, late recorded confirmation, separate correction fields and insufficient-comparison response described above. It matched **64 of the 66 cited source-field references** to the original M16 saved-simulation export. The remaining two references concern the other session and are corroborated by an earlier report subset, not by an original canonical export available in this review.

The complete **117-field** audit, its **51 uncited references**, the complete original provider request/report byte streams and the **14-proposition** scoring artifact were not supplied in those subsets. The **10/10 G1**, **4/4 G2** and **14/14 total** proposition scores remain the producing team’s UI peer-review result. That reviewer was reported as distinct from the backend author and provider operator; it is not an independently reproduced Mac scoring study or a general reliability estimate. The fixed application-owned audit sentence and backend arithmetic remain outside model inference credit. Provider metadata and measured waits were received as historical producer evidence; no new hosted call occurred in this document review.

## Producing session contributors and shared reporting

During the producing Intel session, Root owned integration, actual provider checks, deployment, watcher recovery and Studio availability. `/root/gemma_backend` owned analyst service/context/provider validation and semantic review. `/root/gemma_ui` owned analyst UI and browser verification. `/root/gemma_shared` published the attributed start, meaningful checkpoints and final handoff through the existing shared Mac connection and verified saved notes. These are dated contributor roles, not a current authorization to operate services.

Exact outgoing payloads and receipts are retained in the workspace's `context/outbox/` and `context/sync-receipts/`. Ordinary progress notes contain attributed results and selected evidence; publishing one does not automatically transfer or mirror Intel source files. Explicit source manifests/chunks and complete-delivery envelopes transport frozen source separately. Receipt, review, reconciliation, Git publication and deployment are distinct states. Notion status is tracked separately in `HachingJunction/NOTION_SYNC.md`.

## Later operating-status reports

Intel’s final handoff later identified the container Studio pause event as **November 14, 2026 at 22:47:45.038920 UTC**, following the reported unpause at **22:19:15.687453 UTC**. The **November 15, 05:43–05:45 UTC** window above was a later observation of the paused state. The actor and purpose remain unknown. These event times were received as Intel-reported metadata; this Mac document review did not query Docker or repeat the historical `docker unpause physical-ai-studio-xpu` command.

A newer Intel handoff, `be57f4f6-4f20-479e-bcb6-2164b85bae1b`, saved **November 15, 2026 at 06:21:13.287472 UTC**, reports the owner-requested automatic Intel receiver stop at **06:17:23.644558 UTC** and Codex logout at **06:18:13 UTC**. It states that restart was not authorized and separately reports the GET-only worker, passive watcher and main API preserved. Do not infer that the analyst preview stopped from the receiver stop. These are attributed observations, not a fresh health check or permission to restart, log in or invoke a provider.

A still later Intel handoff, `334eb852-954d-49e6-a7c7-90e250b27c85`, reports an observation at **November 15, 2026 at 06:45:47.972916 UTC** and was saved at **06:45:49.547539 UTC**. It reports one `SIGTERM` sent to the pinned main API PID **188282** at **06:36:26.816413 UTC**, followed by a **20-second** timeout with no replacement. Its reported host check at **06:39:33 UTC** found that old PID sleeping, no pending signals, one established connection, **no port 8000 listener** and unavailable health. It describes controlled recovery as being prepared, not executed or verified successful, and reports worker **417036**, watcher **279692** and dashboard **188283** preserved. This later report supersedes any inference that the earlier main-API availability observations still applied at that time. It does not establish the analyst preview's current health. The underlying activation/recovery evidence remains Intel-local; this document review did not query the host, send a signal, restart a service or verify a recovery.

The current project ownership remains dashboard/analytics on Klemen’s Mac, interaction and coordination on Jose’s Mac, and authoritative training/physical execution records on Intel. Use this document to inspect the historical result and, with the current host owner’s confirmation of availability, its existing saved reports. Any new provider evaluation or service operation is separate work requiring current authorization and ownership.
