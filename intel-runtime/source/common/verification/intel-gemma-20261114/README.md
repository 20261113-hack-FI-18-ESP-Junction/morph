# Intel provider and Gemma implementation evidence

Date: November 14, 2026. Session `f191d039-8f71-48ba-bb6a-91e15bd096c6`. All application exercises below use persisted simulation or synthetic provider input. Physical acceptance remains open.

The approved Gemma analyst is implemented in the existing Intel station backend and dashboard source. It provides an explicit saved-cycle explanation and bounded session comparison, captures immutable evidence and model provenance, validates hosted replies locally, and saves reports separately from canonical records. The saved M16 recovery example has been explained by the actual hosted `gemma-4-26b-a4b-it` model and exercised in Chromium. Backend facts remain authoritative; a structurally accepted interpretation is not guaranteed to be semantically correct.

## Transfer and provider access

The ZIP `Morph-Intel-Providers-Gemma-20261114-214614.zip` was found in Downloads and extracted outside the existing application. Its SHA-256 is `fa76d7219fa575d411ada186f4da46b00146d59616df2e8784bb50901d0933af`, size 484846 bytes, with 134 files. Verification passed all 133 listed file hashes and 42 offline tests on this Intel. The installer dry-run identified different local README/tests/image assets. The existing `check.py` exactly matched the incoming version, so the installed utility and Intel adaptations were retained. No reference station or context snapshot was overlaid.

Credential restoration succeeded without an existing-key conflict. The provider file remains ignored and mode 0600; the temporary task-owned unlock file was removed. No unlock material or credentials belong in this evidence directory. See [provider-setup.json](provider-setup.json) for paths, hashes and permissions.

| Actual minimal request | Requested model | HTTP | Latency | Observed result |
| --- | --- | --- | --- | --- |
| Decisions | `gemini-decision-1` | 200 | 302.68 ms | Permitted pause option; this API supplies no returned model field |
| Gemma | `gemma-4-26b-a4b-it` | 200 | 672.23 ms | READY; returned model matches |
| Generic Gemini | `gemini-3.5-flash-lite` | 200 | 2389.68 ms | READY; returned model matches |
| Verda | `nemotron-3.5-super-vl` | 200 | 600.64 ms | Described the synthetic red rectangle; returned model matches |

Verda used `https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1`. No model substitution was used. Complete sanitized requests, responses, status and timing are in [the live provider report](../../HachingJunction/station/verification/provider-checks/97f2eea5-9d19-4900-9b6c-e3f5bed2709d.json). [ElevenLabs preflight](../../HachingJunction/station/verification/provider-checks/e7dcd443-a85a-4b21-a6fa-18167daac371.json) remains `blocked_missing_credential`; catalogue access, Scribe, microphone input and utterance finalization are not accepted.

## Implemented source

- [Station analyst contract](../../HachingJunction/station/ANALYST.md): routes, bounded context, exact metric ownership, persistence, worker lifecycle, errors and comparison policy.
- [Analysis service](../../HachingJunction/station/morph_station/analysis.py), [context builder](../../HachingJunction/station/morph_station/analysis_context.py), [contract](../../HachingJunction/station/morph_station/analysis_models.py), and [provider transport](../../HachingJunction/station/morph_station/analysis_provider.py).
- [Dashboard analyst](../../morph-station/src/analysis/EvidenceAnalystPanel.tsx) and [UI integration notes](../../morph-station/src/analysis/README.md).
- Narrow existing-file integrations in `station/morph_station/api.py`, the optional private metric filter in `store.py`, dashboard `src/App.tsx`, the allowlisted station proxy and test script. Root snapshots of the existing UI files are retained in [before](before); the colleague's same-directory dashboard work was preserved with focused edits.

The analyst sends no robot commands, creates no reference labels or confirmations, and changes no canonical outcomes. Reports contain separate provider latency and total job duration. Creating analysis requires an explicit POST; mounting, navigation, refresh and replay perform reads only. The bounded worker does not hold a canonical database transaction while waiting for the cloud. Stale corrections, duplicate requests, interrupted jobs, provider errors and invalid citations have explicit behavior.

## Actual recovery demonstration

The original M16 export SHA-256 is `b9b1ebb96928b1d2442491f6d08f7f5b36669de130d57d3b81d7f7e78971d0d8`. [prepare_cases.py](prepare_cases.py) restored its exact records and revisions into a separate verification database and verified the copied evidence. Additional saved evaluation cases are labelled simulation. No live database was used.

The application shows these canonical facts together:

| Measurement | Recorded value |
| --- | --- |
| Correct finished cycles | 1 / 1 |
| Successful finished attempts | 1 / 2 |
| Retries | 1 |
| Recovered cycles | 1 |
| First-attempt successes | 0 |

Actual browser-created report [`561fb240-3ca9-434b-bcef-7bd376b1ed49`](runs/hosted-03/data/analysis/reports/561fb240-3ca9-434b-bcef-7bd376b1ed49.json) uses prompt `gemma-evidence-v7`, context `morph-evidence-v5`, contract `gemma-brief-v1`, and the requested/returned Gemma model above. Its HTTP status is 200, provider latency 11631.86 ms, total job duration 21020.94 ms, and input 4521 tokens. The total includes queue time; it is not robot cycle duration. Its actual text connects the failed first attempt, successful retry, recovered outcome and retained unverified-to-confirmed audit, and states that the physical cause of failure is undocumented. All raw output and exact citations remain saved.

The peer review finds this useful for navigating the deterministic trace, with limitations: its headline loosely attributes population differences to late confirmation, and its prose omits the first-attempt-success metric, which remains visibly zero in the canonical card. The complete review is retained alongside the reports. This is an agent evidence review, not an operator usability study or proof of general model reliability.

The earlier v6 recovery report [`6056fa5c-0c85-474b-916c-16de3f0e2916`](runs/hosted-03/data/analysis/reports/6056fa5c-0c85-474b-916c-16de3f0e2916.json) explicitly cites all five required metric IDs, with 9/10 supported atomic claims, one ambiguous audit phrase, no unsupported claims, and 107/107 exact captured source fields. Of those captured fields, 62 belong to facts actually cited by the v6 answer; the v7 browser answer selects facts containing 68 fields from the same 107-field context. [Its rubric](runs/hosted-03/semantic-review-recovery.json) and the original response are preserved; neither is a hand-authored substitute for inference.

## Evaluation and regressions

[The frozen v6 seven-case evaluation](runs/hosted-03/hosted-results-96fb4bf8-f0b5-4e77-9ad5-4b7a81bd79e8.json) includes recovery, missing confirmation, classification mismatch, audited reference correction, malicious untrusted text, missing reference and unmatched session comparison. Six replies passed structural validation; comparison was rejected. All seven requests returned HTTP 200. Provider latency ranged from 8260.87 to 10071.39 ms, median 8981.76 ms; prompt inputs ranged from 2814 to 4141 tokens. These small designed cases are not a statistical reliability estimate.

[Independent claim review](runs/hosted-03/semantic-review-all-cases.json) checked the six rendered replies: 43/49 atomic claims supported, five ambiguous, one unsupported; 372/372 captured source fields matched their persisted revisions, including 225 fields belonging to model-selected fact citations. Captured-field verification and model citation coverage are different measurements. The unsupported claim called reference coverage unavailable when it was known to be zero checked out of one object; accuracy with no checked examples was the unavailable quantity. Mean usefulness was 3.5/5 by an agent rubric against the deterministic trace. All seven cases retained immutable canonical state, ledger SHA-256 `151bc4e567c482a0b66c38466af9cd730a18e3e9ee95979f2222da4768d65490` before and after. The initial evaluation JSON's pending-semantic-review label records its earlier creation time; the separate review is the later evaluation result.

Early development replies in `runs/hosted-02` remain preserved: fenced JSON, an unknown citation, forbidden prose, invented late-confirmation/correction narratives, and two actual HTTP 429 input-token quota errors. Five actual semantic failures were made regression fixtures. Compact evidence projection and spacing distinct evaluation requests removed quota failures in the later seven-case sample; no automatic repair, hidden model substitution or automatic provider retry was introduced.

[Verification summary](verification-summary.json) records **131 final backend tests**, **50 frontend/proxy tests** and **11 prototype tests** passing, plus type checking and an isolated production build. The final UI accessibility change additionally passed all 24 analyst tests and type checking. The earlier 123-test backend evidence remains preserved; the final eight additional regressions cover comparison scope and the actual coverage error without changing its historical evaluation score.

[Browser run 02](runs/hosted-03/browser-02/browser-results.json) records the original explicit hosted G1 action. It retained later harness/accessibility failures. [Browser run 03](runs/hosted-03/browser-03/browser-results.json) passed all eight checks while reusing that report with zero inference POSTs: exact fact cards, captured failed-attempt citation, late-confirmation audit, keyboard focus, navigation/reload/replay, insufficient comparison, desktop/mobile widths, and unchanged canonical exports/event sequence 126. No browser authorization credential was present. [Desktop report](runs/hosted-03/browser-03/desktop-hosted-report.png) and [mobile comparison](runs/hosted-03/browser-03/mobile-insufficient-comparison.png) are saved screenshots.

## Comparison and remaining boundaries

Comparison accepts exactly two saved sessions with explicit baseline/adaptive roles and source mode. The backend computes full-population metrics before bounded exemplar selection. Reviewed protocol/population/camera/detector/policy/workspace/hardware/timing metadata is absent for the saved pair, so compatibility is `unknown`. Both descriptive tables remain visible, with one cycle per session; improvement deltas and winner/causal claims are withheld.

The v6 comparison was rejected for contract violations and also contained a false cross-session revision narrative. The first v7 comparison [`91029b30-09ee-4609-ad3b-bc3e205e9bbd`](runs/hosted-03/data/analysis/reports/91029b30-09ee-4609-ad3b-bc3e205e9bbd.json) contained correct descriptive values but ignored the metadata-only request and omitted required supporting recovery citation in its final statement. The local validator rejected it. These failures remain preserved.

Final prompt **`gemma-evidence-v8`** adds explicit source-session identity and limits non-comparable analyses to configuration gaps. The full immutable context remains version v5. The actual subsequent report [`ba5d2c29-9477-41d6-8c3e-b39c1a15bd24`](runs/hosted-03/data/analysis/reports/ba5d2c29-9477-41d6-8c3e-b39c1a15bd24.json) passed local validation with **`insufficient_evidence`**, HTTP 200, exact requested/returned model, **2819.88 ms provider latency**, 2833.32 ms total duration and 3108 input tokens. It cites the two saved session configuration facts and says: “Configuration identifiers alone do not establish reviewed matching protocol, population, settings and timing boundaries.” It makes no outcome, recovery, improvement or winner claim. An identical request reused the same report. All sixteen deterministic metric rows remain available separately.

[Independent v8 comparison review](runs/hosted-03/semantic-review-v8-comparison.json) found **5/5 supported atomic claims**, zero ambiguous or unsupported claims, and **10/10 exact captured source fields**. Agent usefulness was **3/5**: a useful concise limitation with modest added value over the deterministic compatibility reason. This demonstrates the required insufficient-evidence behavior when matching data is unavailable; a supported performance comparison remains unverified. The final code also rejects the preserved actual coverage-error fixture as `known_coverage_misstated`, while allowing known zero/incomplete coverage and undefined accuracy. This targeted check is not a general semantic-entailment guarantee.

[Final v8 comparison browser verification](runs/hosted-03/browser-g2-v8-2026-11-14T21-45-58-145Z/browser-results.json) passed four additional checks: the exact hosted insufficient-evidence answer and separate descriptive tables, no improvement deltas, desktop/mobile layout, and zero inference POSTs or exposed browser credentials with event sequence unchanged at 126. This is separate from the earlier eight G1/browser checks. The imported database contains 69 event rows whose maximum sequence is 126; row count and sequence watermark are different quantities.

M20/M21/M23/M24 receive only this approved analyst contribution. Original dependencies, acceptance criteria and sponsor submission requirements remain. M16 stays Done. Nemotron visual evidence, Gemini Decision 1 orchestration, ElevenLabs finalized speech and the substantive Studio/VLA/Anomalib/OpenVINO workflow still require their separate product and physical acceptance.

Leader is `5B91030668`; follower is `5AE6075066`. The owner continues hardware diagnosis. This session opened no robot ports or cameras, changed no calibration, and commanded no motion. Existing services on 3001/8000/3000/7860 were preserved. The analyst preview remains running at **`http://127.0.0.1:50139`**, with its owned API at **`http://127.0.0.1:52197`**, using the separate build and saved-simulation database. Its [running configuration](runs/hosted-03/services.json) and [demonstration instructions](DEMO.md) describe its lifecycle. Only the earlier owned verification services were restarted for final v8; their configuration/logs/cleanup are preserved under `runs/hosted-03/service-version-v7`. Updating source does not imply the colleague's current dashboard/API process has reloaded it.

At **21:47:33 UTC**, HTTP reads succeeded on 3001, 8000, 3000, 50139 and 52197. Container Studio on **7860** timed out after three seconds, then again in a [single ten-second read-only recheck](studio-7860-final-recheck.json) begun at **21:47:49 UTC**. Earlier HTTP 200 evidence remains dated history. No cause is established and no container restart or hardware intervention was performed; owner-led diagnostics remain separate.

Shared Mac notes, exact payloads, read-back receipts, source hashes and task update state are retained in [the active workspace's shared evidence](../../HachingJunction/context/verification/gemma-intel-20261114). Every delegated contribution is attributed through the designated shared reporter. Mac delivery and Notion task read-back remain distinct assertions.
