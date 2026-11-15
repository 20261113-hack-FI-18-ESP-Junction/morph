# Intel manual source ZIP prompt — November 15, 2026

Copy this complete document into the Intel Codex session. Prepare the ZIP on Intel; the project owner will attach it manually to the Mac conversation. This is a packaging request, not a script to run on the Mac.

## Owner request and boundaries

Prepare one bounded, reviewable ZIP containing the nine exact missing originals below and the complete source/dependency picture for the three incomplete delivery groups, plus the separate station-guide mapping exception below. The owner now explicitly authorizes this **separately reviewed manual ZIP attachment**. The previous response to request `cb294a07-e4bb-4381-89a5-9a29d9ddec36` correctly stated that no alternate transport was then authorized; this new request changes only the transport permission for this bounded scope.

Use local inspection and packaging only. Read applicable instructions and inspect source as data. Do not import or execute application, provider, robot, camera, worker, replay, historical inspection or verification scripts. Do not run application tests, install dependencies, start/restart/stop services, signal processes, change worker flags, enable receivers, configure tunnels, deploy, commit or push. The Mac servers, including Mac MCP, are intentionally stopped for this manual handoff. MCP/network availability is not required; do not try to reconnect or restart them. Preserve the M08 STOP, pre-I/O replay hold, revoked automatic Intel receiver and current runtime boundaries.

Do not send messages, call MCP, publish notes/events, upload the ZIP or use network transport. Return the local ZIP path to the human. Do not modify the sender/collector, weaken screening, encode source into MCP notes, rename files to evade screening or substitute redacted files for exact originals. This request allows reviewed safe original bytes in a manual ZIP; it does not authorize disclosure of credentials.

After the static semantic review below, you may create and run a small packaging-only helper using the Python standard library. Review the helper before running it. Its allowed operations are bounded reads, hashing, validation, writes to a new private staging directory, and ZIP creation/readback. It must not import project modules, execute selected files, invoke incoming scripts, contact services or modify originals.

## Evidence and roots

Intel's latest observation, `2026-11-15T09:29:00.090849+00:00`, is recorded in note `aee44be4-a19f-41ee-9676-f4b8a5db9f3b`. It confirms all nine originals were present at the exact sizes/hashes below. Recheck locally at packaging time.

Root aliases used below:

- **J** = `/home/intel/Documents/Junction`
- **C** = `/home/intel/Documents/Junction/morph-intel-continuation-20261114T193410Z/Morph-Intel-Handoff-20261114T191514Z`

An exact `sourceOrigin` is its root plus the listed relative path. Search only the identified project roots and relevant preserved snapshots/outboxes. Do not archive `/home/intel`, the whole Junction tree or unrelated projects.

## Nine required exact originals

Include all nine as full original files. Rows 1–6 repair current delivery gaps; rows 7–9 restore historical provenance. Keep these roles distinct.

| # | Revision | Root | Exact relative source path | Bytes | Expected SHA-256 |
| --- | --- | --- | --- | ---: | --- |
| 1 | current | C | `HachingJunction/station/tests/test_analysis.py` | 59218 | `3bb5a23a91f8a89a00f220c126f18396fd100278b380adab6cd490ddd333d671` |
| 2 | current | J | `reviews/intel-dashboard-20261115T052333Z-d5315791/closing-shared-review-20261115T075045Z/closing-review-result.json` | 32123 | `7f5a32176ba0870dd06650438134c8503326f041d46df69fcec5e4257f32bbcb` |
| 3 | current | J | `reviews/intel-dashboard-20261115T052333Z-d5315791/closing-shared-review-20261115T075045Z/verify_closing_review.py` | 12694 | `4ca8ee9b247dae16042bf198a3e96383c4d1b244f9f8a1dccc3416f661ff0730` |
| 4 | current | J | `reviews/station-write-optin-review-20261115T075433Z-2e12edef/inspect_worker_request_v1.py` | 14992 | `53102fe6cd4e287c12173bf262fd6e6935704567e839415e8e3db981ca444ab3` |
| 5 | current | J | `reviews/station-write-optin-review-20261115T075433Z-2e12edef/inspection-20261115T080519285661Z.json` | 4089 | `1d35f9a42291ff5a553e311a38ca66f06bafbaac90720042915773aab003c9ab` |
| 6 | current | C | `HachingJunction/station/tests/test_producers.py` | 19772 | `60d804e02c367a4bd151c2e4c62383328f9f9efcad079595c774b34ac58b81e9` |
| 7 | historical | C | `morph-station/server/stationProxy.test.ts` | 17218 | `552e8def4cf1f08330a2702d67e1152dd91105a6b3f578f4cbc7da2908ec7d49` |
| 8 | historical | C | `HachingJunction/setup/provider-check/test_check.py` | 11561 | `ef2e01a85bec0f9d4950aabe475a0e6cc4c0dae6746a8b5d8e73cfb6a1c741c5` |
| 9 | historical | C | `verification/intel-reliability-20261114/audit-language-v12-20261115/before/tests/test_analysis.py` | 52823 | `e35d81c31bff372cc65fa10ab1c900e5174698cd67e025be73d7fa14af39e699` |

**Historical row 9 uses the preserved `verification/intel-reliability-20261114/audit-language-v12-20261115/before/tests/test_analysis.py` snapshot under C.** Its original logical application path was `HachingJunction/station/tests/test_analysis.py`; record that separately. Do not read the old hash from the current application path, reconstruct older bytes, replace the current file or overwrite either revision. Preserve the snapshot subdirectories so both `test_analysis.py` files retain their original basenames without collision.

If an expected original changed or disappeared after the observation, locate the real immutable snapshot when available. Include any needed current revision separately with its actual origin, timestamp, hash and explicit revision relationship. Never fabricate bytes to match an expected hash. A missing, unsafe or unverified required original remains an explicit gap and makes the affected manual group incomplete.

## Preserve the three original delivery companions

Locate the frozen local outboxes using these IDs. Include each **unchanged original** `SOURCE_DELIVERY.json` under `original-deliveries/<old-delivery-id>/SOURCE_DELIVERY.json` and its original transport manifest if safely available. Verify the companion hash. Preserve historic flags, exclusions, mappings, test claims, timestamps and IDs.

| Group | Old delivery ID | Old request ID | Old transfer ID |
| --- | --- | --- | --- |
| Analyst backend | `3764e3c7-2536-53c5-b75d-5a2dc1d560c5` | `028a574e-76f4-4874-928f-b7f20bb02aa9` | `cc9db1a6-6ca8-59d8-a9ae-d08f3d96059b` |
| Closing review/source supplement | `97c7ec3e-dd59-47e6-a450-014bad41151a` | `d5315791-6749-4b01-97b5-1b9357306487` | `f0cff213-9da1-40df-8615-44d6d91aff53` |
| Producer ingestion | `831bcaf3-d30f-45cf-a30e-03b8d810d32b` | `d5315791-6749-4b01-97b5-1b9357306487` | `803091e9-4b14-442e-b996-513e0f772405` |

| Group | Original manifest note ID | Original bundle SHA-256 | Original companion SHA-256 |
| --- | --- | --- | --- |
| Analyst | `a53acbc5-68d9-5323-8618-b283bc605b87` | `484e93bff1d74483dc195def01b29d305cdfc17d691b89e398a9ce92bf03343e` | `0075cb37030bad039d551a9949ddcbf4b50f323ad667765c0d23c6fdb05a9016` |
| Closing | `6acb0d83-d83c-5df3-b870-4d0b08a3d137` | `d1c59cc9f1963b18af8d912c97cc211df97a74393188ad5c3922e86a2db2b75d` | `18e8b5ee1246dd064007dcb12dc67c968f1b7d815bf64f162788e5521811af7a` |
| Producer | `f5ed8867-ef91-5f23-a383-1f972af4fdff` | `9abdac36074ba1c33b5ef1e991d20ed7d2c73d95f22fc809981d74fb624a99e5` | `d309a2848ca1a1ca8039ac82a648dee1eeb8e94111ac23a7d1dbfea346a07de0` |

Mac validated the available transport payloads: analyst 5 files / 245,816 source bytes, closing 75 files / 887,118 source bytes, producer 3 files / 45,315 source bytes. These counts include companions/supporting files and **do not establish complete groups**. Row 1 is missing from analyst, rows 2–5 from closing and row 6 from producer. Historical rows 7–9 are additional gaps from source request `90672035-350b-43ad-88d6-025885cfbd65`. Prior redacted review copies from `a8046978-b5fa-4e1b-9363-d18ee24c5a45` remain separate evidence.

Generate one new UUID once for this immutable manual delivery. Give each repaired group, the historical-original set and the separate station-guide mapping exception a distinct subgroup entry. Reference old requests/deliveries/transfers explicitly. Changed frozen contents require a new UUID and `supersedes` reference. Do not reuse reserved completion note IDs or mark old MCP transfers complete. Mac receipt, reconciliation, publication and physical acceptance remain separate later steps.

## Full source and dependency closure

Prefer a self-contained bounded package: include complete reviewed current source, tests, synthetic fixtures, documentation and dependency declarations for analyst/producer, and the full frozen closing supplement with its four missing originals. Exact files already received on Mac may instead be reused only under the proof rule below. One exact payload may serve multiple subgroups if every use is recorded.

The following **24 distinct paths** are the combined source/dependency identities declared by the analyst and producer companions. Paths are relative to **C/`HachingJunction/station/`**. Recheck them; these expected prior identities are not proof of current bytes or an exhaustive dependency list.

| Relative path | Declared use | Bytes | Expected SHA-256 |
| --- | --- | ---: | --- |
| `ANALYST.md` | analyst source | 20629 | `56e6f21bbe9337e7fcc614e061f4df1a920c1dcd6155baf5194ba6e94fd25639` |
| `PRODUCERS.md` | producer source | 12668 | `ad5a05fa93ddc2479a3dde13146e02a365082197a2d9395b798d8c06bfd830a5` |
| `morph_station/__init__.py` | producer dependency | 114 | `84252541a785fd57f879d4878d54bd8af19b803849d1ad438b60ed1738235399` |
| `morph_station/analysis.py` | analyst dependency | 21179 | `5621f3f6d2d89cd6cdab0fc61335ed7da4df51182291cdac87a042edb684039f` |
| `morph_station/analysis_context.py` | analyst dependency | 26188 | `252c97af88de0574816a1d46384129005b3027edf69fda9f3930defb401030de` |
| `morph_station/analysis_models.py` | analyst source | 3130 | `ffc49b64165072a052b74abc35c2166cb69d1443cefd07fe54bb9640d8c12917` |
| `morph_station/analysis_provider.py` | analyst source | 34639 | `1fa8de0146bdf7d85a8c5260e343f21b9542b0e372dd987e0709c9a78938198d` |
| `morph_station/api.py` | producer dependency | 23313 | `3ab02fc234add63fc1150db6c107324dafe68266cfdaad453c554e7753e7845a` |
| `morph_station/client.py` | producer dependency | 1645 | `19f090c9598c1c91ea02813cc301e3c2857b799f938ca97ed41a7f5975314e91` |
| `morph_station/models.py` | analyst dependency, producer dependency | 11096 | `19a63e3603a2045763aec4dfc5b4afe408cc9117b8dc1554e759411ad15ac7a3` |
| `morph_station/producers.py` | producer source | 19409 | `de9dcdb39c539e2f9ec298b29d72c85cc26580bda4be811aba3984ccdb2a94ec` |
| `morph_station/schema.sql` | producer dependency | 1589 | `ac53e1043d59879a2b65dd1092523d181165719fba51ff2141bbd516d4772c45` |
| `morph_station/simulation.py` | producer dependency | 6481 | `67282e62ad0bcad4611e14fc7189081bdb428399c10891f8a4b3c2318003c2cf` |
| `morph_station/store.py` | analyst dependency, producer dependency | 48605 | `d099d4b67269df66be6b09a24941ac71044f3de20e6d151dcded2f3e3bc59939` |
| `pytest.ini` | analyst dependency, producer dependency | 42 | `6c6ccf864e8f2d2e0223ee8e39bfde660c12435aa37d81e2b14000a6bee15003` |
| `requirements.txt` | analyst dependency, producer dependency | 238 | `0a491f0674b2dd255f09385a5f36386212e26621770092b4c1ebaaf2edfca00b` |
| `tests/fixtures/gemma-v11-audit-regressions.json` | analyst source | 162010 | `ed74d1d62360c2712630fcbdba9d09b3d51395150e9ea3ed790560e3f7fdb348` |
| `tests/fixtures/gemma-v5-semantic-regressions.json` | analyst dependency | 388646 | `ca018563e387990520907b74210c5a725a2bfcf5c7ea51d614e91b388b96dc1b` |
| `tests/fixtures/gemma-v6-known-coverage-regression.json` | analyst dependency | 40764 | `1c0a7ac8c5e5741a07b132e172ce0e41b8230864dddcbcf85c650e78c2b3c9b4` |
| `tests/fixtures/gemma-v7-recovery-coverage-regression.json` | analyst dependency | 72322 | `2affb6a8b115dd4e54c6af2fcbcee3cab6a8ce2cde9e627f746f555359266476` |
| `tests/fixtures/gemma-v9-citation-regressions.json` | analyst dependency | 245533 | `99c28d8643a2182a25b4126da9b23f3b0158136c31e979e49be6be657c29bab3` |
| `tests/test_analysis.py` | analyst source | 59218 | `3bb5a23a91f8a89a00f220c126f18396fd100278b380adab6cd490ddd333d671` |
| `tests/test_dashboard.py` | producer dependency | 12063 | `574cb9b804f2e007c0fd01093f25c1d4d1b9b8b474dc0de6bec1ece50175dddd` |
| `tests/test_producers.py` | producer source | 19772 | `60d804e02c367a4bd151c2e4c62383328f9f9efcad079595c774b34ac58b81e9` |

Inspect imports and fixture references statically. Complete the transitive local closure: modules, test helpers, `conftest.py` if used, schemas, configuration, requirements/lockfiles and synthetic fixtures. In particular, `tests/test_analysis.py` uses helpers from `tests/test_reviews.py` and `tests/test_store.py`; include or prove exact reuse of those full files and their dependencies. Check `api.py` imports and every referenced analyst regression fixture. Preserve relevant `pytest.ini`, dependency files and placeholder-only examples even when the old sender did not support an extension or hidden filename. Do not install dependencies or execute tests now.

For each historical original, include or identify the matching historical implementation/test harness, dependency declarations and fixture revisions needed to understand it. Record historical closure as complete, reused or unavailable. Do not claim an old test runs against current implementation just because its filename still exists; do not copy unrelated application trees to hide a gap.

For closing, inventory every original `files` entry and retain the meaning of `reusedPriorGroups`, `reusedSharedInputs`, `reusedPolicy` and `reusedCodeDependencies` in the new closure record. Preserve `source-pins.json`, document provenance/freeze/readback ledgers, review helpers, original result documents and safe source inputs. Its prior groups are:

- Dashboard mapping `44693c32-12a5-4426-9603-72d4e55736ab`, corrected by `77133e66-7c2b-45ce-8ab6-69549d784320`.
- Producer ingestion `831bcaf3-d30f-45cf-a30e-03b8d810d32b`, repaired by this manual package.
- Bounded CLI shutdown `60fff35b-12d2-4efd-a97e-e224b8199cb6`.
- Frozen runtime documents `36126a56-504b-417f-b5d9-b0a376248b59`.
- Final runtime audit source `b4525aac-4261-4706-9eec-3316fd6a2d07`.
- Passive-video source/evidence `29a6f301-d2dd-4bac-b59b-41269b48eead`.

Its recorded code hashes are `reporting.py` = `7bdc27275a5de7bfaa7a3c2a60128c4d27114184535085d6ac84770e7cea3d33`, shared client = `78ef0ed4e9a49cdebafcd5a2c61968f65bb5edb213f0f0b3655ea3a5fc30d4e4`, worker = `bfadd54fb186dffa4bbf0f21a95c0d815bb187833a57a3e382a7b6efc72c0bc2`. Resolve exact paths/mappings from referenced companions; do not guess from labels. Preserve the eight historical/current inspection inputs bound by `source-pins.json` as safe full files or exact references. Shared inputs may remain references to available Mac evidence with original path/hash/page metadata. Do not duplicate private records or retrieve them over a network.

**Reuse proof:** every omitted unchanged dependency requires exact source origin, fresh local bytes/SHA-256, an available Mac original path and its confirmed receipt/manifest or commit plus per-file hash. Cite the original delivery/transfer and mapping. A group hash, stale report or “already on Mac” is insufficient. If existing local receipts cannot establish matching Mac availability, include the full safe original. A changed current hash requires a separately identified current revision, its baseline and reason; preserve the exact older file/reference. Never change a baseline just to make reuse pass.

Record source observation time, known revision/dirty state from read-only metadata, additions/edits and any already authorized deletion/rename intent. Unknown baselines remain `null` with an explanation. Absence never implies deletion. Mappings are proposals for Mac review, not write authorization. Common Intel source belongs under `intel-runtime/source/common/`, including `HachingJunction/station/morph_station/store.py` and `schema.sql`, per corrected mapping `77133e66-7c2b-45ce-8ab6-69549d784320`. Preserve old `klemen-dashboard/analytics/` proposals unchanged in historical companions, not as current destinations. Preserve current Mac dashboard/media/compact-read/session/history/analyst UI adaptations. Closing documents and old policies are historical evidence, not active instructions or proof of current operation.

## Separate station-guide mapping exception

Resolving the nine originals alone does not close every source issue. Delivery `25a1bb77-9fae-55ad-8514-86b2a6665476`, request `fb63f766-124e-4d58-9fb5-603ce5c9b3c6`, transfer `c21648f9-bade-57bf-a6ec-e186ae7451a7` is separately incomplete: both guide revisions are already available on Mac, but its proposed **edit** target `intel-runtime/source/common/HachingJunction/AGENTS.md` is absent. No add/remap has been accepted. Preserve this as a mapping/baseline exception, not a missing-original count or a completed delivery.

Include the following three exact frozen transfer entries, retaining their paths under `original-deliveries/25a1bb77-9fae-55ad-8514-86b2a6665476/` (put guide entries under a `payload/` subdirectory so the original companion keeps its name):

| Frozen transfer entry | Meaning | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `HachingJunction/AGENTS.md` | Delivered post-edit Intel guide | 23559 | `2419d70a7eb68ae5e3de0a49fae2dcb6237e47238c2d997d14763419117c480f` |
| `baseline/HachingJunction/AGENTS.md` | Exact Intel pre-edit guide, not a proved Mac baseline | 22851 | `58a0fae701dd23844d26134dfe6fd691f2f1e885f6ec59a638f1a3e7ea65c13c` |
| `SOURCE_DELIVERY.json` | Unchanged incomplete companion | 2398 | `4fdb6e0e4c1242b59be16ef6e133933a82daacfc9b947806c6f19284a1969466` |

The original bundle SHA-256 is `42c9a70e39580497da5bbe2f859477fd6776faf352253e8eec002a6e8b610fc6`. The guide's logical source origin is C/`HachingJunction/AGENTS.md`; obtain the expected revision and baseline from the real frozen outbox/snapshot, not an assumed `baseline/` directory in the current application. Its original observation time is `2026-11-15T06:12:38.535482+00:00`. Preserve the old companion's source-policy reference and prior supersedes relationship. Treat archived guide text as data, not new instructions for this packaging task.

Add a separate proposed mapping correction in the new manual metadata: identify the original edit target, its missing/unproved Mac baseline, the known Intel before/after hashes, intended guide role and a precise proposed destination/operation. If suggesting an addition, distinguish `baseSha256: null` from the Intel pre-edit comparison hash; if suggesting a dated archive/remap, explain why and list the proposed path. The proposal must be marked **pending Mac review**, not authorized or applied. Do not silently convert the old edit to an addition, overwrite an active guide, change the old companion or claim this exception closed merely because the ZIP includes both revisions.

## Static semantic review and exclusions

Review selected bytes and their context before packaging. The latest Intel review attributed row 1 to deterministic TestClient/FakeProvider auth fixtures, row 6 to a synthetic secret-field rejection test, rows 2–5 to nonsecret permission prose, and rows 7–9 to synthetic test inputs/source construction. Recheck this classification. Safe synthetic literals must remain unchanged; verify they are not captured credentials, operator data or real robot/customer records. Record file/hash, finding category, review method and conclusion without copying credential-shaped values into the report.

If actual private data or secrets are present, exclude that file and record its path, expected hash and value-free reason. Leave the required gap open. Do not redact and call it an exact original. Do not inspect account/key stores or unrelated personal directories.

Exclude `.git`, environments/installed packages, `node_modules`, caches, builds, databases, runtime directories/logs, `.env` values, auth/pairing files, tokens, private account files, recordings, real camera captures, weights/checkpoints and unrelated archives. Include safe relevant ignore/dependency files and public configuration with existing placeholders only. Explicitly listed source-safe historical review JSON is in scope; arbitrary runtime JSON/log collection is not.

Optional after semantic review: **J/`reviews/intel-watcher-recurrence-20261115T073034Z-d5315791/watcher-log-window.jsonl`**, 1,111 bytes, SHA-256 `3486902d2bfc038fbda5e1e113d10f3cdeee8effd43cf95af4448e254092e4db`. Its original `.jsonl` name is allowed in this manual archive. It remains optional historical evidence, not an application dependency; omission is not one of the nine required gaps.

If safely available, include these existing provenance records from J/`reviews/mac-closeout-request-20261115T092402Z/`:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `originals-verification.json` | 16436 | `afb1767e5c117091231bfe353b958557152923a8c52a1694c62fb83fa8d42dd6` |
| `historical-original-locations.json` | 9593 | `08e0721e9ce7615fc9a997bf8187d0845f8bb2d2f8e840781a96410c4541b436` |
| `four-closing-originals-screening-review.json` | 9253 | `12d00d1ea6358e5f391151d60e43ffa89b753ba4f00667bb4a9579de6eaec7c8` |

These support provenance. Save fresh review findings separately; never edit the old reports.

## ZIP layout and manifest

Create a new private staging directory outside application source with restrictive permissions. Preserve originals, frozen outboxes, existing manifests and earlier ZIPs. Use one root such as `morph-intel-manual-source-20261115-<new-delivery-uuid>/` containing:

- `source/common/<exact path relative to C>` and `source/junction/<exact path relative to J>`. Preserve original basenames/subdirectories. Use one canonical payload location for overlapping roots and record aliases. Multiple real revisions need separate labeled snapshot roots with the complete original relative path below each.
- `original-deliveries/<old-delivery-id>/SOURCE_DELIVERY.json` and available original transport manifests, byte-for-byte unchanged.
- New `SOURCE_DELIVERY.json`: schema/version, new UUID, `transport: "manual-human-zip"`, owner request/date, source host/root aliases, UTC observation/freeze times, old identities, scope, per-group completeness, revision/baseline and remaining gaps. This new repair record does not alter old manifests.
- `CLOSURE.json`: included dependencies/reuse proofs, companion references, static import/fixture review, unavailable dependencies and required-original counts. Distinguish source closure from standalone runnable status.
- `EXCLUSIONS.json`: scope exclusions and every missing/unsafe/unverified required path with a value-free reason. An empty required-gap list requires successful verification.
- `REVIEW.md`: static semantic review, synthetic-fixture findings, consistent snapshot checks, limitations and evidence class. Any cited old test results retain their original dates/labels. Explicitly state that no application tests, provider calls or physical verification were performed for packaging.
- `README.md`: layout, roots, current/historical roles, reuse requirements and Mac review boundary. All new prose must be English.
- `MANIFEST.json`: each other included regular file except `SHA256SUMS`, with archive-relative path, exact source origin or generated-metadata origin, bytes, SHA-256, original mode, group membership, current/historical role, baseline hash where known, and mapping/disposition. It excludes itself to avoid a circular hash. Label generated metadata as generated, never original source.
- `SHA256SUMS`: covers all other regular files including `MANIFEST.json`, excluding itself.

Validate the complete allowlist before copying. Reject symlinks and symlink components, device files, traversal/absolute member paths, duplicate members, case/Unicode-normalization collisions and paths outside the selected roots. Do not follow links. Preserve original source encoding/newlines and bytes. Record original modes without making review scripts executable as a packaging step.

Check selected originals are stable across source reads and freeze. If anything changes, leave originals untouched and prepare a new consistent snapshot/identity rather than mixing revisions. Never overwrite or delete original source or earlier archives to fix a conflict. Keep the ZIP and staging private until human attachment.

## Packaging checks and final response

After semantic review, build the ZIP from the explicit allowlist. Reopen it locally as archive data without executing/importing anything. Check member safety, CRC, uncompressed sizes, exact payload hashes, manifest coverage and all nine expected identities. Confirm no extra private/runtime files slipped in. Verify closure or list exact remaining gaps. Compute the final ZIP byte count and SHA-256 outside the archive; do not create a self-referential hash inside the frozen ZIP. Freeze the ZIP and new delivery UUID together.

Save the final packaging handoff locally beside the ZIP, including its final hash and verification summary. Return the absolute local ZIP path, filename, byte count, SHA-256, new manual delivery UUID and local handoff path. Report `N / 9` required originals, completeness of each repaired group, historical closure, the station-guide mapping exception, included/reused counts and exact remaining gaps. State whether optional watcher evidence is included.

Describe it as a prepared, statically reviewed source archive for the owner to attach manually. Do not claim Mac receipt, reconciliation, publication, deployment or physical verification. Do not publish a completion event or upload anything. The owner will attach the ZIP for independent Mac hash verification and review before application/repository changes.
