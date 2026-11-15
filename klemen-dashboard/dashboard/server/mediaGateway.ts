/** A separate, fixed-destination WHEP gateway. It never invokes the station or MCP. */
import type { IncomingMessage, ServerResponse } from 'node:http';
import { constants, closeSync, fstatSync, openSync, readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

type Middleware = (req: IncomingMessage & { originalUrl?: string }, res: ServerResponse, next: () => void) => void;
type SourceMode = 'live' | 'simulation';
interface Profile { width: number; height: number; fps: number }
interface IceServer { urls: string | string[]; username?: string; credential?: string }
export interface MediaConfig {
  version: 1; whepUrl: string; cameraId: string; streamId: string; label: string;
  sourceMode: SourceMode; profile: Profile | null; username?: string; password?: string;
  statusUrl?: string; statusToken?: string; iceServers?: IceServer[];
}
export interface MediaGatewayOptions {
  config?: MediaConfig | null; fetch?: typeof fetch; requestTimeoutMs?: number;
  maxSessions?: number; sessionLifetimeMs?: number; now?: () => number; unavailableReason?: string;
  cleanupRetryMs?: number;
}
interface Producer { state: string; receivedAt: string | null; receiptAgeMs: number | null; counters: Record<string, number> }
interface Session { upstream: URL; expiresAt: number; cleanupAt?: number; cleanupAttempts?: number }
const PREFIX = '/api/media/v1';
const SDP_LIMIT = 65_536;
const STATUS_LIMIT = 32_768;
const ID = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/;
const UUID = '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}';
const SESSION_ROUTE = new RegExp(`^${PREFIX}/sessions/(${UUID})$`);
const PRIVATE_KEYS = new Set(['version', 'whepUrl', 'cameraId', 'streamId', 'label', 'sourceMode', 'profile', 'username', 'password', 'statusUrl', 'statusToken', 'iceServers']);

function fixedUrl(raw: string, whep = false): URL {
  const url = new URL(raw);
  const loopback = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
  if ((!loopback && url.protocol !== 'https:') || !['http:', 'https:'].includes(url.protocol) ||
      url.username || url.password || url.search || url.hash || raw.includes('%') ||
      !/^\/(?:[A-Za-z0-9_.-]+\/?)+$/.test(url.pathname) || (whep && !url.pathname.endsWith('/whep'))) {
    throw new TypeError('Media URLs require a fixed HTTPS endpoint (HTTP only on loopback), without embedded credentials.');
  }
  return url;
}
function boundedString(value: unknown, max: number): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= max && !/[\x00-\x1f\x7f]/.test(value);
}
function profile(value: unknown): value is Profile | null {
  if (value === null) return true;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const p = value as Profile;
  return Object.keys(p).length === 3 && Number.isSafeInteger(p.width) && p.width >= 16 && p.width <= 4096 &&
    Number.isSafeInteger(p.height) && p.height >= 16 && p.height <= 2160 &&
    Number.isFinite(p.fps) && p.fps >= 1 && p.fps <= 120;
}
/** Validate the server-owned configuration; never accept a browser-supplied destination. */
export function validateMediaConfig(value: unknown): MediaConfig {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('Invalid media configuration.');
  const c = value as MediaConfig;
  if (Object.keys(c).some(key => !PRIVATE_KEYS.has(key)) || c.version !== 1 ||
      !ID.test(c.cameraId ?? '') || !ID.test(c.streamId ?? '') || !boundedString(c.label, 100) ||
      !['live', 'simulation'].includes(c.sourceMode) || !profile(c.profile) || typeof c.whepUrl !== 'string') {
    throw new TypeError('Invalid media configuration.');
  }
  const target = fixedUrl(c.whepUrl, true);
  const loopback = ['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname);
  if ((c.username === undefined) !== (c.password === undefined) ||
      (c.username !== undefined && (!boundedString(c.username, 100) || c.username.includes(':') || !boundedString(c.password, 4096))) ||
      (!loopback && c.username === undefined)) throw new TypeError('Remote media requires configured viewer authentication.');
  if (c.statusUrl !== undefined) fixedUrl(c.statusUrl);
  if (c.statusToken !== undefined && (!c.statusUrl || !/^[!-~]{16,4096}$/.test(c.statusToken))) throw new TypeError('Invalid media status token.');
  if (c.iceServers !== undefined) {
    if (!Array.isArray(c.iceServers) || c.iceServers.length > 5) throw new TypeError('Invalid ICE servers.');
    for (const server of c.iceServers) {
      if (!server || typeof server !== 'object' || Object.keys(server).some(key => !['urls', 'username', 'credential'].includes(key))) throw new TypeError('Invalid ICE server.');
      const urls = typeof server.urls === 'string' ? [server.urls] : server.urls;
      if (!Array.isArray(urls) || urls.length < 1 || urls.length > 5 ||
          urls.some(url => !boundedString(url, 1024) || !/^(stun|stuns|turn|turns):[^\s<>]+$/.test(url)) ||
          (server.username !== undefined && !boundedString(server.username, 512)) ||
          (server.credential !== undefined && !boundedString(server.credential, 4096))) throw new TypeError('Invalid ICE server.');
    }
  }
  return structuredClone(c);
}
/** Credentials stay in a small owner-only local file, not the browser environment. */
export function readMediaConfig(file: string): MediaConfig {
  const fd = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.size > 16_384 || (stat.mode & 0o077) !== 0 ||
        (typeof process.getuid === 'function' && stat.uid !== process.getuid())) throw new TypeError('Media configuration must be an owner-only file.');
    return validateMediaConfig(JSON.parse(readFileSync(fd, 'utf8')));
  } finally { closeSync(fd); }
}
function headers(res: ServerResponse): void {
  res.setHeader('Cache-Control', 'private, no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
}
function json(res: ServerResponse, status: number, body: unknown): void {
  if (res.destroyed || res.writableEnded) return;
  headers(res); res.statusCode = status; res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}
function error(res: ServerResponse, status: number, detail: string): void { json(res, status, { detail }); }
async function limitedResponse(response: Response, max: number): Promise<string> {
  if (Number(response.headers.get('content-length') ?? '0') > max) { await response.body?.cancel(); throw new Error('oversized'); }
  const reader = response.body?.getReader();
  if (!reader) throw new Error('empty');
  let total = 0; const parts: Uint8Array[] = [];
  try {
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      total += value.byteLength; if (total > max) throw new Error('oversized'); parts.push(value);
    }
    return new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(parts));
  } finally { void reader.cancel().catch(() => {}); reader.releaseLock(); }
}
async function offerBody(req: IncomingMessage, signal: AbortSignal): Promise<string> {
  if (Number(req.headers['content-length'] ?? 0) > SDP_LIMIT) throw new RangeError('oversized');
  const chunks: Buffer[] = []; let bytes = 0;
  await new Promise<void>((resolve, reject) => {
    function cleanup() {
      req.removeListener('data', data); req.removeListener('end', end);
      req.removeListener('error', failed); req.removeListener('aborted', aborted);
      signal.removeEventListener('abort', aborted);
    }
    function failed(err: Error) { cleanup(); req.pause(); reject(err); }
    function aborted() { failed(new Error('aborted')); }
    function end() { cleanup(); resolve(); }
    function data(chunk: Buffer | string) {
      const raw = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk); bytes += raw.length;
      if (bytes > SDP_LIMIT) { failed(new RangeError('oversized')); return; } chunks.push(raw);
    }
    if (signal.aborted || req.aborted) { aborted(); return; }
    req.on('data', data); req.once('end', end); req.once('error', failed);
    req.once('aborted', aborted); signal.addEventListener('abort', aborted, { once: true });
  });
  const value = new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks));
  // This application is a receive-only video viewer, not a general media publisher.
  const media = value.split(/\r?\n/).filter(line => line.startsWith('m='));
  if (!value.startsWith('v=0') || media.length !== 1 || !media[0]?.startsWith('m=video ') ||
      !/^a=recvonly\r?$/m.test(value) || /^a=(sendrecv|sendonly)\r?$/m.test(value)) throw new TypeError('invalid offer');
  return value;
}
class MediaIdentityError extends Error {}
function producerStatus(value: unknown, config: MediaConfig): Producer {
  if (!value || typeof value !== 'object') throw new Error('status');
  const s = value as Record<string, unknown>;
  if (s.version !== 1 || s.cameraId !== config.cameraId || s.streamId !== config.streamId || s.sourceMode !== config.sourceMode ||
      !profile(s.profile)) throw new MediaIdentityError('status identity');
  const expected = config.profile; const actual = s.profile as Profile | null;
  if (expected && (!actual || actual.width !== expected.width || actual.height !== expected.height || actual.fps !== expected.fps)) throw new MediaIdentityError('status profile');
  if (!boundedString(s.state, 40)) throw new Error('status state');
  const receivedAt = s.receivedAt === null ? null : s.receivedAt;
  if (receivedAt !== null && (typeof receivedAt !== 'string' || !Number.isFinite(Date.parse(receivedAt)) || !/(?:Z|[+-]\d{2}:\d{2})$/.test(receivedAt))) throw new Error('status time');
  if (s.receiptAgeMs !== null && (typeof s.receiptAgeMs !== 'number' || !Number.isFinite(s.receiptAgeMs) || s.receiptAgeMs < 0)) throw new Error('status age');
  const counters: Record<string, number> = {};
  if (!s.counters || typeof s.counters !== 'object' || Array.isArray(s.counters) || Object.keys(s.counters).length > 30) throw new Error('status counters');
  for (const [key, val] of Object.entries(s.counters)) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,49}$/.test(key) || typeof val !== 'number' || !Number.isFinite(val) || val < 0) throw new Error('status counter');
    counters[key] = val;
  }
  return { state: s.state, receivedAt: receivedAt as string | null, receiptAgeMs: s.receiptAgeMs as number | null, counters };
}
export function createMediaGateway(options: MediaGatewayOptions = {}): { middleware: Middleware; close: () => Promise<void>; sessionCount: () => number } {
  const config = options.config ? validateMediaConfig(options.config) : null;
  const fetcher = options.fetch ?? globalThis.fetch;
  const now = options.now ?? Date.now;
  const timeoutMs = options.requestTimeoutMs ?? 12_000;
  const lifetime = options.sessionLifetimeMs ?? 3_600_000;
  const max = options.maxSessions ?? 4;
  const cleanupRetryMs = options.cleanupRetryMs ?? 1000;
  if (![timeoutMs, lifetime, max, cleanupRetryMs].every(value => Number.isSafeInteger(value) && value > 0)) throw new TypeError('Invalid media bounds.');
  const sessions = new Map<string, Session>(); let pending = 0; let closed = false; let identityBlocked = false;
  let producerRequest = 0; let appliedProducerRequest = 0; let identityEpoch = 0;
  let closing: Promise<void> | null = null;
  const removals = new Map<string, Promise<boolean>>();
  const tasks = new Set<Promise<void>>();
  const controllers = new Set<AbortController>();
  function track(task: Promise<void>): void {
    tasks.add(task); void task.then(() => tasks.delete(task), () => tasks.delete(task));
  }
  const destination = config ? fixedUrl(config.whepUrl, true) : null;
  const auth = config?.username !== undefined ? `Basic ${Buffer.from(`${config.username}:${config.password}`).toString('base64')}` : null;
  function authHeaders(): Record<string, string> { return auth ? { Authorization: auth } : {}; }
  async function readProducer(): Promise<Producer | null> {
    if (!config?.statusUrl) return null;
    const request = ++producerRequest;
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), Math.min(timeoutMs, 2500));
    controllers.add(controller);
    try {
      const response = await fetcher(config.statusUrl, { headers: config.statusToken ? { Authorization: `Bearer ${config.statusToken}` } : {},
        signal: controller.signal, redirect: 'error', credentials: 'omit', cache: 'no-store' });
      if (response.status !== 200 || response.headers.get('content-type')?.split(';')[0]?.trim() !== 'application/json') { void response.body?.cancel(); throw new Error('status unavailable'); }
      const producer = producerStatus(JSON.parse(await limitedResponse(response, STATUS_LIMIT)), config);
      if (request > appliedProducerRequest) {
        appliedProducerRequest = request;
        if (identityBlocked) identityEpoch++;
        identityBlocked = false;
      }
      if (identityBlocked) throw new MediaIdentityError('superseded status');
      return producer;
    } catch (err) {
      if (err instanceof MediaIdentityError && request > appliedProducerRequest) {
        appliedProducerRequest = request; identityBlocked = true; identityEpoch++;
        for (const id of sessions.keys()) void remove(id);
      }
      throw err;
    } finally { clearTimeout(timer); controllers.delete(controller); }
  }
  function remove(id: string): Promise<boolean> {
    const running = removals.get(id); if (running) return running;
    const session = sessions.get(id); if (!session) return Promise.resolve(true);
    const operation = (async () => {
      const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), Math.min(timeoutMs, 3000));
      controllers.add(controller);
      try {
        const response = await fetcher(session.upstream, { method: 'DELETE', headers: authHeaders(), redirect: 'error', credentials: 'omit', signal: controller.signal });
        void response.body?.cancel().catch(() => {});
        if (![200, 204, 404, 410].includes(response.status)) return false;
        sessions.delete(id); return true;
      } catch { return false; } finally {
        clearTimeout(timer); controllers.delete(controller);
        if (sessions.has(id)) {
          session.cleanupAttempts = (session.cleanupAttempts ?? 0) + 1;
          session.cleanupAt = now() + Math.min(cleanupRetryMs * 2 ** Math.min(session.cleanupAttempts - 1, 10), 30_000);
        }
      }
    })();
    removals.set(id, operation);
    void operation.then(() => removals.delete(id), () => removals.delete(id));
    return operation;
  }
  const reaper = setInterval(() => {
    for (const [id, session] of sessions) if ((session.cleanupAt ?? session.expiresAt) <= now()) void remove(id);
  }, Math.min(30_000, lifetime, cleanupRetryMs));
  reaper.unref();
  const middleware: Middleware = (req, res, next) => {
    const raw = req.originalUrl ?? req.url ?? '';
    if (!(raw === PREFIX || raw.startsWith(PREFIX + '/') || raw.startsWith(PREFIX + '?'))) { next(); return; }
    headers(res);
    if (closed) { error(res, 503, 'Media gateway is shutting down.'); return; }
    if (raw.includes('?') || raw.includes('#') || raw.includes('%')) { error(res, 404, 'Unknown media endpoint.'); return; }
    const sessionMatch = SESSION_ROUTE.exec(raw);
    if (!['GET', 'POST', 'DELETE'].includes(req.method ?? '')) { res.setHeader('Allow', 'GET, POST, DELETE'); error(res, 405, 'Unsupported media request.'); return; }
    if ((req.method === 'GET' || req.method === 'DELETE') && (req.headers['transfer-encoding'] ||
        (req.headers['content-length'] && req.headers['content-length'] !== '0'))) { error(res, 400, 'This media request must not contain a body.'); return; }
    if (req.method === 'GET' && raw === PREFIX + '/status') {
      track((async () => {
        let producer: Producer | null = null;
        let reason: string | null = config ? null : options.unavailableReason ?? 'Live video is not configured on this dashboard.';
        if (config?.statusUrl) {
          try { producer = await readProducer(); }
          catch { reason = identityBlocked ? 'The media producer identity, mode or profile does not match the configured stream.' : 'The media producer status is unavailable; freshness is determined from displayed frames.'; }
        }
        json(res, 200, { version: 1, configured: config !== null && !identityBlocked, cameraId: config?.cameraId ?? null,
          label: config?.label ?? 'Live camera', streamId: config?.streamId ?? null, sourceMode: config?.sourceMode ?? 'live',
          profile: config?.profile ?? null, whepPath: config && !identityBlocked ? PREFIX + '/whep' : null,
          iceServers: config?.iceServers ?? [], producer, reason, checkedAt: new Date(now()).toISOString() });
      })()); return;
    }
    if (req.method === 'DELETE' && sessionMatch) {
      track(remove(sessionMatch[1]!).then(ok => {
        if (ok) { res.statusCode = 204; res.end(); } else error(res, 502, 'Media session cleanup is pending.');
      })); return;
    }
    if (req.method !== 'POST' || raw !== PREFIX + '/whep') { error(res, 404, 'Unknown media endpoint.'); return; }
    if (!config || !destination) { error(res, 503, 'Live video is not configured on this dashboard.'); return; }
    if (req.headers['content-type']?.split(';')[0]?.trim() !== 'application/sdp') { error(res, 415, 'A receive-only SDP offer is required.'); return; }
    if (sessions.size + pending >= max) { error(res, 429, 'The media viewer limit has been reached. Close another viewer and retry.'); return; }
    pending++;
    const control = new AbortController(); const timer = setTimeout(() => {
      control.abort();
      if (!res.headersSent) res.setHeader('Connection', 'close');
      if (!res.writableEnded) error(res, 504, 'Media negotiation timed out.');
    }, timeoutMs);
    controllers.add(control);
    // Read through a bounded upstream POST even if the local caller leaves so its Location can be cleaned up.
    let localGone = false;
    const gone = () => { localGone = true; };
    res.once('close', gone); req.once('aborted', gone);
    track((async () => {
      let created: string | null = null; let parsedOffer = false;
      try {
        const body = await offerBody(req, control.signal); parsedOffer = true;
        if (localGone || control.signal.aborted) return;
        if (closed) { error(res, 503, 'Media gateway is shutting down.'); return; }
        try { await readProducer(); } catch { /* A known identity mismatch remains blocked until verified again. */ }
        if (identityBlocked) { error(res, 409, 'The media producer does not match the configured stream.'); return; }
        if (localGone || control.signal.aborted) return;
        if (closed) { error(res, 503, 'Media gateway is shutting down.'); return; }
        const expectedIdentityEpoch = identityEpoch;
        const response = await fetcher(destination, { method: 'POST', body,
          headers: { ...authHeaders(), 'Content-Type': 'application/sdp', Accept: 'application/sdp' },
          signal: control.signal, redirect: 'error', credentials: 'omit', cache: 'no-store' });
        if (response.status !== 201) {
          void response.body?.cancel().catch(() => {});
          error(res, response.status === 404 ? 503 : 502, 'The configured video stream is unavailable.'); return;
        }
        const location = response.headers.get('location');
        if (!location || location.length > 2048 || location.includes('%')) throw new Error('missing location');
        const upstream = new URL(location, destination);
        const prefix = destination.pathname + '/';
        if (upstream.origin !== destination.origin || !upstream.pathname.startsWith(prefix) ||
            !new RegExp(`^${UUID}$`).test(upstream.pathname.slice(prefix.length)) || upstream.search || upstream.hash || upstream.username || upstream.password) throw new Error('invalid location');
        created = randomUUID(); sessions.set(created, { upstream, expiresAt: now() + lifetime });
        if (response.headers.get('content-type')?.split(';')[0]?.trim() !== 'application/sdp') throw new Error('invalid answer type');
        const answer = await limitedResponse(response, SDP_LIMIT);
        if (!answer.startsWith('v=0') || !/^m=video /m.test(answer)) throw new Error('invalid answer');
        if (localGone || control.signal.aborted || res.writableEnded) { await remove(created); return; }
        if (closed) { await remove(created); error(res, 503, 'Media gateway is shutting down.'); return; }
        if (identityBlocked || identityEpoch !== expectedIdentityEpoch) {
          await remove(created); error(res, 409, 'The media producer identity changed during negotiation.'); return;
        }
        res.statusCode = 201; res.setHeader('Content-Type', 'application/sdp');
        res.setHeader('Location', `${PREFIX}/sessions/${created}`); res.end(answer);
      } catch (err) {
        if (created) await remove(created);
        error(res, control.signal.aborted ? 504 : !parsedOffer && err instanceof RangeError ? 413 : !parsedOffer ? 400 : 502,
          !parsedOffer && err instanceof RangeError ? 'The SDP offer exceeds the size limit.' : !parsedOffer ? 'Invalid receive-only video offer.' : 'Video negotiation failed.');
      } finally {
        pending--; clearTimeout(timer); controllers.delete(control); res.removeListener('close', gone); req.removeListener('aborted', gone);
      }
    })());
  };
  return { middleware, sessionCount: () => sessions.size, close: () => {
    if (closing) return closing;
    closed = true; clearInterval(reaper);
    // Existing negotiations may still return a cleanup Location. Drain them before shutdown.
    let expired = false;
    const shutdownMs = Math.min(16_000, timeoutMs + Math.min(timeoutMs, 3000) + 100);
    let shutdownTimer: ReturnType<typeof setTimeout>;
    const deadline = new Promise<void>(resolve => {
      shutdownTimer = setTimeout(() => {
        expired = true; for (const controller of controllers) controller.abort(); resolve();
      }, shutdownMs);
    });
    const drain = async () => {
      for (const id of sessions.keys()) void remove(id);
      while (!expired) {
        const active = [...tasks, ...removals.values()];
        if (active.length) { await Promise.allSettled(active); continue; }
        if (sessions.size === 0) return;
        let nextRetry = 1000;
        for (const [id, session] of sessions) {
          const due = session.cleanupAt ?? now();
          if (due <= now()) void remove(id);
          else nextRetry = Math.min(nextRetry, due - now());
        }
        if (removals.size === 0) await new Promise<void>(resolve => {
          const timer = setTimeout(resolve, nextRetry);
          void deadline.then(() => { clearTimeout(timer); resolve(); });
        });
      }
    };
    closing = Promise.race([drain(), deadline]).finally(() => { clearTimeout(shutdownTimer); });
    return closing;
  } };
}

/** Invalid optional media setup does not stop the existing records dashboard. */
export function mediaGatewayFromEnvironment(environment: NodeJS.ProcessEnv = process.env) {
  const file = environment.MORPH_MEDIA_CONFIG_FILE;
  if (!file) return createMediaGateway();
  try { return createMediaGateway({ config: readMediaConfig(file) }); }
  catch { return createMediaGateway({ unavailableReason: 'The server media configuration is invalid or unavailable.' }); }
}
