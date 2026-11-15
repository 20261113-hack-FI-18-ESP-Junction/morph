import { readMediaStatistics, type InboundSample } from "./stats.ts";
import {
  emptyStatistics,
  initialMediaState,
  type MediaConfiguration,
  type MediaSourceMode,
  type MediaState,
} from "./types.ts";

export interface MediaClock {
  now(): number;
  after(callback: () => void, milliseconds: number): unknown;
  cancel(handle: unknown): void;
}

interface MediaClientOptions {
  fetch?: typeof fetch;
  createPeerConnection?: (configuration: RTCConfiguration) => RTCPeerConnection;
  createMediaStream?: () => MediaStream;
  origin?: string;
  clock?: MediaClock;
  onStream: (stream: MediaStream | null) => void;
  staleAfterMs?: number;
  reconnectAfterMs?: number;
  connectionTimeoutMs?: number;
}

class MediaConnectionError extends Error {
  constructor(
    message: string,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}
const transientStatus = (status: number) =>
  [404, 408, 409, 425, 429].includes(status) || status >= 500;

const browserClock: MediaClock = {
  now: () => performance.now(),
  after: (callback, delay) => globalThis.setTimeout(callback, delay),
  cancel: (handle) =>
    globalThis.clearTimeout(handle as ReturnType<typeof globalThis.setTimeout>),
};
const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const optionalText = (value: unknown) =>
  value === null || typeof value === "string";
const isTimestamp = (value: unknown) =>
  typeof value === "string" && Number.isFinite(Date.parse(value));
const positive = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) && value > 0;
const nonnegative = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;

export function parseMediaConfiguration(value: unknown): MediaConfiguration {
  if (
    !isRecord(value) ||
    value.version !== 1 ||
    typeof value.configured !== "boolean" ||
    !optionalText(value.cameraId) ||
    typeof value.label !== "string" ||
    !optionalText(value.streamId) ||
    !["live", "simulation"].includes(value.sourceMode as string) ||
    !optionalText(value.reason) ||
    !isTimestamp(value.checkedAt) ||
    !Array.isArray(value.iceServers) ||
    (value.whepPath !== null && value.whepPath !== "/api/media/v1/whep")
  ) {
    throw new Error("The media configuration is not supported.");
  }
  if (
    value.configured &&
    (!value.cameraId || !value.streamId || !value.whepPath)
  )
    throw new Error("The media configuration is incomplete.");
  if (
    value.profile !== null &&
    (!isRecord(value.profile) ||
      !positive(value.profile.width) ||
      !positive(value.profile.height) ||
      !positive(value.profile.fps))
  )
    throw new Error("The advertised media profile is invalid.");
  for (const server of value.iceServers) {
    if (!isRecord(server))
      throw new Error("The media ICE configuration is invalid.");
    const urls = typeof server.urls === "string" ? [server.urls] : server.urls;
    if (
      !Array.isArray(urls) ||
      !urls.length ||
      urls.some(
        (url) =>
          typeof url !== "string" || !/^(stun|stuns|turn|turns):/i.test(url),
      ) ||
      (server.username !== undefined && typeof server.username !== "string") ||
      (server.credential !== undefined && typeof server.credential !== "string")
    )
      throw new Error("The media ICE configuration is invalid.");
  }
  if (
    value.producer !== null &&
    (!isRecord(value.producer) ||
      typeof value.producer.state !== "string" ||
      !(
        value.producer.receivedAt === null ||
        isTimestamp(value.producer.receivedAt)
      ) ||
      !(
        value.producer.receiptAgeMs === null ||
        nonnegative(value.producer.receiptAgeMs)
      ) ||
      !isRecord(value.producer.counters) ||
      Object.values(value.producer.counters).some((item) => !nonnegative(item)))
  ) {
    throw new Error("The media publisher status is invalid.");
  }
  return value as unknown as MediaConfiguration;
}

export function validateSessionLocation(
  location: string | null,
  origin: string,
): string {
  if (!location)
    throw new Error("The media session response has no cleanup address.");
  const url = new URL(location, origin);
  if (
    url.origin !== new URL(origin).origin ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    !/^\/api\/media\/v1\/sessions\/[a-zA-Z0-9-]+$/.test(url.pathname)
  ) {
    throw new Error(
      "The media session response contains an invalid cleanup address.",
    );
  }
  return url.pathname;
}

function gathered(peer: RTCPeerConnection, signal: AbortSignal): Promise<void> {
  if (signal.aborted)
    return Promise.reject(new DOMException("Aborted", "AbortError"));
  if (peer.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      peer.removeEventListener("icegatheringstatechange", changed);
      signal.removeEventListener("abort", aborted);
    };
    const changed = () => {
      if (peer.iceGatheringState === "complete") {
        cleanup();
        resolve();
      }
    };
    const aborted = () => {
      cleanup();
      reject(new DOMException("Aborted", "AbortError"));
    };
    peer.addEventListener("icegatheringstatechange", changed);
    signal.addEventListener("abort", aborted, { once: true });
    changed();
  });
}

function abortable<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const aborted = () => reject(new DOMException("Aborted", "AbortError"));
    signal.addEventListener("abort", aborted, { once: true });
    operation
      .then(resolve, reject)
      .finally(() => signal.removeEventListener("abort", aborted));
    if (signal.aborted) aborted();
  });
}

/** Owns only a receive-only media session; it never accesses local capture or robot APIs. */
export class LiveMediaClient {
  private state = initialMediaState();
  private readonly listeners = new Set<() => void>();
  private readonly fetcher: typeof fetch;
  private readonly peerFactory: (
    configuration: RTCConfiguration,
  ) => RTCPeerConnection;
  private readonly streamFactory: () => MediaStream;
  private readonly origin: string;
  private readonly clock: MediaClock;
  private readonly staleAfterMs: number;
  private readonly reconnectAfterMs: number;
  private readonly connectionTimeoutMs: number;
  private generation = 0;
  private stopped = false;
  private source: MediaSourceMode = "live";
  private peer: RTCPeerConnection | null = null;
  private abort: AbortController | null = null;
  private session: string | null = null;
  private pending: Promise<void> | null = null;
  private tickTimer: unknown = null;
  private reconnectTimer: unknown = null;
  private deadlineTimer: unknown = null;
  private lastFrameAt: number | null = null;
  private connectedAt: number | null = null;
  private previousStats: InboundSample | null = null;
  private negotiated = false;
  private statsPending = false;
  private retryAttempts = 0;
  private readonly pendingCleanup = new Set<string>();

  constructor(private readonly options: MediaClientOptions) {
    this.fetcher = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.peerFactory =
      options.createPeerConnection ??
      ((configuration) => new RTCPeerConnection(configuration));
    this.streamFactory = options.createMediaStream ?? (() => new MediaStream());
    this.origin = options.origin ?? globalThis.location.origin;
    this.clock = options.clock ?? browserClock;
    this.staleAfterMs = options.staleAfterMs ?? 2500;
    this.reconnectAfterMs = options.reconnectAfterMs ?? 8000;
    this.connectionTimeoutMs = options.connectionTimeoutMs ?? 15000;
  }

  getState = (): MediaState => this.state;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private update(patch: Partial<MediaState>): void {
    if (this.stopped) return;
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener();
  }

  connect(source: MediaSourceMode): Promise<void> {
    this.retryAttempts = 0;
    return this.begin(source);
  }

  private begin(source: MediaSourceMode): Promise<void> {
    this.stopped = false;
    this.source = source;
    const generation = ++this.generation;
    const previous = this.pending;
    const cleanup = this.release();
    this.update({
      status: "connecting",
      configuration: null,
      reason: "Checking the media configuration…",
      frameAgeMs: null,
      statistics: emptyStatistics(),
    });
    const run = async () => {
      // An old POST must settle and its known session must be deleted before another POST.
      await Promise.all([previous?.catch(() => {}), cleanup]);
      if (!this.active(generation)) return;
      for (const session of this.pendingCleanup) {
        if (!(await this.deleteSession(session))) {
          if (this.active(generation))
            this.update({
              status: "error",
              reason:
                "The previous preview session could not be released. Check the media gateway before reconnecting.",
            });
          return;
        }
      }
      if (!this.active(generation)) return;
      await this.open(generation, source);
    };
    this.pending = run();
    return this.pending;
  }

  private active(generation: number): boolean {
    return !this.stopped && generation === this.generation;
  }

  private async open(
    generation: number,
    source: MediaSourceMode,
  ): Promise<void> {
    const abort = new AbortController();
    this.abort = abort;
    let timedOut = false;
    this.deadlineTimer = this.clock.after(() => {
      timedOut = true;
      abort.abort();
    }, this.connectionTimeoutMs);
    try {
      const response = await this.fetcher("/api/media/v1/status", {
        signal: abort.signal,
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!response.ok)
        throw new MediaConnectionError(
          "The media gateway is unavailable.",
          transientStatus(response.status),
        );
      const configuration = parseMediaConfiguration(await response.json());
      if (!this.active(generation)) return;
      if (abort.signal.aborted) throw new DOMException("Aborted", "AbortError");
      this.update({ configuration });
      if (!configuration.configured || configuration.sourceMode !== source) {
        this.update({
          status: "unconfigured",
          reason:
            configuration.configured && configuration.sourceMode !== source
              ? `The configured preview belongs to ${configuration.sourceMode} mode. Select that source to view it.`
              : (configuration.reason ?? "No preview publisher is configured."),
        });
        return;
      }
      const peer = this.peerFactory({ iceServers: configuration.iceServers });
      this.peer = peer;
      peer.addTransceiver("video", { direction: "recvonly" });
      peer.ontrack = (event) => {
        if (
          !this.active(generation) ||
          this.peer !== peer ||
          event.track.kind !== "video"
        )
          return;
        const stream = event.streams[0] ?? this.streamFactory();
        if (!event.streams.length) stream.addTrack(event.track);
        this.options.onStream(stream);
      };
      peer.onconnectionstatechange = () => {
        if (!this.active(generation) || this.peer !== peer) return;
        if (
          peer.connectionState === "failed" ||
          peer.connectionState === "disconnected" ||
          peer.connectionState === "closed"
        ) {
          this.update({
            status: "disconnected",
            reason: "The media connection was interrupted. Reconnecting…",
          });
          this.scheduleReconnect(generation);
        }
      };
      this.update({ reason: "Negotiating a receive-only video connection…" });
      const offer = await abortable(peer.createOffer(), abort.signal);
      await abortable(peer.setLocalDescription(offer), abort.signal);
      await gathered(peer, abort.signal);
      if (!this.active(generation)) return;
      if (!peer.localDescription?.sdp)
        throw new Error("The browser did not produce a media offer.");
      const answer = await this.fetcher(configuration.whepPath!, {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          Accept: "application/sdp",
        },
        body: peer.localDescription.sdp,
        signal: abort.signal,
        credentials: "same-origin",
      });
      if (answer.status !== 201) {
        let detail = "The preview publisher could not accept the connection.";
        try {
          const error: unknown = await answer.json();
          if (isRecord(error) && typeof error.detail === "string")
            detail = error.detail.slice(0, 300);
        } catch {
          /* Keep a credential-free fallback. */
        }
        throw new MediaConnectionError(detail, transientStatus(answer.status));
      }
      const session = validateSessionLocation(
        answer.headers.get("Location"),
        this.origin,
      );
      if (!this.active(generation)) {
        await this.deleteSession(session);
        return;
      }
      this.session = session;
      if (
        answer.headers.get("Content-Type")?.split(";", 1)[0].trim() !==
        "application/sdp"
      )
        throw new Error("The media answer is not SDP.");
      const sdp = await answer.text();
      if (!this.active(generation)) return;
      await abortable(
        peer.setRemoteDescription({ type: "answer", sdp }),
        abort.signal,
      );
      if (!this.active(generation)) return;
      if (abort.signal.aborted) throw new DOMException("Aborted", "AbortError");
      this.negotiated = true;
      this.connectedAt = this.clock.now();
      this.update({
        status: this.state.displayVisible ? "connecting" : "frozen",
        reason: this.state.displayVisible
          ? "Waiting for the first displayed video frame…"
          : "Preview is hidden; display freshness monitoring is suspended.",
      });
      this.scheduleTick(generation);
    } catch (error) {
      if (!this.active(generation)) return;
      this.update({
        status: "error",
        reason: timedOut
          ? "The media connection timed out. Check the publisher and network path."
          : error instanceof Error
            ? error.message
            : "The media connection could not be established.",
      });
      await this.release();
      if (!this.active(generation)) return;
      if (this.pendingCleanup.size > 0) {
        this.update({
          reason:
            "The previous preview session could not be released. Check the media gateway before reconnecting.",
        });
      } else if (
        timedOut ||
        error instanceof TypeError ||
        (error instanceof MediaConnectionError && error.retryable)
      ) {
        this.scheduleReconnect(generation);
      }
    } finally {
      if (this.active(generation) && this.deadlineTimer !== null) {
        this.clock.cancel(this.deadlineTimer);
        this.deadlineTimer = null;
      }
    }
  }

  noteDisplayedFrame(): void {
    if (
      this.stopped ||
      !this.peer ||
      !this.negotiated ||
      !this.state.displayVisible
    )
      return;
    if (
      ["disconnected", "failed", "closed"].includes(this.peer.connectionState)
    )
      return;
    this.lastFrameAt = this.clock.now();
    this.retryAttempts = 0;
    if (
      this.reconnectTimer !== null &&
      this.peer.connectionState === "connected"
    ) {
      this.clock.cancel(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    // Frame pixels and per-frame counter updates never enter React state.
    if (this.state.status !== "live")
      this.update({ status: "live", reason: null, frameAgeMs: 0 });
  }

  setDisplayVisible(visible: boolean): void {
    if (visible === this.state.displayVisible) return;
    this.lastFrameAt = null;
    this.connectedAt = this.clock.now();
    if (this.reconnectTimer !== null) {
      this.clock.cancel(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.update({
      displayVisible: visible,
      frameAgeMs: null,
      ...(this.negotiated
        ? {
            status: visible ? ("connecting" as const) : ("frozen" as const),
            reason: visible
              ? "Waiting for a newly displayed frame…"
              : "Preview is hidden; display freshness monitoring is suspended.",
          }
        : {}),
    });
  }

  private scheduleTick(generation: number): void {
    this.tickTimer = this.clock.after(() => {
      this.tickTimer = null;
      void this.tick(generation);
    }, 1000);
  }

  private async tick(generation: number): Promise<void> {
    const peer = this.peer;
    if (!this.active(generation) || !peer) return;
    const age =
      this.lastFrameAt === null
        ? null
        : Math.max(0, this.clock.now() - this.lastFrameAt);
    const waitingAge =
      this.clock.now() - (this.connectedAt ?? this.clock.now());
    if (
      this.state.displayVisible &&
      (age !== null
        ? age >= this.staleAfterMs
        : waitingAge >= this.staleAfterMs)
    ) {
      this.update({
        status: "frozen",
        reason:
          age === null
            ? "No displayed video frame has been observed."
            : "No new video frame has been displayed recently.",
        frameAgeMs: age,
      });
      if ((age ?? waitingAge) >= this.reconnectAfterMs)
        this.scheduleReconnect(generation);
    } else this.update({ frameAgeMs: age });
    // A slow getStats call must never suspend the independent freshness watchdog.
    this.scheduleTick(generation);
    if (this.statsPending) return;
    this.statsPending = true;
    try {
      const result = readMediaStatistics(
        await peer.getStats(),
        this.previousStats,
      );
      if (!this.active(generation) || this.peer !== peer) return;
      this.previousStats = result.sample;
      this.update({ statistics: result.statistics });
    } catch {
      if (!this.active(generation)) return;
      this.update({ statistics: emptyStatistics() });
    } finally {
      if (this.active(generation)) this.statsPending = false;
    }
  }

  private scheduleReconnect(generation: number): void {
    if (this.reconnectTimer !== null || !this.active(generation)) return;
    if (this.retryAttempts >= 5) {
      this.update({
        status: "error",
        reason:
          "Video did not recover after five automatic retries. Check the publisher and network, then reconnect.",
      });
      return;
    }
    const delay = Math.min(1000 * 2 ** this.retryAttempts, 10000);
    this.retryAttempts++;
    this.update({
      reason: `${this.state.reason ?? "The preview needs to reconnect."} Retry ${this.retryAttempts} of 5 in ${delay / 1000} s.`,
    });
    this.reconnectTimer = this.clock.after(() => {
      this.reconnectTimer = null;
      if (this.active(generation)) void this.begin(this.source);
    }, delay);
  }

  private async deleteSession(session: string): Promise<boolean> {
    this.pendingCleanup.add(session);
    const abort = new AbortController();
    const deadline = this.clock.after(() => abort.abort(), 3000);
    try {
      const response = await this.fetcher(session, {
        method: "DELETE",
        credentials: "same-origin",
        signal: abort.signal,
        keepalive: true,
      });
      if (response.ok || response.status === 404 || response.status === 410) {
        this.pendingCleanup.delete(session);
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      this.clock.cancel(deadline);
    }
  }

  private release(): Promise<boolean> {
    this.abort?.abort();
    this.abort = null;
    for (const timer of [
      this.tickTimer,
      this.reconnectTimer,
      this.deadlineTimer,
    ])
      if (timer !== null) this.clock.cancel(timer);
    this.tickTimer = this.reconnectTimer = this.deadlineTimer = null;
    if (this.peer) {
      this.peer.ontrack = null;
      this.peer.onconnectionstatechange = null;
      this.peer.close();
      this.peer = null;
    }
    this.options.onStream(null);
    this.negotiated = false;
    this.lastFrameAt = this.connectedAt = null;
    this.previousStats = null;
    this.statsPending = false;
    const session = this.session;
    this.session = null;
    return session ? this.deleteSession(session) : Promise.resolve(true);
  }

  async dispose(): Promise<void> {
    this.stopped = true;
    ++this.generation;
    this.listeners.clear();
    await Promise.all([this.release(), this.pending?.catch(() => {})]);
  }
}
