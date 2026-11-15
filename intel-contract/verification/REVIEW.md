# Received Intel source review for Jose

Checked November 15, 2026, `2026-11-15T03:35:47.871883+01:00` (Europe/Ljubljana). This review covers the focused Intel source response to request `00e34e99-cfc8-47bf-ab5d-1d029242f841`, transfer `8dfe841b-f157-469d-84fe-7586cdcd583f`. It does not change the canonical Mac application or the running Intel services.

**The requested current source subset is received and usable as Jose's integration reference. The Intel mission API is absent, so source transfer alone cannot make the Jose-to-Intel control flow operational.** The current Mac control/provider/voice lab remains Jose's implementation starting point.

## Source identity and completeness

The root collector reconstructed all 21 source chunks and verified a 246,146-byte bundle with SHA-256 `f79c9426e361721aa63aa61038a93cbe1799d63e4a93501858a68112ea553e1b`. This independent review rehashed all **17 files / 230,799 source bytes** against the saved collector manifest. All match. The snapshot was frozen on Intel at `2026-11-15T02:29:40.570489+00:00` and collected on Mac at `2026-11-15T02:33:51.290670+00:00`.

Received modules include the current `api.py`, `models.py`, `store.py`, `schema.sql`, CLI/client/simulation support, four analyst modules, requirements, launcher, README and the selected store/review tests. Static analysis found **22 relative imports, all resolved within the received package**, and **27 declared HTTP method/path combinations**. [Static review](static-review.json) contains exact file hashes, import paths, routes and the source comparison.

The analyst files are included because `api.py` imports their route-registration function. Their current source declares `gemma-evidence-v11` and `morph-evidence-v7`; this establishes source versions, not hosted semantic acceptance. This is a focused import closure, not a claim that the entire Intel project, dashboard, datasets or model artifacts have been transferred.

## Contract findings

Direct inspection and a fresh isolated run of the received source confirm:

- `POST /api/v1/commands`, `POST /api/v1/voice/token` and `POST /api/v1/voice/utterances` are unconditional HTTP 503 stubs.
- No mission start/pause/resume/stop or goal-change endpoint is implemented. The transferred modules contain no `providers.py`, `provider_api.py`, `control_api.py`, `dispatcher.py`, `voice.py` or `voice_api.py`.
- The snapshot sets `goalVersion` and `goal` to null, `availableActions` to an empty list and physical/control capabilities to unavailable. Session writes and session end are persistence operations; they do not operate the robot.
- Canonical record revisions, event idempotency and review receipts are bookkeeping contracts. They must not be presented as execution IDs, mission deadlines or a physical dispatcher contract.
- Current source adds the explicit evidence-analyst routes and the attributed cycle-review endpoint. Neither dispatches a physical skill. The analyst can call a provider only after an explicit report submission; it is not needed for Jose's mission-client design.

The locally generated [current-source OpenAPI](current-source-openapi.json), [record schema](current-source-record-schema.json) and [empty snapshot](empty-source-snapshot.json) are derived from these exact source bytes, using temporary data. They are not captures from Intel's running port 8000 or 52197.

## Differences from the current Mac foundation

The received `models.py` preserves all pre-existing Mac definitions unchanged and adds `ReviewLabel`, `ReviewConfirmation`, `ReviewChanges` and `CycleReview` with their validators. The SQLite change adds the `review_requests` table. `store.py` adds atomic `review_cycle` with exact retry receipts, correction attribution and rollback, and extends the internal metrics function with an optional `cycle_ids` filter; its default metric selection remains unchanged. No existing model definition or store method was removed.

The API registers the analyst dependency and includes `CycleReview` in its schema. Consequently, dropping the received `api.py` into Jose's lab would also introduce analyst routes and an idle analyst thread. Preserve the current Mac control lab and keep the received Intel tree as a clearly identified reference until the production bridge is deliberately integrated. Do not overwrite the newer Intel working tree with the older Mac foundation.

## Isolated verification

Reviewed `test_store.py` and `test_reviews.py` before running them. They use temporary databases/evidence and local ASGI `TestClient` calls. Provider credential environment variables were removed in the test process; outbound socket connects and `GemmaProvider.__call__` were patched to fail if invoked. Source bytes were not edited.

**56 tests passed**, with **zero provider attempts and zero outbound socket attempts**. The fresh empty API fixture returned the expected three 503 stubs, null goal state and empty action list. Reads and stub calls left zero sessions and zero persisted events. The idle analyst worker was closed through the application lifespan.

Evidence: [JUnit results](imported-tests.xml), [test log](imported-tests.log), [execution record](execution-review.json) and [repeatable review runner](run_reviewed_tests.py). This is current-source software verification on Mac. No model call, external network connection, robot action, Intel service restart or physical outcome was tested.

## Running-service distinction and remaining work

Intel's immediate response `90a28910-e9bf-4f5c-9731-91573c60af05` reports fresh health/OpenAPI inspection at `2026-11-15T02:25:35+00:00`: main records API port 8000 lacks analyst routes, while isolated port 52197 and current source have them. Both report `hardwareIntegrated=false` and `providersIntegrated=false`. This review establishes the received source facts independently; the running-service observations remain attributed to Intel until their captured artifacts are separately received and checked.

Jose still needs the agreed remote state/read interface and a new application mission client behind the other team's NVIDIA tunnel. Intel needs the corresponding locally validated mission endpoint and physical adapter. Agree on state/goal versions, frame identity, freshness, permitted learned tasks, preconditions, deadlines, execution idempotency and distinct acknowledgment/completion/physical-confirmation responses. A tunnel is transport and does not supply these missing contracts.

No additional hidden Intel mission implementation needs to be waited for based on this response: Intel explicitly inspected and reported its absence, and the received source supports that finding. The small runtime OpenAPI/schema capture response can document the deployment difference without delaying delivery of the current Jose source handoff.
