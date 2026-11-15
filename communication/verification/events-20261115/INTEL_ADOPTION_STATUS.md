# Dated Mac deployment and Intel adoption

Checked November 15, 2026, at 05:22 UTC / 06:22 CET. This is a deployment checkpoint, not a standing health guarantee. Later shared MCP handoffs can supersede it.

## Actual Intel reads verified at 05:26 UTC

This later result supersedes the worker-readiness and cross-host-read gaps in the 05:22 checkpoint below. Intel reported its GET-only worker started at 05:22:25 UTC, PID 417036, using the exact frozen worker hash against `intel-main` / main port 8000. Mac verified the shared readiness note and then received **HTTP 200 for schema, station snapshot and session list** through the existing TLS MCP. All three raw response SHA-256 values were independently recomputed and matched. [Exact request identities, timestamps and response hashes](live-intel-result.json).

The returned snapshot has `sourceMode=simulation`, stateVersion 50, no current goal and no available actions. Robot, cameras and all listed model capabilities are unavailable/unverified in that response. This proves the actual cross-host read path; it does not establish a physical cycle or the new dashboard endpoint. Intel reports the separate dashboard/API adoption has started; its main service still returned dashboard404 at its 05:24 UTC check.

The diagnostic harness initially added an unsupported `limit` parameter to the session-list request. The MCP rejected it before enqueueing, after the two successful schema/snapshot reads. Removing that diagnostic-only argument and running just the missing read succeeded. The initial failure is retained; neither the application allowlist nor worker checks were changed.

Intel's optional event receiver still awaits local Codex authentication. Preserve the already running GET-only worker and continue that remaining setup rather than creating another worker. No Station records, provider calls, hardware or tunnel configuration were changed by these reads.

## Verified Mac result

The existing authenticated Mac MCP is running with 17 tools on its preserved endpoint, pairing and TLS identity. Its event receiver has completed one actual isolated Codex review, saved the durable result, acknowledged processing and exported the proposal. That source was explicitly a Mac-created synthetic Intel-routing fixture. It is not evidence of an actual Intel-origin event. The existing five-minute task reviewer consumed that proposal without duplicating a Notion update. Ordinary notes, idle receipts and acknowledgments do not create new work events.

The canonical communication suite passes 181 cases, including four separately owned dashboard allowlist tests. This published snapshot passes 177 communication and seven source-transfer cases. These overlap and are not summed as a project-wide or physical score. The actual TLS relay test used a local synthetic Station; it verified authentication rejection, exact GET/review/analysis bodies and idempotency without contacting Intel or a provider. [Saved verification](README.md) retains the exact source and result identities.

Fifteen focused communication commits were published through `0ca975297c8fa0f7cc949e5f7eb203e9fe6892ea`. Independent verification matched remote `main`, local HEAD, 58 committed file seals and 33 provenance entries at 05:19:51 UTC. Later documentation commits extend that source snapshot. The owner's existing Git author identity is retained. Separate dashboard/backend source changes are not included in that fifteen-commit sequence.

The running Mac processes use managed foreground sessions. Automatic startup after shutdown is not installed. The event runner reviews supplied evidence; it does not merge Git, implement incoming instructions, edit Notion or operate hardware. Its first result cited temporary input filenames; the durable input/result, canonical note UUID and hashes retained in the verification record are the lasting references.

## Intel result reported through the shared MCP

Bootstrap request `b71f04ec-67da-47c2-9bd8-7d0df7a46ad3` refers to a frozen, hash-checked guide and client manifest on the canonical Mac MCP. The user started an active Intel Codex session. Intel reports exact download verification, an isolated client runtime, Python 3.12.16 and Codex 0.169.0 supporting the required flags.

Intel's checkpoint `bd9c433e-47ea-4612-a1c9-b53187cc9899`, received at 05:16:42.643331 UTC, reports **Not logged in** in both normal and restricted Codex environments. It explicitly says the event receiver has not started. At the independent 05:19:26 UTC readback, the GET-only Station worker was still being prepared; no actual readiness/PID result was available. Bootstrap event `fed22d93-d7ad-511a-aeac-4206410d1bd3` remained queued with zero attempts. The account must be authenticated locally before the optional Intel reviewer can run. A successful file transfer or supported CLI flags do not establish authentication.

Once Intel confirms worker readiness, Mac must make fresh bounded schema, station-snapshot and session requests and verify exact response hashes. The worker remains GET-only during bootstrap. Keep one worker for `intel-main`, preserve private pairing/state and the existing application, and do not replace the authoritative API with an older Mac snapshot.

The separately prepared dashboard API/data-producer request `d5315791-6749-4b01-97b5-1b9357306487` is the next Intel stage after bootstrap. Coordinate its changes with the running worker and avoid competing Station restarts. Jose's NVIDIA tunnel belongs to the other team.

## Task status

M20 and M21 remain In progress with seven and eight open criteria, respectively. Their new publication checkpoints and evidence properties were saved and read back at 05:22:10 UTC, preserving prior history and all dependencies. Real cross-host operation, useful hosted analysis, controller/voice failures and physical outcomes are separate remaining acceptance work. No model/provider call, training, robot movement or tunnel change occurred in this Mac communication verification.
