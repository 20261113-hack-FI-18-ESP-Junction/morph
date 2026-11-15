# Morph Intel runtime source handoff

This package preserves the Intel station backend, setup definitions, diagnostic tools, operator notes, watcher dependency, and selected reproduction material available on November 15, 2026. The station records API is runnable locally. The intended physical mission API, dispatcher, learned-skill registry, Studio execution adapter, and complete training/execution integration are not present in the received implementation.

The owner architecture assigns physical AI and authoritative execution records to Intel, control and chat to Jose, and dashboard and analytics to Klemen. Klemen–Intel communication uses the existing Mac MCP server. Jose–Intel communication uses the NVIDIA tunnel owned by the other team. Current communication code is supplied separately; this package does not replace the Mac server with an older Intel copy. Voice will likely run on Jose's computer; the owner has not finalized ElevenLabs.

## Current package development record — November 15, 2026

The committed Mac dashboard/media work adds the bounded dashboard read contract and a separate [Studio JPEG to H.264 bridge](media-bridge/README.md). Two received backend files, `morph_station/api.py` and `morph_station/store.py`, have documented Mac changes; 34 additional source, contract, test and verification files were committed with that work. [SOURCE_UPDATES.json](SOURCE_UPDATES.json) records every original/imported hash, current hash, reason and source commit, and retains the complete previous package seal. [SOURCE_ORIGINS.json](SOURCE_ORIGINS.json) preserves each changed original provenance row and distinguishes Mac additions from Intel receipts.

The current package seal covers these already committed bytes. Repository-root, dashboard, nested-source and frozen delivery manifests remain their original historical records. This metadata reconciliation runs no application or incoming tests and adds no deployment, provider, camera or physical acceptance. The initial inventory counts and dated reports below retain their original scope.

## Source layout and provenance

| Package path | Purpose and original root |
| --- | --- |
| `source/common/HachingJunction/station/` | Authoritative Python records, reviews, export audit, and Gemma analyst backend; received tests and synthetic fixtures. |
| `source/common/HachingJunction/setup/` | Original Intel/Mac Studio, Anomalib and OpenVINO environment definitions and setup scripts; provider-check source. |
| `source/common/verification/` | Original reproduction scripts, synthetic exports, and dated reports. Some scripts depend on the separate dashboard partition or omitted historical runtime output. |
| `source/common/scripts/` | Original preflight and dashboard/provider helper scripts; preserved for review, not invoked by this package. |
| `source/junction/scripts/` | Original Intel camera/USB/motor diagnostics and Mac context watcher. |
| `source/junction/tests/` | Fake-bus motor discovery and fake-client watcher tests. |
| `source/junction/morph-intel-continuation-20261114T193410Z/…/sync_shared_context.py` | Exact dynamic-import dependency used by the watcher. Its original directory layout is retained. |
| `fixtures/audit/` | Three byte-identical copies of received synthetic exports, placed at the paths expected by the export-audit tests. |
| `fixtures/evidence/` | One separately derived 68-byte synthetic PNG, extracted from the existing `test_store.py` constant without executing project code. |
| `tools/`, `run.sh` | New portable package launcher, offline verification, and integrity tools. |

`common` maps to the original Intel root `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z`; `junction` maps to `/home/intel/Documents/Junction`. Relative source paths and original bytes are preserved. No live Intel working tree was overwritten.

The initial reconstruction contained 123 original source/document/evidence files, three exact fixture aliases, and one separately derived synthetic image. [SOURCE_ORIGINS.json](SOURCE_ORIGINS.json) records every source path, acquisition type, byte count, and SHA-256. Reused Mac bytes were accepted only when they matched the current Intel inventory hash. The complete package inventory is [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json); it excludes only its own self-reference and ignored runtime output.

The source request is `90672035-350b-43ad-88d6-025885cfbd65`. The Intel inventory was captured at `2026-11-15T03:22:50.592056Z`, the completion report was saved at `2026-11-15T03:28:11.681650Z`, and reconstruction was verified at `2026-11-15T03:38:11.054357+00:00`. Source references in the shared context ledger are inventory index `7352a432-face-43d0-bb1e-45bb82ed82fb`, completion `2e753690-9953-4eaa-9bd0-6f9897c1db44`, and constraints `5a8dc4dd-ad58-4ee0-9693-9a7e9641baeb`. A reviewed supplement, `a8046978-b5fa-4e1b-9363-d18ee24c5a45`, was verified at `2026-11-15T03:52:30.711459+00:00` and supplied the exact station ignore file and provider PNG. These raise the wider received inventory coverage to 237 of 240 files.

## Run the records API

Use Python 3.12 and a new environment in this package. These commands install the records API requirements, not robotics dependencies. Review the original pinned requirements before installation on another machine.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r source/common/HachingJunction/station/requirements.txt
./run.sh --help
./run.sh init
./run.sh serve --host 127.0.0.1 --port 8000
```

Run from the package root. The launcher also works from another directory. Set `MORPH_PYTHON` to an absolute interpreter path to use an existing prepared environment. Runtime records, evidence, and the private API token default to `.runtime/station/`; use `MORPH_DATA_DIR` for a separate instance. Initialization creates an empty database and a mode-0600 token file without printing the token. Serving is an explicit action and does not seed simulation or start a robot.

For a deliberate, labeled simulation after initialization:

```bash
./run.sh seed-demo --prefix local-demo
./run.sh request /api/v1/station/snapshot --url http://127.0.0.1:8000
```

The request command is a separate terminal action while the server is running. It reads the local token file. Keep the API loopback-bound unless the separate communication design explicitly requires otherwise. Do not point this new instance at an existing Intel production database to try the package.

The original `station/run.sh` is preserved but assumes the previous `.junction-setup` layout. The root launcher supplies portable interpreter, import, and runtime paths. Historical reproduction scripts retain their original host paths and service assumptions; follow their source as reference rather than treating every imported command as a ready-to-run package entry point.

## Verify without devices or providers

```bash
.venv/bin/python tools/verify_package.py
.venv/bin/python tools/verify_offline.py
```

The offline verifier uses a new output directory under `.runtime/verification/`. It first verifies all imported bytes, parses source Python, checks shell syntax, and exercises the root launcher's help and empty initialization in temporary storage. It then runs only the four received station test modules and two Intel fake-device/fake-client test modules. It checks imported hashes again afterward. Reviewed export-audit CLI subprocesses inherit the same guards. Provider credentials are removed from test environments; network/listener operations, device opens, real hardware-library imports, unreviewed subprocesses, and external process signals are denied. These process-local guards support the source review and are not an OS sandbox.

The final package run passed 158 tests plus five subtests (163 JUnit cases), with zero failures, errors, skips, or blocked operation attempts. All 125 imported/aliased/derived files retained their hashes. The run parsed 42 original Python files and checked nine shell scripts. Results are recorded in [verification/offline-02/result.json](verification/offline-02/result.json), [pytest.log](verification/offline-02/pytest.log), and [tests.xml](verification/offline-02/tests.xml). The earlier `offline-01` result covers the same original tests before the portable launcher smoke and derived fixture were added. Both runs are local Mac offline verification. They do not establish physical operation, provider access, Intel environment installation, or a new deployed service state.

## Diagnostics, watcher, and environment setup

Read the original [junction README](source/junction/README.md), [robot game plan](source/junction/ROBOT_GAMEPLAN.md), [role correction](source/common/ROLE_ASSIGNMENT_CORRECTION.md), and [physical AI setup](source/common/HachingJunction/PHYSICAL_AI_SETUP.md) before using Intel equipment. Their reports and instructions are dated source context. The established serial roles are leader `5B91030668` and follower `5AE6075066`; confirm current physical ownership and calibration before any device access.

Camera checks, RealSense checks, motor probing, Studio, installation, training, provider evaluation, and historical service launchers were not executed while preparing this package. The motor test uses a fake bus and patched device metadata. A script named “readonly” can still communicate with hardware when run normally. These scripts remain explicit operator actions.

The watcher retains its real relative import of `sync_shared_context.py`. That historical client still reads pairing files from `/home/intel/Documents/Junction/morph-intel-transfer/morph-intel-pairing`; no pairing folder or credentials are included. It must be reviewed and configured for the intended Intel host before deliberate use. The current Mac MCP server and station worker/relay are supplied by the separate communication package. The watcher tests construct a fake client and do not initialize that private connection.

## Explicit gaps and remaining work

[SOURCE_GAPS.json](SOURCE_GAPS.json) records the three remaining unreceived original files from the wider current Intel inventory, with expected hashes and transfer reasons:

- `morph-station/server/stationProxy.test.ts` — dashboard test source, not received.
- `HachingJunction/setup/provider-check/test_check.py` — provider-check tests, not received.
- `HachingJunction/station/tests/test_analysis.py` — current analyst tests, not received.

The original 162-byte station `.gitignore` and 159-byte provider PNG are now included byte for byte from the reviewed supplement. The root ignore file remains separate package scaffolding. Redacted copies of the three tests were received as separate review material, not exact or executable replacements; they are not included or run in this package.

The exact Mac CSV was recovered by its current inventory hash and is included. The 68-byte evidence dependency is different from the 159-byte provider PNG: the included synthetic image was derived locally from the existing `test_store.py` constant and hashes to `e35a9b35f300af2d9334aedac4dbb6a4c746345c5c05b25fc4ab7447977baa82`. Intel subsequently reported a bounded current-file comparison at `2026-11-15T03:48:06.194996+00:00`, confirming the original blob matches these exact constant bytes in note `d4569216-5d0d-589f-9ea7-1641db906993`. The local acquisition remains AST derivation; the blob itself was not transferred. [Supplement verification](verification/supplement.json) records the comparison report and the independently checked artifact hashes. Historical replay scripts may require explicitly placing the synthetic fixture in a new scratch replay directory; the package does not create a runtime database or evidence directory automatically.

The current source includes analyst report POST and review POST behavior. The accompanying staged communication package retains `enqueue_station_read`/`claim_station_reads` and adds `enqueue_station_request` plus `claim_station_requests`. Its write allowlist contains only `POST /api/v1/cycles/{id}/review` with intent `record-review` and `POST /api/v1/analysis/reports` with intent `evidence-analysis`. The worker remains GET-only unless explicitly started with `--allow-record-writes`; an intentional analyst request can invoke the configured provider. POST operations are not automatically retried, and an unknown transport outcome must remain visible. This is prepared source capability, not a claim that either service has been upgraded or that these writes work across the current live connection.

At the separate observation time `2026-11-15T02:25:35+00:00`, the main service on port 8000 lacked analyst routes while the isolated service on 52197 exposed them. Importing this newer source does not update either running service, and their current deployment was not rechecked here.

Remaining acceptance work includes obtaining the missing original tests, configuring and verifying the Intel runtime, deploying and checking the explicit dashboard review/analysis contract end to end, implementing and validating mission/skill execution, and recording actual physical and model evidence. Saved historical reports describe their own runs; no new hardware, model, training, or deployment success is claimed by this handoff.

## Analyst documentation update — November 15, 2026

The [dated Intel analyst report](source/common/verification/intel-reliability-20261114/README.md) and [saved-report walkthrough](source/common/verification/intel-reliability-20261114/DEMO.md) now preserve the producing team's v12 results with explicit Intel-host scope, omitted evidence references and later receiver-stop context. These are annotated historical documents. Their original received hashes, previous package baseline, adopted hashes and exact adaptation scope are recorded in [the documentation review record](verification/source-sync-20261115/analyst-documents.json).

This documentation update does not adopt the pending v12 backend/UI, transfer saved runtime databases, start a service or authorize a new provider call. The original inventory counts and offline verification above describe their dated source snapshots and runs; the current file inventory is the package manifest. The separate audit-portability update and its evidence remain intact. Original source hashes are retained even where document wording has been deliberately annotated.

## CLI shutdown update — November 15, 2026

The records API CLI now limits Uvicorn connection/task draining to ten seconds when an event stream remains open. The exact received change and original regression are included, together with the [dated Intel report](source/common/HachingJunction/station/verification/shutdown-20261115/README.md). The separate [Mac verification record](verification/cli-shutdown-20261115/result.json) reproduces the previous 15-second timeout and records a passing shutdown after 10.231 seconds with the synthetic SQLite ledger unchanged. This test used the committed package API/store; pending dashboard changes were not required.

The ten-second setting is a connection-drain deadline, not a deadline for every shutdown activity. An existing analyst request may incur the separate bounded worker join. The targeted test contains no active provider request. Deployment, main-service recovery and physical acceptance remain separately unverified.

The loopback subprocess regression is deliberately separate from the network-denying offline test suite. To reproduce it in a disposable checkout with the package requirements installed, use a clean environment and temporary output directory, set `PYTHONPATH` to the package's station directory, and run `python -B -m pytest source/common/HachingJunction/station/tests/test_cli_shutdown.py -q -p no:cacheprovider -o junit_family=legacy`. The original test creates its own simulation database and token, holds its own authenticated event stream open and signals only its child process. Recorded exact commands and environment keys are in the Mac verification record.

## Dated runtime evidence archive — November 15, 2026

The [Intel dashboard archive](verification/intel-dashboard-20261115-d5315791/README.md) preserves ten original Intel documents/results plus the exact archive README and [delivery companion](verification/intel-dashboard-20261115-d5315791/SOURCE_DELIVERY.json). It includes the [recovery result](verification/intel-dashboard-20261115-d5315791/source/Junction/reviews/intel-dashboard-20261115T052333Z-d5315791/transition-v4-20261115T065901Z/station-recovery-20261115T070831253122Z/recovery-result.json), [nine-request relay result](verification/intel-dashboard-20261115-d5315791/source/Junction/reviews/intel-dashboard-20261115T052333Z-d5315791/relay-verification-20261115T070901Z-8bce8491/result.json), and [309-test summary](verification/intel-dashboard-20261115-d5315791/source/Junction/reviews/intel-dashboard-20261115T052333Z-d5315791/final-integrated-20261115T065834Z/result.json). The original report hashes match the earlier Intel handoff; the nine relay request identities, paths, queries, response codes, hashes and server timestamps match independently retained Mac relay records.

The recovery report records an unclean stop and restored Intel API at 07:08:31 UTC. The subsequent relay report covers nine requests and eight logical checks at 07:09:01–07:09:22 UTC, with a saved one-pixel simulation image. The 309-pass result records the Intel software suite at 06:58:47–06:59:04 UTC; it was not rerun on the Mac as part of this archive. Original XML/logs, private backup bytes and historical per-request response bodies are excluded, so the archive alone cannot reproduce the full suite or repeat the direct-versus-relay body comparisons. Two original test-source gaps remain open.

These files retain their dated pending Notion, mapping, source and UI statements unchanged. Their archive paths keep them separate from working task guides and application source. Later receipt, publication and task updates are separate evidence; receiving this archive neither changes running services nor establishes physical, camera, provider or UI acceptance. Current package source and its earlier offline/CLI verification remain unchanged.

## Historical runtime audit source archive — November 15, 2026

The [runtime audit archive](verification/intel-dashboard-20261115-d5315791/runtime-audit/README.md) adds 21 exact Intel files, including final recovery guards, the original preparation tests, relay verification and fake-client tests, retained failed-shutdown receipts, and policy-review snapshots. Its [delivery companion](verification/intel-dashboard-20261115-d5315791/runtime-audit/SOURCE_DELIVERY.json) records original paths, hashes, reused dependencies and exclusions. The earlier dated runtime archive supplies the separate successful recovery and nine-request relay results.

This is historical source for inspection. The recovery script can send SIGKILL and restart the pinned Intel API when deliberately invoked; its fixed host paths, PID/start-time pins, private backups and explicit execution gate remain unchanged. Do not run these archived tools, import their tests, alter guards, restart a receiver or use this archive as authority for a service action. No application source or active runtime is changed by adding this archive.

The exact saved summaries record 27 isolated preparation cases and nine fake relay-harness cases. The Mac review checked source, mappings, hashes and those summaries without rerunning incoming tests. All ten reused dependencies and nine metadata pins are available by exact hash. Of 33 historical application source pins, 27 match the mapped package, four occur only in older incomplete transfers and two original tests remain unavailable; the archive does not establish complete application reproduction.

Original XML, logs, diffs, private state and superseded scripts are intentionally excluded. The preserved SOURCE_SYNC.before.md snapshot retains links relative to its original context directory; those historical links do not resolve inside this nested archive. Original pending statements, process identities and instructions remain dated evidence, while the current package manifest and separately verified publication record describe receipt. This addition establishes no fresh test run, deployment, provider call, UI, camera or physical acceptance.

## Passive video review archive — November 15, 2026

The [passive video review archive](verification/intel-dashboard-20261115-d5315791/passive-video-review/README.md) adds 12 exact Intel files containing the original readiness report, package and wheel review results, bridge test summary, and review tools. Its [delivery companion](verification/intel-dashboard-20261115-d5315791/passive-video-review/SOURCE_DELIVERY.json) records original paths, exclusions and 62 exact reused dependencies, including the 60-file Mac media package. Those dependencies were hash-checked in the shared source package; this archive does not copy or adopt the active dashboard/media work.

The saved Intel result records 25 original bridge cases with zero failures, errors or skips at 07:26:50 UTC, using synthetic images, temporary loopback servers and two inert test-owned Python children. The 25 reported case identities match the exact original test source. This Mac archive review checked source and saved results without running those tests, installing wheels or starting media components. The original review runner and wheel-review script execute at module top level; do not import or run archived tools.

Original READINESS.md links to dependency-install.json, bridge-tests.xml and bridge-tests.log remain unchanged, but those artifacts are intentionally excluded and their hashes are listed in the companion. Wheel binaries, the test environment and private connection material are also excluded. The historical publisher and package-fetcher source retains explicit MCP behavior and Intel paths without granting connection or publication authority.

The evidence covers the selected package and isolated Intel tests. It does not reproduce the full Mac dashboard suite or establish an active Intel encoder/MediaMTX/Studio bridge, reachable media transport, multiple viewers, real camera-to-display latency, fresh provider evidence or physical acceptance. Original dated pending statements remain historical; current ownership and runtime decisions require separate evidence.

## Final Intel coordination archive — November 15, 2026

The [final coordination archive](verification/intel-dashboard-20261115-d5315791/final-coordination-20261115T082805Z/README.md) preserves 32 exact files from delivery `dd42f038-052e-4f0f-88fd-4b9162a4b894`, including the full continuation report, source inventories, prior transfer receipts and bounded read/selection audits. Its [original companion](verification/intel-dashboard-20261115-d5315791/final-coordination-20261115T082805Z/SOURCE_DELIVERY.json) records all original hashes, reuse and exclusions. This is a metadata archive with no new application or executable source.

The archived M08 audit predates the final source delivery and correctly describes what its author had observed then. Later completion `cabcb290-299a-4850-931a-f731fecadbda` and final ordinary note `48a0d838-0708-4af0-add6-305941e0215a` establish the subsequent 43-file M08 transfer. This dated correction does not rewrite those historical artifacts or establish physical success. The owner's physical stop and replay hold remain in force.

The producer test, four rejected closing-review originals, separate analyst/proxy original-test gaps and unsupported watcher JSONL remain explicit exceptions. Some reused inputs and historical relative references are outside this archive, so it is not a standalone reproduction. The 33-file integrity audit and older 309-case result are separate saved evidence; this Mac review reran neither those tests nor any incoming tool. Archive receipt and source publication do not imply deployment, provider or camera access, a receiver restart, or completed task acceptance.
