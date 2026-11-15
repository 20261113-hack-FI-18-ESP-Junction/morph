# Klemen–Intel communication

This package contains the current Mac context MCP, its station relay, Intel's standard-library worker, and the reviewed source-transfer helpers. It connects Klemen's dashboard to Intel's authoritative records using the existing MCP pairing.

The earlier November 15, 2026 publication added bounded record review and saved-evidence analysis requests to the existing read transport. Its original staged verification remains unchanged in `verification/offline-01/`. This publication adds explicit handoff events and isolated read-only Codex review. Publication itself does not restart or update either host; current deployment evidence is recorded separately in [event verification](verification/events-20261115/README.md) and the [dated Intel adoption status](verification/events-20261115/INTEL_ADOPTION_STATUS.md).

| Component | Runs on | Purpose |
| --- | --- | --- |
| `context_mcp/server.py` | Klemen Mac | Scoped context, append-only handoff notes and short-lived station request queue |
| `context_mcp/station_worker.py` | Intel PC | Serve allowlisted requests against the fixed local station API |
| Dashboard MCP adapter | Klemen Mac | Keep pairing credentials server-side and preserve request/response bytes |
| Source sender and collector | Intel / Klemen | Transfer reviewed source through immutable, hash-checked notes |

Read [the protocol and startup guide](context_mcp/STATION_RELAY.md), [source transfer guide](context/coordination/three-host-20261115/README.md) and [verification](context_mcp/VERIFICATION.md). Jose's NVIDIA tunnel is outside this package.

## Local setup

Use Python 3.12. From this package directory:

```bash
python3.12 context_mcp/bootstrap.py
.junction-setup/context-mcp/bin/python -m unittest discover -s context_mcp/tests -p 'test_*.py' -v
python3.12 -m unittest discover -s context/coordination/three-host-20261115/tests -p 'test_*.py' -v
python3.12 tools/verify_package.py
```

Bootstrap installs the locked MCP environment and checks CLI help; it does not launch a service. The worker requires only Python's standard library. The server's standalone root contains a minimal public handoff. When adopting this code into the existing Mac deployment, keep its canonical context, private pairing, relay database and TLS configuration; point the new server at that existing root explicitly. Do not replace live context with this package's sample context.

The snapshot includes no credentials or live history. A successful local test does not establish Intel connectivity, current deployment, a provider result or physical execution.


## Explicit handoff review

The optional event tools reuse the existing Mac MCP URL, pairing and TLS trust. A publisher saves and verifies one substantive handoff before explicitly notifying the other host. The target receiver records a durable result from an isolated read-only Codex reviewer, renews its processing lease and acknowledges completion. Ordinary handoff notes and idle receipts create no events. Mac review exports remain pending independent reconciliation; they do not write Notion or wake an existing desktop chat.

Read [the event operations guide](context_mcp/HANDOFF_EVENTS.md) and [the public reconciliation contract](context/EVENT_REVIEW.md). Intel needs its existing pairing, Python 3.12 and an explicitly configured authenticated Linux Codex executable. Source adoption and foreground service startup are deliberate steps. Event receipt does not fetch Git, change a dirty working tree, implement received code, start providers or move hardware.

This package was reconstructed from Git commit `ca512b1a2941f5ea0d8e6a2757b138cc41944fed`, then overlaid only with reviewed Mac event source and its documentation/tests. The concurrent dashboard-related changes to the relay, worker and their tests are excluded; those four files still match the base commit. The canonical live environment may contain that separate work, so its test counts and hashes must be reported separately. [Source origins](SOURCE_ORIGINS.json) and [the base inventory](verification/events-20261115/git-base.json) preserve that distinction.

## Standing Intel source delivery

**Owner update, November 15, 2026:** source delivery is now a standing part of authorized project work. Intel sends complete frozen source groups through immutable MCP manifest/chunk notes and publishes one `morph-source-delivery` completion event only after all notes verify. Mac notices each group, reconstructs and reviews it, reconciles it against current source and baseline hashes, then publishes accepted changes in small, meaningful commits. The earlier publication evidence above remains a dated snapshot, not evidence that later source changes have been received or adopted.

Read [the source-delivery policy](context/SOURCE_SYNC.md) for exact sender/collector commands, change metadata, exclusions, conflict handling and the separate received/reviewed/reconciled/published states. The bounded `context_mcp/source_intake.py` entry point coordinates isolated collection and hash comparisons using the existing collector. It does not apply source, run tests or invoke Git; those steps belong to the authorized Mac review workflow. A processed read-only event proposal is not a source receipt or GitHub publication. Keep the existing five-minute reconciliation and private state, and do not emit events for normal ACKs or idle receipts.
