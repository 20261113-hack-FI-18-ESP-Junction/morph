# Dashboard upgrade — November 15, 2026

This source upgrade implements the owner's request for reliable dashboard data and improved visual presentation. Klemen owns monitoring/analytics, Intel owns authoritative records/physical execution, and Jose owns operator interaction and control. Actual Intel adoption and physical producers remain separate work, specified in [INTEL_REQUIREMENTS.md](INTEL_REQUIREMENTS.md).

## User-visible behavior

| View | Implemented behavior |
| --- | --- |
| Live inspection | Large analyzed snapshot with source timestamp and frame identity; optional stored anomaly map; current object; Anomalib score/threshold; Nemotron observations; Gemini offered/selected choices; execution receipts; independent outcome confirmation; actual model payloads and errors. |
| Reliability summary | Backend-owned cycle and attempt fractions with visible denominators; failed, aborted, unverified and in-progress categories; first-attempt successes, recovered cycles, retries and additional inspections kept separate. |
| Robot & system | Records connection, event cursor, source/session identity, latest receipt and capability availability. Unsupported joint, compute, active-goal and phase data stays unavailable. |
| Quality & history | Complete saved-session snapshot loaded on entry, own generation time and metrics, newer-data indicator, explicit refresh, filters, pagination, confusion matrix, trace drawer and existing audited review/analyst features. |
| Cycle trace | Saved image, exact frame links, inspections, decisions, request/acknowledgment/finish, every physical attempt and retry, confirmation source, errors, measured inference timings and correction history. |
| Replay | One explicit full export, frozen records/metrics and original-event navigation. Repeated activation shares a pending request; seeking does not fetch or create records. Reviews and generation are disabled. |

The visual design preserves Morph's dark/bronze identity, increases the emphasis on the current object and evidence, and supports desktop and narrow layouts. The header distinguishes current records, a saved history snapshot and replay. Refresh is the primary monitoring action; control ownership is shown beside it.

An analyzed image is a saved capture, not a live camera stream. A model result is a recorded invocation, not proof of current provider access. Command acknowledgment/finish is separate from physical confirmation. Missing motion or verification duration is unavailable even when a physical outcome has been confirmed.

## Data path

```text
Intel SQLite records
  → coherent GET /api/v1/dashboard
  → Intel worker → existing Mac MCP → local same-origin proxy
  → validated shared client/store → all dashboard views
```

The new endpoint uses one SQLite read transaction for session/snapshot/metrics/details and `lastEventSequence`. It defaults to 20 recent cycles (maximum 100) and the newest 50 matching sessions. Current and focused cycle details remain complete. The client validates source/session scope, sequence bounds, cycle revisions and response shape before publication. Optional older-session discovery uses the existing catalog read. [The wire contract](../intel-runtime/source/common/HachingJunction/station/INTEL_DASHBOARD_API.md) documents exact fields and errors.

The client polls every 2 seconds and coalesces event-triggered refreshes. After 10 seconds without fresh data it marks retained records stale. These are scheduling settings, not measured network guarantees. Reconnects and duplicate events invalidate reads; counters always come from persisted backend records. An explicitly chosen session never silently changes to another on an error. Auto-follow may clear an old focused cycle only after a coherent reply confirms a different session.

Full exports are reserved for history, replay and explicit export actions. A saved history snapshot retains its own records, totals and source generation time, separately from Mac receipt time. A session/source change invalidates pending work, so a late export cannot overwrite the new view. Ordinary refreshes do not repeatedly download that history. The pre-upgrade API remains supported through capability discovery and the original coherent multi-read fallback.

The existing 4 MiB transport limit remains. Exact timing arrays and complete current/focused details can reach the bound in very large sessions; the endpoint returns an explicit 413 instead of truncating evidence. Large complete histories/catalogs still need future paging or a separate chunked export design. Continuous video now has a separate implemented [media path](LIVE_VIDEO.md) with synthetic verification and target adoption pending. High-rate telemetry remains separate producer/transport work.

## Intel changes supplied

The staged Intel API/store now supplies the compact endpoint and capability advertisement. Both communication allowlists accept the exact read parameters. No existing service was restarted or deployed by these source edits. Reconcile the supplied code with Intel's current tree before adoption; retain newer Intel work and the existing real database.

Real producers must populate frames/evidence, inspections, model invocations, validated decisions, attempts, execution receipts, reference labels and confirmation records. Additional versioned contracts are required for live robot phase, real motion/verification timings, training progress and telemetry. Continuous video now uses the independent contract in [LIVE_VIDEO.md](LIVE_VIDEO.md), with the actual Intel source/network acceptance still pending. The [Intel checklist](INTEL_REQUIREMENTS.md) gives exact existing fields, proposed fields, cadence targets and ten acceptance scenarios.

## Verification and provenance

The [verification report](VERIFICATION.md) distinguishes software tests, the temporary simulation demo, browser inspection and missing real Intel/physical verification. [LOCAL_DEMO.md](LOCAL_DEMO.md) provides reproducible commands. The demo uses the modified backend and normal client/proxy, temporary simulation records, synthetic imagery and fixture model outputs. It rejects writes and cleans up its private temporary runtime on exit.

Original `SOURCE_PROVENANCE.json` and `SOURCE_RECONCILIATION.json` remain unchanged. The upgrade's separate source inventory includes the modified dashboard, shared client, backend and communication source. Run `python3 tools/verify_upgrade.py` to verify those hashes. Generated dependencies and build output are not deployment evidence.
