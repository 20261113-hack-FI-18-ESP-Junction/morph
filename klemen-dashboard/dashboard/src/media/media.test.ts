import assert from "node:assert/strict";
import test from "node:test";
import {
  LiveMediaClient,
  parseMediaConfiguration,
  validateSessionLocation,
  type MediaClock,
} from "./client.ts";
import { observeDisplayedFrames } from "./frameObserver.ts";
import { readMediaStatistics } from "./stats.ts";
import type { MediaConfiguration } from "./types.ts";

const configuration = (
  patch: Partial<MediaConfiguration> = {},
): MediaConfiguration => ({
  version: 1,
  configured: true,
  cameraId: "overview",
  label: "Overview camera",
  streamId: "preview-one",
  sourceMode: "live",
  profile: { width: 640, height: 480, fps: 30 },
  whepPath: "/api/media/v1/whep",
  iceServers: [],
  producer: null,
  reason: null,
  checkedAt: "2026-11-15T12:00:00Z",
  ...patch,
});
const flush = async () => {
  for (let i = 0; i < 20; i++) await Promise.resolve();
};
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
};

class FakeClock implements MediaClock {
  time = 0;
  nextId = 0;
  timers = new Map<number, { at: number; callback: () => void }>();
  now = () => this.time;
  after = (callback: () => void, delay: number) => {
    const id = ++this.nextId;
    this.timers.set(id, { at: this.time + delay, callback });
    return id;
  };
  cancel = (handle: unknown) => {
    this.timers.delete(handle as number);
  };
  async advance(milliseconds: number) {
    const target = this.time + milliseconds;
    while (true) {
      const next = [...this.timers]
        .filter(([, timer]) => timer.at <= target)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      this.time = next[1].at;
      this.timers.delete(next[0]);
      next[1].callback();
      await flush();
    }
    this.time = target;
    await flush();
  }
}

class FakePeer extends EventTarget {
  iceGatheringState: RTCIceGatheringState = "complete";
  connectionState: RTCPeerConnectionState = "new";
  localDescription: RTCSessionDescriptionInit | null = null;
  remoteDescription: RTCSessionDescriptionInit | null = null;
  ontrack: ((event: RTCTrackEvent) => void) | null = null;
  onconnectionstatechange: (() => void) | null = null;
  closed = false;
  transceivers: unknown[] = [];
  report = new Map() as unknown as RTCStatsReport;
  stats = async () => this.report;
  addTransceiver(kind: string, init: RTCRtpTransceiverInit) {
    this.transceivers.push({ kind, init });
  }
  createOffer = async (): Promise<RTCSessionDescriptionInit> => ({
    type: "offer",
    sdp: "v=0\r\no=offer",
  });
  setLocalDescription = async (description: RTCSessionDescriptionInit) => {
    this.localDescription = description;
  };
  setRemoteDescription = async (description: RTCSessionDescriptionInit) => {
    this.remoteDescription = description;
  };
  getStats = async () => this.stats();
  close = () => {
    this.closed = true;
    this.connectionState = "closed";
    this.onconnectionstatechange?.();
  };
  connection(state: RTCPeerConnectionState) {
    this.connectionState = state;
    this.onconnectionstatechange?.();
  }
}

function fixture(
  options: {
    config?: MediaConfiguration;
    response?: (
      url: string,
      init: RequestInit | undefined,
    ) => Promise<Response | null>;
    peer?: FakePeer;
  } = {},
) {
  const clock = new FakeClock();
  const calls: {
    url: string;
    method: string;
    init: RequestInit | undefined;
  }[] = [];
  const peers: FakePeer[] = [];
  const streams: (MediaStream | null)[] = [];
  let sessions = 0;
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    calls.push({ url, method: init?.method ?? "GET", init });
    const custom = await options.response?.(url, init);
    if (custom) return custom;
    if (url.endsWith("/status"))
      return Response.json(options.config ?? configuration());
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response("v=0\r\no=answer", {
      status: 201,
      headers: {
        "Content-Type": "application/sdp",
        Location: `/api/media/v1/sessions/test-${++sessions}`,
      },
    });
  };
  const client = new LiveMediaClient({
    fetch: fetcher,
    origin: "http://localhost:3101",
    clock,
    createPeerConnection: () => {
      const peer =
        peers.length === 0 && options.peer ? options.peer : new FakePeer();
      peers.push(peer);
      return peer as unknown as RTCPeerConnection;
    },
    createMediaStream: () => ({ addTrack: () => {} }) as unknown as MediaStream,
    onStream: (stream) => streams.push(stream),
  });
  return { client, clock, calls, peers, streams };
}

test("a connected peer is not live until a frame is displayed; frames do not trigger per-frame state updates", async () => {
  const { client, peers } = fixture();
  await client.connect("live");
  assert.deepEqual(peers[0].transceivers, [
    { kind: "video", init: { direction: "recvonly" } },
  ]);
  peers[0].connection("connected");
  assert.equal(client.getState().status, "connecting");
  let updates = 0;
  client.subscribe(() => updates++);
  client.noteDisplayedFrame();
  for (let i = 0; i < 90; i++) client.noteDisplayedFrame();
  assert.equal(client.getState().status, "live");
  assert.equal(updates, 1);
  await client.dispose();
});

test("unconfigured or mismatched sources never create a peer or media session", async () => {
  for (const config of [
    configuration({
      configured: false,
      cameraId: null,
      streamId: null,
      whepPath: null,
    }),
    configuration({ sourceMode: "simulation" }),
  ]) {
    const { client, peers, calls } = fixture({ config });
    await client.connect("live");
    assert.equal(client.getState().status, "unconfigured");
    assert.equal(peers.length, 0);
    assert.equal(calls.filter((call) => call.method === "POST").length, 0);
    await client.dispose();
  }
});

test("missing media configuration takes precedence over its default source mode", async () => {
  const { client, peers, calls } = fixture({
    config: configuration({
      configured: false,
      cameraId: null,
      streamId: null,
      whepPath: null,
      sourceMode: "live",
      reason: "No media gateway is configured on this dashboard.",
    }),
  });
  await client.connect("simulation");
  assert.equal(client.getState().status, "unconfigured");
  assert.equal(client.getState().reason, "No media gateway is configured on this dashboard.");
  assert.equal(peers.length, 0);
  assert.equal(calls.filter((call) => call.method === "POST").length, 0);
  await client.dispose();
});

test("frozen presentation is detected and reconnect deletes the old session before posting another", async () => {
  const { client, peers, clock, calls } = fixture();
  await client.connect("live");
  peers[0].connection("connected");
  client.noteDisplayedFrame();
  await clock.advance(3000);
  assert.equal(client.getState().status, "frozen");
  assert.equal(client.getState().frameAgeMs, 3000);
  await clock.advance(7000);
  assert.equal(peers[0].closed, true);
  const mutations = calls
    .filter((call) => call.method !== "GET")
    .map((call) => call.method);
  assert.deepEqual(mutations, ["POST", "DELETE", "POST"]);
  assert.equal(client.getState().status, "connecting");
  await client.dispose();
});

test("hidden tabs suspend freshness checks and need a new displayed frame after returning", async () => {
  const { client, clock, calls } = fixture();
  await client.connect("live");
  client.noteDisplayedFrame();
  client.setDisplayVisible(false);
  await clock.advance(20000);
  assert.equal(client.getState().status, "frozen");
  assert.match(client.getState().reason!, /hidden/);
  assert.equal(calls.filter((call) => call.method === "POST").length, 1);
  client.noteDisplayedFrame();
  assert.equal(client.getState().status, "frozen");
  client.setDisplayVisible(true);
  assert.equal(client.getState().status, "connecting");
  client.noteDisplayedFrame();
  assert.equal(client.getState().status, "live");
  await client.dispose();
});

test("a stalled stats request does not stop the frame watchdog", async () => {
  const peer = new FakePeer();
  peer.stats = () => new Promise(() => {});
  const { client, clock } = fixture({ peer });
  await client.connect("live");
  client.noteDisplayedFrame();
  await clock.advance(3500);
  assert.equal(client.getState().status, "frozen");
  await client.dispose();
});

test("late POST answers after a source change are deleted without attaching their stream", async () => {
  const firstAnswer = deferred<Response>();
  let posted = false;
  const { client, calls, peers } = fixture({
    response: async (_url, init) => {
      if (init?.method === "POST" && !posted) {
        posted = true;
        return firstAnswer.promise;
      }
      return null;
    },
  });
  const first = client.connect("live");
  await flush();
  assert.equal(posted, true);
  const next = client.connect("simulation");
  assert.equal(peers[0].closed, true);
  firstAnswer.resolve(
    new Response("old", {
      status: 201,
      headers: {
        "Content-Type": "application/sdp",
        Location: "/api/media/v1/sessions/late",
      },
    }),
  );
  await Promise.all([first, next]);
  assert.equal(peers[0].remoteDescription, null);
  assert.ok(
    calls.some(
      (call) => call.method === "DELETE" && call.url.endsWith("/late"),
    ),
  );
  assert.equal(client.getState().status, "unconfigured");
  assert.equal(calls.filter((call) => call.method === "POST").length, 1);
  await client.dispose();
});

test("unmount closes peers, deletes sessions and cancels reconnection timers", async () => {
  const { client, calls, peers, streams, clock } = fixture();
  await client.connect("live");
  peers[0].connection("disconnected");
  assert.equal(client.getState().status, "disconnected");
  await client.dispose();
  await clock.advance(30000);
  assert.equal(peers[0].closed, true);
  assert.equal(streams.at(-1), null);
  assert.equal(calls.filter((call) => call.method === "DELETE").length, 1);
  assert.equal(calls.filter((call) => call.method === "POST").length, 1);
  assert.equal(clock.timers.size, 0);
});

test("ICE gathering completes before the non-trickle POST and timeout aborts pending negotiation", async () => {
  const peer = new FakePeer();
  peer.iceGatheringState = "gathering";
  const { client, calls } = fixture({ peer });
  const connecting = client.connect("live");
  await flush();
  assert.equal(calls.filter((call) => call.method === "POST").length, 0);
  peer.localDescription = { type: "offer", sdp: "v=0\r\na=candidate:complete" };
  peer.iceGatheringState = "complete";
  peer.dispatchEvent(new Event("icegatheringstatechange"));
  await connecting;
  assert.match(
    String(calls.find((call) => call.method === "POST")?.init?.body),
    /candidate:complete/,
  );
  await client.dispose();

  const waiting = new FakePeer();
  waiting.iceGatheringState = "gathering";
  const timed = fixture({ peer: waiting });
  const pending = timed.client.connect("live");
  await flush();
  await timed.clock.advance(15000);
  await pending;
  assert.equal(timed.client.getState().status, "error");
  assert.match(timed.client.getState().reason!, /timed out/);
  assert.equal(waiting.closed, true);
  await timed.client.dispose();
});

test("an unsuccessful cleanup blocks new session creation", async () => {
  const { client, calls } = fixture({
    response: async (_url, init) =>
      init?.method === "DELETE" ? new Response(null, { status: 503 }) : null,
  });
  await client.connect("live");
  await client.connect("live");
  assert.equal(client.getState().status, "error");
  assert.match(client.getState().reason!, /could not be released/);
  assert.equal(calls.filter((call) => call.method === "POST").length, 1);
  await client.dispose();
});

test("session cleanup addresses and media discovery cannot escape the approved contract", () => {
  assert.equal(
    validateSessionLocation(
      "http://localhost:3101/api/media/v1/sessions/a-b",
      "http://localhost:3101",
    ),
    "/api/media/v1/sessions/a-b",
  );
  for (const location of [
    null,
    "https://elsewhere.test/api/media/v1/sessions/a",
    "/api/v1/control",
    "/api/media/v1/sessions/a?token=secret",
    "/api/media/v1/sessions/a#hash",
  ]) {
    assert.throws(() =>
      validateSessionLocation(location, "http://localhost:3101"),
    );
  }
  assert.throws(() =>
    parseMediaConfiguration({ ...configuration(), version: 2 }),
  );
  assert.throws(() =>
    parseMediaConfiguration({
      ...configuration(),
      iceServers: [{ urls: "https://elsewhere.test" }],
    }),
  );
  assert.throws(() =>
    parseMediaConfiguration({
      ...configuration(),
      profile: { width: 0, height: 480, fps: 30 },
    }),
  );
});

const statsReport = (
  timestamp: number,
  patch: Record<string, unknown> = {},
): RTCStatsReport =>
  new Map([
    [
      "video",
      {
        id: "video",
        type: "inbound-rtp",
        kind: "video",
        timestamp,
        bytesReceived: timestamp * 100,
        framesDecoded: timestamp * 0.03,
        packetsReceived: timestamp * 0.1,
        packetsLost: timestamp * 0.01,
        jitterBufferDelay: timestamp * 0.0006,
        jitterBufferEmittedCount: timestamp * 0.03,
        transportId: "transport",
        codecId: "codec",
        ...patch,
      },
    ],
    [
      "transport",
      { id: "transport", type: "transport", selectedCandidatePairId: "pair" },
    ],
    [
      "pair",
      { id: "pair", type: "candidate-pair", currentRoundTripTime: 0.012 },
    ],
    ["codec", { id: "codec", type: "codec", mimeType: "video/H264" }],
  ]) as unknown as RTCStatsReport;

test("receiver rates use interval deltas and preserve separate loss, buffer and RTT meanings", () => {
  const first = readMediaStatistics(statsReport(1000), null);
  assert.equal(first.statistics.bitrateBps, null);
  assert.equal(first.statistics.jitterBufferMs, null);
  const second = readMediaStatistics(statsReport(2000), first.sample);
  assert.equal(second.statistics.decodedFps, 30);
  assert.equal(second.statistics.bitrateBps, 800000);
  assert.equal(second.statistics.receivedPackets, 100);
  assert.equal(second.statistics.lostPackets, 10);
  assert.equal(second.statistics.packetLossPercent, (10 / 110) * 100);
  assert.equal(second.statistics.jitterBufferMs, 20);
  assert.equal(second.statistics.roundTripMs, 12);
  assert.equal(second.statistics.codec, "video/H264");
});

test("unsupported metrics and reset counters remain unavailable rather than zero", () => {
  const empty = readMediaStatistics(
    new Map() as unknown as RTCStatsReport,
    null,
  );
  assert.equal(empty.statistics.decodedFps, null);
  assert.equal(empty.statistics.roundTripMs, null);
  const first = readMediaStatistics(statsReport(1000), null);
  const reset = readMediaStatistics(
    statsReport(2000, {
      bytesReceived: 1,
      packetsLost: -1,
      framesDecoded: 1,
      jitterBufferEmittedCount: 1,
    }),
    first.sample,
  );
  assert.equal(reset.statistics.bitrateBps, null);
  assert.equal(reset.statistics.packetLossPercent, null);
  assert.equal(reset.statistics.decodedFps, null);
  assert.equal(reset.statistics.jitterBufferMs, null);
});

test("frame observation uses presentation callbacks and cancels queued callbacks on cleanup", () => {
  const page = new EventTarget() as EventTarget & {
    visibilityState: DocumentVisibilityState;
  };
  page.visibilityState = "visible";
  let callback: (() => void) | null = null;
  let cancelled = 0;
  let frames = 0;
  const visibility: boolean[] = [];
  const video = {
    requestVideoFrameCallback: (fn: () => void) => {
      callback = fn;
      return 1;
    },
    cancelVideoFrameCallback: () => cancelled++,
  } as unknown as HTMLVideoElement;
  const stop = observeDisplayedFrames(video, {
    document: page,
    onFrame: () => frames++,
    onVisibility: (visible) => visibility.push(visible),
  });
  callback!();
  assert.equal(frames, 1);
  page.visibilityState = "hidden";
  page.dispatchEvent(new Event("visibilitychange"));
  callback!();
  assert.equal(frames, 1);
  stop();
  callback!();
  assert.equal(frames, 1);
  assert.equal(cancelled, 1);
  assert.deepEqual(visibility, [true, false]);
});

test("fallback needs a growing displayed-frame count; advancing playback time alone is insufficient", () => {
  const page = new EventTarget() as EventTarget & {
    visibilityState: DocumentVisibilityState;
  };
  page.visibilityState = "visible";
  let poll!: () => void;
  let frames = 0;
  let total = 10;
  let dropped = 1;
  const video = {
    paused: false,
    readyState: 4,
    currentTime: 12,
    getVideoPlaybackQuality: () => ({
      totalVideoFrames: total,
      droppedVideoFrames: dropped,
    }),
  } as unknown as HTMLVideoElement;
  const stop = observeDisplayedFrames(video, {
    document: page,
    onFrame: () => frames++,
    onVisibility: () => {},
    setInterval: ((fn: () => void) => {
      poll = fn;
      return 1;
    }) as unknown as typeof setInterval,
    clearInterval: (() => {}) as typeof clearInterval,
  });
  poll();
  video.currentTime = 14;
  poll();
  assert.equal(frames, 0);
  total++;
  dropped++;
  poll();
  assert.equal(frames, 0);
  total++;
  poll();
  assert.equal(frames, 1);
  stop();
});

test("automatic reconnect survives a publisher restart and resets its retry budget only after displayed frames resume", async () => {
  let postCount = 0;
  const { client, clock, calls, peers } = fixture({
    response: async (_url, init) => {
      if (init?.method === "POST") {
        postCount++;
        if (postCount === 2 || postCount === 3)
          return Response.json(
            { detail: "Publisher is restarting." },
            { status: 503 },
          );
      }
      return null;
    },
  });
  await client.connect("live");
  peers[0].connection("connected");
  client.noteDisplayedFrame();
  peers[0].connection("disconnected");
  await clock.advance(1000);
  assert.equal(client.getState().status, "error");
  assert.match(client.getState().reason!, /Retry 2 of 5 in 2 s/);
  await clock.advance(2000);
  assert.match(client.getState().reason!, /Retry 3 of 5 in 4 s/);
  await clock.advance(4000);
  assert.equal(client.getState().status, "connecting");
  peers.at(-1)!.connection("connected");
  client.noteDisplayedFrame();
  assert.equal(client.getState().status, "live");
  peers.at(-1)!.connection("disconnected");
  assert.match(client.getState().reason!, /Retry 1 of 5 in 1 s/);
  assert.deepEqual(
    calls
      .filter((call) => call.method !== "GET")
      .slice(0, 3)
      .map((call) => call.method),
    ["POST", "DELETE", "POST"],
  );
  await client.dispose();
});

test("transient negotiation retries are bounded and an intentional reconnect can start a new budget", async () => {
  const { client, clock, calls } = fixture({
    response: async (_url, init) =>
      init?.method === "POST"
        ? Response.json({ detail: "No stream publisher." }, { status: 404 })
        : null,
  });
  await client.connect("live");
  await clock.advance(60000);
  assert.equal(calls.filter((call) => call.method === "POST").length, 6);
  assert.equal(client.getState().status, "error");
  assert.match(client.getState().reason!, /five automatic retries/);
  await clock.advance(60000);
  assert.equal(calls.filter((call) => call.method === "POST").length, 6);
  await client.connect("live");
  assert.equal(calls.filter((call) => call.method === "POST").length, 7);
  assert.match(client.getState().reason!, /Retry 1 of 5/);
  await client.dispose();
});
