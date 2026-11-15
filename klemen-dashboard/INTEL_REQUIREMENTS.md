# Intel requirements for the Morph dashboard

Prepared November 15, 2026, Europe/Ljubljana (UTC+01:00), for the owner-authorized dashboard upgrade. This checklist separates source changes from Intel adoption and missing physical producers. It does not claim that the running Intel API, worker, camera, models or robot have been verified through Klemen's dashboard.

Intel remains the authority for records and physical execution. Klemen reads and analyzes those records. Jose owns interaction, coordination and intentional control through the other team's NVIDIA tunnel. Dashboard load, refresh, reconnect and replay must remain read-only with respect to motion.

## Current connection checkpoint — November 15, 2026

At 07:22–07:29 UTC, the restored `intel-main` API was independently read through the existing authenticated MCP and displayed in the actual Mac dashboard. Schema/dashboard/detail/image/context reads succeeded with exact response hashes. The service contains one saved simulation session and five cycles at event cursor 50; Live has no eligible session. The retry image is a 1×1 synthetic PNG. Current camera discovery and online hardware capabilities remain unavailable. This advances the dated adoption checklist below without establishing a physical session, camera video or provider invocation. Use [the working-system guide](../WORKING_SYSTEM.md) and its GET-only checker for the current entry points.

## Delivery and adoption boundary

The upgrade adds a bounded dashboard read to the canonical source package at `intel-runtime/source/common/HachingJunction/station/`, the corresponding communication allowlist and a matching Klemen client. Its detailed wire contract is documented in [Intel dashboard API](../intel-runtime/source/common/HachingJunction/station/INTEL_DASHBOARD_API.md). Source changes and local software tests do not update the live processes.

`GET /api/v1/dashboard` accepts optional `sessionId` and `cycleId`, `sourceMode=live|simulation`, and a recent-cycle `limit` (default 20, maximum 100). The response supplies one coherent `lastEventSequence`, its `generatedAt`, selected source/session, `sessions`, the existing `snapshot` and authoritative `metrics`, `recentCycles`, `cameras`, `currentDetail` and `detail`. These reads occur in one SQLite read transaction. No session export belongs in this request.

`sessions.items` contains the newest 50 sessions in the selected source mode; an explicitly selected older session remains available as `snapshot.session` even when it is absent from that list. `recentCycles` contains `items`, `offset: 0`, `limit`, `total` and `hasMore`. `currentDetail` preserves the complete current cycle, while `detail` contains the optional focused `cycleId` or the same current detail. A missing session/cycle returns 404; a source/session mismatch or a cycle outside the selected session returns 409. A response of 4 MiB or more returns HTTP 413 with `dashboard_response_too_large`, instead of silently omitting evidence. Exact timing arrays remain in metrics, so a very large session can reach this limit. Confirm keys against the linked versioned contract before implementing a separate client.

Check `GET /api/v1/schema` for `capabilities.dashboardRead` with `version: 1`, `path: /api/v1/dashboard`, `maxResponseBytes: 4194303`, `sessionLimit: 50`, `defaultCycleLimit: 20` and `maxCycleLimit: 100`. This is API capability discovery, not a physical-readiness claim.

Adopt reviewed changes into Intel's current working tree; do not replace it with the older Mac simulation tree, copy a fixture database over real records, or overwrite newer Intel work. Keep the original [source provenance](SOURCE_PROVENANCE.json) and [reconciliation record](SOURCE_RECONCILIATION.json). Record the adopted source revision/hash, service start time, API address and worker station ID without credentials.

- [ ] Reconcile the new dashboard endpoint with the actual current Intel API/store and its existing analyst, correction and history code.
- [ ] Run the relevant backend tests against temporary data before selecting the live service.
- [ ] Resolve which service is authoritative. The dated report that port 8000 lacked analyst routes while isolated port 52197 contained them is historical, not a current routing instruction.
- [ ] Adopt the matching relay allowlist on the existing Mac MCP and the matching worker on Intel. Preserve canonical shared context, pairing, CA and relay data; deployment is a separate action.
- [ ] Point the Intel worker at the intended fixed local records API and use the same `station_id` as Klemen. Keep credentials in private configuration and use the existing TLS pairing.
- [ ] Start with read support. The optional `--allow-record-writes` flag permits only explicit audited review and saved-evidence analysis; it does not enable robot commands.
- [ ] Verify actual Intel API → worker → Mac MCP → Klemen UI responses and save the evidence listed below before describing the connection as live.

See [communication startup and protocol](../communication/context_mcp/STATION_RELAY.md) and [dashboard configuration](README.md). A stopped worker, expired request, absent service or unsupported route must produce an unavailable/stale state.

## Required record producers

The following are existing persisted wire records. Each record has its stable `id`; returned records include `revision`. Related records must retain `sessionId`, `cycleId` and the exact object/frame/execution relationships. Persist the record before publishing the corresponding event. Do not create a new cycle or attempt merely because the dashboard reconnects.

| Producer | Exact fields to populate | Publication boundary and missing evidence behavior |
| --- | --- | --- |
| Session lifecycle | `name`, `sourceMode`, `startedAt`, `endedAt`, `configId`, `robotId`, actual model/configuration metadata | Create once at intentional run start; update at actual end. Use `live` only for real hardware records. Keep unfinished cycles visible when ending a session. |
| Object cycle | `objectId`, `startedAt`, `endedAt`, `outcome`, `commandedDestination`, `observedDestination`, `referenceLabelId`, `inspectionId`, `confirmationId` | Write each real transition. Finish as `correct`, `failed`, `aborted` or `unverified` according to evidence; a connection failure alone cannot establish physical failure. |
| Physical attempt | `ordinal`, `startedAt`, `endedAt`, `outcome`, `retryOfAttemptId`, `retryReason`, `errorCode`, `confirmationId` | One record per physical attempt. A retry is another attempt within the same cycle, preserving the earlier failure. Additional inspection alone creates neither a cycle nor an attempt. |
| Analyzed camera frame | `objectId`, `cameraId`, `capturedAt`, `receivedAt`, `width`, `height`, `evidenceId` | Save the exact image consumed by the model. New frame identity means new evidence; never overwrite an old image under an existing ID. A separate live preview does not replace this image. |
| Evidence bytes | `mediaType`, `sha256`, `size`, `capturedAt` | Persist the original bytes and expose them through `GET /api/v1/evidence/{evidence_id}`. Verify metadata/hash against the bytes. Keep each relayed response below 4 MiB; the record schema's higher image allowance is not the relay limit. |
| Anomalib inspection | `objectId`, `frameIds`, `modelRunId`, `score`, `threshold`, `classification`, `mapEvidenceId`, `additionalInspectionOfId`, `requestedAt`, `completedAt` | Emit once per analysis, linking exact frame and model run. Save a heatmap/overlay as separate evidence if produced. Display `score` and `threshold` in their actual scale, not an invented probability. |
| Model invocation | `provider`, actual `modelId`, `requestedAt`, `completedAt`, `frameIds`, sanitized `input`, actual `output`, `error`, `latencyMs`, `device`, `precision` | Persist each invocation and its result/error. Use null for unmeasured timing/device fields. Separate Nemotron observations, Gemini choices, Anomalib measurements and optional retrospective Gemma reports. Keep secrets out of inputs/outputs. |
| Task or goal choice | `kind`, `modelRunId`, `offeredChoices`, `selectedChoice`, `stateVersion`, `goalVersion`, `frameIds`, `requestedAt`, `completedAt`, `accepted`, `rejectionReason` | Record the offered fixed choices and actual selection; then record local acceptance/rejection. A saved `Decision` does not execute a task or confirm a result. |
| Dispatcher execution receipt | `attemptId`, `taskId`, `policyId`, `decisionId`, `status`, `requestedAt`, `acknowledgedAt`, `finishedAt`, `error` | The actual validated Intel dispatcher produces `requested`, `acknowledged`, `finished`, `failed` or `unverified` transitions. Do not synthesize acknowledgment or finish from sending a command. |
| Independent reference quality | `objectId`, `quality`, `authorId`, `method`, `evidenceIds`, `createdAt` | Assign independently of the model prediction. Unlabeled objects remain outside detection-correctness denominators. Preserve audited changes. |
| Physical confirmation | `source`, `evidenceIds`, `authorId`, `attemptId`, `confirmedAt`, `physicalSuccess`, `observedDestination` | Camera/sensor confirmation requires evidence; operator confirmation requires attribution. Controller completion alone is insufficient. Late confirmation updates the existing records/revisions. |
| Operator utterance, when integrated | `text`, `source`, `provider`, `modelId`, `startedAt`, `completedAt`, `status`, `language` | Jose supplies the actual typed/finalized voice data through the agreed integration. Keep partial/finalized/rejected states distinct and deduplicate the completed utterance. ElevenLabs is optional pending owner provider choice. |

The authoritative schema is [models.py](../intel-runtime/source/common/HachingJunction/station/morph_station/models.py), mirrored by the shared client's [types.ts](station-client/src/types.ts). Schema presence establishes storage support, not a physical producer. The existing command/voice stubs and saved execution records do not constitute a production mission API, dispatcher, learned-skill registry or Studio adapter.

## Cadence, ordering and freshness

The small aggregate poll and stale thresholds below are the chosen client configuration. Other sample rates are initial integration targets to measure on the actual network, not verified throughput or latency guarantees.

| Data path | Initial target | Rule |
| --- | --- | --- |
| Durable records and events | On the actual state transition | Persist exactly identified events and every analyzed-frame reference; publish the committed global sequence. Preview-video frames and joint heartbeats belong to separate channels rather than the reliability ledger. |
| Live dashboard aggregate | Poll every 2 seconds; also refresh on events/reconnect; mark data stale after 10 seconds | Coalesce changes and permit one refresh in flight. Poll configuration is not a guarantee of 2-second cross-host delivery. A fallback refresh must not repeatedly download the complete session export. |
| Analyzed image/heatmap | Fetch when the selected evidence ID changes | Reuse the displayed bytes while identity is unchanged. Source capture time remains visible even if a new aggregate was just received. |
| History and export | Explicit navigation/selection/export | The current history/replay workflow loads a complete session on demand and retains its own metrics/load time; later live updates show that an update is available. Never silently truncate an export to fit transport. Further server paging or chunked export is required for complete sessions beyond the relay cap. |
| Separate optional system telemetry | Start at 1 sample/second | Publish the latest measured value and its measurement time through a separately bounded design. Do not let telemetry traffic drive reliability refreshes. |
| Separate optional joint preview | Start at 5 samples/second if hardware supports it | Decimate for display; retain the source sample time. It is not a robot-control feedback loop. |
| Separate optional training progress | Start every 2–5 seconds and on state changes | Report actual trainer state and last measured step, including failed/interrupted status. |

`lastEventSequence` is the persisted global event cursor, not a robot state version. `occurredAt`, server `receivedAt`, frame `capturedAt`, response `generatedAt` and Mac receipt time have different meanings. Store timezone-qualified timestamps; label the display timezone. Use a monotonic clock for local durations. Do not calculate exact cross-host latency by subtracting unsynchronized wall clocks.

The relay has a 30-second request expiry and a 4 MiB raw response limit. HTTP 413 means the requested response is too large; it does not authorize dropping frames, event history or records without disclosure. A hash mismatch, missing worker or expired response must not render as fresh data. Keep the last successful data visibly stale when useful, with the actual last receipt time. Analyzed-frame freshness remains separate from transport freshness: the existing projection treats live-source frames older than 5 seconds, or more than 1 second in the future, as unsuitable for a fresh analyzed-frame indication. Simulation captures remain explicitly frozen evidence.

## Missing producers and schema extensions

These fields are requirements for a later producer/schema integration. They are not accepted by the current strict record models merely because they are listed here. Add a versioned backend contract, client validation/projection and tests together before wiring them into the UI.

| Missing capability | Required producer contract | Acceptance boundary |
| --- | --- | --- |
| Active goal and phase | Proposed read-only fields: `goalId`, `goalVersion`, `goalText`, `phase`, `phaseStartedAt`, `executionId`, `robotStateVersion`, `observedAt`, `source` | Intel confirms committed goal and actual dispatcher checkpoint. Current snapshot `stateVersion` cannot be reused as robot state. A model-selected task is not proof that execution began. |
| Jose control lifecycle | Proposed records: stable `commandId`, `kind`, `requestedAt`, `acknowledgedAt`, `finishedAt`, `status`, `reason`, `executionId`, and independent confirmation reference | Preserve request, acknowledgment and physical confirmation separately. Document whether pause waits for a cycle boundary or interrupts. Klemen displays receipts; Jose initiates control. Software stop is not a verified physical emergency stop. |
| Motion and verification timing | Proposed measurements: `executionId`, `motionStartedAt`, `motionFinishedAt`, `verificationStartedAt`, `verificationFinishedAt`, measured `motionMs`, `verificationMs`, and `timingMethod` | The dispatcher/confirmation producer must define actual boundaries. Queue time and command acknowledgment cannot stand in for motor motion. Full-cycle duration includes cloud waiting whenever execution waits for it. |
| CPU, memory, GPU/NPU utilization | Proposed envelope: `sourceId`, `sampledAt`, `receivedAt`, `status`, `values`, `units`, `measurementMethod`, `error` | Populate only readings actually supported and measured on the target. Unsupported GPU/NPU utilization, power and temperatures remain unavailable. A selected device string is not utilization evidence. |
| Joint/servo measurements | Same measured envelope plus stable joint identifiers, actual position values and units; optional measured velocity/current/temperature only when exposed by hardware | Verify robot model/calibration mapping and telemetry access. Commanded angles are not measured angles; motor-current or force values cannot be inferred from position. |
| Training job progress | Proposed fields: `jobId`, `status`, `datasetId`, `policyId`, `configHash`, `device`, `startedAt`, `updatedAt`, actual `step`/`totalSteps`, measured loss values, checkpoint path/hash, error | Publish trainer-owned state. A decreasing loss or completed job does not establish a usable physical policy; evaluate against saved demonstrations and actual execution separately. |
| Continuous camera video/depth | Separate authenticated media channel with stable camera ID, stream state, measured FPS/resolution, last-frame time and disconnect handling | Continuous video is outside the current finite MCP read relay. Validate transport, access, resource cost and timestamp mapping before adding a live label. D415 acquisition on Intel does not prove this dashboard path. Depth remains optional until a real use and measured producer exist. |

The existing snapshot capability flags remain unavailable until an explicit backend capability/readiness contract is implemented. Do not flip capability state based only on installed packages, a connected socket, an earlier provider test or the presence of historical records.

## Intel and cross-host acceptance checklist

Run software checks on isolated temporary records first. Real movement belongs to an intentional operator-run test under Intel's operating/calibration procedure. Save exact IDs, timestamps, source/runtime revision, logs and UI evidence with each result.

1. **Aggregate coherence and isolation:** request a live session, a simulation session, an empty source mode and a missing session. Confirm one consistent event cursor, matching session/source IDs, exact backend metrics and explicit errors. Large histories must not require the full export for the live view.
2. **Exact transport:** read the aggregate, cycle detail and a saved image through the actual Intel worker/MCP path. Compare body size/hash and evidence IDs to Intel's source. Test absent worker and API, expiry, wrong station ID and oversized response. Do not mark these tests passed from local synthetic results.
3. **Event recovery:** disconnect after a known cursor, save new records on Intel, reconnect and recover authoritative state. Duplicate events must not add cycles or attempts; an event gap must trigger resynchronization. Verify session switching and late confirmations.
4. **Image truth:** trace the displayed analyzed image to `Frame.evidenceId`, SHA-256, object/cycle and actual Anomalib `frameIds`; trace the heatmap separately. Show stale source capture time, absent evidence and disconnected preview correctly.
5. **Recovery metrics:** save one failed attempt followed by a confirmed successful retry in the same cycle. Expect one recovered cycle, two attempts, one retry and the earlier failed attempt retained. Verify no-data denominators and labeled-only detection accuracy.
6. **Execution and outcome:** demonstrate separate request, acknowledgment, finish and independent confirmation records. Withhold confirmation and confirm the UI stays unverified. Successfully placing an incorrectly classified object in the wrong bin must not become end-to-end correct.
7. **Provider trace:** link one actual Nemotron observation and one actual Gemini fixed-choice selection to exact model runs, frames, offered choices, acceptance/rejection and latency/error records. Keep simulated, historical access checks and live integration evidence distinct.
8. **Read-only navigation:** instrument Intel dispatch counts while opening, refreshing, reconnecting, switching tabs and replaying history. These actions must generate no mission or motion. Explicit history review and Gemma request remain separately intentional and idempotent.
9. **Freshness and load:** measure aggregate response bytes and latency, update delay, queue depth and event lag under the expected event rate and a growing session. Record p50/p95 and sample counts. Confirm no repeated full export and no stale response labeled current. Test any optional telemetry channel separately.
10. **Physical trace:** after adoption and intentional hardware testing, save one complete real session/cycle/attempt with analyzed image, classification, requested/observed destination, independent reference quality and confirmation. Only this evidence can establish the physical dashboard path.

Keep failed, aborted, unverified and in-progress records. Export acceptance evidence without credentials. Update existing M20/M21 tasks with actual results, timezone-qualified times, limitations and links; keep physical acceptance open until demonstrated.

## November 15 live-video implementation

A separate [Studio JPEG → H.264 bridge](../intel-runtime/media-bridge/README.md) and [dashboard media contract](LIVE_VIDEO.md) are now implemented and tested with synthetic input. The earlier continuous-video row remains a target-integration acceptance item, not an absent Mac UI. Intel must provide the exact active Studio camera configuration, confirm capture-owner reuse, install reviewed Python/FFmpeg/MediaMTX dependencies, select authenticated HTTPS signaling and reachable ICE media candidates, and return source/receiver/resource/optical-delay evidence. Depth is still outside this implementation.

Adoption is coordinated by the current Intel control owner through Jose Mac. The verified shared owner-correction report `be57f4f6-4f20-479e-bcb6-2164b85bae1b` at 2026-11-15T06:21:13Z reports that automatic Intel Codex control was stopped and is not authorized to restart. Passive source delivery does not start any process or camera. Keep the station worker and existing camera owner in place.
