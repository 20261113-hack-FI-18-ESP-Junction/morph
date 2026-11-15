# Intel delivery status and remaining mission work for Jose

Updated after the verified source receipt, comparison and independent guarded audit at **2026-11-15T03:35:47.871883+01:00** (Europe/Ljubljana, UTC+01:00). Jose's handoff is the first priority. The focused Intel record-contract source has now arrived; a physical mission API is still absent.

## Received and included

The [intel-contract folder](intel-contract/README.md) contains **17 exact source files, 230,799 bytes**, reconstructed from all **21** notes for transfer `8dfe841b-f157-469d-84fe-7586cdcd583f`. Request ID: `00e34e99-cfc8-47bf-ab5d-1d029242f841`. Manifest-note ID: `b5c45c9c-58ca-521e-a26e-8bd8e2cc0179`.

Intel froze the source at **03:29:40.570489 CET**; Mac collected and verified it at **03:33:51.290670 CET**. The entire 246,146-byte bundle has SHA-256 `f79c9426e361721aa63aa61038a93cbe1799d63e4a93501858a68112ea553e1b`. [manifest.json](intel-contract/manifest.json) and [report.json](intel-contract/report.json) retain the exact UTC timestamps and all file hashes. An independent static check verified those hashes again before copying the reference tree into this package.

The delivery includes current `models.py`, `store.py`, `schema.sql`, `api.py`, the four analyst modules required by its imports, supporting runtime files, requirements, launch script, README and two focused tests (`test_reviews.py`, `test_store.py`). All relative imports across eleven runtime Python files and their named symbols resolve under static inspection. The initial review was static. A subsequent [guarded isolated audit](intel-contract/verification/REVIEW.md) passed **56 tests**, with **zero provider attempts and zero outbound socket attempts**. It generated the included current-source OpenAPI/schema and confirmed the command/voice stubs without altering source bytes. Intel's delivery note `1717cf39-0221-4966-aafe-e5b2b963ceaf` confirms all source notes were saved/read back and separately reports 72 target tests; 16 API tests were excluded from transfer by the conservative source filter. The local verified count is 56, not 72.

The runnable Mac lab remains in `station/`, with all 26 original copied hashes unchanged. The incoming tree is under `intel-contract/source/` and is not on the launcher's import path. See [CONTRACT_COMPARISON.md](intel-contract/CONTRACT_COMPARISON.md) for the exact differences. New Intel review models, atomic review receipts and analyst routes are preserved without replacing the lab's foundation.

## What is still absent

Intel's [fresh priority reply](../../../context/notes/90a28910-e9bf-4f5c-9731-91573c60af05.json), observed **03:27:14.565918 CET**, reports no real mission/control HTTP API, dispatcher, learned-skill registry or mission hardware adapter. `/api/v1/commands`, `/api/v1/voice/token` and `/api/v1/voice/utterances` are unavailable stubs. Creating or ending a session only writes bookkeeping records. The received source independently confirms those stubs and contains no newer Nemotron/Gemini/control/voice implementation to replace the Mac modules.

The current source's records `Snapshot` has `goalVersion: null`, `goal: null`, `availableActions: []` and unavailable/unverified online capabilities. Its `stateVersion` is the record event sequence. These are not the state/goal versions or permission menu of a physical mission dispatcher. Preserve that distinction when building Jose's client.

The earlier [Intel presence review](../../../context/notes/4198cdf3-e521-4e57-b91b-443c17995d01.json), saved November 14 at **23:32:42 CET**, and [final integration report](../../../context/notes/4da23947-85ac-460e-8c53-90dc081fb1fe.json), saved **23:38:52 CET**, already kept the Mac control/provider/voice lane separate from Intel M16/Gemma work. The new inventory and received source supersede those older absence observations. Linked historical notes live in the canonical shared workspace and are not part of this standalone package; the actual received source and comparison are included locally.

## Exact remaining request to Intel

| Item | Current state | Needed next |
| --- | --- | --- |
| Mission/control API and skill execution | Absent in the current inventory/source | Agree the owner and typed application contract, then implement the locally validated mission service. Supply any separate current skill/adapter interface if one exists; explicitly report absent components. |
| Records API/models/store/schema and import closure | Received and hash-verified | Reconcile these definitions with Jose's read adapter. Do not resend a broad historical application archive. |
| Actual frame/checkpoint/inspection adapters | Not supplied; source still reports unavailable camera/Anomalib controls | Send the actual implemented adapter interfaces or explicit absence, with one small sanitized or clearly simulated fixture and stable frame/object/timestamp linkage. |
| Dependencies and focused tests | Pinned requirements, launcher, review/store tests received; 56 tests independently passed on Mac with provider/network guards | Preserve the included evidence and use explicit `PYTHONPATH` for the source tree. Intel reports 72 target tests separately; its 16 API tests were not part of the transfer. |
| Newer online Nemotron/Gemini/voice/OpenClaw/Argon modules | Intel reports none; no such modules appear in the transfer | Continue from the available Mac modules. Report any separate or later implementation without recreating files merely to satisfy the request. |
| Running-service OpenAPI versus source | Intel reports different snapshots on main `8000` and isolated `52197` | Provide exact dated OpenAPI captures/provenance before selecting a production target. Source receipt alone does not identify loaded main-service modules. |

Intel freshly reported source root `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z/HachingJunction` and no usable Git repository. Fresh GET inspection at **03:25:35 CET** found API `8000` and isolated API `52197` healthy, with `hardwareIntegrated=false` and `providersIntegrated=false`. Main `8000` had no analyst routes; isolated `52197` and current source had them. These are attributed runtime observations; live response captures are not included in this transfer.

## The mission contract still needs these fields

The new service must define its application base path/authentication, supported goals and permitted learned tasks; actual policy IDs/versions and physical preconditions; coherent mission state/goal versions; stable session/cycle/object/attempt/frame/request/execution IDs; original deadlines and duplicate/conflict behavior; and distinct accepted/acknowledged/finished/failed/unverified lifecycle. Specify how a provider `decisionId` binds to a task, when a goal commits, whether one-shot extra inspection is implemented, and how stop/pause/restart uncertainty works. Independent confirmation must preserve commanded versus observed destination and the confirmation source.

**Jose ↔ Intel uses the NVIDIA tunnel supplied by the other team.** They provide the URL/transport; an implemented mission API must exist behind it. This package does not set up their tunnel. Keep provider keys on Jose's server and final validation plus physical execution on Intel. Klemen's read-only runtime data path through Mac MCP remains separate.

## Jose can continue immediately

Run the package's [existing Mac lab](README.md). Its current UI, bounded Nemotron observations, Decision 1 goal/task selection, optional finalized Scribe input, simulated dispatcher and persistent receipts are included. Its relocated checks passed **124 Python tests**, **seven voice JavaScript groups** and **11 smoke checks**. These tests describe the Mac lab, not the incoming Intel source.

Mac previously verified one actual clear spoken `sort` selection and one local simulated goal commit, followed by a fresh `place_good` recommendation without dispatch. That sample is not physical acceptance or broad speech-quality evidence. ElevenLabs remains optional under the owner's latest direction. OpenClaw and the diagram's Argon adapter still require interface/access verification and implementation; Argon is not substituted for Decision 1.

Jose can build the chat/operator UI and reconcile read schemas now. The physical mission client waits for the agreed Intel mission/skill service. Full M16 history UI, Gemma product work, dashboard archives, training datasets/checkpoints and old ZIPs remain deferred from this priority delivery. The included analyst files are present only because the current records API imports them.
