# Morph

Morph combines an operator interface, model-assisted task selection and recorded quality evidence for a physical robot workflow. This repository contains the three agreed host partitions and their shared communication code. Jose's existing runnable control lab remains at the root; the other packages have their own setup and verification guides.

For the combined dashboard/video demonstration, actual Intel records connection and remaining non-Jose integration work, start with [Run and finish the Morph system](WORKING_SYSTEM.md). The runnable local demonstration and the actual station connection are explicit separate modes.

| Owner | Start here | Included behavior |
| --- | --- | --- |
| Jose Mac | Root instructions below | Operator/control simulation lab, Nemotron and Gemini adapters, optional voice |
| Klemen Mac | [klemen-dashboard](klemen-dashboard/README.md) | Current dashboard, audited history/replay, Gemma evidence UI, shared client and offline analytics |
| Intel PC | [intel-runtime](intel-runtime/README.md) | Current records/analyst backend, setup, diagnostics and reproduction source |
| Klemen ↔ Intel | [communication](communication/README.md) | Existing Mac MCP, worker, restricted review/analysis requests and source-transfer helpers |

The [remaining-source handoff](REMAINING_SOURCE_HANDOFF.md) records source freshness, package checks and the three original test files still represented by redacted review copies. [source-review](source-review/README.md) preserves those copies separately from executable test suites.

The lab includes bounded Nemotron observations, Gemini Decision 1 goal/task selection, version-checked simulated dispatch, persisted provider receipts and an optional ElevenLabs microphone path. It can start without provider credentials. **Physical robot dispatch is not implemented here**, and the received Intel source has no mission service or learned-skill dispatcher yet. Jose can build the operator/chat interface and reconcile record schemas immediately while that service is agreed with the Intel team.

This repository was imported from the November 15, 2026 handoff. The [Mac verification](VERIFICATION.md) records 124 passing Python tests, seven voice JavaScript groups and 11 smoke checks. The separate [Intel source audit](intel-contract/verification/REVIEW.md) records 56 passing tests under provider/network guards, with zero attempted calls. These are software and simulation results; they do not establish physical acceptance.

## Get started

Use **Python 3.12**, Git and Bash on macOS. The voice regression harness also requires **Node.js**; it uses built-in Node modules and needs no npm installation. No robotics SDK or model credentials are required to start the local lab.

```bash
git clone https://github.com/20261113-hack-FI-18-ESP-Junction/morph.git
cd morph
python3.12 -m venv .venv
.venv/bin/python -m pip install -r station/requirements.txt
bash run.sh
```

Open `http://127.0.0.1:8012/lab`. The launcher binds to loopback and creates its local database and owner-only token under `.data/jose-control/`. The browser page contains that local lab token and should remain private to this machine. Loading or refreshing the page reads state. The **Create simulation** button explicitly creates simulated input records; none of the bundled fixtures represents a live robot session.

To use an existing isolated Python environment:

```bash
MORPH_PYTHON=/absolute/path/to/python bash run.sh
```

To select another port or private data directory:

```bash
bash run.sh --port 8013 --data-dir /absolute/path/to/private/jose-lab
```

[env.example](env.example) lists optional server environment variables. It contains placeholders and is not loaded automatically; configure real values privately in the launching process. This repository excludes the original machine's credential loader, so provider credentials are read only from the supported environment variables. An unconfigured provider remains unavailable.

## Repository guide

| Path | Purpose |
| --- | --- |
| `station/morph_station/lab.html`, `lab.py` | Operator UI, microphone transport and local lab launcher |
| `station/morph_station/control_api.py` | Authenticated control/provider/voice routes for the simulator |
| `station/morph_station/providers.py` | Frame-linked Nemotron observations and bounded Decision 1 goal/task selections |
| `station/morph_station/voice.py`, `voice_api.py` | Optional Scribe configuration, token request and durable complete-utterance journal |
| `station/morph_station/dispatcher.py` | Simulated task execution with state/goal versions and duplicate checks |
| `station/morph_station/models.py`, `store.py`, `schema.sql`, `api.py` | Records and API dependencies used by the lab |
| `station/morph_station/client.py`, `simulation.py`, `export_audit.py`, `__main__.py` | HTTP client, explicit fixtures, offline export audit and records CLI |
| `station/tests/` | Python regression tests and the Node voice harness |
| `setup/provider-check/fixtures/red-rectangle.png` | Synthetic image for the explicit lab fixture |
| [intel-contract](intel-contract/README.md) | Exact received Intel source, transfer hashes, comparison and isolated audit evidence |
| [API_CONTRACT.md](API_CONTRACT.md) | Current interfaces and the missing production mission transport |
| [INTEL_REQUIRED_FOR_JOSE.md](INTEL_REQUIRED_FOR_JOSE.md) | Intel delivery scope and the remaining mission implementation work |
| [THREE_HOST_ARCHITECTURE.md](THREE_HOST_ARCHITECTURE.md) | Host responsibilities and the agreed transport boundaries |

The root launcher imports only `station/`. The **17 received Intel files, 230,799 source bytes**, remain under `intel-contract/source/`; all transfer and per-file hashes were checked before import. Their records API adds review/analyst behavior beyond the Mac foundation. Keep the two snapshots separate while designing the production integration. The immutable provenance is in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json), [Intel manifest](intel-contract/manifest.json) and [Intel receipt](intel-contract/report.json).

The later `klemen-dashboard/`, `intel-runtime/` and `communication/` packages preserve newer received source and intentional MCP adaptations separately from this original Jose lab. Use `intel-runtime/` for the broader current Intel snapshot; `intel-contract/` remains the immutable focused reference received earlier. References to canonical task IDs, context notes and workspace paths identify historical evidence, not additional private files in this checkout.

## Integration responsibilities

Jose owns the operator/chat interface, high-level coordination, Nemotron and Gemini orchestration, likely voice hosting, and the future mission client. **Jose ↔ Intel uses the NVIDIA tunnel supplied by the other team.** That team provides the URL and transport; Jose and Intel must agree the application authentication and mission contract. This repository does not create or configure the tunnel. `MORPH_INTEL_BASE_URL` is reserved for the future client and is not read by the current simulator.

Intel owns authoritative records and the eventual locally validated learned-skill execution, physical adapters and outcome confirmation. Klemen's dashboard/analytics uses the existing Mac MCP server supplied in `communication/`. Its worker defaults to reads; explicit write opt-in permits audited record review and saved-evidence analysis. A tunnel or a records endpoint does not implement physical mission dispatch.

The owner's November 15 decision makes **ElevenLabs optional** and places voice provisionally on Jose's Mac. Its experimental implementation is retained for reuse if selected. OpenClaw and the diagram's Argon component still need interface/access verification and implementation. Decision 1 remains a fixed-choice selector; application code owns task parameters and must never turn model output into joint commands.

## Continue development

1. Run the lab and inspect `control_api.py`, `providers.py` and `lab.html`. The current flow separates observation, selection, goal commitment and simulated dispatch.
2. Read the [Intel contract comparison](intel-contract/CONTRACT_COMPARISON.md) and reconcile authoritative record reads. Preserve original session/cycle/attempt/frame IDs, revisions, timestamps and source-mode labels.
3. Agree and implement the missing Intel mission/skill service with its owner, then connect Jose's server-side mission client through the other team's tunnel. Keep final validation and motion execution on Intel.
4. Build the operator chat UI and verify the OpenClaw/Argon boundaries. Preserve complete-utterance finalization and stable IDs if adapting voice; partial transcripts and late metadata must not issue repeated commands.
5. Verify versions, evidence freshness, permitted tasks, preconditions, deadlines and execution deduplication across the actual interface. Keep accepted, acknowledged, finished and physically confirmed outcomes distinct.

The one-shot `inspect_more` budget remains open. A previously recorded spoken `sort` goal committed once in simulation, followed by a selected `place_good` task without dispatch; this does not demonstrate a changed physical next action. The included Intel source confirms unavailable command/voice stubs and null goal state. Intel also reports different loaded snapshots on main API `8000` and isolated analyst API `52197`; the included generated OpenAPI describes received source tested locally, not those live services.

## Run the checks

After creating `.venv` and installing the pinned requirements above, run from the repository root:

```bash
PYTHONPATH=station .venv/bin/python -m pytest station/tests -q
node station/tests/test_voice_browser.cjs
bash -n run.sh
```

Python tests use temporary data and fake providers. The Node harness executes the actual voice JavaScript with fake audio and sockets without opening a microphone; it refreshes `station/verification/voice-browser-tests.json`. [VERIFICATION.md](VERIFICATION.md) explains the saved results, the corrected `PYTHONPATH` invocation and the separate Intel audit. The original Intel audit runner retains its canonical-workspace paths; see [the Intel reference guide](intel-contract/README.md) before attempting to reuse it.

Keep `.data/`, `.venv/`, real environment files, credentials and private provider/session evidence out of version control. Preserve the supplied source manifests and record intentional later changes separately.
