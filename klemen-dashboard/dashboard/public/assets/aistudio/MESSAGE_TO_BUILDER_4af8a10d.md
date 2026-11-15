# Message to the Morph dashboard builder

Copy the message below and send it with `Morph-dashboard-handoff-2026-11-14.zip`.

---

Please build **Morph**, our dashboard for a voice-directed SO-101 robot that inspects and sorts Duplo bricks. The attached ZIP contains the improved visual references, logo, graphics, fonts, a working presentation prototype, an AI Studio prompt, and the proposed integration contract.

Extract the ZIP with its directory structure intact. Start with `START_HERE.md`, then read `AGENTS.md` and `design/morph-handoff/HANDOVER_GUIDE.md`. Follow the guide's reading order, implementation stages and acceptance checklist.

The visual direction is a subtle **Tech Renaissance** interface: neutral black, restrained bronze, readable typography and a small orbital/Copernicus treatment at the absolute top. The current object and evidence must dominate. Match `01-live.png` and `06-design-system.png`, then implement all three views and the other reference states, including disconnected and mobile. Keep interface text and documentation in English.

For AI Studio, copy the entire `AI_STUDIO_MASTER_PROMPT.txt`, supply `DESIGN_SPEC.md`, `INTEGRATION_CONTRACT.md` and `HANDOVER_GUIDE.md` as context, and attach the relevant screen PNGs. The guide gives the exact sequence and first-stage instruction. Use the provided assets in the actual project, retaining font licenses and artwork attribution.

Implement the persisted session/cycle/attempt model and a clearly labeled Simulation adapter first. Then build the UI and interactions against `StationClient`. The included HTML is an offline presentation reference with in-memory examples; it is not the finished database, station API or robot integration.

Preserve these requirements: independent detection labels; separate physical and overall task outcomes; retries within one cycle; frame-linked analysis; visible metric denominators; audited corrections; replay without new executions; and a large red **Software stop** with actual acknowledgment. Do not copy fictional hardware or performance claims from older Stitch concepts.

The product must include Anomalib/OpenVINO and Studio-trained robot skills, plus **NVIDIA Nemotron**, **online Gemini Decision 1**, and **ElevenLabs voice input**. Keep their contributions distinct. The local application validates task choices and owns robot dispatch. Report unavailable accounts, models or hardware as blockers; do not silently substitute providers or call simulated behavior verified.

Return the source repository or ZIP, exact setup/run/build commands, dependency lockfile, placeholder-only configuration, tests/results, desktop/mobile screenshots, a sanitized simulation trace and `IMPLEMENTATION_STATUS.md`. List what is implemented, what is verified and what still needs access or physical testing. Use section 8 of the handover guide as the delivery checklist.

Start with stages 1–3 so we can review a coherent dashboard in simulation, then connect the verified station adapters and complete physical validation. Keep the package's data rules and visual direction consistent throughout.
