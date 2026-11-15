# Three-host ownership

Owner direction recorded November 15, 2026. This public handoff reflects the supplied architecture and subsequent transport clarification.

| Host | Responsibility | Connection |
| --- | --- | --- |
| Klemen Mac | Dashboard, quality/history, reliability analytics and saved-evidence analysis | Existing authenticated Mac MCP to Intel |
| Jose Mac | Interaction/chat, coordination, Nemotron observations and Gemini task/goal selection; voice expected here | NVIDIA tunnel supplied by the other team |
| Intel PC | Physical AI Studio, demonstrations/training, learned policies, Anomalib/OpenVINO, physical execution and authoritative records | MCP worker for Klemen; external tunnel for Jose |

NVIDIA and Gemini remain in scope. Decision 1 selects fixed choices, while a local validated Intel dispatcher must enforce execution rules. Gemma evidence analysis has no dispatch or outcome-writing authority. ElevenLabs is an optional voice adapter; the final provider remains undecided. OpenClaw/Argon/world-model labels in the sketch are intended components, not verified implementations.

## Communication

The [MCP relay](communication/context_mcp/STATION_RELAY.md) carries allowlisted reads plus explicitly intended audited reviews and saved-evidence analysis. An Intel worker must opt into those two POST routes. Robot commands, mission lifecycle and voice credentials are excluded. Keep pairing credentials on the servers and preserve response source-mode and freshness labels.

The NVIDIA tunnel is outside this implementation scope. A tunnel does not implement a mission API or validate physical actions.

## Current source and evidence

Jose's original control lab and separate 17-file Intel records-contract reference were published first. The later remaining-source inventory contains 240 root-qualified files: 110 transferred, 124 exact declared reuses and one additional exact CSV reuse. The reviewed supplement adds the exact ignore rules and synthetic PNG, bringing receipt to 237 of 240 originals. Three original test files remain pending; redacted copies are available for review only. The older Intel context server is a comparison reference; the newer Mac MCP is preserved.

Received Intel source still lacks an integrated mission lifecycle, dispatcher, learned-skill registry and Studio execution adapter. Command and voice endpoints are unavailable stubs. Session persistence and Decision/Execution records do not start robot missions.

The Intel service report dated November 15, 2026, 02:25:35 UTC distinguishes the main API on port 8000 from an isolated service on 52197: analyst routes exist in current source and the latter service, while the main loaded API lacks them. This is historical reported evidence, not a fresh deployment check.

## Remaining work

Adopt the reviewed packages deliberately and verify the actual Mac–Intel worker connection. Jose and Intel must implement the mission contract and validated physical execution adapter alongside the externally supplied tunnel. Complete actual voice, provider, calibration, training and physical-cycle acceptance with dated evidence. Local software tests and source publication do not close those criteria.
