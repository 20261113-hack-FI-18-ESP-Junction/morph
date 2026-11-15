/** Fixed media endpoints exercised over real loopback HTTP; upstreams are synthetic. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer, request, type IncomingMessage, type ServerResponse } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, writeFile, chmod, symlink, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createLocalRequestGuard } from './stationProxy.ts';
import { createMediaGateway, readMediaConfig, validateMediaConfig, type MediaConfig, type MediaGatewayOptions } from './mediaGateway.ts';

const ID = '11111111-1111-4111-8111-111111111111';
const OFFER = 'v=0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=recvonly\r\n';
const ANSWER = 'v=0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=sendonly\r\n';
const config: MediaConfig = { version: 1, whepUrl: 'http://127.0.0.1:8889/inspection/whep',
  cameraId: 'synthetic-inspection', streamId: 'inspection', label: 'Synthetic preview', sourceMode: 'simulation',
  profile: { width: 640, height: 480, fps: 30 }, username: 'viewer', password: 'test-only-viewer-secret' };
const producer = { version: 1, cameraId: config.cameraId, streamId: config.streamId, sourceMode: config.sourceMode,
  profile: config.profile, state: 'publishing', receivedAt: '2026-11-15T06:00:00Z', receiptAgeMs: 10, counters: { received: 1 } };
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
async function until(check: () => boolean) { for (let i = 0; !check() && i < 100; i++) await delay(5); assert.ok(check()); }
function answer(location = `/inspection/whep/${ID}`, body = ANSWER) {
  return new Response(body, { status: 201, headers: { 'Content-Type': 'application/sdp', Location: location } });
}
async function serve(handler: (req: IncomingMessage, res: ServerResponse) => void) {
  const server = createServer(handler); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const port = (server.address() as { port: number }).port;
  return { port, origin: `http://127.0.0.1:${port}`, close: async () => {
    const done = new Promise<void>(resolve => server.close(() => resolve())); server.closeAllConnections(); await done;
  } };
}
async function host(options: MediaGatewayOptions = {}) {
  const gateway = createMediaGateway(options); let guard: ReturnType<typeof createLocalRequestGuard>;
  const server = await serve((req, res) => guard(req, res, () => gateway.middleware(req, res, () => { res.statusCode = 418; res.end('records-route'); })));
  guard = createLocalRequestGuard(server.port);
  return { ...server, gateway, close: async () => { await gateway.close(); await server.close(); } };
}
const post = (origin: string, body = OFFER, headers: Record<string, string> = {}) => fetch(origin + '/api/media/v1/whep', {
  method: 'POST', headers: { 'Content-Type': 'application/sdp', ...headers }, body,
});

test('unconfigured media remains separate from records and rejects arbitrary routes', async () => {
  let calls = 0; const h = await host({ fetch: async () => { calls++; throw new Error(); } });
  try {
    const status = await fetch(h.origin + '/api/media/v1/status'); assert.equal(status.status, 200);
    const data = await status.json(); assert.equal(data.configured, false); assert.equal(data.producer, null);
    assert.equal((await post(h.origin)).status, 503);
    assert.equal((await fetch(h.origin + '/api/v1/schema')).status, 418);
    for (const route of ['/api/media/v1/status?url=http://evil.invalid', '/api/media/v1/status%2Fbad', '/api/media/v1/commands']) {
      assert.equal((await fetch(h.origin + route)).status, 404);
    }
    assert.equal(calls, 0);
  } finally { await h.close(); }
});

test('only the fixed viewer destination and server authentication are used', async () => {
  const seen: { url: string; method?: string; headers: Headers }[] = [];
  const h = await host({ config, fetch: async (url, init) => {
    seen.push({ url: String(url), method: init?.method, headers: new Headers(init?.headers) });
    assert.equal(init?.redirect, 'error');
    return init?.method === 'DELETE' ? new Response(null, { status: 204 }) : answer();
  } });
  try {
    const response = await post(h.origin, OFFER, { Authorization: 'Bearer browser-secret', Cookie: 'private=browser' });
    assert.equal(response.status, 201); assert.equal(await response.text(), ANSWER);
    const location = response.headers.get('location')!; assert.match(location, /^\/api\/media\/v1\/sessions\/[a-f0-9-]{36}$/);
    assert.equal(h.gateway.sessionCount(), 1);
    assert.equal((await fetch(h.origin + location, { method: 'DELETE' })).status, 204);
    assert.equal((await fetch(h.origin + location, { method: 'DELETE' })).status, 204);
    assert.equal(h.gateway.sessionCount(), 0); assert.equal(seen.length, 2);
    assert.equal(seen[0]!.url, config.whepUrl); assert.equal(seen[1]!.url, config.whepUrl + '/' + ID);
    for (const call of seen) {
      assert.equal(call.headers.get('authorization'), 'Basic ' + Buffer.from(`${config.username}:${config.password}`).toString('base64'));
      assert.equal(call.headers.get('cookie'), null);
    }
    const statusText = await (await fetch(h.origin + '/api/media/v1/status')).text();
    assert.ok(!statusText.includes(config.password!)); assert.ok(!statusText.includes(config.whepUrl));
  } finally { await h.close(); }
});

test('host and origin guard prevents cross-origin media mutations', async () => {
  let calls = 0; const h = await host({ config, fetch: async () => { calls++; return answer(); } });
  try {
    const deniedHeaders: Record<string, string>[] = [{ Origin: 'https://evil.invalid' }, { 'Sec-Fetch-Site': 'cross-site' }];
    for (const headers of deniedHeaders) {
      assert.equal((await post(h.origin, OFFER, headers)).status, 403);
    }
    const badHost = await new Promise<number>((resolve, reject) => {
      const req = request(h.origin + '/api/media/v1/whep', { method: 'POST', headers: { Host: 'evil.invalid', 'Content-Type': 'application/sdp' } }, res => {
        res.resume(); res.on('end', () => resolve(res.statusCode!));
      }); req.on('error', reject); req.end(OFFER);
    });
    assert.equal(badHost, 403);
    assert.equal(calls, 0);
  } finally { await h.close(); }
});

test('receive-only bounded video offers reject publishing, audio and oversized input', async () => {
  let calls = 0; const h = await host({ config, fetch: async () => { calls++; return answer(); } });
  try {
    for (const invalid of [OFFER.replace('recvonly', 'sendrecv'), OFFER.replace('recvonly', 'sendonly'),
      OFFER + 'm=audio 9 UDP/TLS/RTP/SAVPF 0\r\n', 'invalid']) assert.equal((await post(h.origin, invalid)).status, 400);
    assert.equal((await post(h.origin, OFFER + 'x'.repeat(65_536))).status, 413);
    assert.equal((await post(h.origin, OFFER, { 'Content-Type': 'application/json' })).status, 415);
    assert.equal(calls, 0);
  } finally { await h.close(); }
});

test('upstream failures and unsafe cleanup destinations are sanitized without following them', async () => {
  for (const location of ['https://evil.invalid/inspection/whep/' + ID, '/other/whep/' + ID,
    '/inspection/whep/' + ID + '?token=secret', '/inspection/whep/not-a-uuid']) {
    let calls = 0; const h = await host({ config, fetch: async () => { calls++; return answer(location); } });
    try { const response = await post(h.origin); assert.equal(response.status, 502); assert.equal(calls, 1); assert.equal(h.gateway.sessionCount(), 0); }
    finally { await h.close(); }
  }
  const h = await host({ config, fetch: async () => { throw new TypeError(config.password); } });
  try { const response = await post(h.origin); assert.equal(response.status, 502); assert.ok(!(await response.text()).includes(config.password!)); }
  finally { await h.close(); }
});

test('an invalid or oversized answer cleans up its created upstream session', async () => {
  for (const body of ['invalid', ANSWER + 'x'.repeat(65_536)]) {
    let deletes = 0; const h = await host({ config, fetch: async (_url, init) => {
      if (init?.method === 'DELETE') { deletes++; return new Response(null, { status: 204 }); } return answer(undefined, body);
    } });
    try { assert.equal((await post(h.origin)).status, 502); assert.equal(deletes, 1); assert.equal(h.gateway.sessionCount(), 0); }
    finally { await h.close(); }
  }
});

test('producer status is authenticated, bounded and blocks source/profile identity mismatch', async () => {
  let current = { ...producer }; let posted = 0;
  const media = { ...config, statusUrl: 'http://127.0.0.1:8790/api/media/v1/status', statusToken: 'test-only-status-secret' };
  const h = await host({ config: media, fetch: async (url, init) => {
    if (String(url) === media.statusUrl) {
      assert.equal(new Headers(init?.headers).get('authorization'), `Bearer ${media.statusToken}`);
      return Response.json(current);
    }
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
    posted++; return answer();
  } });
  try {
    const read = () => fetch(h.origin + '/api/media/v1/status').then(r => r.json());
    assert.deepEqual((await read()).producer.counters, { received: 1 });
    current = { ...producer, sourceMode: 'live' }; assert.equal((await read()).configured, false);
    assert.equal((await post(h.origin)).status, 409); assert.equal(posted, 0);
    current = { ...producer, profile: { width: 1280, height: 720, fps: 30 } };
    assert.equal((await post(h.origin)).status, 409);
    current = { ...producer }; assert.equal((await read()).configured, true);
    assert.equal((await post(h.origin)).status, 201); assert.equal(posted, 1);
  } finally { await h.close(); }
});

test('missing producer status retains unknown freshness without fabricating counters', async () => {
  const h = await host({ config: { ...config, statusUrl: 'http://127.0.0.1:8790/api/media/v1/status' }, fetch: async () => { throw new Error('offline'); } });
  try { const data = await (await fetch(h.origin + '/api/media/v1/status')).json(); assert.equal(data.configured, true); assert.equal(data.producer, null); assert.match(data.reason, /unavailable/); }
  finally { await h.close(); }
});

test('pending viewers count toward the cap and an abandoned POST is cleaned up', async () => {
  let release!: () => void; let posted = false; let deletes = 0;
  const ready = new Promise<void>(resolve => { release = resolve; });
  const h = await host({ config, maxSessions: 1, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') { deletes++; return new Response(null, { status: 204 }); }
    posted = true; await ready; return answer();
  } });
  try {
    const req = request(h.origin + '/api/media/v1/whep', { method: 'POST', headers: { 'Content-Type': 'application/sdp' } });
    req.on('error', () => {}); req.end(OFFER); await until(() => posted);
    assert.equal((await post(h.origin)).status, 429);
    req.destroy(); await delay(10); release();
    await until(() => deletes === 1); assert.equal(h.gateway.sessionCount(), 0);
  } finally { release(); await h.close(); }
});

test('slow incoming bodies time out and release pending viewer capacity', async () => {
  let calls = 0; const h = await host({ config, requestTimeoutMs: 75, maxSessions: 1, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') return new Response(null, { status: 204 }); calls++; return answer();
  } });
  try {
    const result = new Promise<number>((resolve, reject) => {
      const req = request(h.origin + '/api/media/v1/whep', { method: 'POST', headers: { 'Content-Type': 'application/sdp', 'Content-Length': '1000' } }, res => {
        res.resume(); res.on('end', () => { resolve(res.statusCode!); req.destroy(); });
      }); req.on('error', reject); req.write('v=0\r\n');
    });
    assert.equal(await result, 504); assert.equal(calls, 0);
    assert.equal((await post(h.origin)).status, 201); assert.equal(calls, 1);
  } finally { await h.close(); }
});

test('upstream timeout ends negotiation and expiring sessions are deleted', async () => {
  const stuck = await host({ config, requestTimeoutMs: 40, fetch: async (_url, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  }) });
  try { assert.equal((await post(stuck.origin)).status, 504); } finally { await stuck.close(); }
  let deleted = 0;
  const h = await host({ config, sessionLifetimeMs: 50, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') { deleted++; return new Response(null, { status: 204 }); } return answer();
  } });
  try { assert.equal((await post(h.origin)).status, 201); await until(() => deleted > 0); assert.equal(h.gateway.sessionCount(), 0); }
  finally { await h.close(); }
});

test('private configuration rejects unsafe endpoints, cleartext remote auth and broad filesystem permissions', async () => {
  for (const change of [{ whepUrl: 'http://intel.example/inspection/whep' }, { whepUrl: 'https://viewer:secret@intel.example/inspection/whep' },
    { whepUrl: 'https://intel.example/inspection/whep?target=x' }, { whepUrl: 'https://intel.example/inspection/whep', username: undefined, password: undefined },
    { sourceMode: 'replay' }, { unexpected: true }]) assert.throws(() => validateMediaConfig({ ...config, ...change }));
  assert.doesNotThrow(() => validateMediaConfig({ ...config, whepUrl: 'https://intel.example/inspection/whep' }));
  const directory = await mkdtemp(path.join(tmpdir(), 'morph-media-test-')); const file = path.join(directory, 'media.json');
  try {
    await writeFile(file, JSON.stringify(config), { mode: 0o600 }); assert.deepEqual(readMediaConfig(file), config);
    await chmod(file, 0o644); assert.throws(() => readMediaConfig(file)); await chmod(file, 0o600);
    await symlink(file, path.join(directory, 'link.json')); assert.throws(() => readMediaConfig(path.join(directory, 'link.json')));
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('an identity mismatch invalidates pending SDP even when the producer recovers before its answer arrives', async () => {
  let current = { ...producer }; let posted = false; let deletes = 0; let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  const media = { ...config, statusUrl: 'http://127.0.0.1:8790/api/media/v1/status' };
  const h = await host({ config: media, fetch: async (url, init) => {
    if (String(url) === media.statusUrl) return Response.json(current);
    if (init?.method === 'DELETE') { deletes++; return new Response(null, { status: 204 }); }
    posted = true; await waiting; return answer();
  } });
  try {
    const pending = post(h.origin); await until(() => posted);
    current = { ...producer, sourceMode: 'live' };
    assert.equal((await (await fetch(h.origin + '/api/media/v1/status')).json()).configured, false);
    current = { ...producer };
    assert.equal((await (await fetch(h.origin + '/api/media/v1/status')).json()).configured, true);
    release();
    assert.equal((await pending).status, 409);
    assert.equal(deletes, 1); assert.equal(h.gateway.sessionCount(), 0);
  } finally { release(); await h.close(); }
});

test('an older successful status reply cannot erase a newer identity mismatch', async () => {
  let statusCalls = 0; let posted = 0; let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  const media = { ...config, statusUrl: 'http://127.0.0.1:8790/api/media/v1/status' };
  const h = await host({ config: media, fetch: async (url, init) => {
    if (String(url) === media.statusUrl) {
      statusCalls++;
      if (statusCalls === 1) { await waiting; return Response.json(producer); }
      if (statusCalls === 2) return Response.json({ ...producer, sourceMode: 'live' });
      throw new Error('Producer status temporarily unavailable.');
    }
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
    posted++; return answer();
  } });
  try {
    const older = fetch(h.origin + '/api/media/v1/status'); await until(() => statusCalls === 1);
    const newer = await fetch(h.origin + '/api/media/v1/status');
    assert.equal((await newer.json()).configured, false);
    release(); assert.equal((await (await older).json()).configured, false);
    assert.equal((await post(h.origin)).status, 409); assert.equal(posted, 0);
  } finally { release(); await h.close(); }
});

test('failed cleanup of an undisclosed session retries promptly without waiting for its normal lifetime', async () => {
  let deletes = 0;
  const h = await host({ config, cleanupRetryMs: 10, sessionLifetimeMs: 3_600_000, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') { deletes++; return new Response(null, { status: deletes === 1 ? 503 : 204 }); }
    return answer(undefined, 'invalid SDP');
  } });
  try {
    assert.equal((await post(h.origin)).status, 502);
    await until(() => deletes >= 2 && h.gateway.sessionCount() === 0);
    assert.equal(deletes, 2);
  } finally { await h.close(); }
});

test('concurrent callers share one in-flight upstream DELETE', async () => {
  let deletes = 0; let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  const h = await host({ config, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') { deletes++; await waiting; return new Response(null, { status: 204 }); }
    return answer();
  } });
  try {
    const created = await post(h.origin); const location = created.headers.get('location')!; await created.text();
    const first = fetch(h.origin + location, { method: 'DELETE' }); await until(() => deletes === 1);
    const second = fetch(h.origin + location, { method: 'DELETE' }); await delay(25);
    assert.equal(deletes, 1); release();
    assert.equal((await first).status, 204); assert.equal((await second).status, 204);
    assert.equal(h.gateway.sessionCount(), 0);
  } finally { release(); await h.close(); }
});

test('shutdown awaits a pending answer and its cleanup before its barrier resolves', async () => {
  let posted = false; let deletes = 0; let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  const h = await host({ config, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') { deletes++; return new Response(null, { status: 204 }); }
    posted = true; await waiting; return answer();
  } });
  try {
    const pending = post(h.origin); await until(() => posted);
    let closed = false; const closing = h.gateway.close().then(() => { closed = true; });
    await delay(20); assert.equal(closed, false);
    assert.equal((await post(h.origin)).status, 503);
    release(); assert.equal((await pending).status, 503); await closing;
    assert.equal(deletes, 1); assert.equal(h.gateway.sessionCount(), 0);
  } finally { release(); await h.close(); }
});

test('shutdown while checking producer status prevents a new upstream POST', async () => {
  let checking = false; let posted = 0; let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  const media = { ...config, statusUrl: 'http://127.0.0.1:8790/api/media/v1/status' };
  const h = await host({ config: media, fetch: async (url, init) => {
    if (String(url) === media.statusUrl) { checking = true; await waiting; return Response.json(producer); }
    if (init?.method === 'DELETE') return new Response(null, { status: 204 });
    posted++; return answer();
  } });
  try {
    const pending = post(h.origin); await until(() => checking);
    let closed = false; const closing = h.gateway.close().then(() => { closed = true; });
    await delay(20); assert.equal(closed, false);
    release(); assert.equal((await pending).status, 503); await closing;
    assert.equal(posted, 0);
  } finally { release(); await h.close(); }
});

test('shutdown retries cleanup but remains bounded when the upstream stays unavailable', async () => {
  let deletes = 0;
  const h = await host({ config, requestTimeoutMs: 30, cleanupRetryMs: 10, fetch: async (_url, init) => {
    if (init?.method === 'DELETE') { deletes++; return new Response(null, { status: 503 }); }
    return answer();
  } });
  try {
    const created = await post(h.origin); assert.equal(created.status, 201); await created.text();
    const started = Date.now(); await h.gateway.close();
    assert.ok(Date.now() - started < 1000);
    assert.ok(deletes > 1); assert.equal(h.gateway.sessionCount(), 1);
    const atClose = deletes; await delay(80); assert.equal(deletes, atClose);
  } finally { await h.close(); }
});
