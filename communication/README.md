# Klemen–Intel communication

This package contains the current Mac context MCP, its station relay, Intel's standard-library worker, and the reviewed source-transfer helpers. It connects Klemen's dashboard to Intel's authoritative records using the existing MCP pairing.

The November 15, 2026 publication adds bounded record review and saved-evidence analysis requests to the existing read transport. These changes are staged source with isolated verification. The live Mac server and Intel worker have not been updated by this publication.

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

