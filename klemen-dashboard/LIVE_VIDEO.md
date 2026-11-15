# Dashboard live video

Implemented on November 15, 2026. This adds an independent receive-only media connection to Live inspection. Intel remains the source of authoritative records and analyzed evidence. The browser displays native H.264/WebRTC video; the Mac MCP continues to carry records and explicit evidence requests. Video creates no station sessions, cycles, attempts, confirmations, or robot commands.

The new [Intel bridge](../intel-runtime/media-bridge/README.md) contains the persistent Studio subscription, latest-frame buffer, software encoder, authenticated producer status and a synthetic source. The Mac [media gateway](dashboard/server/mediaGateway.ts) accepts only fixed media endpoints configured by the server owner. The [video panel](dashboard/src/components/LiveVideoPanel.tsx) leaves the exact analyzed snapshot below it intact.

## What the UI reports

- **Frames arriving** requires newly displayed frames. A connected peer alone is insufficient. This does not prove that a camera captured a new scene; repeated stale pixels from an upstream capture process require separate source checks.
- **Frozen** means the visible tab has not displayed another frame for 2.5 seconds. Hidden tabs suspend the presentation watchdog. A later visible frame restores the status.
- A prolonged freeze or failed connection triggers bounded reconnect. Transient negotiation failures use five automatic retries with delays of 1, 2, 4, 8 and 10 seconds; the user can retry after that. Old known sessions are closed before a replacement is negotiated.
- **Simulation video** is explicit and shown only when the selected records source is simulation. A configured source mismatch prevents video negotiation. Replay removes the current video panel and retains historical analyzed evidence.
- Receiver FPS, bitrate, interval packet loss, mean jitter-buffer residence, selected-path RTT and negotiated codec are sampled about once per second. Unsupported metrics are unavailable. Packet loss shows both lost and total interval packets. RTT and buffer residence are not camera-to-display latency.

Opening/reconnecting the dashboard negotiates only a video viewer. It does not open a camera, change capture settings, start a physical run or invoke a model. The Intel publisher is started separately by its authorized operator and serves all viewers through one source subscription.

## Reproduce a local simulation

For a supervised records-and-video demonstration with the installed dependencies, run `npm run demo:all` from `klemen-dashboard/dashboard/`. It uses the same bridge and media configuration helpers, generates private disposable configuration, and owns startup and cleanup. [Run and finish the system](../WORKING_SYSTEM.md) provides the normal workflow. The separate-process procedure below remains useful for debugging the media components individually.

Use the prepared Python 3.12 runtime or a reviewed environment with the bridge dependencies. Obtain MediaMTX from its official release and verify the release checksum; use an FFmpeg build with `libx264`. This procedure has three separately owned processes and makes no Intel or hardware connection.

From `intel-runtime/media-bridge`, create a new private runtime directory:

```bash
python3.12 tools/prepare_synthetic.py --directory /absolute/private/path/video-demo --ffmpeg /absolute/path/to/ffmpeg
python3.12 -m morph_media_bridge preflight --config /absolute/private/path/video-demo/bridge.json
```

From `klemen-dashboard`, create the gateway file from those exact generated credentials:

```bash
python3.12 tools/prepare_demo_media.py --runtime /absolute/private/path/video-demo
```

Start the generated MediaMTX configuration in one terminal, then start the synthetic publisher from the bridge directory in another:

```bash
/absolute/path/to/mediamtx /absolute/private/path/video-demo/mediamtx.yml
python3.12 -m morph_media_bridge run --config /absolute/private/path/video-demo/bridge.json
```

From `klemen-dashboard/dashboard`, start the dashboard in a third terminal:

```bash
npm run demo -- --media-config /absolute/private/path/video-demo/dashboard-media.json
```

Open `http://127.0.0.1:3101` and select **Simulation**. The source image says `SIMULATION - NO CAMERA` and includes a changing frame counter and bar. The generator defaults to 640 × 480 at 15 FPS; the reviewed 30 FPS profile can be set in the private bridge configuration before generating its matching gateway file. Never change a real Studio camera's profile implicitly.

The default `npm run demo` still works with video unconfigured. Demo mode rejects live sources, remote WHEP/status URLs and external ICE servers. The launcher ignores ambient media configuration; only its explicit `--media-config` is passed to the dashboard child. The records backend remains read-only and isolated. Stop each separately started process with Ctrl-C when it is no longer needed.

## Configure the real Intel source

The actual source and route need current Intel-owner verification. The historical Studio camera check is not a deployed media endpoint. See the bridge's exact-camera and network instructions before deployment. A working Mac MCP connection does not establish a WebRTC packet path.

Create a private owner-only JSON file for the normal Mac server and point `MORPH_MEDIA_CONFIG_FILE` to its absolute path. It is a server variable, never a `VITE_*` browser variable. Example structure, with placeholders that must be replaced locally:

```json
{
  "version": 1,
  "whepUrl": "https://verified-intel-host.example:8889/inspection/whep",
  "cameraId": "verified-current-camera-id",
  "streamId": "inspection",
  "label": "Intel inspection camera",
  "sourceMode": "live",
  "profile": {"width": 640, "height": 480, "fps": 30},
  "username": "morph-viewer",
  "password": "<local>",
  "iceServers": []
}
```

The normal host uses its existing MCP pairing for records and the media configuration for preview:

```bash
MORPH_MEDIA_CONFIG_FILE=/absolute/private/path/intel-media.json npm run dev
```

The normal dashboard defaults to port 3000; the disposable simulation defaults to 3101. `PORT` can select another normal-host port. Neither host is exposed beyond loopback by this change.

Remote WHEP requires HTTPS with a trusted certificate and exact-path viewer authentication. Keep RTSP and the bridge status listener on Intel loopback. An optional `statusUrl` can point to a separately authorized protected route; its `statusToken` is a separate bearer secret. Missing status produces unknown producer freshness. A known identity, source-mode or profile mismatch blocks negotiation. No URL, token, password, arbitrary target or camera settings are accepted from the browser. Optional `iceServers` must contain only the topology owner's reviewed STUN/TURN endpoints; any TURN credential delivered to a browser must be scoped to that viewer. This package provisions no relay or tunnel.

**Current control boundary:** the verified shared Intel owner-correction report `be57f4f6-4f20-479e-bcb6-2164b85bae1b`, saved at 2026-11-15T06:21:13Z, reports that its automatic Codex receiver was stopped and CLI logged out, with `restartAuthorized: false`, and Jose's Mac owns control. The source handoff is passive. The existing authorized owner coordinates adoption; do not reactivate that receiver or change the station worker to install video. Detailed stop/logout evidence remains Intel-local; the Mac independently verified the shared report and handoff-event state.

## Browser-facing contract

| Endpoint | Contract |
| --- | --- |
| `GET /api/media/v1/status` | Version, configured flag, explicit source/camera/stream/profile, same-origin WHEP path, reviewed ICE list, nullable producer status, reason and UTC check time. No upstream viewer/status secrets or raw upstream URLs. |
| `POST /api/media/v1/whep` | One receive-only video SDP offer, all local ICE candidates already gathered; maximum 64 KiB. Returns 201 SDP answer and an opaque same-origin session `Location`. |
| `DELETE /api/media/v1/sessions/<uuid>` | Idempotent viewer cleanup mapped to the fixed upstream session. An unknown local ID does not contact upstream. |

This version uses non-trickle negotiation and does not implement PATCH. The gateway limits concurrent/pending viewers to four, negotiation to 12 seconds, and each session to 60 minutes. Expired/abandoned sessions enter cleanup; a failed delete is retried with bounded backoff. Shutdown drains pending negotiations and deletion for up to 15.1 seconds by default. If the upstream stays unavailable, remote cleanup remains unconfirmed and must not be reported as successful. The local Host/Origin guard also protects media endpoints. Upstream redirects and unsafe session Locations are rejected. Station proxy methods and robot boundaries are unchanged.

## Acceptance and evidence

Run `npm run test:media`, `npm run typecheck`, `npm test` and `npm run build` from the dashboard. The gateway tests use real local HTTP with synthetic upstreams. Receiver tests use fake peers/clocks to exercise lifecycle races. The bridge's independent verifier runs local WebSocket fixtures and actual software H.264 encoding. Browser evidence is in [verification/live-video-20261115](verification/live-video-20261115/README.md).

Intel acceptance still requires the actual Studio capture owner/configuration, one source subscriber with multiple viewers, authenticated WHEP and reachable ICE candidates, source loss and restoration, frame progress under the real model/robot workload, and resource measurements. Measure capture-to-display delay with an optical timing target visible to the actual camera and receiver, saving the method, sample count, median and p95 over a ten-minute workload. The proposed p95 below 300 ms is an acceptance target, not a result of a loopback browser test. Hardware encoding is a later explicit adapter/test; this revision uses the tested `libx264` path.
