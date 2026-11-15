import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { createMcpStationFetch, MCP_PROXY_ORIGIN, type ToolCall } from './mcpStationTransport.ts';

function fixture(body = '{"value":1}', chunk = 60_000) {
  const encoded = Buffer.from(body).toString('base64');
  const calls: { name: string; args: Record<string, unknown> }[] = [];
  const captured = new Date().toISOString();
  const call: ToolCall = async (name, args) => {
    calls.push({ name, args });
    if (name === 'enqueue_station_read') return { request_id: args.request_id, state: 'queued', expires_at: captured };
    const offset = Number(args.offset), text = encoded.slice(offset, offset + chunk);
    return { state: 'ready', request_id: args.request_id, status_code: 200, content_type: 'application/json',
      body_base64: text, offset, next_offset: offset + text.length < encoded.length ? offset + text.length : null,
      response_sha256: createHash('sha256').update(body).digest('hex'), captured_at: captured, completed_at: captured };
  };
  return { call, calls };
}
const url = `${MCP_PROXY_ORIGIN}/api/v1/sessions`;
test('queues fresh UUID reads and reconstructs exact response across base64 chunks', async () => {
  const f = fixture('{"value":"same bytes ✓"}', 5);
  const fetch = createMcpStationFetch({ callTool: f.call, stationId: 'intel-main' });
  const response = await fetch(url);
  assert.equal(response.status, 200); assert.equal(await response.text(), '{"value":"same bytes ✓"}');
  await fetch(url);
  const starts = f.calls.filter(c => c.name === 'enqueue_station_read');
  assert.equal(starts.length, 2); assert.notEqual(starts[0].args.request_id, starts[1].args.request_id);
  assert.equal(starts[0].args.path, '/api/v1/sessions');
  assert.ok(f.calls.every(c => ['enqueue_station_read', 'read_station_response'].includes(c.name)));
});
test('rejects wrong checksums, mixed metadata, offsets and oversized replies', async () => {
  for (const kind of ['hash', 'identity', 'offset', 'size']) {
    const f = fixture('1234567890', 4);
    const call: ToolCall = async (name, args, signal) => {
      const r = await f.call(name, args, signal);
      if (r.state === 'ready') {
        if (kind === 'hash') r.response_sha256 = '0'.repeat(64);
        if (kind === 'identity' && Number(args.offset) > 0) r.status_code = 201;
        if (kind === 'offset') r.offset = 2;
      }
      return r;
    };
    const fetch = createMcpStationFetch({ callTool: call, stationId: 'intel-main', maxBytes: kind === 'size' ? 5 : 100 });
    assert.equal((await fetch(url)).status, 503, kind);
  }
});
test('polls pending response and fails expired or unavailable workers without cached output', async () => {
  const f = fixture(); let pending = true;
  const call: ToolCall = async (name, args, signal) => {
    if (name === 'read_station_response' && pending) { pending = false; return { state: 'claimed' }; }
    return f.call(name, args, signal);
  };
  assert.equal((await createMcpStationFetch({ callTool: call, stationId: 'intel-main', pollMs: 1 })(url)).status, 200);
  for (const state of ['expired', 'failed']) {
    const call: ToolCall = async (name, args) => name === 'enqueue_station_read'
      ? { state: 'queued', request_id: args.request_id } : { state };
    assert.equal((await createMcpStationFetch({ callTool: call, stationId: 'intel-main' })(url)).status, 503);
  }
});
test('sanitizes tool failures and disallows other origins or write methods before queueing', async () => {
  const calls: unknown[] = [];
  const fetch = createMcpStationFetch({ stationId: 'intel-main', callTool: async (...args) => { calls.push(args); throw new Error('PRIVATE_TOKEN_MUST_NOT_LEAK'); } });
  assert.equal((await fetch('https://elsewhere.example/api/v1/sessions')).status, 503);
  assert.equal((await fetch(url, { method: 'POST' })).status, 503); assert.equal(calls.length, 0);
  const response = await fetch(url); assert.equal(response.status, 503);
  assert.equal((await response.text()).includes('PRIVATE_TOKEN_MUST_NOT_LEAK'), false);
});
test('finite SSE preserves bytes and forces once=true on the Intel request', async () => {
  const f = fixture(': no events\n\n');
  const call: ToolCall = async (name, args, signal) => {
    const result = await f.call(name, args, signal);
    if (result.state === 'ready') result.content_type = 'text/event-stream';
    return result;
  };
  const fetch = createMcpStationFetch({ callTool: call, stationId: 'intel-main' });
  const response = await fetch(`${MCP_PROXY_ORIGIN}/api/v1/events?after=4&once=true`, { headers: { 'Last-Event-ID': '6' } });
  assert.equal(await response.text(), ': no events\n\n');
  assert.deepEqual(f.calls[0].args.query, { after: '6', once: 'true' });
});
test('browser SSE advances Intel cursor and fails on worker loss instead of replaying cached data', async () => {
  const body = 'id: 7\nevent: record.created\ndata: {"sequence":7}\n\n';
  const f = fixture(body); let reads = 0;
  const call: ToolCall = async (name, args, signal) => {
    if (name === 'enqueue_station_read' && ++reads > 1) { f.calls.push({ name, args }); throw new Error('worker unavailable'); }
    const result = await f.call(name, args, signal);
    if (result.state === 'ready') result.content_type = 'text/event-stream';
    return result;
  };
  const response = await createMcpStationFetch({ callTool: call, stationId: 'intel-main', pollMs: 1 })(`${MCP_PROXY_ORIGIN}/api/v1/events?after=6`);
  const reader = response.body!.getReader();
  assert.equal(Buffer.from((await reader.read()).value!).toString(), body);
  assert.equal(Buffer.from((await reader.read()).value!).toString(), ': mcp-read-received\n\n');
  await assert.rejects(reader.read());
  assert.equal(([...f.calls].reverse().find(c => c.name === 'enqueue_station_read')!.args.query as any).after, '7');
});
test('aborted pending reads stop polling and return unavailable', async () => {
  const control = new AbortController(); let polls = 0;
  const call: ToolCall = async (name, args) => {
    if (name === 'enqueue_station_read') return { state: 'queued', request_id: args.request_id };
    polls++; control.abort(); return { state: 'claimed' };
  };
  const response = await createMcpStationFetch({ callTool: call, stationId: 'intel-main', pollMs: 1 })(url, { signal: control.signal });
  assert.equal(response.status, 503); assert.equal(polls, 1);
});

test('decodes validated record identifiers for the relay plain-path contract', async () => {
  const f = fixture();
  const fetch = createMcpStationFetch({ callTool: f.call, stationId: 'intel-main' });
  await fetch(`${MCP_PROXY_ORIGIN}/api/v1/sessions/demo%3Asession/export?format=json`);
  assert.equal(f.calls[0].args.path, '/api/v1/sessions/demo:session/export');
});
test('overall deadline stops a pending worker even when a tool ignores cancellation', async () => {
  const timer = setTimeout(() => {}, 100);
  try {
    const fetch = createMcpStationFetch({ stationId: 'intel-main', timeoutMs: 5,
      callTool: async () => new Promise(() => {}) });
    assert.equal((await fetch(url)).status, 503);
  } finally { clearTimeout(timer); }
});
