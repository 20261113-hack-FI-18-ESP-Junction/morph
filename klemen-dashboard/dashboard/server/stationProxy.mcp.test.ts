/** Local HTTP -> MCP adapter regression checks. Queue replies are synthetic; no Intel/provider calls. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { createServer } from 'node:http';
import test from 'node:test';
import { createLocalRequestGuard, createStationProxy } from './stationProxy.ts';
import { createMcpStationFetch, MCP_LOCAL_TRANSPORT_MARKER, MCP_PROXY_ORIGIN, type ToolCall } from './mcpStationTransport.ts';

function queue(body = '{"accepted":true}', status = 200) {
  const requests: Record<string, unknown>[] = [];
  const bytes = Buffer.from(body), encoded = bytes.toString('base64'), at = new Date().toISOString();
  const call: ToolCall = async (name, args) => {
    if (name.startsWith('enqueue_')) {
      requests.push({ tool: name, ...args });
      return { request_id: args.request_id, state: 'queued', expires_at: at };
    }
    assert.equal(name, 'read_station_response');
    const offset = Number(args.offset), part = encoded.slice(offset, offset + 60000);
    return { state: 'ready', request_id: args.request_id, status_code: status, content_type: 'application/json',
      body_base64: part, offset, next_offset: offset + part.length < encoded.length ? offset + part.length : null,
      response_sha256: createHash('sha256').update(bytes).digest('hex'), captured_at: at, completed_at: at };
  };
  return { call, requests };
}
async function bridge(callTool: ToolCall) {
  const proxy = createStationProxy({ upstreamOrigin: MCP_PROXY_ORIGIN, getToken: () => MCP_LOCAL_TRANSPORT_MARKER,
    fetch: createMcpStationFetch({ callTool, stationId: 'local-mcp-test', pollMs: 1 }), requestTimeoutMs: 1000 });
  let guard: ReturnType<typeof createLocalRequestGuard>;
  const server = createServer((req, res) => guard(req, res, () => proxy(req, res, () => res.end('ui'))));
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const port = (server.address() as { port: number }).port;
  guard = createLocalRequestGuard(port);
  return { origin: `http://127.0.0.1:${port}`, async close() {
    const closed = once(server, 'close'); server.close(); server.closeAllConnections(); await closed;
  } };
}
const review = JSON.stringify({ id: 'review:1', eventId: 'review:event:1', expectedRevision: 1,
  authorId: 'operator', reason: 'Late review: Živjo ✓', createdAt: '2026-11-15T03:00:00Z', changes: { outcome: 'unverified' } }, null, 2);
const analysis = JSON.stringify({ requestId: 'analysis:1', kind: 'cycle_explanation', sessionIds: ['demo:session'],
  cycleId: 'demo:retry', sourceMode: 'simulation', expectedSelectionDigest: 'a'.repeat(64), question: 'Explain saved evidence.' });
const post = (body: string | Uint8Array<ArrayBuffer>, intent: string) => ({ method: 'POST', body,
  headers: { 'Content-Type': 'application/json', 'X-Morph-Intent': intent } });

test('comparison reads preserve both sessionIds through proxy and MCP', async () => {
  const q = queue(); const server = await bridge(q.call);
  try {
    const response = await fetch(`${server.origin}/api/v1/analysis/context?kind=session_comparison&sessionIds=baseline&sessionIds=adaptive&sourceMode=simulation&baselineSessionId=baseline&adaptiveSessionId=adaptive`);
    assert.equal(response.status, 200); await response.text();
    assert.equal(q.requests.length, 1); assert.equal(q.requests[0].tool, 'enqueue_station_read');
    assert.deepEqual((q.requests[0].query as Record<string, unknown>).sessionIds, ['baseline', 'adaptive']);
    assert.equal(q.requests[0].body, undefined); assert.equal(q.requests[0].intent, undefined);
  } finally { await server.close(); }
});
test('compact dashboard read preserves its scope and rejects extra, duplicate and write inputs', async () => {
  const q = queue(); const server = await bridge(q.call);
  try {
    const response = await fetch(`${server.origin}/api/v1/dashboard?sessionId=session%3A1&cycleId=cycle%3A2&sourceMode=simulation&limit=20`);
    assert.equal(response.status, 200); await response.text();
    assert.equal(q.requests.length, 1); assert.equal(q.requests[0].tool, 'enqueue_station_read');
    assert.deepEqual(q.requests[0].query, { sessionId: 'session:1', cycleId: 'cycle:2', sourceMode: 'simulation', limit: '20' });
    for (const route of ['/api/v1/dashboard?limit=10&limit=20', '/api/v1/dashboard?sourceMode=live&url=http://foreign.invalid']) {
      const denied = await fetch(server.origin + route); assert.equal(denied.status, 404); await denied.text();
    }
    const deniedWrite = await fetch(`${server.origin}/api/v1/dashboard`, post('{}', 'record-review'));
    assert.equal(deniedWrite.status, 405); await deniedWrite.text();
    assert.equal(q.requests.length, 1);
  } finally { await server.close(); }
});

test('explicit review and analyst submission preserve body, intent, IDs and HTTP status', async () => {
  for (const [route, body, intent, status] of [
    ['/api/v1/cycles/demo%3Aretry/review', review, 'record-review', 200],
    ['/api/v1/analysis/reports', analysis, 'evidence-analysis', 202],
  ] as const) {
    const q = queue('{"duplicate":false,"note":"exact ✓"}', status); const server = await bridge(q.call);
    try {
      const response = await fetch(server.origin + route, post(body, intent));
      assert.equal(response.status, status); assert.equal(await response.text(), '{"duplicate":false,"note":"exact ✓"}');
      assert.equal(q.requests.length, 1); assert.equal(q.requests[0].tool, 'enqueue_station_request');
      assert.equal(q.requests[0].method, 'POST'); assert.equal(q.requests[0].body, body); assert.equal(q.requests[0].intent, intent);
      assert.equal(q.requests[0].path, decodeURIComponent(route)); assert.deepEqual(q.requests[0].query, {});
      assert.equal(JSON.stringify(q.requests).includes(MCP_LOCAL_TRANSPORT_MARKER), false);
    } finally { await server.close(); }
  }
});

test('structured backend errors remain exact and never trigger an automatic POST retry', async () => {
  for (const status of [409, 422, 429, 503]) {
    const body = JSON.stringify({ detail: { code: 'saved_error', message: 'Evidence needs review.', status } });
    const q = queue(body, status); const server = await bridge(q.call);
    try {
      const response = await fetch(`${server.origin}/api/v1/analysis/reports`, post(analysis, 'evidence-analysis'));
      assert.equal(response.status, status); assert.equal(await response.text(), body); assert.equal(q.requests.length, 1);
    } finally { await server.close(); }
  }
});

test('wrong intent, forbidden writes, excessive query values and cross-origin writes never queue', async () => {
  const q = queue(); const server = await bridge(q.call);
  try {
    for (const [route, init, expected] of [
      ['/api/v1/cycles/demo/review', post(review, 'evidence-analysis'), 415],
      ['/api/v1/analysis/reports', post(analysis, 'record-review'), 415],
      ['/api/v1/commands', post(review, 'record-review'), 405],
      ['/api/v1/records', post(review, 'record-review'), 405],
      ['/api/v1/analysis/context?sessionIds=a&sessionIds=b&sessionIds=c', {}, 404],
      ['/api/v1/analysis/reports', { ...post(analysis, 'evidence-analysis'), headers: { ...post(analysis, 'evidence-analysis').headers, Origin: 'https://foreign.example' } }, 403],
    ] as const) {
      const response = await fetch(server.origin + route, init);
      assert.equal(response.status, expected, route); await response.text();
    }
    assert.equal(q.requests.length, 0);
  } finally { await server.close(); }
});

test('invalid UTF-8, non-object JSON and oversized request bytes never queue', async () => {
  const q = queue(); const server = await bridge(q.call);
  try {
    for (const [body, expected] of [[new Uint8Array([0xff]), 400], ['[]', 400], ['{', 400], [' '.repeat(65537), 413]] as const) {
      const response = await fetch(`${server.origin}/api/v1/analysis/reports`, post(body, 'evidence-analysis'));
      assert.equal(response.status, expected); await response.text();
    }
    assert.equal(q.requests.length, 0);
  } finally { await server.close(); }
});

test('missing POST response reports unknown outcome without repeating the submitted operation', async () => {
  let enqueues = 0;
  const call: ToolCall = async (name, args) => {
    if (name === 'enqueue_station_request') { enqueues++; return { request_id: args.request_id, state: 'queued' }; }
    return { state: 'expired' };
  };
  const response = await createMcpStationFetch({ stationId: 'local-mcp-test', callTool: call })(
    `${MCP_PROXY_ORIGIN}/api/v1/analysis/reports`, post(analysis, 'evidence-analysis'));
  assert.equal(response.status, 503); assert.equal(enqueues, 1);
  assert.match(await response.text(), /outcome is unknown/);
});
