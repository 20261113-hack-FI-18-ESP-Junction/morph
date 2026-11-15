# Run and finish the Morph system

Current integration checkpoint: November 15, 2026, Europe/Ljubljana (UTC+01:00). Klemen owns this dashboard and the Intel records/video integration. Jose owns chat, voice, coordination and the external NVIDIA tunnel. The owner confirmed that Jose's connection is not complete. This guide covers the work that can proceed independently.

## Two explicit ways to run the dashboard

Run the commands from `klemen-dashboard/dashboard/`. The launchers reuse installed dependencies; they do not install packages, open a camera, call a model or start robot motion. Python 3.12, the dashboard Node dependencies and the built sibling `station-client` must be available. The synthetic video demonstration additionally needs FFmpeg with `libx264`, the bridge requirements and MediaMTX. The workspace's prepared runtimes are discovered when present; use the launcher's `--help` for explicit executable paths on another machine.

### Complete local demonstration

```bash
npm run demo:all
```

Open `http://127.0.0.1:3101/` and select **Simulation**. One supervisor owns the temporary Station API, dashboard, synthetic video bridge and MediaMTX. It prints the dashboard address after its startup checks. It creates new private temporary configuration and records; it does not reuse a production database. The video is labeled synthetic and the records remain simulation evidence.

An occupied port is an error; the launcher does not replace another application. Select another port when needed:

```bash
npm run demo:all -- --port 3102
```

Use **Ctrl+C** in its terminal to stop its owned processes and remove its disposable runtime. [Detailed local-demo behavior](klemen-dashboard/LOCAL_DEMO.md) and the [media contract](klemen-dashboard/LIVE_VIDEO.md) describe the independent records and video paths.

### Actual Intel records through the existing Mac MCP

```bash
python3 ../tools/run_station.py station \
  --pairing-dir /ABSOLUTE/PRIVATE/intel-pairing \
  --station-id intel-main \
  --port 3000
```

Open `http://127.0.0.1:3000/`. Use the existing owner-provided pairing directory. The launcher starts only the local dashboard. It connects reads to the existing Intel worker; it does not start or replace Intel services. Runtime configuration is explicit and server-side. The optional `--media-config /ABSOLUTE/PRIVATE/dashboard-media.json` selects a separately provisioned media source; the records pairing does not carry WebRTC media.

Select **Live** for physical records and **Simulation** for saved simulation on that same Intel service. An empty Live view is correct when Intel has no physical session. A working records connection does not establish working cameras, policies or physical control.

## Check the connection without changing records

```bash
npm run station:check -- --port 3000 --source-mode live
npm run station:check -- --port 3000 --source-mode simulation
```

The checker makes bounded GET requests to the selected local dashboard. It distinguishes local host configuration, the versioned records response, eligible session data, and media configuration/producer status. It does not negotiate video, call a provider, export a full session or submit a command. `/api/local/v1/runtime` reports the configured transport only; remote response verification remains a separate result. Camera-to-display latency and physical readiness require their own measurements.

For the disposable demonstration's stronger records/history/replay regression, use:

```bash
npm run demo:check -- 3101
```

## Walk through one coherent result

1. Choose the source. **Follow latest session** follows newly received sessions; choosing a named session pins that selection. Reconnect preserves this choice.
2. In **Live inspection**, inspect the current object, classification, selected action, execution receipt and independent confirmation. The current camera preview is separate from the exact saved analyzed image.
3. Open **Quality & history** to load a complete saved session snapshot. Read the visible counts and denominators, including failed, aborted, unverified and unfinished outcomes.
4. Open a cycle's trace. Check its original frame, attempts, model records, commanded/observed destination and confirmation source. Closing the trace clears its selected detail request.
5. **JSON** exports the loaded history snapshot. **CSV** explicitly requests the latest server records and may include later changes. Replay JSON remains the frozen replay export.
6. Use **Replay** to inspect saved events. It does not start live video or change repetition records. Return to a records mode to resume polling.

## Current acceptance boundary

On November 15 at 07:22 UTC, authenticated Mac MCP reads independently verified the restored `intel-main` dashboard API: one saved simulation session, five cycles, event cursor 50, and no eligible live session. The simulation contains two correct of four finished cycles, one recovered cycle and one retry. Its exact selected retry image is a 1×1 synthetic PNG, not a camera photograph. Camera discovery returns unavailable; the reported online robot/model capabilities are unverified. These observations confirm the records transport, not a physical run.

The complete new launcher was verified with a changing 640×480 H.264 stream at 30 FPS in the browser. Its canonical simulation API passed the history/export/replay check. Ctrl+C stopped all seven observed owned processes and removed its disposable runtime while a real event-stream client was connected. The earlier two-minute jitter/source-gap regression remains separate evidence. Actual Intel capture, resource use, network media delivery and optical latency still require target verification. The proposed p95 below 300 ms is a target, not an observed result.

The actual Intel-backed browser also displayed the five-cycle history, the failed first grasp and successful second attempt, and original replay events with unchanged session totals. A later GET check retained event cursor 50. One explicitly submitted analyst request expired without a worker claim; its application request ID is retained. Intel's read-back handoff `921c66b9-b650-43b8-aedc-60a4dad32168` reports that at 08:05:19 UTC the request was absent from its saved analysis store and the worker remained GET-only. At 08:14:58 UTC a complete read-only Mac queue snapshot found no nonexpired queued or claimed POSTs; this is a dated observation, not a queue freeze. The Intel owner still requires direct-owner resolution of that boundary, coordinated maintenance and a rollback plan for the current processes. The write opt-in also permits audited record-review POSTs. No retry, worker change, completed product explanation or provider call is inferred. The [adoption evidence](klemen-dashboard/verification/workflow-integration-20261115/analysis-adoption-check.json) records these boundaries.

Intel's prerequisite handoff `bc26bdec-2908-4c8a-bd3d-31e7aa72c871`, finalized at 07:52:14 UTC, reports 25 original bridge tests passing in a separate reviewed environment. It found FFmpeg/ffprobe 8.0.1 with libx264, but did not test encoding or find a verified MediaMTX installation in its scoped search. Studio configuration records 640×480 at 30 FPS and a process holds a camera device; this does not establish exclusive capture ownership. Its preview subscription may call `shared_camera.connect(overwrite_settings=True)` and alter capture settings. The capture owner must confirm reuse before connecting the bridge. WHEP/TLS routing and producer-status forwarding remain unavailable.

## Remaining work outside Jose's implementation

| Owner | Concrete next action | Evidence needed to call it complete |
| --- | --- | --- |
| Intel records worker owner | Resolve the existing GET-only boundary with the direct owner, prepare current-process rollback and coordinated queue maintenance, enable the constrained writer, then re-check the retained request before its same-ID retry | Confirmed writer adoption followed by a saved terminal report with the actual model ID, citations, measured latency and errors; ordinary reads already pass |
| Intel capture owner | Select the existing Studio camera stream and adopt the reviewed media bridge without creating a second capture pipeline | Exact camera/stream configuration, one capture owner, source interruption/recovery and actual frame linkage |
| Intel + media network owner | Provision authenticated signaling and a reachable WebRTC media route | Successful browser playback from Intel, rejected unauthorized viewers, measured resource cost and optical delay |
| Intel physical owner | Finish calibration, learned skills, Anomalib/OpenVINO inference and the validated local execution adapter | Actual model/policy identities, calibration and bounded operator-run tests; unavailable features remain unavailable |
| Intel physical owner + Klemen | Record one complete physical baseline and a failed attempt followed by recovery | Stable session/cycle/attempt/frame IDs, reference quality, commanded/observed destination and independent confirmation visible in the dashboard |

The detailed producer fields and test cases are in [Intel requirements](klemen-dashboard/INTEL_REQUIREMENTS.md). [Three-host ownership](THREE_HOST_ARCHITECTURE.md) defines the control boundary. Automatic Intel Codex receiver startup remains revoked; ordinary shared handoffs do not start services. Target adoption goes through the current Intel owner, preserving active diagnostics and the camera owner.

## Evidence and source publication

Tests, source review/publication, target service adoption and physical acceptance are separate checkpoints. Preserve the original source manifests and previous results; do not regenerate historical hashes to make an old snapshot look current. Keep private pairing, generated credentials, databases, real captures, models and dependency installations out of source deliveries. The [integration verification folder](klemen-dashboard/verification/workflow-integration-20261115/) records the commands and observations for this revision.
