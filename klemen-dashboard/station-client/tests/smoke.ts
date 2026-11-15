/** Real HTTP assertions. The Python runner owns an isolated server, fixture and token. */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { StationClient, StationHttpError } from '../src/client.ts';
import { DashboardStore } from '../src/store.ts';
import type { Metrics, StationEvent } from '../src/types.ts';

function environment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`The isolated smoke runner must supply ${name}.`);
  return value;
}

const baseUrl = environment('MORPH_SMOKE_BASE_URL');
const token = environment('MORPH_SMOKE_TOKEN');
const prefix = environment('MORPH_SMOKE_PREFIX');
const sessionId = environment('MORPH_SMOKE_SESSION_ID');
const liveSessionId = environment('MORPH_SMOKE_LIVE_SESSION_ID');
const expectedSequence = Number(environment('MORPH_SMOKE_EXPECTED_SEQUENCE'));
const resumeAfter = Number(environment('MORPH_SMOKE_RESUME_AFTER'));
const phase = environment('MORPH_SMOKE_PHASE');
const reportPath = environment('MORPH_SMOKE_REPORT_PATH');
const requests: { method: string; path: string; eventStream: boolean }[] = [];
let interruptNextStream = false;
let interruptedStreams = 0;
const interruptTimers = new Set<ReturnType<typeof setTimeout>>();

// The transport always calls the real server. One deliberate connection cut tests
// reconnect behavior without writing fake events or requiring a robot/provider.
const observedFetch: typeof fetch = async (input, init) => {
  const request = new Request(input, init);
  const url = new URL(request.url);
  assert.equal(url.origin, baseUrl);
  assert.equal(url.searchParams.has('token'), false, 'Credentials must not appear in a query string.');
  const eventStream = url.pathname === '/api/v1/events';
  requests.push({ method: request.method, path: url.pathname, eventStream });
  if (interruptNextStream && eventStream && !request.signal.aborted && url.searchParams.get('once') !== 'true') {
    interruptNextStream = false;
    interruptedStreams++;
    const interruption = new AbortController();
    const timer = setTimeout(() => {
      interruptTimers.delete(timer);
      interruption.abort();
    }, 150);
    interruptTimers.add(timer);
    return fetch(input, { ...init, signal: AbortSignal.any([request.signal, interruption.signal]) });
  }
  return fetch(input, init);
};

const client = new StationClient({ baseUrl, getToken: () => token, fetch: observedFetch });
const unauthorized = new StationClient({ baseUrl, getToken: () => 'invalid-smoke-token-'.repeat(3), fetch: observedFetch });
const checks: string[] = [];
const stores: DashboardStore[] = [];

async function check(name: string, action: () => Promise<void>): Promise<void> {
  process.stdout.write(`Checking: ${name}\n`);
  await action();
  checks.push(name);
}

async function collect(iterable: AsyncIterable<StationEvent>): Promise<StationEvent[]> {
  const values: StationEvent[] = [];
  for await (const value of iterable) values.push(value);
  return values;
}

function simulationMetrics(metrics: Metrics | null): void {
  assert.ok(metrics);
  assert.deepEqual([metrics.endToEnd.numerator, metrics.endToEnd.denominator], [2, 4]);
  assert.deepEqual([metrics.physicalExecution.numerator, metrics.physicalExecution.denominator], [3, 5]);
  assert.equal(metrics.endToEnd.value, 0.5);
  assert.equal(metrics.physicalExecution.value, 0.6);
  assert.equal(metrics.cycles.total, 5);
  assert.equal(metrics.cycles.inProgress, 1);
  assert.equal(metrics.cycles.unverified, 1);
  assert.equal(metrics.attempts.failed, 1);
  assert.equal(metrics.attempts.unverified, 1);
  assert.equal(metrics.firstAttemptSuccesses, 1);
  assert.equal(metrics.recoveredCycles, 1);
  assert.equal(metrics.retries, 1);
  assert.equal(metrics.additionalInspections, 1);
  assert.deepEqual([metrics.detection.correct, metrics.detection.checked, metrics.detection.totalPopulation], [3, 4, 5]);
}

function emptyMetrics(metrics: Metrics | null): void {
  assert.ok(metrics);
  assert.equal(metrics.endToEnd.denominator, 0);
  assert.equal(metrics.endToEnd.value, null);
  assert.equal(metrics.physicalExecution.denominator, 0);
  assert.equal(metrics.physicalExecution.value, null);
}

// Parse complete CSV cells, including JSON's quoted commas and escaped quotes.
function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], field = '', quoted = false;
  for (let position = 0; position < text.length; position++) {
    const char = text[position];
    if (quoted) {
      if (char === '"' && text[position + 1] === '"') { field += '"'; position++; }
      else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"') quoted = true;
    else if (char === ',') { row.push(field); field = ''; }
    else if (char === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (char !== '\r') field += char;
  }
  assert.equal(quoted, false, 'CSV must end outside a quoted field.');
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows;
}

async function eventually(predicate: () => boolean, description: string): Promise<void> {
  const deadline = Date.now() + 5_000;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error(`Timed out: ${description}`);
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}

let replayed: StationEvent[] = [];
let resumeCursor = 0;
try {
  await check('invalid bearer token rejects JSON and SSE with HTTP 401', async () => {
    const isUnauthorized = (error: unknown) => error instanceof StationHttpError && error.status === 401;
    await assert.rejects(unauthorized.listSessions(), isUnauthorized);
    await assert.rejects(collect(unauthorized.events({ after: 0, once: true })), isUnauthorized);
  });

  await check('live metrics exclude simulation and preserve empty denominators', async () => {
    emptyMetrics(await client.getMetrics({}));
    emptyMetrics(await client.getMetrics({ sessionId }));
    emptyMetrics(await client.getMetrics({ sessionId: liveSessionId }));
    assert.equal((await client.listCycles({})).total, 0);
  });

  await check('explicit simulation uses persisted cycle, attempt and detection denominators', async () => {
    simulationMetrics(await client.getMetrics({ includeSimulation: true }));
    simulationMetrics(await client.getMetrics({ sessionId, includeSimulation: true }));
    const snapshot = await client.getSnapshot(sessionId);
    assert.equal(snapshot.lastEventSequence, expectedSequence);
    assert.equal(snapshot.sourceMode, 'simulation');
    assert.equal(snapshot.session?.id, sessionId);
    assert.deepEqual(snapshot.availableActions, []);
    assert.ok(Object.values(snapshot.capabilities).every((capability) => capability.status === 'unavailable' && !capability.verified));
    const cycles = await client.listCycles({ sessionId, sourceMode: 'simulation', includeSimulation: true });
    assert.equal(cycles.total, 5);
    const retries = await client.listCycles({ sessionId, sourceMode: 'simulation', hasRetry: true });
    assert.deepEqual(retries.items.map((cycle) => cycle.id), [`${prefix}:retry`]);
  });

  await check('retry detail preserves failed attempt, extra inspection and physical evidence', async () => {
    const detail = await client.getCycle(`${prefix}:retry`);
    assert.equal(detail.cycle.outcome, 'correct');
    assert.deepEqual(detail.attempts.map((attempt) => attempt.outcome), ['failed', 'successful']);
    assert.equal(detail.attempts[1].retryOfAttemptId, detail.attempts[0].id);
    assert.equal(detail.attempts[0].errorCode, 'simulated_failed_grasp');
    assert.equal(detail.inspections.length, 2);
    assert.equal(detail.inspections[1].additionalInspectionOfId, detail.inspections[0].id);
    assert.ok(detail.revisions.length > detail.attempts.length);
    const wrongBin = await client.getCycle(`${prefix}:wrong_bin`);
    assert.equal(wrongBin.attempts[0].outcome, 'successful');
    assert.equal(wrongBin.cycle.outcome, 'failed');
    assert.equal(wrongBin.cycle.observedDestination, 'defective_bin');
    assert.equal(wrongBin.referenceLabels[0].quality, 'good');
    const evidence = detail.evidence[0];
    const blob = await client.getEvidence(evidence.id);
    const bytes = Buffer.from(await blob.arrayBuffer());
    assert.equal(blob.type, 'image/png');
    assert.equal(bytes.length, evidence.size);
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), evidence.sha256);
  });

  await check('authenticated SSE catch-up pages all events exactly once', async () => {
    let cursor = 0;
    while (cursor < expectedSequence) {
      const page = await collect(client.events({ after: cursor, once: true, limit: 7 }));
      assert.ok(page.length > 0 && page.length <= 7);
      replayed.push(...page);
      cursor = page.at(-1)!.sequence;
    }
    assert.deepEqual(replayed.map((event) => event.sequence), Array.from({ length: expectedSequence }, (_, index) => index + 1));
    assert.equal(new Set(replayed.map((event) => event.eventId)).size, expectedSequence);
    assert.ok(replayed.some((event) => event.sourceMode === 'live'));
    assert.ok(replayed.some((event) => event.sourceMode === 'simulation'));
    assert.deepEqual(await collect(client.events({ after: cursor, once: true })), []);
    resumeCursor = replayed[4].sequence;
  });

  await check(phase === 'after-restart' ? 'saved SSE cursor resumes persisted history after server restart' : 'partial SSE cursor resumes without replaying earlier events', async () => {
    const cursor = resumeAfter || resumeCursor;
    const resumed = await collect(client.events({ after: cursor, once: true, limit: 1000 }));
    assert.deepEqual(resumed.map((event) => event.sequence), replayed.filter((event) => event.sequence > cursor).map((event) => event.sequence));
    await assert.rejects(collect(client.events({ after: expectedSequence + 1, once: true })),
      (error: unknown) => error instanceof StationHttpError && error.status === 409);
  });

  await check('JSON and CSV exports preserve source labels, outcomes and record counts', async () => {
    const exported = await client.exportSession(sessionId, 'json');
    assert.equal(exported.session.sourceMode, 'simulation');
    assert.equal(exported.records.cycle.length, 5);
    assert.equal(exported.records.attempt.length, 5);
    assert.equal(exported.records.attempt.filter((attempt) => attempt.outcome === 'failed').length, 1);
    simulationMetrics(exported.metrics);
    const rows = csvRows(await client.exportSession(sessionId, 'csv'));
    assert.deepEqual(rows.shift(), ['section', 'recordType', 'id', 'dataJson']);
    assert.ok(rows.every((row) => row.length === 4));
    assert.equal(rows.filter((row) => row[0] === 'records' && row[1] === 'cycle').length, 5);
    assert.equal(rows.filter((row) => row[0] === 'records' && row[1] === 'attempt').length, 5);
    assert.equal(rows.filter((row) => row[0] === 'events').length, exported.events.length);
    const csvSession = rows.find((row) => row[0] === 'session');
    assert.ok(csvSession);
    assert.equal(JSON.parse(csvSession[3]).sourceMode, 'simulation');
  });

  await check('caller abort stops an open authenticated stream and pre-aborted read', async () => {
    const controller = new AbortController();
    const pending = collect(client.events({ after: expectedSequence, signal: controller.signal }));
    const timer = setTimeout(() => controller.abort(), 100);
    try {
      await assert.rejects(pending, (error: unknown) => error instanceof Error && error.name === 'AbortError');
    } finally { clearTimeout(timer); controller.abort(); }
    await assert.rejects(client.getSnapshot(undefined, controller.signal),
      (error: unknown) => error instanceof Error && error.name === 'AbortError');
  });

  await check('shared store construction, live/simulation selection and refresh remain read-only', async () => {
    const beforeConstruction = requests.length;
    const store = new DashboardStore(client, { pollIntervalMs: 60_000, staleAfterMs: 60_000, reconnectDelayMs: 25 });
    stores.push(store);
    let updates = 0;
    let sawReconnect = false;
    const unsubscribe = store.subscribe(() => { updates++; sawReconnect ||= store.getState().stream === 'reconnecting'; });
    assert.equal(requests.length, beforeConstruction);
    assert.equal(store.getState().connection, 'idle');
    await store.start();
    assert.equal(store.getState().connection, 'connected');
    assert.equal(store.getState().selection.sourceMode, 'live');
    assert.equal(store.getState().session?.id, liveSessionId);
    emptyMetrics(store.getState().metrics);
    assert.equal(store.getState().cycles?.total, 0);
    assert.equal(store.getState().detail, null);

    await store.select({ sourceMode: 'simulation' });
    assert.equal(store.getState().session?.id, sessionId);
    simulationMetrics(store.getState().metrics);
    assert.equal(store.getState().cycles?.total, 5);
    assert.equal(store.getState().currentDetail?.cycle.id, `${prefix}:in_progress`);
    assert.ok(store.getState().sessions.every((session) => session.sourceMode === 'simulation'));
    await store.selectCycle(`${prefix}:retry`);
    assert.equal(store.getState().detail?.attempts.length, 2);
    assert.equal(store.getState().detail?.cycle.id, `${prefix}:retry`);
    await store.refresh();
    simulationMetrics(store.getState().metrics);
    assert.equal(store.getState().lastEventSequence, expectedSequence);
    assert.equal(Object.isFrozen(store.getState()), true);
    assert.equal(Object.isFrozen(store.getState().metrics), true);

    await store.select({ sourceMode: 'live', sessionId: liveSessionId });
    emptyMetrics(store.getState().metrics);
    assert.equal(store.getState().detail, null);
    assert.equal(store.getState().currentDetail, null);
    assert.equal(store.getState().cycles?.total, 0);
    assert.ok(store.getState().sessions.every((session) => session.sourceMode === 'live'));

    const previousStreams = requests.filter((request) => request.eventStream).length;
    interruptNextStream = true;
    await store.select({ sourceMode: 'simulation', sessionId });
    try {
      await eventually(() => sawReconnect && requests.filter((request) => request.eventStream).length >= previousStreams + 2,
        'shared store reconnects after the injected real SSE connection cut');
    } catch (error) {
      const state = store.getState();
      throw new Error(`${String(error)}; connection=${state.connection}; stream=${state.stream}; ` +
        `interrupted=${interruptedStreams}; opened=${requests.filter((request) => request.eventStream).length - previousStreams}`);
    }
    await eventually(() => store.getState().connection === 'connected', 'shared store refreshes after reconnect');
    simulationMetrics(store.getState().metrics);
    assert.equal(store.getState().lastEventSequence, expectedSequence);
    assert.equal(interruptedStreams, 1);
    assert.ok(updates > 0);
    unsubscribe();
    const updatesAtUnsubscribe = updates;
    store.stop();
    assert.equal(store.getState().stale, true);
    const requestsAtStop = requests.length;
    await store.refresh();
    assert.equal(requests.length, requestsAtStop);
    assert.equal(updates, updatesAtUnsubscribe);
  });

  await check('shared store reports rejected authentication without showing a connected state', async () => {
    const store = new DashboardStore(unauthorized, { pollIntervalMs: 60_000 });
    stores.push(store);
    await store.start();
    assert.equal(store.getState().connection, 'unauthorized');
    assert.equal(store.getState().stale, true);
    assert.equal(store.getState().metrics, null);
    store.stop();
  });

  await check('all client operations use GET and leave the authoritative event sequence unchanged', async () => {
    assert.equal((await client.getSnapshot()).lastEventSequence, expectedSequence);
    assert.ok(requests.length > 0);
    assert.ok(requests.every((request) => request.method === 'GET'));
  });

  await writeFile(reportPath, JSON.stringify({
    status: 'passed', phase, checks, checkCount: checks.length, httpRequestCount: requests.length,
    eventCountAfterReads: expectedSequence, replayedEventCount: replayed.length, resumeCursor,
    resumedFromCursor: resumeAfter || resumeCursor, injectedStreamDisconnects: interruptedStreams,
    reconnectTransport: 'One aborted real SSE request, followed by real HTTP reconnect and refresh.',
    allRequestsReadOnly: true,
  }, null, 2) + '\n');
} finally {
  for (const store of stores) store.stop();
  for (const timer of interruptTimers) clearTimeout(timer);
}
