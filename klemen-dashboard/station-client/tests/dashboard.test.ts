/** Compact reads use saved simulation records and mocked HTTP, never physical equipment. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { StationClient, StationProtocolError, StationHttpError } from '../src/client.ts';
import { DashboardStore } from '../src/store.ts';
import type { DashboardRead, CycleDetail, SessionExport, Snapshot } from '../src/types.ts';
const read = <T>(name: string): T => JSON.parse(readFileSync(new URL(`../../verification/fixtures/${name}`, import.meta.url), 'utf8'));
const saved = read<SessionExport>('sample-export.json');
const snap = read<Snapshot>('sample-snapshot.json');
function detail(cycleId: string): CycleDetail {
  const records = saved.records;
  const scoped = <T extends { cycleId: string | null }>(rows: T[]) => rows.filter(row => row.cycleId === cycleId);
  return { cycle: records.cycle.find(c => c.id === cycleId)!, attempts: scoped(records.attempt), frames: scoped(records.frame),
    inspections: scoped(records.inspection), modelRuns: scoped(records.model_run), utterances: scoped(records.utterance),
    decisions: scoped(records.decision), executions: scoped(records.execution), referenceLabels: scoped(records.reference_label),
    confirmations: scoped(records.confirmation), corrections: scoped(records.correction), evidence: scoped(records.evidence),
    events: scoped(saved.events), revisions: saved.revisions.filter(r => r.entityId === cycleId) };
}
export function bundle(sequence = 50): DashboardRead {
  const snapshot = structuredClone(snap); snapshot.lastEventSequence = snapshot.stateVersion = sequence;
  const currentDetail = snapshot.cycle ? detail(snapshot.cycle.id) : null;
  return { schemaVersion: 1, dashboardVersion: 1, generatedAt: snapshot.generatedAt, lastEventSequence: sequence,
    sourceMode: 'simulation', selectedSessionId: saved.session.id,
    sessions: { items: [saved.session], total: 1, limit: 50, hasMore: false }, snapshot, metrics: snapshot.metrics,
    recentCycles: { items: saved.records.cycle, total: saved.records.cycle.length, limit: 20, offset: 0, hasMore: false },
    currentDetail, detail: currentDetail, cameras: { status: 'unavailable', cameras: [], reason: 'Not integrated' } };
}
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const client = (value: unknown) => new StationClient({ baseUrl: 'http://127.0.0.1:1234', getToken: () => 'isolated-test-token-no-real-credentials', fetch: async () => json(value) });
test('compact response validates coherent scope, watermark and bounded pages', async () => {
  const result = await client(bundle()).getDashboard({ sourceMode: 'simulation' });
  assert.equal(result.metrics.endToEnd.denominator, 4); assert.equal(result.metrics.retries, 1);
  for (const mutate of [
    (v: DashboardRead) => { v.lastEventSequence++; },
    (v: DashboardRead) => { v.sourceMode = 'live'; },
    (v: DashboardRead) => { v.recentCycles.hasMore = true; },
    (v: DashboardRead) => { v.sessions.items.push(v.sessions.items[0]); },
    (v: DashboardRead) => { v.selectedSessionId = 'other'; },
    (v: DashboardRead) => { v.currentDetail = null; },
    (v: DashboardRead) => { v.currentDetail = structuredClone(v.currentDetail); v.currentDetail!.cycle.revision++; },
  ]) {
    const invalid = structuredClone(bundle()); mutate(invalid);
    await assert.rejects(client(invalid).getDashboard({ sourceMode: 'simulation' }), StationProtocolError);
  }
});
test('dashboard discovery requires the explicitly advertised version and route', async () => {
  assert.equal(await client({ capabilities: { dashboardRead: { version: 1, path: '/api/v1/dashboard' } } }).supportsDashboard(), true);
  assert.equal(await client({ recordTypes: {} }).supportsDashboard(), false);
  assert.equal(await client({ capabilities: { dashboardRead: { version: 2, path: '/wrong' } } }).supportsDashboard(), false);
});
test('one compact snapshot per refresh works while global sequence advances and never loads export', async () => {
  let sequence = 50, reads = 0, discovery = 0;
  const forbidden = async () => { throw new Error('Legacy/whole-session read should not occur'); };
  const fake = { getDashboard: async () => { reads++; return bundle(sequence++); }, supportsDashboard: async () => { discovery++; return true; },
    getSnapshot: forbidden, listSessions: forbidden, getMetrics: forbidden, listCycles: forbidden, getCycle: forbidden,
    getCameras: forbidden, exportSession: forbidden,
    events: async function*({ signal }: { signal?: AbortSignal }) { await new Promise<void>(r => signal?.addEventListener('abort', () => r(), { once: true })); } };
  const store = new DashboardStore(fake as any, { preferDashboard: true, pollIntervalMs: 600000, staleAfterMs: 600000 });
  try {
    await store.start({ sourceMode: 'simulation' });
    await store.refresh(); await store.refresh();
    assert.equal(reads, 3); assert.equal(discovery, 1); assert.equal(store.getState().lastEventSequence, 52);
    assert.equal(store.getState().metrics?.retries, 1); assert.equal(store.getState().sessionExport, null);
    assert.equal(store.getState().connection, 'connected');
  } finally { store.stop(); }
});
test('failed compact read retains counts as stale instead of inventing failures', async () => {
  let fail = false;
  const fake = { supportsDashboard: async () => true, getDashboard: async () => { if (fail) throw new Error('offline'); return bundle(); },
    events: async function*({ signal }: { signal?: AbortSignal }) { await new Promise<void>(r => signal?.addEventListener('abort', () => r(), { once: true })); } };
  const store = new DashboardStore(fake as any, { preferDashboard: true, pollIntervalMs: 600000, staleAfterMs: 600000 });
  try {
    await store.start({ sourceMode: 'simulation' }); const before = store.getState().metrics;
    fail = true; await store.refresh();
    assert.equal(store.getState().stale, true); assert.equal(store.getState().connection, 'disconnected');
    assert.deepEqual(store.getState().metrics, before);
    fail = false; await store.refresh(); assert.equal(store.getState().stale, false);
  } finally { store.stop(); }
});
test('compact auto-follow clears old focused cycle only after confirming a newer session', async () => {
  let next = false, focused = false;
  const fake = { supportsDashboard: async () => true, getDashboard: async (options: any) => {
    if (next && options.cycleId) throw new StationHttpError(409);
    focused = !!options.cycleId;
    const value = bundle();
    if (next) { value.snapshot.session = { ...value.snapshot.session!, id: 'new:session' }; value.currentDetail = value.detail = null; }
    return value;
  }, events: async function*({ signal }: { signal?: AbortSignal }) { await new Promise<void>(r => signal?.addEventListener('abort', () => r(), { once: true })); } };
  const store = new DashboardStore(fake as any, { preferDashboard: true, pollIntervalMs: 600000, staleAfterMs: 600000 });
  try {
    await store.start({ sourceMode: 'simulation' }); await store.selectCycle('demo:retry');
    assert.equal(focused, true); next = true; await store.refresh();
    assert.equal(store.getState().session?.id, 'new:session'); assert.equal(store.getState().connection, 'connected');
    assert.equal(store.getState().detail, null);
  } finally { store.stop(); }
});
