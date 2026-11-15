/** Read-only cross-layer check against an explicitly running disposable demo. */
import assert from 'node:assert/strict';
import { StationClient } from '@morph/station-client';
import { MorphStationClient } from '../src/services/stationClient.ts';

const port = Number(process.argv[2] ?? 3101);
if (!Number.isSafeInteger(port) || port < 1 || port > 65535) throw new Error('Choose a valid local demo port.');
const origin = `http://127.0.0.1:${port}`;
Object.defineProperty(globalThis, 'location', { value: { origin }, configurable: true });
const requests: string[] = [];
const records = new StationClient({ baseUrl: origin, authMode: 'same-origin-proxy',
  fetch: (input, init) => {
    assert.ok(!init?.method || init.method === 'GET', 'This QA check only reads records.');
    requests.push(new URL(String(input)).pathname);
    return fetch(input, init);
  } });
const client = new MorphStationClient(records);
try {
  assert.equal(await records.supportsDashboard(), true);
  const initial = await records.getDashboard({ sourceMode: 'simulation' });
  assert.equal(initial.selectedSessionId, 'local-demo:session');
  assert.equal(initial.currentDetail?.cycle.id, 'local-demo:inspection-example');
  assert.equal(initial.currentDetail?.attempts.length, 2);
  assert.equal(initial.currentDetail?.cycle.outcome, 'correct');
  assert.equal(initial.metrics.recoveredCycles, 2);
  assert.equal(initial.metrics.cycles.unverified, 2);
  assert.ok(initial.currentDetail?.frames[0]?.evidenceId);
  const image = await records.getEvidence(initial.currentDetail!.frames[0]!.evidenceId);
  assert.equal(image.type, 'image/png');
  assert.ok(image.size > 100);
  await client.start();
  assert.equal(client.getState().activeSession, null);
  await client.selectMode('simulation');
  assert.equal(client.getState().dataConnection, 'connected');
  assert.equal(client.getState().activeSession?.id, 'local-demo:session');
  assert.ok(client.getState().nemotronObservations.some(observation =>
    observation.observations.some(text => text.startsWith('Synthetic fixture:'))));
  assert.equal(requests.filter(path => path.endsWith('/export')).length, 0);
  await client.refresh();
  assert.equal(requests.filter(path => path.endsWith('/export')).length, 0);
  await client.setHistoryVisible(true);
  assert.equal(client.getState().historyStatus, 'ready');
  assert.equal(client.getState().recordScope, 'session');
  assert.equal(requests.filter(path => path.endsWith('/export')).length, 1);
  await client.startReplay();
  assert.equal(client.getState().viewMode, 'replay');
  client.seekReplay(0);
  const after = await records.getDashboard({ sourceMode: 'simulation' });
  assert.equal(after.lastEventSequence, initial.lastEventSequence);
  assert.deepEqual(after.metrics, initial.metrics);
  console.log(JSON.stringify({ status: 'passed', sourceMode: 'simulation',
    checks: ['actual dashboard contract', 'complete current evidence', 'synthetic image bytes', 'fixture observation projected',
      'live mode excludes simulation', 'no export on live refresh', 'history export on demand',
      'frozen replay preserves records and metrics'], requests: requests.length,
    exports: requests.filter(path => path.endsWith('/export')).length,
    lastEventSequence: after.lastEventSequence }, null, 2));
} finally { client.stop(); }
