# Jose Mac — control, chat and voice handoff

**Ready for Jose:** the runnable Mac control/voice lab and the requested current Intel records source are included. All source hashes passed; the lab passed 124 Python tests and the received Intel source passed 56 separate tests under network/provider guards. Read [Intel delivery status and remaining mission work](INTEL_REQUIRED_FOR_JOSE.md). Jose can continue UI/control development immediately; physical missions still require an Intel mission service, which the current Intel inventory and source confirm is absent.

Prepared for the owner's three-computer architecture on November 15, 2026. This folder contains the runnable Mac control/provider/voice implementation and its local dependencies, plus the newly received Intel record-contract source in a separate reference tree. `SOURCE_MANIFEST.json` records the Mac lab files; `intel-contract/manifest.json` and `report.json` identify the received Intel files.

**Runnable today:** the existing browser control lab, bounded Nemotron observations, Gemini Decision 1 selections, version-checked simulated goal/task handling, persisted provider receipts and the optional ElevenLabs microphone path. Every dispatcher in this package is a **simulation** dispatcher. The current source has no Intel mission transport and no physical robot adapter.

**Intel source received and verified, November 15 at 03:33 CET:** all 21 source-transfer chunks reconstructed **17 current Intel files, 230,799 source bytes**. They are included in [intel-contract](intel-contract/README.md), with a [static contract comparison](intel-contract/CONTRACT_COMPARISON.md), without replacing the runnable lab. The received source confirms the unavailable command/voice stubs; Intel reports that its real mission API and dispatcher are absent. Main API `8000` and isolated/current-source analyst API `52197` are different snapshots. See [delivery status and next steps](INTEL_REQUIRED_FOR_JOSE.md). The other team's NVIDIA tunnel will transport a future agreed mission interface; it does not implement one.

**Jose owns the next implementation:** the operator chat/interface, high-level coordination, Nemotron and Gemini orchestration, the likely voice host, and the mission client that will communicate with Intel. The owner has specified **Jose ↔ Intel through the NVIDIA tunnel being prepared by the other team**. Use that team's supplied URL and application contract; this package does not implement or configure their tunnel. OpenClaw and the diagram's Argon component are planned integration points; no implementation or model/API substitution is claimed here. Argon is retained as the owner's diagram label; its exact model/API and access must be verified before implementation. Decision 1 remains a distinct fixed-choice selector.

The owner's November 15 instruction makes **ElevenLabs undecided**. Its working experimental source is retained so it can be reused if chosen. Starting the package does not require provider credentials. Voice provider selection and a broader chatbot are still development work.

## Start the existing application

From this folder, use Python 3.12 and an isolated environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r station/requirements.txt
bash run.sh
```

Open `http://127.0.0.1:8012/lab` in a browser. The launcher uses `.data/jose-control/` for a fresh local lab database and owner-only token. It binds only to loopback. The browser page contains the local lab token and must remain private to this machine. Loading or refreshing the page reads state; the **Create simulation** button intentionally creates simulated input records. No supplied package data is a live session.

For the already prepared development environment, use an explicit interpreter:

```bash
MORPH_PYTHON=/absolute/path/to/python bash run.sh
```

An alternate port or data directory can be selected explicitly:

```bash
bash run.sh --port 8013 --data-dir /absolute/path/to/private/jose-lab
```

`env.example` lists the optional server environment names. It contains no credentials and is not loaded automatically. Configure actual values privately in the launching process. No secret configuration from Klemen's Mac is included. This portable copy intentionally has no `setup/provider-check/check.py`, so the existing credential loader reads only the permitted environment variables. An unconfigured provider remains unavailable; it is never silently replaced.

## Code ownership and the handoff boundary

| Code | Purpose and ownership |
| --- | --- |
| `station/morph_station/lab.html` | Existing operator UI and microphone transport; Jose's starting UI, not a finished chatbot |
| `station/morph_station/lab.py` | Loopback launcher and isolated lab token/database |
| `station/morph_station/control_api.py` | Current authenticated control/provider/voice routes; still simulation-only |
| `station/morph_station/providers.py` | Frame-linked Nemotron requests and bounded Decision 1 goal/task selection; never dispatches motion |
| `station/morph_station/voice.py`, `voice_api.py` | Optional Scribe transport settings, token request and durable complete-utterance journal |
| `station/morph_station/dispatcher.py` | Vendored simulator and contract reference for development; actual hardware validation/dispatch stays on Intel |
| `station/morph_station/models.py`, `store.py`, `schema.sql`, `api.py` | Vendored records/API dependency needed by the lab; this local simulation database is not the production source of truth |
| `station/morph_station/client.py`, `simulation.py`, `export_audit.py`, `__main__.py` | Existing supporting clients, explicit fixtures and offline audit tooling |
| `setup/provider-check/fixtures/red-rectangle.png` | Copied synthetic image needed by the explicit lab fixture; not a camera observation |

Klemen's React dashboard and analytics are in the separate dashboard package, with **Klemen ↔ Intel communication through the existing Mac MCP server** as directed by the owner. Intel owns Physical AI Studio, training, the local learned-skill dispatcher, cameras, Anomalib/OpenVINO execution and confirmed outcomes. The duplicated Python foundation is included only to let this folder run independently while the shared contract is reconciled. It is not permission to replace newer Intel files with older Mac copies.

The existing `/api/v1/control/*` and `/api/v1/lab/*` routes document the development behavior. These routes are not asserted to exist on Intel. [API_CONTRACT.md](API_CONTRACT.md) maps the current interfaces and the exact missing transport. Before implementing the network bridge, use the included Intel source and schema comparison to agree the missing mission contract and actual target service. Preserve stable session/cycle/attempt/frame/request/execution IDs, state and goal versions, deadlines, permitted task menus and duplicate rejection. Send a validated mission/task request; never cloud-generated joint commands. Intel must validate and execute locally and return acknowledgment, completion and physical confirmation as distinct facts.

## Continue development

1. Run the lab and read `station/morph_station/control_api.py`, `providers.py` and `lab.html`; the existing UI already separates observation, selection, goal commitment and dispatch.
2. Read the received `intel-contract/` comparison and reconcile its record schemas. Agree the missing Intel mission service and the other team's NVIDIA tunnel URL before writing the production mission client. The tunnel is outside this package's implementation scope. Keep this lab available as a deterministic simulator during that work.
3. Build the operator chat UI and decide the OpenClaw/Argon boundary against actual available code and model access. Keep Decision 1 fixed-choice and application-owned task parameters.
4. Keep voice local to Jose's operator UI if that remains the team's choice. An alternative provider must preserve complete-utterance finalization and stable IDs; partials and late metadata must never issue another command.
5. Integrate only currently permitted learned tasks. Unknown state, stale evidence, a timeout or missing physical confirmation must remain visible and must not become a successful outcome.

The one-shot `inspect_more` budget is still open in the current Mac source. A supported spoken `sort` goal and a subsequent selected task were recorded previously in a simulated control context; that does not establish a changed physical next action. The handoff itself makes no provider calls and includes no owner audio or private session database.

## Verify this copy

```bash
PYTHONPATH=station .venv/bin/python -m pytest station/tests -q
node station/tests/test_voice_browser.cjs
```

The selected Python tests cover control lifecycle, provider requests, speech finalization and dispatcher boundaries. The Node harness runs the actual voice JavaScript against fake audio and sockets without opening a microphone. [VERIFICATION.md](VERIFICATION.md) describes the checks run for this handoff and their scope. The separate [Intel source audit](intel-contract/verification/REVIEW.md) passed 56 store/review tests with zero outbound socket or provider attempts; its OpenAPI and record schema were generated locally from the received bytes, not captured from Intel running services.

`SOURCE_MANIFEST.json` identifies the original Mac source snapshot. The separately received Intel reference has its own manifest, receipt, comparison and isolated test evidence in `intel-contract/`. Source-byte receipt is verified; target deployment, a mission service and physical acceptance are not established by that receipt. Keep this folder's `.data/`, `.venv/`, real environment files and any new provider evidence out of source transfers.
