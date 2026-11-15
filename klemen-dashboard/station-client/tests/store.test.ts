import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { DashboardStore } from '../src/store.ts';
import { StationHttpError, StationProtocolError } from '../src/client.ts';
import { formatRatio, formatTimestamp, frameFreshness, projectViews } from '../src/views.ts';

const fixture = JSON.parse(await readFile(new URL('../../verification/fixtures/sample-snapshot.json', import.meta.url), 'utf8'));
const copy = <T>(value: T): T => structuredClone(value);
const noEvents = async function* ({ signal }: { signal?: AbortSignal }) {
  await new Promise<void>((resolve) => {
    if (signal?.aborted) resolve();
    else signal?.addEventListener('abort', () => resolve(), { once: true });
  });
};
function fake() {
  const live = { ...copy(fixture.session), id: 'live:session', sourceMode: 'live', startedAt: '2026-11-14T14:00:00Z' };
  const f: any = { sessions: [copy(fixture.session)], calls: [], version: 50,
    async getSnapshot(id?: string) {
      f.calls.push(['snapshot', id]);
      const snapshot = copy(fixture);
      snapshot.lastEventSequence = snapshot.stateVersion = f.version;
      if (id === live.id) { snapshot.session = live; snapshot.sourceMode = 'live'; snapshot.cycle = null; snapshot.activeCycleIds = []; }
      return snapshot;
    },
    async listSessions() { f.calls.push(['sessions']); return copy(f.sessions); },
    async getMetrics(options: any) {
      f.calls.push(['metrics', options]);
      const m = copy(fixture.metrics); m.filters.sessionId = options.sessionId; m.filters.includedSessionIds = [options.sessionId];
      m.filters.includeSimulation = options.includeSimulation; return m;
    },
    async listCycles(filters: any) { f.calls.push(['cycles', filters]); return { items: [], total: 0, offset: 0, limit: 100 }; },
    async getCycle(id: string) { f.calls.push(['cycle', id]); return { cycle: { ...copy(fixture.cycle), id }, attempts: [], frames: [], inspections: [], modelRuns: [], utterances: [], decisions: [], executions: [], referenceLabels: [], confirmations: [], corrections: [], evidence: [], events: [], revisions: [] }; },
    async getCameras() { return { status: 'unavailable', cameras: [], reason: 'Not integrated' }; },
    events: noEvents,
    live,
  };
  return f;
}
const options = { pollIntervalMs: 600_000, staleAfterMs: 600_000, reconnectDelayMs: 600_000 };

test('construct/subscribe do no I/O; live default does not expose the server-selected simulation', async () => {
  const f = fake(); const store = new DashboardStore(f, options); const unsubscribe = store.subscribe(() => {});
  assert.equal(f.calls.length, 0);
  await store.start();
  try {
    const state = store.getState();
    assert.equal(state.connection, 'connected'); assert.equal(state.session, null); assert.equal(state.snapshot, null);
    assert.equal(state.metrics, null); assert.equal(state.cycles, null); assert.equal(state.lastEventSequence, 50);
    assert.equal(projectViews(state).quality.endToEnd.value, 'No data yet');
    assert.equal(f.calls.some((c: any[]) => c[0] === 'metrics'), false);
  } finally { unsubscribe(); store.stop(); }
});

test('explicit simulation shares authoritative session and metrics across all views without changing retries', async () => {
  const f = fake(); const store = new DashboardStore(f, options);
  await store.start({ sourceMode: 'simulation' });
  try {
    const s = store.getState(); const views = projectViews(s);
    assert.equal(s.metrics?.endToEnd.numerator, 2); assert.equal(s.metrics?.endToEnd.denominator, 4);
    assert.equal(s.metrics?.physicalExecution.numerator, 3); assert.equal(s.metrics?.physicalExecution.denominator, 5);
    assert.equal(s.metrics?.retries, 1); assert.equal(s.metrics?.recoveredCycles, 1);
    assert.equal(views.live.session, views.quality.session); assert.equal(views.system.session, views.live.session);
    assert.equal(views.quality.endToEnd.counts, '2 / 4'); assert.equal(views.system.telemetry, null);
    assert.equal(views.live.liveVideo.status, 'unavailable'); assert.deepEqual(views.live.availableActions, []);
    await store.refresh(); assert.deepEqual(store.getState().metrics, s.metrics);
    assert.ok(Object.isFrozen(s.metrics));
  } finally { store.stop(); }
});

test('selecting live clears prior simulation and requests an explicitly live session', async () => {
  const f = fake(); f.sessions.push(f.live); const store = new DashboardStore(f, options);
  await store.start({ sourceMode: 'simulation' });
  await store.select({ sourceMode: 'live' });
  try {
    assert.equal(store.getState().session?.id, 'live:session');
    assert.equal(store.getState().detail, null); assert.equal(store.getState().currentDetail, null);
    assert.ok(f.calls.some((c: any[]) => c[0] === 'metrics' && c[1].includeSimulation === false && c[1].sessionId === 'live:session'));
  } finally { store.stop(); }
});

test('a snapshot watermark change retries all reads before publishing a coherent version', async () => {
  const f = fake(); const getMetrics = f.getMetrics; let changed = false;
  f.getMetrics = async (o: any) => { const m = await getMetrics(o); if (!changed) { f.version++; changed = true; } return m; };
  const store = new DashboardStore(f, options); const commits: number[] = [];
  store.subscribe(() => { if (store.getState().metrics) commits.push(store.getState().lastEventSequence); });
  await store.start({ sourceMode: 'simulation' });
  try { assert.equal(store.getState().lastEventSequence, 51); assert.ok(commits.every((v) => v === 51)); assert.equal(f.calls.filter((c: any[]) => c[0] === 'metrics').length, 2); }
  finally { store.stop(); }
});

test('late requests from a previous source cannot overwrite the new selection', async () => {
  const f = fake(); const getMetrics = f.getMetrics; let release!: () => void;
  f.getMetrics = async (o: any) => { await new Promise<void>((r) => { release = r; }); return getMetrics(o); };
  const store = new DashboardStore(f, options);
  const oldLoad = store.start({ sourceMode: 'simulation' });
  while (!release) await new Promise((r) => setTimeout(r, 1));
  await store.select({ sourceMode: 'live' });
  release(); await oldLoad;
  try { assert.equal(store.getState().selection.sourceMode, 'live'); assert.equal(store.getState().metrics, null); }
  finally { store.stop(); }
});

test('unknown explicit session fails visibly and never falls back to another session', async () => {
  const store = new DashboardStore(fake(), options);
  await store.start({ sourceMode: 'live', sessionId: fixture.session.id });
  try { assert.equal(store.getState().connection, 'incompatible'); assert.equal(store.getState().session, null); }
  finally { store.stop(); }
});

test('disconnect retains last confirmed records, marks them stale, and recovers without incrementing metrics', async () => {
  const f = fake(); const store = new DashboardStore(f, options);
  await store.start({ sourceMode: 'simulation' }); const oldMetrics = store.getState().metrics;
  const previous = f.listSessions; f.listSessions = async () => { throw new Error('network'); };
  await store.refresh();
  assert.equal(store.getState().connection, 'disconnected'); assert.equal(store.getState().stale, true);
  assert.equal(store.getState().metrics, oldMetrics);
  f.listSessions = previous; await store.refresh();
  try { assert.equal(store.getState().connection, 'connected'); assert.deepEqual(store.getState().metrics, oldMetrics); }
  finally { store.stop(); }
});

test('receipt age and stale analyzed frame age are distinct', async () => {
  let now = Date.parse('2026-11-14T16:50:00Z');
  const store = new DashboardStore(fake(), { ...options, staleAfterMs: 1_000, now: () => now });
  await store.start({ sourceMode: 'simulation' }); now += 1_001; store.checkFreshness();
  try {
    assert.equal(store.getState().stale, true);
    assert.equal(frameFreshness('2026-11-14T16:49:00Z', now, 'live').status, 'stale');
    assert.equal(frameFreshness('2026-11-14T16:49:00Z', now, 'simulation').status, 'simulation');
    assert.equal(frameFreshness('2026-11-14T17:49:00Z', now, 'live').status, 'invalid_timestamp');
  } finally { store.stop(); }
});

test('empty ratios and timestamps retain meaningful labels', () => {
  assert.equal(formatRatio(null).value, 'No data yet');
  assert.equal(formatRatio(fixture.metrics.detection.defectEscape).value, 'No data yet');
  assert.match(formatTimestamp('2026-11-14T16:50:00Z'), /17:50:00/);
  assert.match(formatTimestamp('2026-11-14T16:50:00Z'), /Europe\/Ljubljana/);
  assert.equal(formatTimestamp(null), 'Unavailable');
});

test('duplicate, out-of-order and gap events only invalidate authoritative reads', async () => {
  const f = fake(); let delivered = false;
  f.events = async function* ({ signal }: { signal: AbortSignal }) {
    yield { sequence: 50 };
    f.version = 52;
    yield { sequence: 52 };
    yield { sequence: 52 };
    yield { sequence: 49 };
    delivered = true;
    yield* noEvents({ signal });
  };
  const store = new DashboardStore(f, options);
  await store.start({ sourceMode: 'simulation' });
  while (!delivered) await new Promise((r) => setTimeout(r, 1));
  try {
    assert.equal(store.getState().lastEventSequence, 52);
    assert.equal(store.getState().metrics?.cycles.total, 5);
    assert.equal(store.getState().metrics?.endToEnd.numerator, 2);
    assert.equal(f.calls.filter((c: any[]) => c[0] === 'metrics').length, 2);
  } finally { store.stop(); }
});

test('history selection does not replace the current object in Live inspection', async () => {
  const store = new DashboardStore(fake(), options);
  await store.start({ sourceMode: 'simulation' }); await store.selectCycle('demo:retry');
  try {
    const views = projectViews(store.getState());
    assert.equal(views.quality.selectedCycle?.cycle.id, 'demo:retry');
    assert.equal(views.live.cycle?.id, 'demo:in_progress');
  } finally { store.stop(); }
});

test('auto-follow of a newer session clears the previous session history focus', async () => {
  const f = fake(); const originalSnapshot = f.getSnapshot;
  const nextSession = { ...copy(fixture.session), id: 'demo:next-session', startedAt: '2026-11-14T19:00:00Z' };
  f.getSnapshot = async (id?: string) => {
    const snapshot = await originalSnapshot(id);
    if (id === nextSession.id) { snapshot.session = nextSession; snapshot.cycle = null; snapshot.activeCycleIds = []; }
    return snapshot;
  };
  const store = new DashboardStore(f, options);
  await store.start({ sourceMode: 'simulation' }); await store.selectCycle('demo:retry');
  f.sessions.push(nextSession); f.version++;
  await store.refresh();
  try {
    assert.equal(store.getState().connection, 'connected');
    assert.equal(store.getState().session?.id, nextSession.id);
    assert.equal(store.getState().detail, null);
    assert.equal(store.getState().currentDetail, null);
  } finally { store.stop(); }
});

for (const [label, error, connection] of [
  ['unauthorized', new StationHttpError(401), 'unauthorized'],
  ['incompatible', new StationProtocolError(), 'incompatible'],
] as const) {
  test(`initial ${label} response does not install automatic polling`, async () => {
    const f = fake(); let reads = 0;
    f.getSnapshot = async () => { reads++; throw error; };
    const store = new DashboardStore(f, { ...options, pollIntervalMs: 1 });
    await store.start();
    await new Promise((resolve) => setTimeout(resolve, 15));
    try {
      assert.equal(reads, 1);
      assert.equal(store.getState().connection, connection);
      assert.equal(store.getState().stream, 'unavailable');
    } finally { store.stop(); }
  });
}
