# Gemma evidence analyst

The station implements explicit, asynchronous explanations of saved cycle evidence and bounded session comparisons. This is the isolated analyst portion of M20, with regression coverage contributing to M21. It does not complete the original task dependencies, live acceptance, or the required work of Nemotron, Gemini Decision 1, ElevenLabs, Studio, VLA, Anomalib or OpenVINO.

The application owns canonical outcomes, reference labels, counts, denominators, revisions, comparison eligibility and timing. Gemma supplies a separately labelled interpretation with citations. Reports are saved under the selected database directory's `analysis/` folder; they are never decisions, confirmations, corrections or canonical events. Analysis does not change replay, counters, physical cycle timestamps or robot control.

## Explicit API workflow

These routes use the station's existing bearer authentication. The frontend must obtain evidence first and submit a report only after an explicit user action. Opening history, replay, navigation, refreshing and reconnecting may fetch reports but must never POST new work.

1. `GET /api/v1/analysis/context?kind=cycle_explanation&sessionIds=SESSION&cycleId=CYCLE&sourceMode=simulation` captures bounded context without inference.
2. `POST /api/v1/analysis/reports` submits the following closed request shape. Unknown fields, including model names, endpoints, credentials, supplied facts and supplied metrics, are rejected.
3. Poll `GET /api/v1/analysis/reports/REPORT_ID`. `GET /api/v1/analysis/reports?sessionId=SESSION&cycleId=CYCLE&limit=50` returns the newest matching reports; the limit is bounded to one hundred.

```json
{
  "requestId": "client-generated-unique-id",
  "kind": "cycle_explanation",
  "sessionIds": ["saved-session"],
  "cycleId": "saved-cycle",
  "sourceMode": "simulation",
  "question": "Explain the final cycle outcome and retained attempt evidence.",
  "expectedSelectionDigest": "COPY_THE_CONTEXT_CONTENT_DIGEST"
}
```

The digest placeholder above must be replaced with the exact SHA-256 `contentDigest` returned by the context endpoint. Source mismatch is HTTP 409 before inference. Empty or entirely unfinished eligible populations return HTTP 422 with `No data yet`; no report or provider request is created.

The POST returns HTTP 202 and an application-owned report. States are `queued`, `running`, `ready`, `rejected`, `failed` and `interrupted`. `freshness` is computed independently as `current` or `stale` when a report is read; a subsequent correction never rewrites its captured context or accepted answer. Missing credentials, permissions, HTTP rejection, timeout, truncation, malformed JSON, invalid citations and comparison policy violations have distinct error codes.

If analyst storage is damaged or unavailable, the canonical station API remains available. The report-list response includes `warnings` with code `analysis_storage_unavailable`, readable reports remain accessible, and new analysis is blocked with HTTP 503. Invalid files retain their original bytes. A final-save failure exposes a failed report with `persistenceState: unavailable`; it does not claim that a ready report was durably saved. Repair the affected analyst storage and restart its service before new analysis. This recovery is separate from canonical database repair and never authorizes a robot or Studio restart.

Request identifiers are persistent and idempotent: identical input returns the original report; changed input with an existing identifier returns HTTP 409. Successful equivalent context/question/model/prompt requests can reuse the accepted report and return `cacheReused: true`. Failed, rejected or interrupted jobs require an explicit new identifier to retry. Reopening a report never retries it.

## Bounded evidence and provenance

Context reads occur in one SQLite transaction and end before cloud inference. The digest covers selected source records, revisions, scope, context version and comparison specification; it excludes volatile read timestamps. The event watermark and captured revisions remain available for audit. A referenced session-level decision/model run is included through its recorded IDs, with matching session checks. No embedded URL is fetched.

The full captured context retains source references and revision mappings. The provider receives a smaller projection containing exact fact values with source kind, entity ID, session ID and revision, typed metric values and denominators, gaps, evidence flags and sampling counts. It does not receive repeated verbose source-reference lists. The report preserves both the full context and the actual projected request. This reduces prompt size without replacing the canonical source mapping used by the UI and validator.

Context version `morph-evidence-v6` corrects the historical-record label: ordinary lifecycle revisions are record history, not automatically a correction audit. It also rejects blank or invalid reviewed comparison metadata. Earlier contexts and hosted reports retain their original versions; this version change can mark an earlier report stale without changing any canonical outcome.

Cycle evidence includes the commanded and observed destinations separately, the selected inspection and actual source-frame metadata, independent reference labels, ordinal attempts, confirmations, corrections and relevant historical outcome revisions. Raw images are not sent. Provider output, transcripts, retry reasons and error/review prose are bounded, labelled untrusted excerpts. Credentials and raw environment dumps are excluded.

Application limits are one cycle or exactly two sessions, two hundred facts, fifty exemplar cycles, five hundred characters per untrusted excerpt, and forty KiB of serialized context. Whole-population arithmetic precedes deterministic outcome-stratified exemplar sampling. Shown and omitted cycle IDs are disclosed. Required cycle evidence that cannot fit produces `too_large`; a failed attempt is never silently dropped.

The existing canonical calculator is reused with an optional private cycle-ID filter. Default public metrics retain their previous behavior. Cycle and attempt ratios show their exact included/excluded record IDs. Reference coverage, retries, recovery, first-attempt successes and full-cycle timing are separate metrics. A recovered correct cycle can have a failed retained attempt: the saved acceptance example remains one correct finished cycle, one successful attempt among two finished attempts, one retry, one recovered cycle and no first-attempt successes. A later confirmation does not change the original cycle duration.

Each report retains captured input, strict output, validation decision, requested and returned model identifiers, response ID, usage when provided, HTTP status, sanitized provider request/response, source digest, contract/prompt versions and timestamps. Monotonic timings distinguish provider latency, validation time and total report time. Provider errors also retain the actual sanitized request and elapsed latency when an HTTP attempt was made.

## Comparison eligibility

Use `kind=session_comparison`, exactly two distinct `sessionIds`, no `cycleId`, and explicit `baselineSessionId` and `adaptiveSessionId` in both context query parameters and the POST body. Both sessions must match the selected `sourceMode`. An optional `comparisonSpecId` must name a server-owned specification; browser-provided metadata is never accepted.

Reviewed specifications may be provisioned in `analysis/comparison-specs.json` using this shape:

```json
{
  "reviewed-specification-id": {
    "comparedVariable": "recovery",
    "sessions": {
      "baseline-session-id": {
        "configId": "recorded-configuration-id",
        "protocolVersion": "reviewed protocol and version",
        "population": "reviewed objects and independent reference population",
        "cameraPreprocessing": "reviewed camera and preprocessing",
        "detectorThreshold": "reviewed detector and threshold",
        "policy": "reviewed policy",
        "recovery": "baseline recovery setting",
        "robotWorkspaceCalibration": "reviewed robot, workspace and calibration",
        "hardwareDevicePrecision": "reviewed hardware, device and precision",
        "timingBoundaries": "reviewed timing boundaries"
      },
      "adaptive-session-id": {
        "configId": "recorded-configuration-id",
        "protocolVersion": "reviewed protocol and version",
        "population": "reviewed objects and independent reference population",
        "cameraPreprocessing": "reviewed camera and preprocessing",
        "detectorThreshold": "reviewed detector and threshold",
        "policy": "reviewed policy",
        "recovery": "adaptive recovery setting",
        "robotWorkspaceCalibration": "reviewed robot, workspace and calibration",
        "hardwareDevicePrecision": "reviewed hardware, device and precision",
        "timingBoundaries": "reviewed timing boundaries"
      }
    }
  }
}
```

These strings illustrate the schema, not verified configuration evidence. Do not install this example as a real specification. Match actual reviewed configuration contents and the canonical session's `configId`. Missing metadata makes compatibility `unknown`; differences beyond the deliberately compared field make it `incompatible`. In either case both descriptive tables remain visible, deltas are withheld and Gemma must answer `insufficient_evidence`. Even compatible comparisons prohibit superiority and causal claims; backend percentage-point deltas remain descriptive. The current saved simulation lacks this reviewed comparison metadata.

Every reviewed metadata field above must be a nonempty string describing the reviewed configuration. Matching blank strings cannot establish compatibility. Invalid specification container shapes produce a controlled unavailable error; they do not become matched comparisons or an unhandled API failure.

For unknown or incompatible comparisons, the model request specifically asks for one short interpretation of the named compatibility gaps, citing session configuration facts and no metrics. It excludes outcome and recovery narrative for that request; the complete deterministic tables remain available separately. Compatible comparisons receive a different descriptive instruction with explicit session roles and source session IDs. These instructions guide generation; local validation and hosted evaluation remain necessary.

## Provider and validation boundary

The only analyst model is `gemma-4-26b-a4b-it` at Google's fixed `generateContent` endpoint. The server uses `GEMINI_API_KEY` or `GOOGLE_API_KEY` from process configuration or the literal `station/.env.providers` file. That file must be a regular owner-only file; it is never sourced as shell code. No model fallback, function calling, browsing, structured-output assumption or repair request is used.

The transport disables redirects, caps the response at 256 KiB and applies a twenty-five-second total deadline. One file-locked worker serves a bounded queue of four waiting jobs. A second station process can read reports but cannot enqueue competing work in the same analysis directory. Startup marks unfinished reports interrupted, repairs a missing request index from persisted evidence, and never resubmits them. Shutdown cancels queued work and allows only an already running bounded request to finish.

Saved analysis JSON reads are limited to one MiB per file and reject duplicate keys and non-finite numbers. Atomic writes synchronize both file contents and the containing directory. A damaged report/index, failed write or malformed provider error cannot terminate the sole worker or abort canonical station startup. Storage warnings remain latched until repair and service restart so an uncertain request identity cannot cause a duplicate cloud request. A shutdown check after dequeue prevents a queued request from starting during closure. No automatic cloud retry is introduced.

Validation requires HTTP 200, exactly one final candidate with `STOP`, the expected returned model ID when supplied, text-only final parts, and one exact JSON object. Thought parts are not displayed as an interpretation. Duplicate keys, non-finite values, unknown fields, invalid enum/length values, foreign citation IDs, digits, percentage signs, markup and URLs in generated prose are rejected. All metric rendering and evidence navigation use trusted application data. No Markdown fence extraction or automatic JSON repair is performed.

Additional event checks were added after actual hosted development replies invented correction and recovery narratives. Backend flags distinguish real correction records from ordinary lifecycle revisions, confirmation after the persisted cycle end from ordinary confirmation, canonical recovery from other outcomes, and retained failed attempts from cycle-level failure. Recovery, correction and late-confirmation wording require the corresponding flags and cited supporting metrics/record types. The observed comparison of an attempt ratio with a first-attempt-success count is rejected. These conservative checks can reject an otherwise accurate mention of an absent event; the prompt instructs the model to avoid those event terms when the flags are false.

Five actual earlier hosted replies are retained as regression fixtures in `tests/fixtures/gemma-v5-semantic-regressions.json`. They demonstrate why structural acceptance alone was insufficient. New prompt/context versions create different cache identities; earlier rejected or semantically inadequate development reports remain preserved.

The later actual missing-reference reply is retained in `tests/fixtures/gemma-v6-known-coverage-regression.json`. It incorrectly called detection coverage unavailable even though the application supplied zero checked examples and a known total population. A narrow local guard now rejects that observed wording and equivalent claims of unknown reference coverage. It still permits incomplete or zero coverage and unavailable agreement accuracy. This targeted regression does not retroactively improve the historical hosted evaluation or establish general semantic entailment.

Citation membership and schema checks do not establish semantic entailment. Hosted answers must still be evaluated for supported claims, coverage, absent evidence, sample counts and usefulness compared with the deterministic trace. A passing build, fake response, or HTTP 200 alone is not product acceptance.

Prompt version `gemma-evidence-v10` requests a neutral cycle headline: `Simulation cycle evidence` or `Live cycle evidence`, matching the captured source mode. Local validation accepts surrounding whitespace, case differences and one terminal period without rewriting the actual model reply. Other cycle headlines are rejected. For a recorded recovered cycle, all five core metric IDs must appear across the interpretations: cycle ratio, attempt ratio, first-attempt successes, recovered cycles and retries. Each interpretation still permits at most four metric IDs. Comparison headline and citation rules remain unchanged. The actual v7 recovery response is preserved in `tests/fixtures/gemma-v7-recovery-coverage-regression.json`; separate regressions demonstrate its ambiguous headline and omitted first-attempt metric.

Context version `morph-evidence-v7` supplies bounded, application-selected current-record citation requirements. A recovered-cycle count interpretation requires the current cycle, a preceding failed attempt and the final attempt in that same paragraph. First-attempt and retry counts have their own current-record witnesses. Recorded late confirmation requires the actual confirmation, cycle and final attempt among the interpretations; an existing correction audit requires an actual outcome-correction witness. Historical revisions cannot substitute for current outcomes. These witnesses explain the authoritative metrics; they do not replace full-population arithmetic or imply that an excerpt contains every attempt.

The v10 prompt explicitly distinguishes recovered cycles from additional retry attempts and requests the timing relationship of a recorded late confirmation. When `causal_evidence_unavailable` is supplied, hypotheses are rejected; absence of evidence must remain a limitation rather than become an invented cause. Three problematic actual v9 API replies and the browser reply with a neutral terminal period are preserved in `tests/fixtures/gemma-v9-citation-regressions.json`. General current-record dependency checks reject their missing evidence, and the hypothesis rule rejects the two absence-only hypotheses. The browser response passes the corrected headline rule but remains rejected for its separate missing metric witnesses. These targeted constraints do not establish general semantic entailment: a model can still use correctly cited values imprecisely, so fresh hosted review remains necessary.

The final generation revision `gemma-evidence-v11` retains that validator and context version. It supplies a response outline with application-selected citation arrays and empty hypotheses, asking Gemma to write only the explanation text. A recovery outline separates cycle/attempt ratios, recovery/first-attempt/retry counts, recorded late confirmation and the correction audit. Other saved-cycle outlines describe their outcomes and reference-evidence limitations; unknown comparisons retain their single configuration-gap paragraph. The provider request explicitly sets temperature to zero. Returned citations are never repaired or replaced: the actual response must pass the unchanged validator, and input/output provenance remains persisted. Outline tests verify bounded citation/schema consistency, not generated usefulness. The v10 rejection evidence remains separate from subsequent v11 hosted validation.

## Local regression command

Run the existing prepared Python runtime from the workspace:

```text
/home/intel/Documents/Junction/morph-intel-transfer/morph-context/.junction-setup/python/bin/python -B -m pytest station/tests -q
```

`station/tests/test_analysis.py` covers recovery/audit denominators, immutable canonical state, stale corrections, idempotency/cache/restart, single-worker queue bounds, empty eligibility, source separation, explicit comparison roles, full-population sampling, configuration compatibility, authentication, hostile output, unknown citations and mocked HTTP redirect/size/deadline behavior. These tests do not contact providers or hardware. Actual Intel hosted evaluation artifacts are retained separately by the parent implementation session.
