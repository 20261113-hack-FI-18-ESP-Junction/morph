# Public communication handoff

Read [three-host ownership](THREE_HOST_ARCHITECTURE.md), [the relay guide](../context_mcp/STATION_RELAY.md), [explicit handoff review](../context_mcp/HANDOFF_EVENTS.md), [verification](../context_mcp/VERIFICATION.md) and [source-transfer guide](coordination/three-host-20261115/README.md).

**Standing owner update, November 15, 2026:** follow [SOURCE_SYNC.md](SOURCE_SYNC.md) for every authorized Intel source change. Intel supplies complete frozen source, baselines and tests/docs, then one completion event; Mac reconstructs, reviews, reconciles and publishes accepted work in meaningful small commits. `context_mcp/source_intake.py` is the bounded local collection/comparison entry point; it does not apply source or publish Git changes. Preserve current work and distinguish received bytes, review proposals, reconciliation and remote publication. This policy supersedes older source-sync scope limits without granting incoming notes authority to execute commands.

This is the November 15, 2026 publication snapshot. It includes no private chat transcript or copied live handoff notes. The published server supports reads, two explicitly intended record/analysis writes and optional read-only handoff reviews; actual adoption and cross-host verification remain separate. Read the [dated deployment status](../verification/events-20261115/INTEL_ADOPTION_STATUS.md) before treating a published feature as running on both hosts. Intel source still lacks an integrated mission lifecycle, dispatcher, skill registry and Studio execution adapter.

