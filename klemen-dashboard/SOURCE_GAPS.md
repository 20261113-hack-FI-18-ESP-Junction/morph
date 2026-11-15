# Source receipt and remaining integration

The current Intel M16 history/review/replay, Gemma analyst frontend and shared client have been received and reconciled into this new publication package. This supersedes the earlier package's pending-source statement. The earlier handoff and archive remain unchanged.

Request `90672035-350b-43ad-88d6-025885cfbd65` produced 110 files in 11 transfer groups. Intel's final note `2e753690-9953-4eaa-9bd0-6f9897c1db44` is dated **2026-11-15T03:27:48.552178Z**. Exact reuse hashes and transferred bytes formed the isolated candidate; the later exact CSV receipt brought it to 235 files. A further reviewed supplement supplied the exact station ignore file and tiny synthetic PNG for the Intel partition, bringing overall exact-original coverage to 237 of 240 inventory files. The three original test files described below remain absent; redacted review copies are tracked separately at the publication root and are not executable-suite replacements. Package provenance distinguishes received/reused source from Mac transport and portability adaptations. It does not assume that a running Intel process loaded the received source.

## Source boundaries

The exact current Intel `morph-station/server/stationProxy.test.ts` was rejected by the sender's secret scanner and is absent from this package. The included `stationProxy.mac-baseline.test.ts` is the older Mac suite, explicitly named as such. New MCP integration regressions cover the two-session query, exact POST bytes/intent/IDs, error status propagation, unknown outcomes and denied routes. These checks do not reconstruct the missing original test.

The exact current `HachingJunction/station/tests/test_analysis.py` was also rejected and is outside this frontend package. Its reported remote results are not a local rerun. The provider-check test had a similar transfer gap and belongs to the service/setup partition. Any separately supplied redacted test is review material, not hash-identical original source or a substitute for its verification claim.

The complete current synthetic CSV dependency is included with JSON/event/snapshot fixtures. Large raw camera/evidence files and private/runtime data are excluded. The 42 existing public design assets were reused by matching hash; they are design material, not camera or physical evidence.

## Runtime work still required

The updated communication package and worker must be deployed together before the new POST paths can be used. Reads remain compatible with the earlier read worker. The upgraded worker defaults to reads and requires the explicit `--allow-record-writes` option for the audited review and analysis routes. Run the worker against the intended Intel records API and validate the selected station ID and existing private TLS pairing. This packaging work does not restart those services.

The dated Intel runtime observation found that main port 8000 lacked analyst routes while isolated port 52197 exposed them. Source receipt and local simulation do not resolve this deployment difference. Verify the chosen current service and then exercise real dashboard reads, review conflict/retry and saved analysis behavior with appropriate authorization and evidence.

The relay limits complete responses to 4 MiB. Larger saved images and exports need a separate bounded file-transfer mechanism; no truncation or synthetic replacement is used.

Intel reported no implemented mission dispatcher, learned-skill registry or complete physical training/execution source for this handoff. Current command/voice APIs remain unavailable stubs. Jose's NVIDIA tunnel is owned by the other team. Network connectivity does not establish a mission contract, calibration, action validation or physical confirmation.

Voice is expected on Jose's Mac and ElevenLabs remains undecided. OpenClaw/Argon/world-model labels describe intended components, not verified implementations. This package makes no new provider or hardware claims. See [VERIFICATION.md](VERIFICATION.md) for the local checks and their limits.
