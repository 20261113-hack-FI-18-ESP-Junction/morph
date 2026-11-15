# Remaining three-host source handoff

Prepared November 15, 2026. Jose's original 25-commit handoff was published first. The canonical Mac workspace was then preserved in a private verified archive before the additional source reconciliation. The archive includes both project roots, five consistent SQLite backups and a restorable bundle of all 25 original commits. Private archive contents and runtime data are not part of this repository.

## Received source

Intel request `90672035-350b-43ad-88d6-025885cfbd65` covers a 240-file inventory. Mac verified 110 transferred files across eleven groups (1,965,184 source bytes), 124 declared exact reuses and an additional exact 83,993-byte CSV reuse. The reviewed supplement adds two exact artifacts, bringing the result to **237 original files** plus three separately labeled redacted test review copies.

All seventeen earlier Intel contract files and all forty-two dashboard public assets were exact baseline reuses. Source roots, original hashes and intentional packaging changes are recorded in each package's provenance. The older Intel context server remains a comparison reference; the current Mac relay and worker are preserved.

| Package | Ownership and source |
| --- | --- |
| [klemen-dashboard](klemen-dashboard/README.md) | Current history/review/replay and Gemma UI, shared client, offline analytics, portable dependency paths and server-side MCP adapter |
| [intel-runtime](intel-runtime/README.md) | Current records/analyst backend, setup, diagnostics, synchronization and explicitly labeled reproduction source |
| [communication](communication/README.md) | Current Mac context server/worker, restricted review/analysis relay extension and unchanged reviewed source-transfer helpers |
| [source-review](source-review/README.md) | Three complete redacted test copies, original/redacted hashes and supplemental artifact receipts |

The packages preserve functional source, historical evidence and reproduction scripts distinctly. Some historical scripts reference tools, original working directories or provider environments which are intentionally not bundled. Follow package launchers and documented offline checks.

## Verified behavior

The dashboard/shared client/analytics suite passes **174 tests**. Its full isolated TLS bridge check completes seven station requests exactly once, preserving two selected sessions, review HTTP 200, analysis HTTP 202, structured HTTP 409 errors, CSV and event bytes, and a 91,040-byte JSON response over three base64 pages. A missing worker produces explicit failure/unknown-mutation status.

The Intel package passes **158 test methods plus five subtests**, 42 Python parses and nine shell syntax checks. A guarded launcher initialization creates an empty temporary database and owner-only token. Guards report no attempted provider, robot or unapproved process operation.

Communication passes **63 context/relay/worker tests plus seven source-transfer receiver tests**. Checks include authenticated MCP, legacy GET workers, exact JSON request bytes, repeated session query values, restricted write intent, stable IDs, migrations, expiry, response hashes and no automatic POST retry.

These are isolated software tests using temporary data, fake transports and synthetic fixtures. Package guides link the actual logs, result files and source manifests. The three excluded original tests are not counted as passing. Historical Intel tests and provider results retain their original dates and scope.

## Adoption and remaining work

Deploying these files is a separate step. This publication does not restart the live Mac MCP or an Intel service. The worker defaults to reads; enabling `--allow-record-writes` permits only an explicit audited record review or evidence-analysis request. Analysis can reach the already configured Intel provider. The relay excludes commands, mission lifecycle and voice credentials.

Intel's service report remains a **November 15, 2026, 02:25:35 UTC** observation: current source and the isolated 52197 service have analyst routes, while the main loaded 8000 API lacks them. Verify the actual target before adoption.

Received Intel code still lacks an integrated mission lifecycle, dispatcher, learned-skill registry and Studio execution adapter. Jose and Intel must agree and implement that interface. The NVIDIA tunnel belongs to the other team. Voice is expected on Jose's Mac and ElevenLabs remains optional.

The original three test files remain pending; the review copies provide visibility into their behavior without claiming full original test reconstruction. Real cross-host deployment, voice/provider behavior, calibrated physical execution, training and full-cycle acceptance remain open. M20 and M24 remain In progress.
