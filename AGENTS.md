# Jose control package instructions

This is a portable snapshot of the current Mac simulation/provider/voice implementation. Preserve the supplied `SOURCE_MANIFEST.json` when recording later changes. Read `README.md` and the shared three-host handoff before changing interfaces.

The owner selected Jose's Mac for operator chat, coordination and likely voice on November 15, 2026. ElevenLabs is now undecided; its implementation is retained as an optional adapter. OpenClaw and Argon remain integration work until actual implementation and model access are established.

The owner specified Jose ↔ Intel through the NVIDIA tunnel owned by the other team. Use their supplied URL; do not implement or configure a tunnel. Klemen ↔ Intel uses the existing Mac MCP server. The local simulator does not yet implement a mission client for either path.

Keep new documentation in English. Keep credentials and runtime records out of source control. Do not copy the local lab database to Intel or use its simulated records as hardware reliability evidence. Starting or opening an application must not start physical motion.

Intel owns physical execution and must validate missions locally. Model selections do not supply joint commands, outcomes or reference labels. Preserve frame identity, state/goal versions, deadlines, preconditions and request/execution deduplication. Controller completion and physical confirmation are separate.

The current copied dispatcher is a simulator. Reconcile the newer Intel implementation and network contract before replacing it in a product path. Preserve original record identities and earlier failed, aborted or unverified outcomes. Add an explicit development note when implementation diverges from the supplied source hashes.
