# Intel source compared with the runnable Mac lab

Comparison used exact file hashes, UTF-8 diffs and Python AST inspection at **2026-11-15T03:34:56.775389+01:00**. That initial comparison did not import or execute incoming modules. A later [independent isolated audit](verification/REVIEW.md) ran the 56 received store/review tests with zero outbound socket attempts and zero provider attempts, and confirmed the empty-state/503 behavior. The underlying manifest, receipt and machine-readable comparison are in this folder.

## Actual source differences

| Area | Received Intel source | Consequence for Jose |
| --- | --- | --- |
| Core record model classes | All classes that already existed in Mac `models.py` are AST-identical; none removed | Existing session/cycle/attempt/frame/inspection/decision/utterance shapes remain a usable reference. Do not equate record state with robot control state. |
| Review models | Adds `ReviewLabel`, `ReviewConfirmation`, `ReviewChanges`, `CycleReview` | These are attributed history-review inputs, not learned-task requests. `CycleReview` is an additional request envelope. |
| SQLite schema | Preserves the old schema and appends `review_requests`, linked to request receipts | Intel has additional review idempotency metadata; overwriting its schema/store with the old foundation would omit this behavior. |
| Store | Adds `review_cycle`; changes internal `_metrics` to accept optional `cycle_ids` and report the selected IDs | Reviews atomically preserve correction history and receipt/revision checks. The public metrics method and default full-population path remain unchanged in the static comparison. |
| Main API source | Adds `/api/v1/cycles/{cycle_id}/review`, the `CycleReview` schema envelope, optional `analysis_dir`/`analysis_provider` construction arguments, and analyst route registration | These extend review/analysis. They do not add a mission endpoint. Do not replace the lab's base factory to gain them implicitly. |
| Analyst dependency closure | `analysis.py`, `analysis_context.py`, `analysis_models.py`, `analysis_provider.py` are included because current `api.py` imports them | Keep them together as received reference source. They are a Gemma evidence analyst with explicit request/report endpoints, not Gemini Decision 1 or Nemotron control. |
| Requirements and supporting code | Requirements, package initialization, CLI, HTTP client and simulation fixture source match the Mac versions byte-for-byte | No changed declared dependency set was observed. This is not a test of installing or running the incoming source. |
| Control/provider/voice implementation | No `dispatcher.py`, `control_api.py`, `providers.py`, `provider_api.py`, `voice.py`, `voice_api.py`, `lab.py` or `lab.html` in the focused Intel source; fresh inventory also reports them absent from the active station tree | The current Mac lab remains Jose's available implementation for these features. There is no new Intel mission module to merge into it. |

The original frozen Intel source is under [source/station](source/station/README.md). Its README is retained verbatim as source provenance and can contain references to files outside this focused transfer; use this folder's guide for the handoff scope.

## State and actions are still a records contract

The received API's `Snapshot` class and `StationStore.snapshot` method are AST-identical to the Mac foundation. They expose:

- `stateVersion` equal to the persisted event sequence, alongside `lastEventSequence`.
- `goalVersion: null`, `goal: null` and `availableActions: []`.
- `robot`, `cameras`, `anomalib`, `nemotron`, `gemini` and `elevenlabs` capabilities as unavailable and `verified: false`.
- Existing persisted session/cycle records and metrics, retaining their live/simulation labels.

These fields are different from the lab's separate `/api/v1/control/snapshot` and its `SimulationDispatcher` versions. Never pass the records event watermark as if it were an Intel mission controller's state version. No such Intel controller exists in this transfer.

Session create/end routes perform bookkeeping only. `/api/v1/commands`, `/api/v1/voice/token`, `/api/v1/voice/utterances` and camera streaming remain unavailable. The four received analyst routes are `GET /api/v1/analysis/context`, `POST /api/v1/analysis/reports`, `GET /api/v1/analysis/reports` and `GET /api/v1/analysis/reports/{report_id}`. They must not be treated as mission, goal or movement APIs.

## Runtime snapshot remains separate

Intel's inventory at **03:25:35 CET on November 15** reported main API `8000` and isolated analyst API `52197` both healthy with `hardwareIntegrated=false` and `providersIntegrated=false`. Main `8000` had no analyst routes; isolated `52197` and the current source did. The source receipt verifies bytes from the current tree, not the identity of loaded main-service modules or those health responses. The generic provider capability flags also do not replace inspecting the explicitly registered analyst routes. Live OpenAPI capture and its provenance remain a separate requested response.

## Jose's next implementation steps

1. Run the existing Mac lab from the package root and continue the operator/chat UI. Its existing Nemotron observations, Decision 1 selections and optional finalized-voice flow stay separate from dispatch. Keep OpenClaw and the diagram's Argon component as explicitly unimplemented adapters until their interfaces and access are verified and developed.
2. Use the received record contract to design a read adapter for authoritative frame/inspection/session state. Retain original record IDs, revisions, timestamps and source-mode labels; imported reads must not create repetitions.
3. Agree a new mission service with the Intel implementation owner. It needs an actual learned-skill registry, permitted tasks, trustworthy physical preconditions, explicit goal/state versions, deadlines, request/execution identity, duplicate rejection and acknowledged/finished/physically-verified lifecycle. Current session and record-write endpoints cannot fill this role.
4. Once Intel implements that service, bind Jose's server-side mission client to the other team's supplied NVIDIA tunnel URL. Keep final validation and motion execution on Intel. The tunnel setup is owned by that team.
5. Verify a staged end-to-end path with the actual interface before enabling physical dispatch. Keep the lab as a separate simulator and preserve the newer Intel review/analyst behavior. A real outcome requires independent confirmation; source receipt, tests or a tunnel connection alone do not establish it.

The immediate handoff is ready for UI/control development and records-contract reconciliation. The remaining blocker for physical missions is missing implemented Intel mission/skill integration, not missing copies of the old Mac provider or voice files.
