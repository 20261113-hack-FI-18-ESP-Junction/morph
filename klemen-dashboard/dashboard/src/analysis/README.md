# Gemma evidence analyst UI

This isolated module adds an explicit saved-evidence analyst to Quality & history. It consumes the station analysis API and does not mutate the canonical station store or issue control commands. The selected provider remains server-side `gemma-4-26b-a4b-it`.

## Integration

Import `EvidenceAnalystPanel` from `./analysis/EvidenceAnalystPanel.tsx` in the application and mount it alongside the existing `QualityHistoryView`:

```tsx
<EvidenceAnalystPanel
  snapshot={snapshot}
  onOpenSource={(source) => {
    if (source.sessionId === snapshot.activeSession?.id && source.cycleId) {
      setSelectedCycleId(source.cycleId);
    }
  }}
/>
```

The callback is optional navigation to the **current** cycle trace after the user has reviewed the analyst's own cited-evidence dialog. It must not describe current records as the cited historical revision. The built-in dialog shows captured fields, record identity, revision, selected field, evidence time and saved audit-note excerpts. Image requests use the existing authenticated evidence route, with recorded capture time and hash when supplied.

The same-origin proxy must allow `GET /api/v1/analysis/context`, `GET /api/v1/analysis/reports`, `GET /api/v1/analysis/reports/{id}` and explicit `POST /api/v1/analysis/reports`. The client attaches `X-Morph-Intent: evidence-analysis` only to POST. Context queries use repeated `sessionIds` and explicit comparison roles.

## Behavior and limits

- Reading facts, navigation, reconnecting, refreshing saved reports and replay never submit inference. Only the Generate button or an explicit retry submits an analysis request.
- Facts and metric arithmetic come from the backend. Saved report facts remain immutable when a correction makes the report stale. Current facts are available separately for explicit regeneration.
- Saved correction records show each captured target, field, typed previous/replacement value, author, time and source revision directly above the explanation. `null`, empty strings, zero and false retain their JSON meanings. Incomplete, malformed or inconsistently cited correction shapes remain available in the generic evidence ledger; the UI does not infer missing values or substitute the current cycle trace. The correction list remains available for stale and rejected reports.
- For the reviewed v12 prompt contract only, the exact application-owned audit preservation sentence is labeled **Application audit summary** when its citations reference correction facts exclusively and contain no metrics. Other model wording and older saved replies retain their original attribution and content. This label does not establish that arbitrary model prose is semantically correct.
- Pending request IDs are retained per selection scope in browser session storage. A confirmed report or explicit abandonment clears the pending entry. If browser storage is disabled, the current component retains the request in memory.
- Question drafts are retained independently per source, cycle or ordered comparison selection in browser session storage. Selecting a mode does not clear a draft. A recovered unconfirmed request displays its original submitted question; the saved report separately displays the question it answered.
- The context, report envelope and generated response are checked before rendering. An unreadable report is excluded with a visible warning while valid reports and deterministic facts remain available. Storage warnings or unsuccessful fact/report reads disable new submissions until a healthy refresh. Selecting another saved report does not clear a storage failure.
- API requests have a 40-second response deadline covering headers and body. A timed-out submission remains unconfirmed with its original request ID; reconnecting or refreshing never retries it automatically. Provider job deadlines remain owned by the backend.
- Latency labels round recorded values for readability, showing seconds and rounded milliseconds for values above one second. Persisted measurements are unchanged. Citation views are remounted for a different evidence digest or report so old dialog state cannot attach to another record.
- Comparison role and specification identity are checked along with source, session and cycle identity. Unknown or incompatible configurations show descriptive tables and an insufficient-evidence state.
- Replay accepts only a saved report matching a previously captured context for the same frozen local record fingerprint. A context is captured for replay only when its backend event watermark also matches the station snapshot watermark. After a fresh browser load with no captured context, it shows that a verified matching historical report is unavailable. It never replaces frozen replay facts with a current context read.
- Generated prose renders as ordinary React text. Supplied citation mappings provide navigation; model text never supplies a URL. Unknown references or rejected reports hide the model explanation while retaining deterministic facts.
- No eligible finished denominator disables new inference. Provider errors and saved interrupted jobs remain visible; another model is never substituted.

## Validation

The current package uses the MCP adapter and a 40-second browser deadline. See [package verification](../../../VERIFICATION.md) for checks rerun on this source. The dated Intel browser reports below are preserved source-document claims; their original artifacts are not included in this package.

The November 15 saved-correction adaptation passed 39 focused analyst tests, all 122 dashboard tests and TypeScript checking. Its [source and reconciliation record](../../../verification/analyst-ui-r2-20261115/README.md) preserves the received originals separately. The checks cover typed values, stale/rejected reports, escaped text, citation identity and timestamps with an explicit timezone; no browser, provider or physical action was performed for this adaptation.

From the dashboard directory:

```bash
node_modules/.bin/tsx --test src/analysis/analysis.test.tsx
node_modules/.bin/tsc --noEmit
```

The focused suite covers source/navigation isolation, reconnect, duplicate actions, persisted pending request recovery, explicit abandonment, stale revisions, replay, zero eligible records, provider errors, context-role mismatch, safe rendering, exact citation fields, backend metric denominators, comparison gaps, request headers and provenance. These checks use test responses and server rendering; they do not establish a hosted model result, browser interaction acceptance or physical verification. The root integration session owns the live application and hosted-response checks.

On November 14, 2026, the initial integration passed 24 focused tests and TypeScript checking. The delegated browser acceptance against the isolated verification application passed all eight checks at 21:38 UTC. It checked the exact recovery denominators, captured citation revisions and correction notes, keyboard focus, saved reports, replay, insufficient comparison evidence, 1440/390-pixel layouts, unchanged canonical exports and event sequence, and absence of browser authorization credentials.

The final browser result (original Intel source reference: `../../../verification/intel-gemma-20261114/runs/hosted-03/browser-03/browser-results.json`) reused actual hosted report `561fb240-3ca9-434b-bcef-7bd376b1ed49` without a new inference request. The preceding browser result (original Intel source reference: `../../../verification/intel-gemma-20261114/runs/hosted-03/browser-02/browser-results.json`) contains the original explicit hosted action: exact requested and returned Gemma model, accepted response and measured provider latency of approximately 11.632 seconds. That earlier run retains its failed selector/assertion checks; the subsequent accessibility labels and corrected replay assertion were verified in the final run. These are saved-simulation and browser results. Semantic claim evaluation and physical acceptance remain separate evidence.

The subsequent reliability review at 22:11 UTC reproduced actual question loss on mode selection, plus injected unreadable-report crashes and storage-failure controls that stayed enabled. Its immutable before-change observations (original Intel source reference: `../../../verification/intel-reliability-20261114/analyst-review-2026-11-14T22-11-15-181Z/observations.json`) retain those failures. The reliability changes passed 33 focused tests and TypeScript checking.

The rebuilt dashboard passed eight browser regression checks (original Intel source reference: `../../../verification/intel-reliability-20261114/analyst-regression-2026-11-14T22-21-47-734Z/browser-results.json`) at 22:21 UTC. They cover independent question drafts through navigation and reload, report-storage warnings and recovery, malformed response containment, rejected/failed/interrupted reports, escaped model prose, exact-request retry after a lost response, selection races, stale citation revisions, readable latency, and desktop/mobile layout. The two POST requests in that suite were intercepted inside the browser; neither reached the server. Four broader navigation checks (original Intel source reference: `../../../verification/intel-reliability-20261114/dashboard-navigation-2026-11-14T22-23-23-732Z/browser-results.json`) subsequently covered all three dashboard views, source switching and read-only replay. Canonical event sequence stayed at 126 and the compared session exports were unchanged.

A separately authorized actual hosted browser request (original Intel source reference: `../../../verification/intel-reliability-20261114/deployed-browser-inference-2026-11-14T22-24-20-792Z/browser-results.json`) on the promoted preview at 22:24 UTC received HTTP 202, reached the exact Gemma model with HTTP 200 and 8253.321 ms provider latency, and persisted report `9b0f843b-c75d-41b3-b3f1-26877d4bae41`. Local validation rejected that v9 reply with `unsupported_cycle_headline`. The UI recovered and displayed the rejected report after navigation and reload, with one POST, no automatic retry, no page error and unchanged canonical evidence. This establishes the tested rejection/recovery behavior; it does not establish an accepted useful explanation. The failed hosted result and screenshots remain immutable evidence for the subsequent backend refinement. Rejected headlines use plain-language UI text while the exact validation code remains available in the validation details.
