# Communication publication verification

Verified November 15, 2026 in an isolated Python 3.12 environment using the locked MCP dependencies.

The 63 context/relay/worker tests pass. Tests exercise scoped reads, private-path exclusions, immutable notes, authenticated MCP, legacy GET behavior, request expiry and migration, exact response hashes, two-session query preservation, two narrowly allowed POSTs, explicit intent, stable IDs, bounded JSON, structured HTTP status preservation and no automatic POST retry. The new authenticated round trip verifies that the SDK preserves the original JSON body string.

All seven source-transfer receiver tests pass and are recorded separately under `verification/offline-01/`. Incoming source is never executed by sender/receiver verification.

Logs and manifest hashes identify the actual tested source. The earlier live Mac server and Intel service observation are historical deployment evidence, not evidence that this publication is running. This work starts no provider, robot, training, tunnel or production service.

