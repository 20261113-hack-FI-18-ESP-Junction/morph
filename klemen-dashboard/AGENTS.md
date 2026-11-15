# Klemen dashboard handoff instructions

Write project documentation in English. This partition is the Klemen Mac dashboard and analytics lane from the owner's November 15, 2026 architecture. The parent handoff records the shared three-host contract and task status.

Keep Jose's chat/mission/voice lane and Intel's local physical execution lane separate. ElevenLabs is an open choice; voice is provisionally assigned to Jose. Existing historical files do not override that owner direction.

This publication package reconciles the verified Intel M16 history/replay, Gemma UI and shared-client source with the Mac MCP adapter. Preserve the original SOURCE_PROVENANCE.json and the separate SOURCE_RECONCILIATION.json when making later changes. Source receipt and local verification do not establish an updated Intel deployment.

Do not start motion through dashboard load, refresh or reconnect. Preserve the existing Mac MCP transport and server-only pairing credentials. The proxy accepts reads plus two explicit JSON intents: record-review for /api/v1/cycles/{id}/review, and evidence-analysis for /api/v1/analysis/reports. Keep their bodies and application identifiers unchanged, validate the route/intent/size, and never retry a mutation automatically. Other writes and mission routes remain unavailable. Jose-to-Intel NVIDIA networking belongs to the other team; do not implement it here. Never copy real environment files, tokens, recordings, local databases or dependency installations into a delivery archive.

Keep sessions, cycles and attempts distinct. Preserve IDs, event times, revisions, reference labels and confirmation evidence. Ratios use persisted metrics and visible denominators. Simulation remains explicit and excluded from real hardware metrics by default. Model text is not physical evidence.

Run relevant existing tests after edits, save evidence and coordinate Notion/shared MCP updates through the parent project workflow. Mark physical/provider capabilities verified only with their actual evidence.
