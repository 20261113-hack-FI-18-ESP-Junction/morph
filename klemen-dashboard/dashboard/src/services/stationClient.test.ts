import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { StationClient } from '@morph/station-client';
import type { DashboardRead, SessionExport, Snapshot, CycleDetail } from '@morph/station-client';
import { MorphStationClient } from './stationClient.ts';
const read = <T>(name: string): T => JSON.parse(readFileSync(new URL(`../../../verification/fixtures/${name}`, import.meta.url), 'utf8'));
const data = read<SessionExport>('sample-export.json');
const savedSnapshot = read<Snapshot>('sample-snapshot.json');
const detailKeys = { attempts: 'attempt', frames: 'frame', inspections: 'inspection', modelRuns: 'model_run',
  utterances: 'utterance', decisions: 'decision', executions: 'execution', referenceLabels: 'reference_label',
  confirmations: 'confirmation', corrections: 'correction', evidence: 'evidence' } as const;
function harness(sessionCount = 1) {
  let sequence = 50, exports = 0, reads = 0, catalogReads = 0, sessionId = data.session.id, deferExport: (() => Promise<void>) | null = null;
  let serverExport = structuredClone(data);
  const dashboardRequests: { sessionId: string | null; cycleId: string | null }[] = [];
  const forSession = <T>(value: T, selected: string): T => JSON.parse(JSON.stringify(value).replaceAll(data.session.id, selected));
  const catalog = Array.from({ length: sessionCount }, (_, index) => ({ ...data.session,
    id: index === 0 ? data.session.id : `saved:session:${index}`,
    startedAt: new Date(Date.parse(data.session.startedAt) - index * 60_000).toISOString() }));
  function bundle(selected: string, focusedCycleId: string | null): DashboardRead {
    const snapshot = structuredClone(savedSnapshot); snapshot.lastEventSequence = snapshot.stateVersion = sequence;
    snapshot.metrics = serverExport.metrics;
    const cycleDetail = (cycleId: string) => {
      const cycle = serverExport.records.cycle.find(record => record.id === cycleId)!;
      const detail: any = { cycle, events: serverExport.events.filter(e => e.cycleId === cycle.id), revisions: [] };
      for (const [key, type] of Object.entries(detailKeys)) detail[key] = serverExport.records[type as Exclude<keyof typeof data.records, 'cycle'>].filter(row => row.cycleId === cycle.id);
      return detail as CycleDetail;
    };
    const result = forSession({ schemaVersion: 1, dashboardVersion: 1, sourceMode: 'simulation', selectedSessionId: data.session.id,
      generatedAt: snapshot.generatedAt, lastEventSequence: sequence,
      sessions: { items: catalog.slice(0, 50), total: catalog.length, limit: 50, hasMore: catalog.length > 50 }, snapshot, metrics: snapshot.metrics,
      recentCycles: { items: serverExport.records.cycle, total: serverExport.records.cycle.length, offset: 0, limit: 20, hasMore: false },
      currentDetail: cycleDetail(snapshot.cycle!.id), detail: cycleDetail(focusedCycleId ?? snapshot.cycle!.id),
      cameras: { status: 'unavailable', cameras: [], reason: 'Not integrated' } } as DashboardRead, selected);
    result.sessions.items = catalog.slice(0, 50);
    return result;
  }
  const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
  const records = new StationClient({ baseUrl: 'http://127.0.0.1:1234', getToken: () => 'isolated-software-test-token-only', fetch: async (input, init) => {
    const url = new URL(String(input)), path = url.pathname;
    if (path.endsWith('/schema')) return json({ capabilities: { dashboardRead: { version: 1, path: '/api/v1/dashboard' } } });
    if (path.endsWith('/dashboard')) {
      reads++;
      const selection = { sessionId: url.searchParams.get('sessionId'), cycleId: url.searchParams.get('cycleId') };
      dashboardRequests.push(selection);
      return json(bundle(selection.sessionId ?? sessionId, selection.cycleId));
    }
    if (path.endsWith('/sessions')) { catalogReads++; return json([...catalog, { ...data.session, id: 'live:session', sourceMode: 'live' }]); }
    if (path.endsWith('/export')) {
      exports++; const requested = decodeURIComponent(path.split('/').at(-2)!); await deferExport?.();
      const current = forSession(serverExport, requested);
      if (url.searchParams.get('format') === 'csv') return new Response(
        'section,recordType,id,dataJson\n' + current.records.cycle.map(cycle =>
          `record,cycle,${cycle.id},"${JSON.stringify(cycle).replaceAll('"', '""')}"\n`).join(''),
        { headers: { 'Content-Type': 'text/csv' } });
      return json(current);
    }
    if (path.endsWith('/events')) return new Response(new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode(': ready\n\n'));
      init?.signal?.addEventListener('abort', () => { try { controller.close(); } catch {} }, { once: true });
    } }), { headers: { 'Content-Type': 'text/event-stream' } });
    throw new Error(`Unexpected read: ${path}`);
  } });
  return { ui: new MorphStationClient(records), advance: () => sequence++, nextSession: (id = 'new:session') => {
      sessionId = id; sequence++;
      catalog.unshift({ ...data.session, id, startedAt: new Date(Date.parse(catalog[0].startedAt) + 60_000).toISOString() });
    }, count: () => ({ exports, reads, catalogReads }), requests: () => [...dashboardRequests],
    setExport: (next: SessionExport) => { serverExport = structuredClone(next); },
    defer: (fn: () => Promise<void>) => { deferExport = fn; } };
}
test('live polling does not load session exports; history loads once and preserves its own totals', async () => {
  const h = harness();
  try {
    await h.ui.selectMode('simulation'); await h.ui.refresh(); await h.ui.refresh();
    assert.equal(h.count().exports, 0); assert.equal(h.ui.getState().recordScope, 'recent');
    assert.ok(h.ui.getState().activeCycle); assert.equal(h.ui.getState().metrics.confirmedCorrectCycles.denominator, 4);
    await h.ui.setHistoryVisible(true);
    const saved = h.ui.getState(); assert.equal(h.count().exports, 1);
    assert.equal(saved.recordScope, 'session'); assert.equal(saved.historyStatus, 'ready');
    assert.equal(saved.cycles.length, data.records.cycle.length); assert.equal(saved.historyLoadedAt, data.exportedAt);
    assert.equal(saved.generatedAt, data.exportedAt);
    assert.notEqual(saved.receivedAt, data.exportedAt);
    assert.ok(Math.abs(Date.now() - Date.parse(saved.receivedAt!)) < 5000);
    await h.ui.setHistoryVisible(false); h.advance(); await h.ui.refresh();
    assert.equal(h.count().exports, 1); assert.equal(h.ui.getState().recordScope, 'recent');
    await h.ui.setHistoryVisible(true);
    assert.equal(h.count().exports, 1); assert.equal(h.ui.getState().historyUpdateAvailable, true);
    assert.deepEqual(h.ui.getState().metrics, saved.metrics);
    await h.ui.refresh(); assert.equal(h.count().exports, 2);
    assert.equal(h.ui.getState().historyUpdateAvailable, false);
  } finally { h.ui.stop(); }
});
test('older session catalog is loaded only on demand and stays available across compact refreshes', async () => {
  const h = harness(55);
  try {
    await h.ui.selectMode('simulation'); await h.ui.refresh();
    assert.equal(h.ui.getState().sessions.length, 50);
    assert.equal(h.ui.getState().sessionCatalogHasMore, true);
    assert.equal(h.ui.getState().sessionCatalogTotal, 55);
    assert.equal(h.count().catalogReads, 0);
    await h.ui.loadOlderSessions(); await h.ui.refresh();
    assert.equal(h.count().catalogReads, 1); assert.equal(h.count().exports, 0);
    assert.equal(h.ui.getState().sessions.length, 55);
    assert.equal(h.ui.getState().sessionCatalogHasMore, false);
    assert.ok(h.ui.getState().sessions.some(session => session.id === 'saved:session:54'));
    assert.ok(h.ui.getState().sessions.every(session => session.sourceMode === 'simulation'));
  } finally { h.ui.stop(); }
});
test('replay loads a frozen export only on explicit action and seeking/exporting adds no reads', async () => {
  const h = harness();
  try {
    await h.ui.selectMode('simulation'); await h.ui.startReplay();
    assert.equal(h.count().exports, 1); assert.equal(h.ui.getState().viewMode, 'replay');
    const before = h.count(), metrics = h.ui.getState().metrics;
    h.ui.seekReplay(12); await h.ui.refresh();
    assert.deepEqual(JSON.parse(await h.ui.exportJson()), data);
    assert.deepEqual(h.count(), before); assert.deepEqual(h.ui.getState().metrics, metrics);
    await assert.rejects(h.ui.reviewCycle('demo:retry', {} as any), /read-only/);
  } finally { h.ui.stop(); }
});
test('concurrent replay requests share one export and cannot replace an already opened replay', async () => {
  const h = harness(); let release!: () => void;
  try {
    await h.ui.selectMode('simulation');
    h.defer(() => new Promise<void>(r => { release = r; }));
    const first = h.ui.startReplay(), second = h.ui.startReplay();
    while (!release) await new Promise(r => setTimeout(r, 1));
    assert.equal(h.count().exports, 1);
    release(); await Promise.all([first, second]);
    h.ui.seekReplay(12); const sought = h.ui.getState();
    await h.ui.startReplay();
    assert.equal(h.ui.getState(), sought); assert.equal(h.count().exports, 1);
  } finally { h.ui.stop(); }
});
test('late history completion after a reset cannot restore the previous view', async () => {
  const h = harness(); let release!: () => void;
  try {
    await h.ui.selectMode('simulation');
    h.defer(() => new Promise<void>(r => { release = r; }));
    const pending = h.ui.setHistoryVisible(true);
    while (!release) await new Promise(r => setTimeout(r, 1));
    await h.ui.setHistoryVisible(false); h.ui.stop(); release(); await pending;
    assert.notEqual(h.ui.getState().recordScope, 'session');
    assert.equal(h.ui.getState().historyStatus, 'idle');
  } finally { h.ui.stop(); }
});
test('auto-follow during the first history export clears the pending load and loads the new session', async () => {
  const h = harness(); let release!: () => void, first = true;
  try {
    await h.ui.selectMode('simulation');
    h.defer(async () => { if (first) { first = false; await new Promise<void>(r => { release = r; }); } });
    const oldHistory = h.ui.setHistoryVisible(true);
    while (!release) await new Promise(r => setTimeout(r, 1));
    h.nextSession(); await h.ui.refresh();
    release(); await oldHistory;
    assert.equal(h.ui.getState().activeSession?.id, 'new:session');
    assert.equal(h.ui.getState().historyStatus, 'ready');
    assert.equal(h.ui.getState().recordScope, 'session');
    assert.equal(h.count().exports, 2);
  } finally { h.ui.stop(); }
});

test('saved history JSON remains frozen after new records arrive while CSV explicitly reads the latest server export', async () => {
  const h = harness();
  try {
    await h.ui.selectMode('simulation'); await h.ui.setHistoryVisible(true);
    const newer = structuredClone(data);
    const cycle = { ...newer.records.cycle.at(-1)!, id: 'demo:next-object', objectId: 'demo:object:5' };
    newer.records.cycle.push(cycle);
    newer.metrics.cycles.total++; newer.metrics.cycles.in_progress++; newer.metrics.cycles.inProgress++;
    newer.metrics.detection.totalPopulation++;
    const { revision, ...payload } = cycle;
    newer.events.push({ ...newer.events.at(-1)!, type: 'cycle.created', recordType: 'cycle',
      sequence: 51, eventId: `${cycle.id}:create`, entityRevision: revision,
      entityId: cycle.id, cycleId: cycle.id, payload });
    newer.exportedAt = '2026-11-14T16:28:00Z';
    h.setExport(newer); h.advance();
    await h.ui.setHistoryVisible(false); await h.ui.refresh(); await h.ui.setHistoryVisible(true);
    assert.equal(h.ui.getState().historyUpdateAvailable, true);
    assert.equal(h.ui.getState().cycles.length, data.records.cycle.length);
    const before = h.count();
    assert.deepEqual(JSON.parse(await h.ui.exportJson(data.session.id)), data);
    await assert.rejects(h.ui.exportJson('another:session'), /does not match the displayed saved snapshot/);
    assert.deepEqual(h.count(), before);
    assert.match(await h.ui.exportCsv(), /demo:next-object/);
    assert.equal(h.count().exports, before.exports + 1);
    assert.equal(h.ui.getState().cycles.length, data.records.cycle.length);
    await h.ui.refresh();
    assert.deepEqual(JSON.parse(await h.ui.exportJson()), newer);
  } finally { h.ui.stop(); }
});

test('replay JSON rejects an explicit different session without making another request', async () => {
  const h = harness();
  try {
    await h.ui.selectMode('simulation'); await h.ui.startReplay();
    const before = h.count();
    await assert.rejects(h.ui.exportJson('another:session'), /does not match the displayed saved snapshot/);
    assert.deepEqual(h.count(), before);
    assert.deepEqual(JSON.parse(await h.ui.exportJson(data.session.id)), data);
  } finally { h.ui.stop(); }
});

test('reconnect preserves follow-latest or pinned session selection as newer sessions arrive', async () => {
  const h = harness(2);
  try {
    await h.ui.selectMode('simulation');
    assert.equal(h.ui.getState().selectedSessionId, null);
    assert.equal(h.requests().at(-1)?.sessionId, null);
    h.nextSession(); await h.ui.refresh(); await h.ui.reconnect();
    assert.equal(h.ui.getState().activeSession?.id, 'new:session');
    assert.equal(h.ui.getState().selectedSessionId, null);
    assert.equal(h.requests().at(-1)?.sessionId, null);

    await h.ui.selectMode('simulation', data.session.id);
    h.nextSession('newer:session'); await h.ui.refresh(); await h.ui.reconnect();
    assert.equal(h.ui.getState().activeSession?.id, data.session.id);
    assert.equal(h.ui.getState().selectedSessionId, data.session.id);
    assert.equal(h.requests().at(-1)?.sessionId, data.session.id);

    await h.ui.selectMode('simulation');
    assert.equal(h.ui.getState().activeSession?.id, 'newer:session');
    assert.equal(h.ui.getState().selectedSessionId, null);
    assert.equal(h.requests().at(-1)?.sessionId, null);
  } finally { h.ui.stop(); }
});

test('closing a focused cycle clears its detail request even after opening saved history', async () => {
  const h = harness();
  try {
    await h.ui.selectMode('simulation');
    const currentCycleId = h.ui.getState().activeCycle?.id;
    await h.ui.selectCycle('demo:retry');
    assert.equal(h.requests().at(-1)?.cycleId, 'demo:retry');
    assert.equal(h.ui.getState().cycles.find(cycle => cycle.id === 'demo:retry')?.detailsLoaded, true);
    assert.equal(h.ui.getState().activeCycle?.id, currentCycleId);
    await h.ui.setHistoryVisible(true);
    await h.ui.selectCycle();
    assert.equal(h.requests().at(-1)?.cycleId, null);
    await h.ui.setHistoryVisible(false); await h.ui.refresh();
    assert.equal(h.requests().at(-1)?.cycleId, null);
    assert.equal(h.ui.getState().cycles.find(cycle => cycle.id === 'demo:retry')?.detailsLoaded, false);
    assert.equal(h.ui.getState().activeCycle?.id, currentCycleId);
  } finally { h.ui.stop(); }
});
