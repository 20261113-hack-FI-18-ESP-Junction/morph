/** Server-only transport: dashboard -> shared Mac MCP -> Intel records/review worker. */
import { constants } from 'node:fs';
import { open, readFile } from 'node:fs/promises';
import https from 'node:https';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

export type ToolCall = (name: string, args: Record<string, unknown>, signal?: AbortSignal) => Promise<Record<string, unknown>>;
const TOOL_NAMES = new Set(['enqueue_station_read', 'enqueue_station_request', 'read_station_response']);
const PSEUDO_ORIGIN = 'http://morph-mcp-relay.invalid';
export const MCP_PROXY_ORIGIN = PSEUDO_ORIGIN;
// Passed only to our in-process fetch adapter. It is never a station or MCP credential.
export const MCP_LOCAL_TRANSPORT_MARKER = 'morph-local-mcp-read-transport-no-credential';
const FAILURE = 'The shared MCP station request is unavailable.';

async function privateJson(file: string): Promise<Record<string, unknown>> {
  const handle = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.size > 64_000 || (info.mode & 0o077) !== 0 ||
      (typeof process.getuid === 'function' && info.uid !== process.getuid())) throw new Error(FAILURE);
    return JSON.parse(await handle.readFile('utf8'));
  } finally { await handle.close(); }
}

/** Match the existing context_mcp/connect_intel.py stateless, JSON MCP transport. */
export function createMcpToolClient(pairingDir: string): ToolCall {
  let requestId = 0;
  let protocol: Promise<string> | undefined;
  const rpc = async (payload: Record<string, unknown>, version: string | undefined, signal?: AbortSignal) => {
    try {
      const config = await privateJson(path.join(pairingDir, 'connection.json'));
      const url = new URL(String(config.url));
      const token = config.token;
      if (url.protocol !== 'https:' || url.pathname !== '/mcp' || url.username || url.password || url.search || url.hash ||
        typeof token !== 'string' || token.length < 32 || token.length > 4096 || !/^[!-~]+$/.test(token)) throw new Error(FAILURE);
      const ca = await readFile(path.join(pairingDir, 'morph-ca.pem'));
      const body = Buffer.from(JSON.stringify(payload));
      return await new Promise<Record<string, any>>((resolve, reject) => {
        const combined = signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000);
        const req = https.request(url, { method: 'POST', ca, rejectUnauthorized: true, signal: combined,
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream', 'Content-Length': body.length,
            ...(version ? { 'MCP-Protocol-Version': version } : {}) } }, res => {
          const chunks: Buffer[] = []; let size = 0;
          res.on('data', (chunk: Buffer) => {
            size += chunk.length;
            if (size > 2 * 1024 * 1024) { req.destroy(); reject(new Error(FAILURE)); }
            else chunks.push(chunk);
          });
          res.once('error', () => reject(new Error(FAILURE)));
          res.once('end', () => {
            try {
              if (![200, 202, 204].includes(res.statusCode ?? 0)) throw new Error(FAILURE);
              const bytes = Buffer.concat(chunks);
              if (bytes.length && !(res.headers['content-type'] ?? '').startsWith('application/json')) throw new Error(FAILURE);
              const result = bytes.length ? JSON.parse(bytes.toString('utf8')) : {};
              if (result.error || (payload.id !== undefined && (result.jsonrpc !== '2.0' || result.id !== payload.id))) throw new Error(FAILURE);
              resolve(result);
            } catch { reject(new Error(FAILURE)); }
          });
        });
        req.once('error', () => reject(new Error(FAILURE)));
        req.end(body);
      });
    } catch { throw new Error(FAILURE); }
  };
  return async (name, args, signal) => {
    if (!TOOL_NAMES.has(name)) throw new Error(FAILURE);
    if (!protocol) {
      protocol = (async () => {
        const hello = await rpc({ jsonrpc: '2.0', id: ++requestId, method: 'initialize', params: {
          protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'morph-dashboard-mcp', version: '1.0' },
        } }, undefined, signal);
        const version = hello.result?.protocolVersion;
        if (version !== '2025-11-25') throw new Error(FAILURE);
        await rpc({ jsonrpc: '2.0', method: 'notifications/initialized' }, version, signal);
        return version;
      })();
      protocol.catch(() => { protocol = undefined; });
    }
    const version = await protocol;
    const reply = await rpc({ jsonrpc: '2.0', id: ++requestId, method: 'tools/call', params: { name, arguments: args } }, version, signal);
    if (reply.result?.isError || !reply.result?.structuredContent || typeof reply.result.structuredContent !== 'object') throw new Error(FAILURE);
    return reply.result.structuredContent;
  };
}

interface Options { callTool: ToolCall; stationId: string; pollMs?: number; timeoutMs?: number; maxBytes?: number }
async function bounded<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) { void operation.catch(() => {}); throw new Error(FAILURE); }
  let rejectOnAbort: () => void;
  const aborted = new Promise<never>((_resolve, reject) => {
    rejectOnAbort = () => reject(new Error(FAILURE));
    signal.addEventListener('abort', rejectOnAbort, { once: true });
  });
  try { return await Promise.race([operation, aborted]); }
  finally { signal.removeEventListener('abort', rejectOnAbort!); }
}
interface RelayResponse { status: number; contentType: string; bytes: Buffer; capturedAt: string; completedAt: string }
interface Mutation { body: string; intent: 'record-review' | 'evidence-analysis' }
function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new Error(FAILURE)); return; }
    const abort = () => { clearTimeout(timer); reject(new Error(FAILURE)); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    signal.addEventListener('abort', abort, { once: true });
  });
}

/** Fresh relay UUID per request; application submission IDs and body bytes stay unchanged. */
export function createMcpStationFetch(options: Options): typeof fetch {
  const pollMs = options.pollMs ?? 250, timeoutMs = options.timeoutMs ?? 35_000, maxBytes = options.maxBytes ?? 4 * 1024 * 1024;
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(options.stationId) ||
      ![pollMs, timeoutMs, maxBytes].every(n => Number.isSafeInteger(n) && n > 0)) throw new TypeError('Invalid MCP relay configuration.');
  const read = async (url: URL, outer?: AbortSignal, mutation?: Mutation): Promise<RelayResponse> => {
    const signal = outer ? AbortSignal.any([outer, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs);
    const request_id = randomUUID();
    const query: Record<string, string | string[]> = {};
    for (const [key, value] of url.searchParams) {
      const previous = query[key];
      if (previous === undefined) query[key] = value;
      else if (url.pathname === '/api/v1/analysis/context' && key === 'sessionIds' && typeof previous === 'string')
        query[key] = [previous, value];
      else throw new Error(FAILURE);
    }
    if (url.pathname === '/api/v1/events') query.once = 'true';
    const args = { station_id: options.stationId, request_id, path: decodeURIComponent(url.pathname), query,
      ...(mutation ? { method: 'POST', body: mutation.body, intent: mutation.intent } : {}) };
    const queued = await bounded(options.callTool(mutation ? 'enqueue_station_request' : 'enqueue_station_read', args, signal), signal);
    if (queued.request_id !== request_id || !['queued', 'claimed', 'ready'].includes(String(queued.state))) throw new Error(FAILURE);
    let offset = 0, base64 = '', identity: string | undefined;
    let metadata: Record<string, unknown> | undefined;
    while (!signal.aborted) {
      const result = await bounded(options.callTool('read_station_response', { station_id: options.stationId, request_id, offset, limit: 60_000 }, signal), signal);
      if (result.request_id !== undefined && result.request_id !== request_id) throw new Error(FAILURE);
      if (['queued', 'claimed'].includes(String(result.state))) { await pause(pollMs, signal); continue; }
      if (result.state !== 'ready') throw new Error(FAILURE);
      const currentIdentity = JSON.stringify([result.status_code, result.content_type, result.response_sha256, result.captured_at, result.completed_at]);
      if (identity !== undefined && identity !== currentIdentity) throw new Error(FAILURE);
      identity = currentIdentity; metadata = result;
      if (result.offset !== offset || typeof result.body_base64 !== 'string' || !/^[A-Za-z0-9+/=]*$/.test(result.body_base64)) throw new Error(FAILURE);
      base64 += result.body_base64;
      if (base64.length > Math.ceil(maxBytes / 3) * 4) throw new Error(FAILURE);
      if (result.next_offset === null) break;
      if (!Number.isSafeInteger(result.next_offset) || Number(result.next_offset) !== base64.length || Number(result.next_offset) <= offset) throw new Error(FAILURE);
      offset = Number(result.next_offset);
    }
    if (signal.aborted || !metadata) throw new Error(FAILURE);
    const bytes = Buffer.from(base64, 'base64');
    if (bytes.toString('base64') !== base64 || bytes.length > maxBytes ||
      createHash('sha256').update(bytes).digest('hex') !== metadata.response_sha256 ||
      !Number.isSafeInteger(metadata.status_code) || Number(metadata.status_code) < 200 || Number(metadata.status_code) > 599 ||
      (Number(metadata.status_code) >= 300 && Number(metadata.status_code) < 400) ||
      typeof metadata.content_type !== 'string' || typeof metadata.captured_at !== 'string' || typeof metadata.completed_at !== 'string' ||
      !Number.isFinite(Date.parse(metadata.captured_at)) || !Number.isFinite(Date.parse(metadata.completed_at))) throw new Error(FAILURE);
    return { status: Number(metadata.status_code), contentType: metadata.content_type, bytes,
      capturedAt: metadata.captured_at, completedAt: metadata.completed_at };
  };
  return (async (input, init) => {
    let write = false;
    try {
      const url = new URL(typeof input === 'string' || input instanceof URL ? String(input) : input.url);
      const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
      if (url.origin !== PSEUDO_ORIGIN || !url.pathname.startsWith('/api/v1/') || !['GET', 'POST'].includes(method)) throw new Error(FAILURE);
      const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined);
      const requestHeaders = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
      let mutation: Mutation | undefined;
      if (method === 'POST') {
        const pathname = decodeURIComponent(url.pathname);
        const review = /^\/api\/v1\/cycles\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\/review$/.test(pathname);
        const analysis = pathname === '/api/v1/analysis/reports';
        const intent = requestHeaders.get('X-Morph-Intent');
        if ((!review && !analysis) || url.search || intent !== (review ? 'record-review' : 'evidence-analysis') ||
          requestHeaders.get('Content-Type')?.split(';', 1)[0]?.trim().toLowerCase() !== 'application/json' ||
          typeof init?.body !== 'string' || Buffer.byteLength(init.body, 'utf8') > 65536) throw new Error(FAILURE);
        const value: unknown = JSON.parse(init.body);
        if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(FAILURE);
        const object = value as Record<string, unknown>;
        const validId = (id: unknown) => typeof id === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(id);
        if (review ? !validId(object.id) || !validId(object.eventId) : !validId(object.requestId)) throw new Error(FAILURE);
        mutation = { body: init.body, intent: intent as Mutation['intent'] };
        write = true;
      } else if (init?.body || requestHeaders.has('X-Morph-Intent')) throw new Error(FAILURE);
      const resumed = requestHeaders.get('Last-Event-ID');
      if (url.pathname === '/api/v1/events' && resumed !== null) {
        if (!/^\d+$/.test(resumed) || !Number.isSafeInteger(Number(resumed))) throw new Error(FAILURE);
        url.searchParams.set('after', resumed);
      }
      const first = await read(url, signal, mutation);
      const headers = { 'Content-Type': first.contentType, 'Cache-Control': 'no-store',
        'X-Morph-Captured-At': first.capturedAt, 'X-Morph-MCP-Completed-At': first.completedAt };
      if (url.pathname !== '/api/v1/events' || first.status !== 200 || url.searchParams.get('once') === 'true')
        return new Response(new Uint8Array(first.bytes), { status: first.status, headers });
      if (!first.contentType.startsWith('text/event-stream')) throw new Error(FAILURE);
      const control = new AbortController();
      const streamSignal = signal ? AbortSignal.any([signal, control.signal]) : control.signal;
      let next = first;
      const body = new ReadableStream<Uint8Array>({
        async start(controller) {
          try {
            while (!streamSignal.aborted) {
              if (next.status !== 200 || !next.contentType.startsWith('text/event-stream')) throw new Error(FAILURE);
              controller.enqueue(next.bytes);
              // Preserve Intel event payload bytes; bridge heartbeat carries no record or sequence.
              controller.enqueue(Buffer.from(': mcp-read-received\n\n'));
              for (const match of next.bytes.toString('utf8').matchAll(/^id: *(\d+)\r?$/gm)) {
                const cursor = Number(match[1]), before = Number(url.searchParams.get('after') ?? 0);
                if (!Number.isSafeInteger(cursor)) throw new Error(FAILURE);
                if (cursor > before) url.searchParams.set('after', String(cursor));
              }
              await pause(Math.max(pollMs, 250), streamSignal);
              next = await read(url, streamSignal);
            }
          } catch { if (!streamSignal.aborted) controller.error(new Error(FAILURE)); }
        },
        cancel() { control.abort(); },
      });
      return new Response(body, { status: 200, headers });
    } catch { return new Response(JSON.stringify({ detail: write ? {
      code: 'station_relay_unavailable', message: `${FAILURE} The submission outcome is unknown; retain its identifiers for an explicit retry.`,
    } : FAILURE }), { status: 503, headers: { 'Content-Type': 'application/json' } }); }
  }) as typeof fetch;
}
