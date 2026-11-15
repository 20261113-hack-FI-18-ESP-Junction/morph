# Intel Studio video bridge

This is new source prepared on November 15, 2026. It keeps one explicit subscription to an existing Physical AI Studio binary JPEG WebSocket, replaces superseded pending frames, and publishes one software-encoded H.264 stream to a local MediaMTX server. The Mac dashboard gateway reads that stream through WHEP. Importing this package starts nothing. The package does not open RealSense/OpenCV directly, modify Studio, replace the station API, or use the record-oriented Mac MCP relay for video.

Local tests and synthetic encoding establish software behavior. Intel deployment, reuse of the active Studio capture publisher, camera performance, network reachability, and physical glass-to-glass latency still require separate verification. The original Intel source manifests remain unchanged; this directory is a new implementation.

## Data path and ownership

```text
Existing Studio capture owner
  → one /api/cameras/ws subscription with its exact existing camera configuration
  → bounded binary JPEG receive validation
  → one replaceable latest complete JPEG slot
  → one bounded FFmpeg pipe write
  → libx264 H.264 Constrained Baseline, no B frames, zerolatency
  → local MediaMTX RTSP path /inspection
  → authenticated WHEP signaling + separate WebRTC media connection
  → dashboard video element
```

Viewer requests never open another Studio connection. MediaMTX distributes the one encoded stream to viewers. `overridePublisher: false` prevents a second publisher from taking over the configured path, and the bridge locks its private runtime directory against a second instance.

The initial adapter reuses Studio's already encoded JPEG output. FFmpeg decodes the selected JPEG and encodes it to H.264; that extra decode/encode cost must be measured on Intel. A future raw-frame fanout from Studio's existing capture owner may remove the JPEG stage. It must preserve single ownership; adding another `rs.pipeline()` or independent OpenCV camera opener is not this design.

The source contract comes from the received [camera client](../source/junction/scripts/check_cameras.py), especially its `capture` function. It sends a JSON `camera` query containing `name`, `hardware_name`, `driver`, `fingerprint`, and `payload`, then receives binary JPEG messages. The [dated camera report](../source/junction/camera-check-2026-11-14/README.md) describes Studio's shared `read_latest` capture and a reopen timeout during earlier checks. These are source/report observations, not a fresh verification of the deployed producer. Confirm the native Studio owner and its actual endpoint before configuration; historical native port 3000 and container port 7860 are different installations.

## Dependencies and preflight

Use Python 3.12. The tested Python dependencies are pinned in [requirements.txt](requirements.txt): `websockets==17.4` and `Pillow==13.0.0`. Unit tests use Python's standard `unittest`. The publisher requires an explicit FFmpeg executable that advertises `libx264`; verification also uses `ffprobe`. Software encoding was checked on the Mac with FFmpeg 9.0.2. MediaMTX configuration targets 1.21.3; the deployment owner must obtain and verify its release separately. The package installs and downloads nothing automatically.

For a new reviewed environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Alternatively use an existing prepared Python 3.12 environment. Run commands below from this `media-bridge` directory, replacing `python3.12` with that interpreter if needed. `preflight` validates configuration, private token permissions, and local FFmpeg encoder availability. It makes no source or network connection and does not prove RTSP publication.

Only `libx264` is supported in this revision. A requested hardware encoder such as `h264_qsv` is rejected explicitly. Adding hardware support requires a separate adapter, exact device configuration, and tests; there is no automatic software/hardware fallback that could hide an unavailable device.

## Reproducible synthetic run

The following prepares private configuration and credentials in a **new** directory. It does not start a service, use live environment variables, discover a camera, or access a device:

```bash
python3.12 tools/prepare_synthetic.py --directory .runtime/synthetic-demo --ffmpeg ffmpeg
python3.12 -m morph_media_bridge preflight --config .runtime/synthetic-demo/bridge.json
```

The generator creates mode-0600 `bridge.json`, `mediamtx.yml`, `status.token`, and `viewer-password.token` under a mode-0700 directory. Its printed result contains file paths and the non-secret viewer username `morph-viewer`; it does not print either credential. Existing directories are rejected. The committed MediaMTX YAML contains a password placeholder; the generator replaces it with a private random value. Never expose or run the placeholder template as a deployed server.

After confirming these local ports are free, explicitly start your separately verified MediaMTX binary in one terminal:

```bash
/absolute/path/to/mediamtx .runtime/synthetic-demo/mediamtx.yml
```

Start the changing synthetic publisher in a second terminal:

```bash
python3.12 -m morph_media_bridge run --config .runtime/synthetic-demo/bridge.json
```

For a bounded local run, add `--duration 15`. The image is labeled `SIMULATION - NO CAMERA`; its generated frame counter, color and moving bar change. This is an artificial image sequence, with no hardware or capture-time claim. Synthetic input cannot be configured as `sourceMode: live`.

Read its authenticated producer status without exposing a token in a command argument:

```bash
python3.12 tools/read_status.py --config .runtime/synthetic-demo/bridge.json
```

The default local topology is:

| Purpose | Explicit local value |
| --- | --- |
| One RTSP publisher path | `rtsp://127.0.0.1:8554/inspection` |
| WHEP upstream for the server-side gateway | `http://127.0.0.1:8889/inspection/whep` |
| WebRTC media UDP listener/candidate | `127.0.0.1:8189` |
| Producer status | `http://127.0.0.1:8790/api/media/v1/status` |
| Viewer authorization | HTTP Basic `morph-viewer` plus password read from `viewer-password.token` by the gateway |
| Producer-status authorization | Separate HTTP Bearer read from `status.token` by the gateway |

The gateway must keep both credentials server-side. Neither belongs in browser JSON, URLs, screenshots, logs, or committed configuration. MediaMTX permits anonymous **publish only**, for this exact path and loopback IPs; its RTSP listener is loopback-bound. The separate named viewer has **read only** permission for that path. API, metrics, profiling, playback, RTMP, HLS, SRT and MoQ listeners are explicitly disabled. MediaMTX 1.21.3 enables MoQ by default, so retaining `moq: false` matters when adapting the template.

Ctrl-C or SIGTERM stops the bridge, cancels its receiver/backoff/write, closes the status listener, and terminates its owned FFmpeg process group. A sanitized final `last-status.json` is saved under the configured private `runtimeDir`. Stopping the bridge does not stop the separately launched MediaMTX process; the operator who started it owns its cleanup. No background service or automatic restart is installed.

## Configure an existing Studio source

Copy [examples/studio.json](examples/studio.json) to private local configuration and replace every camera placeholder with the **exact configuration of the already active Studio camera**. Its empty fingerprint intentionally fails validation. Record the camera identity, capture owner, existing width/height/fps, and verified local Studio URL. Do not copy a USB serial from a historical report and assume it identifies the current Studio stream.

The initial topology requires Studio, the bridge, and MediaMTX on the same Intel host. Studio `baseUrl` must use a literal loopback address; no discovery, URL credentials, arbitrary URL query, or camera default is accepted. The output dimensions must match the existing Studio dimensions. The output frame rate may be lower than the existing capture rate. Never silently renegotiate another capture profile. An optional Studio `tokenFile` is read privately and sent as a bearer header if the already deployed endpoint requires it.

Run `preflight` against the prepared file first. A later, explicitly authorized `run` makes the one WebSocket subscription. Confirm from Studio's actual process/capture ownership and producer diagnostics that it reuses the existing publisher, then record startup behavior, disconnect/reconnect, Intel resource cost and timestamps. A successful local synthetic run is not that acceptance evidence.

## Network and viewer security

The committed/default topology supports same-host QA only. Opening or proxying WHEP HTTP does **not** carry the WebRTC media packets. The browser must also reach a negotiated MediaMTX UDP/TCP candidate, or a separately configured TURN relay. An existing HTTPS Mac MCP connection is not proof of this reachability. The package contains no guessed Intel LAN address, public hostname, tunnel, STUN server, or TURN credential.

For Intel-to-Mac deployment, the topology owner must explicitly select and test:

1. The verified Intel WHEP address/port and a trusted certificate. If WHEP listens beyond loopback, enable `webrtcEncryption: true`, set owner-only `webrtcServerKey` and `webrtcServerCert` paths, and retain exact-path viewer authentication. The Mac gateway must verify TLS and inject the private Basic credential.
2. A media listener/interface and candidates the actual browser can reach. Change `webrtcLocalUDPAddress` and `webrtcAdditionalHosts` only to observed, permitted values. Do not infer a usable candidate from WHEP success. If UDP is blocked, explicitly test MediaMTX's optional TCP listener or the selected TURN relay; document the measured result.
3. A protected route for optional producer status. The bridge deliberately remains loopback-bound; use an explicitly configured authenticated TLS reverse proxy or controlled forwarding path for remote reads. Keep its separate bearer secret in the gateway. If this route is not configured, the dashboard must show producer status as unavailable.
4. Exact dashboard origins and any chosen HTTPS reverse proxy policy. Do not relax viewer auth or expose RTSP to make a browser test pass. The local example has no permissive browser CORS origin; the same-origin gateway owns browser access.

WebRTC's media encryption and WHEP signaling are different parts of the connection. TLS/authentication protects signaling and credentials; WebRTC negotiates encrypted media. Measure both the network path and browser frame progress during acceptance.

## Status contract and bounds

`GET /health` is unauthenticated loopback liveness only and returns `{"status":"ok"}`. It does not establish a camera, encoder, publication or viewer connection.

`GET /api/media/v1/status` requires the private bearer token and returns at least:

```json
{
  "version": 1,
  "cameraId": "synthetic-inspection",
  "streamId": "inspection",
  "sourceMode": "simulation",
  "profile": {"width": 640, "height": 480, "fps": 15},
  "state": "streaming",
  "receivedAt": "2026-11-15T12:00:00.000Z",
  "receiptAgeMs": 24.8,
  "counters": {"receivedMessages": 30, "acceptedFrames": 30, "replacedFrames": 2, "submittedFrames": 27}
}
```

This is an illustrative response, not a measured result. `receivedAt` is the bridge's UTC time when it accepted a complete JPEG. `receiptAgeMs` uses the bridge monotonic clock since that receipt. Bare Studio JPEG messages do not provide a trustworthy capture timestamp; `captureTimestampAvailable` is therefore `false`. Never relabel receipt age or `lastSubmittedReceiptAgeMs` as camera latency, capture-to-display latency, inference time, or a timestamp on an analyzed station frame.

Additional fields report `encoder`, `configuredBitrateKbps`, `sourceState`, `publisherState`, the latest successful pipe submission time/receipt age, one pending/inflight frame's bytes, and a sanitized `lastErrorCode`. Source state is connecting/connected/disconnected. Overall state can be connecting, starting, streaming, failed, stale, disconnected or stopped. `streaming` follows FFmpeg's positive encoded-frame progress; it does not prove browser display. Current stale/disconnected state overrides a previously positive encoder report.

| Counter | Meaning |
| --- | --- |
| `receivedMessages`, `receivedBytes` | Application-visible received messages and binary bytes. WebSocket oversize rejection can happen before these counters. |
| `acceptedFrames` | JPEG envelopes/headers matching configured dimensions, placed in the latest slot. |
| `replacedFrames` | Previously pending complete JPEGs superseded before pixel decode/encoding. |
| `invalidFrames`, `oversizedFrames` | Rejected type, envelope/header/profile or size; oversize includes a WebSocket 1009 close. |
| `staleFrames` | Selected frames older than `maxReceiptAgeMs`, discarded before submission. |
| `submittedFrames`, `submittedBytes` | FFmpeg stdin write/drain completed; this is not a browser delivery acknowledgment. |
| `encodedFramesReported` | Cumulative frames reported by FFmpeg progress across owned publisher restarts. |
| `writeTimeouts`, `publisherFailures`, `publisherStarts`, `publisherRestarts` | Encoder progress through starts and bounded write failures; a partial stalled input is discarded by terminating that process. |
| `sourceConnections`, `sourceReconnects`, `sourceFailures`, `sourceTimeouts` | The one receiver connection's lifecycle; no per-viewer source count. |
| `discardedOnDisconnect` | A pending JPEG cleared when the source or bridge closes. |
| `sourceCadenceSkipped`, `publisherCadenceSkipped` | Missed scheduled generation/publication ticks; these are not extra accepted frames or physical capture drops. |

Default maximum JPEG size is 2 MiB; configuration cannot exceed 4 MiB. The application has one replaceable pending JPEG and at most one selected write. WebSocket framing is configured with `max_queue=1`, `max_size`, no compression and explicit timeouts. It drains continuously, independently of target encoding FPS. JPEG header validation does not decode pixels; FFmpeg owns the selected frame's decode, with fatal decode errors enabled.

The consumer throttles **before** taking the latest frame. Generation and publication use scheduled monotonic deadlines; work time does not accumulate on top of each period. Missed ticks are skipped, with no catch-up backlog. It drops frames older than the configured receipt age, and bounds the write deadline by both `writeTimeoutMs` and remaining freshness budget. Python's pipe transport uses zero high/low water marks. A stalled write terminates/restarts the owned encoder so a partial JPEG cannot be reused. OS pipe, FFmpeg decoder/muxer and MediaMTX/browser buffers still exist; the package does not claim a measured bound for total memory or end-to-end latency.

`publisher.bitrateKbps` defaults to 1500. FFmpeg receives explicit `-b:v`/`-maxrate` settings and a small VBV buffer equal to about 200 ms of that budget (300 kbit at the default). This is an encoder budget, not a measured network rate; simple scenes may encode well below it and protocol overhead is additional. Exact input/output FPS, bitrate, dropped frames and Intel utilization must be measured together.

The configured frame rate remains the nominal source/publication cadence and codec rate. Image2pipe initially rounds packet wall-clock timestamps to that frame interval, which can assign equal timestamps to two jittered arrivals. RTSP rejects those duplicates. After decode, the bridge's FFmpeg filter therefore assigns local frame-arrival timestamps on a finer `1/90000` clock, with a minimum one-tick monotonic increment, and preserves that time base through the encoder. Missing-input gaps remain visible without the coarse rounding failure.

These are FFmpeg decode/filter-arrival timestamps, not camera capture times, the bridge's `receivedAt`, or analyzed-frame timestamps. Frames flushed at end of input can be very close together; a fine-clock test container is required to inspect them. Host wall-clock changes can affect this presentation timeline, while the bridge's own freshness checks remain monotonic. A later raw capture adapter should pass real source timestamps explicitly if they are available and verified.

Source reconnect backoff doubles from 250 ms to at most 5 s by default; a sustained accepted stream resets it. Source receive timeout defaults to 3 s. No reconnect is tied to viewer count. HTTP headers, concurrent clients and request time are bounded; there are no write/control routes.

## Verification and remaining acceptance

```bash
python3.12 -m unittest discover -s tests -v
python3.12 tools/verify_offline.py --output verification/my-run --ffmpeg ffmpeg --ffprobe ffprobe
```

The verifier creates a new output directory, tests actual loopback fixture WebSockets and authenticated status HTTP, and encodes eight changing synthetic JPEGs with the same H.264 codec options into a temporary NUT file. This container preserves fine timestamp precision; Matroska's millisecond clock can collapse closely spaced EOF frames. A deliberate 200 ms missing-input interval checks that arrival-based PTS preserves the gap. It checks the result through ffprobe, removes its temporary video, and saves test output, encoder diagnostics, dependency versions and current source hashes. This is a local synthetic test; it does not connect to MediaMTX, Studio or hardware. A missing/failed real software encoder makes the verifier fail instead of silently skipping its verification.

The initial [offline result](verification/offline-01/result.json) passed 19 tests. The [cadence/budget/timestamp result](verification/offline-02/result.json) and [first completed source result](verification/offline-03/result.json) predate a real RTSP timestamp issue: their short file test did not exercise the RTSP muxer's strict timestamp ordering. A [deterministic jitter reproduction](verification/rtsp-jitter-before-fix/result.json) captured non-monotonic DTS errors with the earlier coarse clock. The [fixed jitter regression](verification/rtsp-jitter-filter-fix/result.json) exercises the same bounded scheduling disturbance without failures. Intermediate candidate/test-container failures remain saved as historical evidence; they are not acceptance results.

The final [offline result](verification/offline-07/result.json) covers 25 tests and the current fine-clock software encoder/gap check. The [120-second RTSP soak](verification/rtsp-soak-clock-fix/result.json) uses a separate MediaMTX instance, 640×480 at 30 FPS, alternating 25 ms write jitter and an explicit 400 ms source gap. Its result records exact counters, bounded diagnostics and owned-process/port/private-runtime cleanup. See the parent dashboard's separate synthetic MediaMTX/browser evidence before making broader claims.

To reproduce that deliberate, synthetic-only RTSP check with a separately obtained and verified MediaMTX binary:

```bash
python3.12 tools/verify_rtsp.py --mediamtx /absolute/path/to/mediamtx --ffmpeg ffmpeg --duration 120 --jitter --gap-seconds 0.4 --output verification/my-rtsp-run
```

The tool requires unused loopback RTSP 18554, WHEP 18889 and media UDP 18189. It starts its own private MediaMTX and synthetic encoder, then terminates those owned process groups and removes its temporary credentials/configuration. It does not reuse the dashboard preview's services or touch Studio/cameras. Opening these local QA listeners is an explicit action, separate from the offline verifier.

Before Intel adoption is considered complete, verify dependency versions, exact Studio owner/configuration, one source subscriber with multiple viewers, accepted camera profile, authenticated WHEP and rejected unauthorized viewers, changing decoded browser frames, reconnect and source stall behavior, renderer freeze indication, owned-process cleanup, measured Intel CPU/resource cost, and capture-to-display latency using an actual shared timing target. Keep the analyzed station snapshot separate from this observational live video. No robot movement, outcome or reliability record is produced by the bridge.

Upstream references checked for this implementation: [MediaMTX authentication](https://mediamtx.org/docs/usage/authentication), [MediaMTX configuration](https://mediamtx.org/docs/references/configuration-file), [WebRTC connectivity](https://mediamtx.org/docs/usage/webrtc-specific-features), [FFmpeg formats](https://ffmpeg.org/ffmpeg-formats.html), and [websockets asyncio client](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html). The selected release's own configuration is authoritative for its supported keys.
