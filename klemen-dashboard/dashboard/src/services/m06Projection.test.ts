import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import type { DashboardState, SessionExport, Snapshot } from '@morph/station-client';
import { projectM06State } from './m06Projection.ts';
import { MorphStationClient } from './stationClient.ts';

const fixtureRoot = process.env.MORPH_FIXTURE_DIR ?? path.resolve(process.cwd(), '../verification/fixtures');
const read = <T>(name: string): T => JSON.parse(readFileSync(path.join(fixtureRoot, name), 'utf8'));
const data = read<SessionExport>('sample-export.json');
const snapshot = read<Snapshot>('sample-snapshot.json');
function state(): DashboardState {
  return { selection: { sourceMode: 'simulation' }, connection: 'connected', stream: 'connected',
    stale: false, error: null, receivedAt: '2026-11-14T16:30:00Z', lastEventSequence: 50,
    session: snapshot.session, sessions: [snapshot.session!], snapshot, metrics: data.metrics,
    cycles: null, currentDetail: null, detail: null, cameras: null, sessionExport: data };
}
test('canonical fractions convert once and retry relations cover the complete persisted session', () => {
  const result = projectM06State(state());
  assert.equal(result.metrics.confirmedCorrectCycles.value, 50);
  assert.equal(result.metrics.confirmedCorrectCycles.numerator, 2);
  assert.equal(result.metrics.confirmedCorrectCycles.denominator, 4);
  assert.equal(result.metrics.physicalExecution.value, 60);
  assert.equal(result.metrics.attemptCounts.retries, 1);
  assert.equal(result.metrics.cycleCounts.recoveredCycles, 1);
  const retry = result.cycles.find(c => c.id === 'demo:retry')!;
  assert.equal(retry.attemptIds.length, 2); assert.equal(retry.inspectionIds.length, 2);
  assert.equal(result.attempts.find(a => a.id === retry.attemptIds[0])?.outcome, 'failed');
  assert.equal(result.inspections.filter(i => i.isDecisionInspection).length, data.records.cycle.filter(c => c.inspectionId).length);
});
test('unimplemented state and telemetry remain unavailable while API data is connected', () => {
  const result = projectM06State(state());
  assert.equal(result.canonicalSource, true); assert.equal(result.dataConnection, 'connected');
  assert.equal(result.stationConnected, false); assert.equal(result.canControl, false);
  assert.equal(result.goalState.goalVersion, null); assert.equal(result.goalState.activeGoal, null);
  assert.equal(result.activeCycle?.activePhase, null); assert.equal(result.activeCycle?.phaseElapsedSec, null);
  assert.equal(result.hardwareSummary.cpuLoad.value, null);
  assert.ok(result.components.every(c => c.capabilityStatus === 'unavailable'));
  assert.ok(result.inspections.every(i => i.scoreRange === null));
  assert.ok(result.skillExecutions.every(e => e.policyVersion === null && e.motionStartedAt === null));
});
test('execution request timestamps and statuses do not imply that a command was sent', () => {
  const next = state();
  const requested = structuredClone(data);
  requested.records.execution[0].status = 'requested';
  next.sessionExport = requested;
  const result = projectM06State(next);
  for (const execution of requested.records.execution) {
    const projected = result.skillExecutions.find(e => e.id === execution.id)!;
    assert.equal(projected.requestedAt, execution.requestedAt);
    assert.equal(projected.commandSentAt, null);
    assert.equal(projected.controllerStatus, execution.status);
  }
  assert.equal(result.skillExecutions[0].controllerStatus, 'requested');
});
test('state version uses the recorded snapshot version and is unavailable without a snapshot', () => {
  const next = state();
  assert.equal(projectM06State(next).stateVersion, next.snapshot!.stateVersion);
  next.snapshot = null;
  next.lastEventSequence = 123;
  assert.equal(projectM06State(next).stateVersion, null);
  assert.equal(projectM06State(next).lastEventSequence, 123);
});
test('frames and confirmations preserve actual evidence IDs, capture times and confirmation results', () => {
  const result = projectM06State(state());
  const original = data.records.frame[0]; const frame = result.frames.find(f => f.id === original.id)!;
  assert.equal(frame.evidenceId, original.evidenceId); assert.equal(frame.capturedAt, original.capturedAt);
  assert.equal(frame.imageUrl, `/api/v1/evidence/${encodeURIComponent(original.evidenceId)}`);
  assert.equal(frame.fps, null);
  assert.deepEqual(result.confirmations.map(c => c.physicalSuccess), data.records.confirmation.map(c => c.physicalSuccess));
});
test('empty live startup has no fixture records, goals, counts or side effects', () => {
  const client = new MorphStationClient(); const snapshot = client.getState();
  assert.equal(snapshot.viewMode, 'live'); assert.equal(snapshot.activeSession, null);
  assert.equal(snapshot.cycles.length, 0); assert.equal(snapshot.frames.length, 0);
  assert.equal(snapshot.metrics.confirmedCorrectCycles.value, null);
  assert.equal(snapshot.goalState.goalVersion, null); assert.equal(snapshot.dataConnection, 'idle');
  assert.equal(snapshot.stateVersion, null); assert.equal(snapshot.lastEventSequence, 0);
  const unsubscribe = client.subscribe(() => {}); unsubscribe();
  assert.equal(client.getState(), snapshot);
});
test('disconnect retains persisted counts marked stale and never implies robot failure', () => {
  const next = state(); next.connection = 'disconnected'; next.stale = true;
  const result = projectM06State(next);
  assert.equal(result.metrics.confirmedCorrectCycles.numerator, 2);
  assert.equal(result.dataStale, true); assert.equal(result.dataConnection, 'disconnected');
  assert.equal(result.metrics.cycleCounts.failed, data.metrics.cycles.failed);
});
test('cross-source/session exports are rejected rather than shown in live metrics', () => {
  const next = state(); next.selection = { sourceMode: 'live' };
  assert.throws(() => projectM06State(next), /another source or session/);
});
