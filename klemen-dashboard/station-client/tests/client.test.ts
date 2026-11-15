/** Transport tests use saved M06 simulation fixtures and mocked HTTP; they do not verify hardware. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { StationAccessError, StationClient, StationHttpError, StationProtocolError, StationStreamError, StationTimeoutError } from "../src/client.ts";
import { DashboardStore } from "../src/store.ts";
import type { SessionExport, Snapshot, StationEvent } from "../src/types.ts";

const TOKEN = "unit-test-only-token-with-at-least-32-characters";
const fixture = <T>(name: string): T => JSON.parse(readFileSync(new URL(`../../verification/fixtures/${name}`, import.meta.url), "utf8")) as T;
const savedSnapshot = fixture<Snapshot>("sample-snapshot.json");
const savedEvents = fixture<StationEvent[]>("sample-events.json");
const json = (data: unknown) => new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
const clientFor = (fetcher: typeof fetch) => new StationClient({ baseUrl: "http://127.0.0.1:8765", getToken: () => TOKEN, fetch: fetcher });
const from = (data: unknown) => clientFor(async () => json(data));
const collect = async <T>(source: AsyncIterable<T>): Promise<T[]> => { const values: T[] = []; for await (const v of source) values.push(v); return values; };
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function eventText(event: StationEvent, newline = "\n"): string {
  const lines = JSON.stringify(event, null, 2).split("\n").map(line => `data: ${line}`);
  return [`id: ${event.sequence}`, `event: ${event.type}`, ...lines, "", ""].join(newline);
}
function streamResponse(text: string, byteChunks = false): Response {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream<Uint8Array>({ start(controller) {
    if (byteChunks) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); }
    else controller.enqueue(bytes);
    controller.close();
  } }), { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}

test("GET transport keeps bearer credentials only in headers and applies browser restrictions", async () => {
  let seen = false;
  const client = clientFor(async (input, init) => {
    seen = true;
    const url = new URL(String(input));
    assert.equal(url.pathname, "/api/v1/station/snapshot");
    assert.equal(url.searchParams.get("sessionId"), "demo:session");
    assert.equal(url.href.includes(TOKEN), false);
    assert.equal(new Headers(init?.headers).get("Authorization"), `Bearer ${TOKEN}`);
    assert.equal(init?.method, "GET"); assert.equal(init?.credentials, "omit");
    assert.equal(init?.redirect, "error"); assert.equal(init?.cache, "no-store");
    assert.equal(init?.referrerPolicy, "no-referrer"); assert.ok(init?.signal);
    return json(savedSnapshot);
  });
  const value = await client.getSnapshot("demo:session");
  assert.equal(seen, true); assert.equal(value.sourceMode, "simulation");
  assert.equal(value.metrics.endToEnd.value, 0.5);
});

test("tokens are requested again for each operation and never cached by the client", async () => {
  let calls = 0;
  const client = new StationClient({ baseUrl: "https://station.example", getToken: async () => `${TOKEN}-${++calls}`,
    fetch: async (_input, init) => { assert.equal(new Headers(init?.headers).get("Authorization"), `Bearer ${TOKEN}-${calls}`); return json([]); } });
  await client.listSessions(); await client.listSessions(); assert.equal(calls, 2);
});

test("rejects unsupported base origins and invalid record IDs before sending requests", async () => {
  for (const baseUrl of ["file:///tmp/station", "http://user:secret@host", "http://host/prefix", "http://host?token=secret", "http://host/#secret"]) {
    assert.throws(() => new StationClient({ baseUrl, getToken: () => TOKEN }), TypeError);
  }
  let calls = 0;
  const client = clientFor(async () => { calls++; return json({}); });
  await assert.rejects(client.getCycle("../private"), TypeError);
  await assert.rejects(client.getSnapshot("bad/id"), TypeError);
  await assert.rejects(client.listCycles({ limit: 1001 }), TypeError);
  await assert.rejects(collect(client.events({ after: -1 })), TypeError);
  assert.equal(calls, 0);
});

test("HTTP errors retain status but never echo provider tokens or response bodies", async () => {
  let calls = 0;
  const client = clientFor(async () => { calls++; return new Response(TOKEN, { status: 401 }); });
  await assert.rejects(client.listSessions(), error => {
    assert.ok(error instanceof StationHttpError); assert.equal(error.status, 401);
    assert.equal(String(error).includes(TOKEN), false); return true;
  });
  assert.equal(calls, 1);
});

test("token failures are sanitized and invalid tokens never reach fetch", async () => {
  for (const getToken of [() => "short", () => { throw new Error(TOKEN); }]) {
    const client = new StationClient({ baseUrl: "https://station.example", getToken,
      fetch: async () => { throw new Error("fetch must not run"); } });
    await assert.rejects(client.listSessions(), error => error instanceof StationAccessError && !String(error).includes(TOKEN));
  }
});

test("rejects malformed snapshot schema, source, timestamps, capabilities and counts", async () => {
  const cases: ((s: Snapshot) => void)[] = [
    s => { (s as unknown as { schemaVersion: number }).schemaVersion = 2; },
    s => { s.sourceMode = "live"; },
    s => { s.generatedAt = "2026-11-14T16:27:52"; },
    s => { (s.capabilities.robot as unknown as { verified: boolean }).verified = true; },
    s => { s.metrics.cycles.failed = -1; },
    s => { s.metrics.cycles.total++; },
    s => { s.metrics.endToEnd.value = 0.8; },
    s => { s.metrics.detection.defectEscape.value = 0; },
    s => { s.metrics.detection.checked++; },
    s => { s.metrics.timings.fullCycle.valuesMs.push(5); },
    s => { s.metrics.endToEnd.filters.includeSimulation = false; },
  ];
  for (const change of cases) {
    const bad = structuredClone(savedSnapshot); change(bad);
    await assert.rejects(from(bad).getSnapshot(), StationProtocolError);
  }
  await assert.rejects(from(savedSnapshot).getSnapshot("other-session"), StationProtocolError);
});

test("rejects non-JSON content, malformed JSON, invalid UTF-8 and overlarge JSON", async () => {
  const responses = [new Response("{}", { headers: { "Content-Type": "text/html" } }),
    new Response("{", { headers: { "Content-Type": "application/json" } }),
    new Response(new Uint8Array([0xff]), { headers: { "Content-Type": "application/json" } }),
    new Response("{}", { headers: { "Content-Type": "application/json", "Content-Length": String(17 * 1024 * 1024) } })];
  for (const response of responses) await assert.rejects(clientFor(async () => response).listSessions(), StationProtocolError);
});

test("metrics require explicit simulation selection and match returned filters", async () => {
  const client = clientFor(async (input) => {
    const url = new URL(String(input)); assert.equal(url.pathname, "/api/v1/sessions/demo%3Asession/metrics");
    assert.equal(url.searchParams.get("includeSimulation"), "true"); return json(savedSnapshot.metrics);
  });
  assert.equal((await client.getMetrics({ sessionId: "demo:session", includeSimulation: true })).cycles.total, 5);
  await assert.rejects(from(savedSnapshot.metrics).getMetrics({ sessionId: "demo:session" }), StationProtocolError);
});

test("cycle list preserves false filters, pagination and verifies returned scope", async () => {
  const page = { items: [savedSnapshot.cycle], total: 1, offset: 0, limit: 20 };
  const client = clientFor(async input => {
    const url = new URL(String(input));
    assert.equal(url.searchParams.get("sourceMode"), "simulation"); assert.equal(url.searchParams.get("hasRetry"), "false");
    assert.equal(url.searchParams.get("limit"), "20"); return json(page);
  });
  assert.equal((await client.listCycles({ sourceMode: "simulation", hasRetry: false, limit: 20 })).items.length, 1);
  await assert.rejects(from(page).listCycles({ sessionId: "wrong", limit: 20 }), StationProtocolError);
});

test("saved retry detail and complete session export preserve records and revisions", async () => {
  const detail = fixture<Record<string, unknown>>("sample-cycle-retry.json");
  const result = await from(detail).getCycle("demo:retry");
  assert.equal(result.attempts.length, 2); assert.equal(result.inspections.length, 2);
  assert.ok(result.revisions.length > 0);
  const data = fixture<Record<string, unknown>>("sample-export.json");
  const exported = await from(data).exportSession("demo:session", "json");
  assert.equal(exported.events.length, 50); assert.equal(exported.records.cycle.length, 5);
  assert.equal(exported.records.evidence.length, 4);
  assert.ok(exported.revisions.length >= exported.events.length);
});

test("camera availability stays unavailable and evidence is an authenticated bounded Blob", async () => {
  const cameras = await from({ status: "unavailable", cameras: [], reason: "Not integrated" }).getCameras();
  assert.equal(cameras.status, "unavailable");
  const client = clientFor(async (_input, init) => {
    assert.ok(new Headers(init?.headers).has("Authorization"));
    return new Response("local evidence", { headers: { "Content-Type": "text/plain; charset=utf-8" } });
  });
  const blob = await client.getEvidence("demo:good:image"); assert.equal(blob.type, "text/plain");
  assert.equal(await blob.text(), "local evidence");
  await assert.rejects(clientFor(async () => new Response("", { headers: { "Content-Type": "text/plain" } })).getEvidence("id"), StationProtocolError);
  await assert.rejects(clientFor(async () => new Response("x", { headers: { "Content-Type": "text/plain", "Content-Length": "5242881" } })).getEvidence("id"), StationProtocolError);
});

test("CSV download retains export sections and rejects a foreign header", async () => {
  const csv = readFileSync(new URL("../../verification/fixtures/sample-export.csv", import.meta.url), "utf8");
  const client = clientFor(async input => {
    assert.equal(new URL(String(input)).searchParams.get("format"), "csv");
    return new Response(csv, { headers: { "Content-Type": "text/csv; charset=utf-8" } });
  });
  assert.equal(await client.exportSession("demo:session", "csv"), csv);
  await assert.rejects(clientFor(async () => new Response("foo,bar\n", { headers: { "Content-Type": "text/csv" } })).exportSession("id", "csv"), StationProtocolError);
});

test("pre-aborted and in-flight requests terminate even when fetch ignores the signal", async () => {
  const before = new AbortController(); before.abort(); let calls = 0;
  const client = clientFor(async () => { calls++; return new Promise<Response>(() => {}); });
  await assert.rejects(client.listSessions(before.signal), { name: "AbortError" }); assert.equal(calls, 0);
  const running = new AbortController(); const pending = client.listSessions(running.signal);
  await flush(); running.abort();
  await assert.rejects(pending, { name: "AbortError" }); assert.equal(calls, 1);
});

test("fixed request timeout covers an unresolved token provider", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const client = new StationClient({ baseUrl: "http://station.example", getToken: () => new Promise<string>(() => {}),
    fetch: async () => { throw new Error("fetch must not run"); } });
  const rejected = assert.rejects(client.listSessions(), StationTimeoutError);
  t.mock.timers.tick(40_000); await rejected;
});

test("fixed request timeout also bounds a body that never finishes", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const client = clientFor(async () => new Response(new ReadableStream<Uint8Array>(), { headers: { "Content-Type": "application/json" } }));
  const rejected = assert.rejects(client.listSessions(), StationTimeoutError);
  await flush(); t.mock.timers.tick(40_000); await rejected;
});

test("SSE parses byte-split UTF-8, BOM, CRLF, comments and multiline JSON data", async () => {
  const first = structuredClone(savedEvents[0]!);
  assert.equal(first.recordType, "session");
  if (first.recordType === "session") first.payload.name = "Hello 🤖";
  const text = "\uFEFF: connected\r\n\r\n" + eventText(first, "\r\n") + ": keep-alive\r\n\r\n" + eventText(savedEvents[1]!, "\r\n");
  let opened = 0;
  const events = await collect(clientFor(async input => {
    const url = new URL(String(input)); assert.equal(url.searchParams.get("after"), "0");
    assert.equal(url.searchParams.get("once"), "true"); assert.equal(url.searchParams.get("limit"), "2");
    return streamResponse(text, true);
  }).events({ after: 0, once: true, limit: 2, onOpen: () => { opened++; } }));
  assert.deepEqual(events, [first, savedEvents[1]]); assert.equal(opened, 1);
});

test("SSE resume accepts a global cursor and caught-up comments without events", async () => {
  const event = savedEvents[2]!;
  assert.deepEqual(await collect(clientFor(async () => streamResponse(eventText(event, "\r"))).events({ after: 2, once: true })), [event]);
  assert.deepEqual(await collect(clientFor(async () => streamResponse(": caught-up\n\n")).events({ after: 50, once: true })), []);
});

test("SSE rejects malformed IDs and payload/type mismatch as incompatible data", async () => {
  const first = eventText(savedEvents[0]!);
  const badPayload = structuredClone(savedEvents[0]!); badPayload.sourceMode = "live";
  const cases = [first.replace("id: 1", "id: nope"), first.replace("id: 1", "id: 2"),
    first.replace("event: session.created", "event: session.updated"),
    eventText(badPayload), "data: {}\n\n", "id: 1\nevent: session.created\ndata: {\n\n"];
  for (const text of cases) await assert.rejects(collect(clientFor(async () => streamResponse(text)).events({ after: 0, once: true })), StationProtocolError);
});

test("SSE ignores validated duplicates and requests resync after gaps or incomplete EOF", async () => {
  const first = eventText(savedEvents[0]!);
  assert.deepEqual(await collect(clientFor(async () => streamResponse(first + first)).events({ after: 0, once: true })), [savedEvents[0]]);
  assert.deepEqual(await collect(clientFor(async () => streamResponse(first + eventText(savedEvents[1]!) + first)).events({ after: 0, once: true })), savedEvents.slice(0, 2));
  for (const text of [eventText(savedEvents[1]!), first.slice(0, -1)])
    await assert.rejects(collect(clientFor(async () => streamResponse(text)).events({ after: 0, once: true })), StationStreamError);
});

test("SSE bounds partial events and rejects invalid UTF-8 without advancing a cursor", async () => {
  await assert.rejects(collect(clientFor(async () => streamResponse("data: " + "x".repeat(2 * 1024 * 1024))).events({ after: 0, once: true })), StationProtocolError);
  await assert.rejects(collect(clientFor(async () => new Response(new Uint8Array([0xff]), { headers: { "Content-Type": "text/event-stream" } })).events({ after: 0, once: true })), StationProtocolError);
});

test("SSE calls onOpen for a quiet authenticated stream and abort cancels its reader", async () => {
  let opened = 0, canceled = false;
  const control = new AbortController();
  const client = clientFor(async () => new Response(new ReadableStream<Uint8Array>({ cancel() { canceled = true; } }),
    { headers: { "Content-Type": "text/event-stream" } }));
  const rejected = assert.rejects(collect(client.events({ after: 0, signal: control.signal, onOpen: () => { opened++; } })), { name: "AbortError" });
  await flush(); assert.equal(opened, 1); control.abort(); await rejected; assert.equal(canceled, true);
});

test("SSE does not call onOpen for errors or wrong content type and never retries", async () => {
  for (const response of [new Response("error", { status: 401 }), new Response("{}", { headers: { "Content-Type": "application/json" } })]) {
    let opened = 0, calls = 0;
    const client = clientFor(async () => { calls++; return response; });
    await assert.rejects(collect(client.events({ after: 0, onOpen: () => { opened++; } })));
    assert.equal(opened, 0); assert.equal(calls, 1);
  }
});

test("SSE rejects unexpected live EOF and breaking consumption cancels the response", async () => {
  await assert.rejects(collect(clientFor(async () => streamResponse(": heartbeat\n\n")).events({ after: 0 })), StationStreamError);
  let canceled = false;
  const client = clientFor(async () => new Response(new ReadableStream<Uint8Array>({
    start(c) { c.enqueue(new TextEncoder().encode(eventText(savedEvents[0]!))); }, cancel() { canceled = true; },
  }), { headers: { "Content-Type": "text/event-stream" } }));
  for await (const _event of client.events({ after: 0 })) break;
  assert.equal(canceled, true);
});

test("SSE idle timeout is refreshed by server heartbeats", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let stream!: ReadableStreamDefaultController<Uint8Array>;
  const client = clientFor(async () => new Response(new ReadableStream<Uint8Array>({ start(c) { stream = c; } }),
    { headers: { "Content-Type": "text/event-stream" } }));
  const pending = collect(client.events({ after: 0, once: true }));
  await flush(); t.mock.timers.tick(30_000);
  stream.enqueue(new TextEncoder().encode(": keep-alive\n\n")); await flush();
  t.mock.timers.tick(30_000); stream.enqueue(new TextEncoder().encode(eventText(savedEvents[0]!))); stream.close();
  assert.equal((await pending).length, 1);
});

test("SSE quiet streams time out after the bounded heartbeat grace period", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const client = clientFor(async () => new Response(new ReadableStream<Uint8Array>(), { headers: { "Content-Type": "text/event-stream" } }));
  const rejected = assert.rejects(collect(client.events({ after: 0 })), StationTimeoutError);
  await flush(); t.mock.timers.tick(45_000); await rejected;
});

test("abort between token resolution and fetch observes the rejected fetch promise", async () => {
  const control = new AbortController();
  const client = new StationClient({ baseUrl: "http://station.example", getToken: () => TOKEN,
    fetch: async (_input, init) => { control.abort(); assert.equal(init?.signal?.aborted, true); throw new DOMException("Aborted", "AbortError"); } });
  await assert.rejects(client.listSessions(control.signal), { name: "AbortError" });
  // Let Node's unhandled-rejection turn run; a rejected operation must remain observed.
  await new Promise<void>(resolve => setImmediate(resolve));
});

test("real StationClient and DashboardStore reconnect after clean EOF, truncated EOF and cursor gaps", async () => {
  for (const interruption of ["clean", "truncated", "gap"] as const) {
    let eventCalls = 0, snapshotCalls = 0;
    const client = clientFor(async input => {
      const path = new URL(String(input)).pathname;
      if (path.endsWith("/station/snapshot")) { snapshotCalls++; return json(savedSnapshot); }
      if (path.endsWith("/sessions")) return json([savedSnapshot.session]);
      if (path.endsWith("/cameras")) return json({ status: "unavailable", cameras: [], reason: "Not integrated" });
      if (path.endsWith("/events")) {
        eventCalls++;
        if (eventCalls === 1) {
          if (interruption === "clean") return streamResponse(": keep-alive\n\n");
          if (interruption === "truncated") return streamResponse("id: 51\nevent: cycle.updated\ndata: {");
          const event = { ...savedEvents[0]!, sequence: 52 } as StationEvent;
          return streamResponse(eventText(event));
        }
        return new Response(new ReadableStream<Uint8Array>(), { headers: { "Content-Type": "text/event-stream" } });
      }
      throw new Error("Unexpected test endpoint");
    });
    const store = new DashboardStore(client, { reconnectDelayMs: 1, pollIntervalMs: 600_000, staleAfterMs: 600_000 });
    try {
      // The default live selection deliberately excludes the saved simulated session.
      await store.start();
      for (let i = 0; eventCalls < 2 && i < 100; i++) await new Promise(resolve => setTimeout(resolve, 2));
      assert.ok(eventCalls >= 2, `${interruption} must reconnect`);
      assert.ok(snapshotCalls >= 4, `${interruption} must refresh snapshots`);
      assert.notEqual(store.getState().connection, "incompatible");
      assert.equal(store.getState().lastEventSequence, 50);
      assert.equal(store.getState().metrics, null);
    } finally { store.stop(); }
  }
});

test("same-origin proxy mode sends no bearer credential and stays restricted to the browser origin", async () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, "location");
  Object.defineProperty(globalThis, "location", { configurable: true, value: { origin: "https://dashboard.example" } });
  let calls = 0;
  try {
    const client = new StationClient({ baseUrl: "https://dashboard.example", authMode: "same-origin-proxy", fetch: async (input, init) => {
      calls++; assert.equal(new URL(String(input)).origin, "https://dashboard.example");
      assert.equal(new Headers(init?.headers).has("Authorization"), false);
      assert.equal(init?.credentials, "omit"); assert.equal(init?.method, "GET");
      return json([]);
    } });
    assert.deepEqual(await client.listSessions(), []); assert.equal(calls, 1);
    assert.throws(() => new StationClient({ baseUrl: "https://other.example", authMode: "same-origin-proxy" }), TypeError);
    assert.throws(() => new StationClient({ baseUrl: "https://dashboard.example", authMode: "same-origin-proxy", getToken: () => TOKEN } as never), TypeError);
    Object.defineProperty(globalThis, "location", { configurable: true, value: { origin: "https://other.example" } });
    await assert.rejects(client.listSessions(), TypeError); assert.equal(calls, 1);
  } finally {
    if (previous) Object.defineProperty(globalThis, "location", previous);
    else Reflect.deleteProperty(globalThis, "location");
  }
  if (!previous) assert.throws(() => new StationClient({ baseUrl: "https://dashboard.example", authMode: "same-origin-proxy" }), TypeError);
});

function exportTestClient(options: { changeWatermark?: boolean; wrongScope?: boolean } = {}) {
  const exported = fixture<SessionExport>("sample-export.json");
  let version = 50, exports = 0;
  const client = clientFor(async input => {
    const url = new URL(String(input));
    if (url.pathname.endsWith("/station/snapshot")) {
      const snapshot = structuredClone(savedSnapshot); snapshot.lastEventSequence = snapshot.stateVersion = version; return json(snapshot);
    }
    if (url.pathname.endsWith("/sessions")) return json([savedSnapshot.session]);
    if (url.pathname.endsWith("/metrics")) return json(savedSnapshot.metrics);
    if (url.pathname.endsWith("/cycles")) return json({ items: exported.records.cycle, total: 5, offset: 0, limit: 100 });
    if (url.pathname.endsWith("/cycles/demo%3Ain_progress")) return json({ cycle: savedSnapshot.cycle, attempts: [], frames: [],
      inspections: [], modelRuns: [], utterances: [], decisions: [], executions: [], referenceLabels: [], confirmations: [], corrections: [], evidence: [], events: [], revisions: [] });
    if (url.pathname.endsWith("/cameras")) return json({ status: "unavailable", cameras: [], reason: "Not integrated" });
    if (url.pathname.endsWith("/export")) {
      exports++;
      if (options.changeWatermark && exports === 1) version++;
      const value = structuredClone(exported);
      if (options.wrongScope) value.session.sourceMode = "live";
      return json(value);
    }
    if (url.pathname.endsWith("/events")) return new Response(new ReadableStream<Uint8Array>(), { headers: { "Content-Type": "text/event-stream" } });
    throw new Error("Unexpected test endpoint");
  });
  return { client, count: () => exports };
}

test("full-session export is opt-in, preserves related records and clears on source switch", async () => {
  const options = { pollIntervalMs: 600_000, staleAfterMs: 600_000, reconnectDelayMs: 600_000 };
  const f = exportTestClient(); const defaultStore = new DashboardStore(f.client, options);
  try {
    await defaultStore.start({ sourceMode: "simulation" });
    assert.equal(f.count(), 0); assert.equal(defaultStore.getState().sessionExport, null);
  } finally { defaultStore.stop(); }
  const enabled = new DashboardStore(f.client, { ...options, loadSessionExport: true });
  try {
    await enabled.start({ sourceMode: "simulation" });
    const data = enabled.getState().sessionExport;
    assert.equal(f.count(), 1); assert.equal(data?.session.id, "demo:session");
    assert.equal(data?.records.cycle.length, 5); assert.equal(data?.events.length, 50);
    assert.ok(Object.isFrozen(data?.records));
    await enabled.select({ sourceMode: "live" });
    assert.equal(enabled.getState().sessionExport, null); assert.equal(enabled.getState().session, null); assert.equal(f.count(), 1);
  } finally { enabled.stop(); }
});

test("full-session export is read again if its enclosing snapshot watermark changes", async () => {
  const f = exportTestClient({ changeWatermark: true });
  const store = new DashboardStore(f.client, { loadSessionExport: true, pollIntervalMs: 600_000, staleAfterMs: 600_000 });
  const commits: number[] = [];
  store.subscribe(() => { if (store.getState().sessionExport) commits.push(store.getState().lastEventSequence); });
  try {
    await store.start({ sourceMode: "simulation" });
    assert.equal(f.count(), 2); assert.equal(store.getState().sessionExport?.session.id, "demo:session");
    assert.ok(commits.length > 0); assert.ok(commits.every(value => value === 51));
  } finally { store.stop(); }
});

test("full-session export with another source is rejected instead of published", async () => {
  const f = exportTestClient({ wrongScope: true });
  const store = new DashboardStore(f.client, { loadSessionExport: true });
  try {
    await store.start({ sourceMode: "simulation" });
    assert.equal(store.getState().connection, "incompatible");
    assert.equal(store.getState().sessionExport, null);
  } finally { store.stop(); }
});

test("audited review retains the exact payload for explicit retry and validates the returned original cycle", async () => {
  const detail = fixture<any>('sample-cycle-retry.json');
  const request = { id: 'review-1', eventId: 'review-event-1', expectedRevision: detail.cycle.revision,
    authorId: 'operator', reason: 'Independent late confirmation', createdAt: '2026-11-14T20:00:00Z', changes: { outcome: 'unverified' as const } };
  const sent: string[] = [];
  const client = clientFor(async (input, init) => {
    assert.equal(new URL(String(input)).pathname, '/api/v1/cycles/demo%3Aretry/review');
    assert.equal(init?.method, 'POST'); assert.equal(new Headers(init?.headers).get('X-Morph-Intent'),'record-review');
    assert.equal(new Headers(init?.headers).get('Content-Type'),'application/json');
    sent.push(String(init?.body)); return json({cycle:detail,duplicate:sent.length>1});
  });
  assert.equal((await client.reviewCycle('demo:retry',request)).duplicate,false);
  assert.equal((await client.reviewCycle('demo:retry',request)).duplicate,true);
  assert.equal(sent.length,2); assert.equal(sent[0],sent[1]); assert.deepEqual(JSON.parse(sent[0]!),request);
  await assert.rejects(from({cycle:detail,duplicate:false}).reviewCycle('another-cycle',request),StationProtocolError);
});

test("review conflicts and uncertain network failures never trigger an automatic retry", async () => {
  const request = {id:'review-2',eventId:'review-event-2',expectedRevision:1,authorId:'operator',reason:'Review',createdAt:'2026-11-14T20:00:00Z'};
  let calls=0;
  const client=clientFor(async()=>{calls++;return new Response('private server error',{status:409});});
  await assert.rejects(client.reviewCycle('demo:retry',request),error=>error instanceof StationHttpError&&error.status===409);
  assert.equal(calls,1);
  const disconnected=clientFor(async()=>{calls++;throw new TypeError('Network unavailable');});
  await assert.rejects(disconnected.reviewCycle('demo:retry',request)); assert.equal(calls,2);
});
