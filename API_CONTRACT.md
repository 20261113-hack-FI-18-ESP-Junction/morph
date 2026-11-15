# Current Jose lab interfaces and the Intel transport gap

This contract describes the copied Mac implementation. It is not a claim that Intel exposes these routes. The generated [OpenAPI document](verification/openapi.json) and [record schema](verification/record-schema.json) are derived from this package's source with empty credentials and a temporary database.

The browser and server run on Jose's Mac. Every `/api` route requires the local bearer token; the loopback-only `/lab` page supplies that token to its own JavaScript. The owner directs **Jose ↔ Intel through the NVIDIA tunnel provided by the other team**, and **Klemen ↔ Intel through the existing Mac MCP server**. Tunnel provisioning is outside this package's scope. Remote Intel credentials must remain in a server-side client when the application bridge is implemented. Existing code embeds no cross-host address and opens no SSH connection.

## Read the current state

| Method and route | Meaning |
| --- | --- |
| `GET /api/v1/control/snapshot` | Simulator state including state/goal versions, mode, phase and execution boundary |
| `GET /api/v1/control/decision-context` | Fresh context and currently permitted choices for task selection |
| `GET /api/v1/control/policy` | Simulation policy; `physicalAdapterImplemented: false` |
| `GET /api/v1/control/journal` | Persisted control events, selections and executions |
| `GET /api/v1/lab/providers` | Credential-presence flags only; not successful provider-access evidence |
| `GET /api/v1/schema` | Current record and request schemas |
| `GET /api/v1/station/snapshot` | Persisted records snapshot and event cursor |
| `GET /api/v1/events?after=N` | Ordered saved events; reads and reconnects add no repetitions |

## Observe, select, commit, then dispatch explicitly

The following are separate operations. A successful provider response does not execute a task.

| Route | Required fields | Effect |
| --- | --- | --- |
| `POST /api/v1/lab/providers/observe` | `requestId`, `sessionId`, `cycleId`, `frameId` | One bounded Nemotron observation of the persisted frame |
| `POST /api/v1/lab/providers/select-goal` | `requestId`, `sessionId`, `utteranceId`, `expectedStateVersion`, `expectedGoalVersion` | Decision 1 choice from supported goals using a finalized utterance |
| `POST /api/v1/control/goals` | `requestId`, `sessionId`, `goalId`, `expectedStateVersion`, `expectedGoalVersion`; optional `utteranceId`, `decisionId` | Validate and apply/queue a goal at the supported boundary |
| `POST /api/v1/lab/providers/select-task` | `requestId`, `sessionId`, `expectedStateVersion`, `expectedGoalVersion`; optional `observationRunIds` | Decision 1 choice from the fresh allowed task menu |
| `POST /api/v1/control/dispatch` | `requestId`, `executionId`, `sessionId`, `cycleId`, `objectId`, `attemptId`, `taskId`, `expectedStateVersion`, `expectedGoalVersion`, `frameIds`, `deadlineAt`; optional `decisionId` | Validate and submit to the local simulator only |
| `GET /api/v1/lab/providers/requests/{requestId}` | Request ID in path | Read the saved receipt without repeating the provider call |

Use the actual IDs, versions, frame references and original deadline from a validated receipt. Repeating a request with the same ID and same payload is distinct from creating a new request. Never refresh a stale decision's deadline to make it appear current.

`POST /api/v1/control/commands` accepts `commandId`, `action`, `sessionId` and `expectedStateVersion`. Current actions are `start`, `pause_after_cycle`, `resume` and `stop`. These actions affect only the simulator in this package. The software stop is not a physical emergency stop.

The simulator exposes separate acknowledgment, finish and reconciliation endpoints under `/api/v1/control/executions/{executionId}`. A controller-style finish remains an unverified physical outcome. Intel's real adapter must return its own observed lifecycle and confirmation evidence; Jose must not manufacture those callbacks in response to a model prediction.

## Optional voice

The `/api/v1/lab/voice` endpoints support `GET /options`, `POST /token`, `POST /start`, `POST /{id}/events`, `POST /{id}/release`, `POST /{id}/finalize` and `GET /{id}`. `start` requires `utteranceId` and `sessionId`, with optional `cycleId`. `events` requires a stable `eventId`, the relayed `event`, and an optional `segmentIndex`. `finalize` requires an exact `expectedSegmentCount` and `terminalCommitEventId`.

Finalized text creates one canonical utterance and a stable goal-request identity. It does not automatically select or apply a goal. Provisional speech and later timestamp enrichment are never another command. Current provider events are explicitly labeled `browser_relay`. ElevenLabs is an optional retained adapter under the owner's November 15 direction; a different voice provider must preserve these identity/finalization rules.

## Missing Intel integration

Intel's November 15 priority reply, observed **03:27:14.565918 CET**, reports that the current target has **no mission/control API, dispatcher, mission version/deadline handling, learned-skill registry or mission hardware adapter**. The focused source transfer arrived and passed all hashes at **03:33:51.290670 CET**; [the received static comparison](intel-contract/CONTRACT_COMPARISON.md) confirms the unavailable command/voice stubs and that the record snapshot has `goalVersion: null`, `goal: null`, `availableActions: []` and unavailable capabilities. Record-write revisions and event IDs are not a substitute mission contract. [INTEL_REQUIRED_FOR_JOSE.md](INTEL_REQUIRED_FOR_JOSE.md) records receipt scope and differentiates main API `8000` from isolated/current-source analyst API `52197`. The initial comparison was static; the subsequent [guarded source audit](intel-contract/verification/REVIEW.md) passed 56 tests and confirmed the stubs with no outbound network/provider attempts. Its generated [OpenAPI](intel-contract/verification/current-source-openapi.json) describes the received source locally, while `verification/openapi.json` describes the separate Mac lab.

The existing `ProviderService` reads a local `StationStore` and a local `SimulationDispatcher`. There is no remote state adapter, no mission HTTP client, no source-of-truth synchronization service and no implemented OpenClaw/Argon adapter in this package. Copying the files to Jose does not establish those integrations. The future mission client must accept the other team's user-supplied NVIDIA tunnel base URL as server configuration, with the agreed application authentication. `env.example` reserves `MORPH_INTEL_BASE_URL` for that future client; the current simulator does not read it. Do not invent a tunnel hostname, create an alternative tunnel or treat tunnel connectivity as mission API compatibility.

The requested Intel source handoff must supply:

1. Current source and provenance for records/schema, hardware/local dispatcher, task registry, camera/frame and execution adapters, plus relevant tests.
2. Exact supported mission/state endpoints behind the other team's NVIDIA tunnel, or the current local adapter boundary, plus application authentication and error semantics. The other team supplies tunnel URL and connectivity separately.
3. Fresh snapshot/allowed-task fields, command/request IDs, goal/state version rules, original decision deadlines and duplicate execution behavior.
4. Returned acknowledgment/finished/failed/unverified states and independent physical confirmation, with frame/evidence references.
5. Which code is live, simulated or planned; which M16/Gemma changes supersede the Mac foundation.

Agree and implement Intel's locally validated mission service before binding Jose's server-side mission client to it through the supplied NVIDIA tunnel URL. Keep incoming Intel record-contract source as a separate `intel-contract/` reference; do not replace the runnable Mac lab's foundation or add the incoming tree to its import path automatically. Feed authoritative saved records to Klemen's dashboard through the separately owned Mac MCP path. A local read cache must preserve the source record IDs/revisions and must not replay imported events as new sessions, cycles or attempts. Define a deliberate authenticated import or read interface before wiring provider context to remote frames.
