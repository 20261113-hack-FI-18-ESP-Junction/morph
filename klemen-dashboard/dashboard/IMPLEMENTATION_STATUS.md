# Dashboard implementation and evidence

Updated November 15, 2026 after source reconciliation. Implementation, package verification, deployment and physical/provider evidence are separate claims.

| Area | Included behavior | Verification limit |
| --- | --- | --- |
| Records and metrics | Current typed client/store reads coherent Intel-owned records and backend metric denominators. | Local client/projection tests pass; real cross-host runtime is not verified here. |
| MCP transport | Loopback proxy, server-only TLS pairing, fresh bounded relay requests, exact hashed responses and finite event batches. | Isolated Node/TLS MCP/staged worker/synthetic API integration passes. |
| Audited reviews | Explicit exact-body submission, stable review/event IDs, revision handling, persisted pending draft and identical manual retry. | New transport regressions and existing UI/client tests pass; the exact current Intel proxy suite is unavailable. |
| History and replay | Complete saved-session filtering/pagination, original event/revision playback and fixed metrics. | Replay creates no records and cannot submit reviews or inference. |
| Gemma analyst UI | Deterministic facts, saved reports, captured citations, drafts, explicit report requests and error/rejection containment. | Frontend/controller tests pass; no new provider request or useful explanation was verified. |
| Robot and physical controls | Truthful unavailable controls and persisted results where supplied. | No motion routes, calibration, trained skill, camera or physical cycle verified here. |
| Jose coordination and voice | Assigned to Jose by the owner's three-host design. | NVIDIA tunnel belongs to the other team; ElevenLabs is undecided. |

No startup action seeds records or starts motion. Simulation explicitly selects existing simulated records. The retained prototype code and design assets do not generate active metrics or substitute for missing telemetry. Operator confirmations remain attributed evidence; a model explanation is not a measured outcome.

[VERIFICATION.md](../VERIFICATION.md) reports 174 passing software tests, TypeScript/build results and the isolated TLS transport checks. The older Mac reports and Intel source-document claims retain their original dates and are not new validation of this publication. [SOURCE_RECONCILIATION.json](../SOURCE_RECONCILIATION.json) distinguishes exact received/reused source from portability and MCP adaptations.
