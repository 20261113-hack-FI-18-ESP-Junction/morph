/** Pure UI projection of persisted M06 data. No fixtures, local outcomes or write path. */
import type { DashboardState, Metrics, Ratio, SessionExport, StationEvent, ModelRun } from '@morph/station-client';
import type {
  ComponentStatusRecord, Cycle, DecisionRecord, MetricRatio, Session, SessionMetrics,
  SkillExecution, StationSnapshot, TelemetryValue, VoiceUtterance,
} from '../types/morph.ts';

export const DISPLAY_TIME_ZONE = 'Europe/Ljubljana';
const unavailable = (unit: string): TelemetryValue => ({ value: null, unit, measuredAt: null, state: 'unavailable' });
const age = (timestamp: string, now: number) => now - Date.parse(timestamp);
const duration = (start: string, end: string | null): number | null => {
  if (end === null) return null;
  const result = Date.parse(end) - Date.parse(start);
  return Number.isFinite(result) && result >= 0 ? result : null;
};
function percentile(values: number[], quantile: number): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const rank = (sorted.length - 1) * quantile;
  const lower = Math.floor(rank), upper = Math.ceil(rank);
  return (sorted[lower] + (sorted[upper] - sorted[lower]) * (rank - lower)) / 1000;
}

/** Canonical ratios are fractions. This legacy presentation contract uses percentages. */
function uiRatio(ratio: Ratio | undefined, state: DashboardState, excluded: number): MetricRatio {
  return {
    numerator: ratio?.numerator ?? 0, denominator: ratio?.denominator ?? 0,
    value: ratio?.value === null || ratio?.value === undefined ? null : ratio.value * 100,
    definition: ratio?.definition ?? 'No eligible persisted records',
    sourceMode: state.selection.sourceMode, sessionId: state.session?.id ?? null,
    excludedInProgressCount: excluded,
  };
}

export function projectMetrics(state: DashboardState): SessionMetrics {
  const m: Metrics | null = state.metrics;
  const fullCycleValues = m?.timings.fullCycle.valuesMs ?? [];
  const p50 = percentile(fullCycleValues, 0.5), p95 = percentile(fullCycleValues, 0.95);
  return {
    sessionId: state.session?.id ?? null, sourceMode: state.selection.sourceMode,
    confirmedCorrectCycles: uiRatio(m?.endToEnd, state, m?.cycles.inProgress ?? 0),
    physicalExecution: uiRatio(m?.physicalExecution, state, m?.attempts.inProgress ?? 0),
    detectionAccuracy: { ...uiRatio(m?.detection.rate, state, 0),
      totalPopulation: m?.detection.totalPopulation ?? 0, checkedPopulation: m?.detection.checked ?? 0,
      reviewRequiredCount: m?.detection.unresolved ?? 0 },
    defectEscape: uiRatio(m?.detection.defectEscape, state, 0),
    streak: { current: m?.currentStreak ?? 0, best: m?.longestStreak ?? 0, hasData: (m?.cycles.finished ?? 0) > 0 },
    // Linear-interpolated quantiles of the backend's persisted full-cycle durations.
    medianFullCycleSec: { value: p50, p50, p95, sampleCount: m?.timings.fullCycle.sampleCount ?? 0,
      includesCloudWait: true },
    cycleCounts: { started: m?.cycles.total ?? 0, finished: m?.cycles.finished ?? 0,
      inProgress: m?.cycles.inProgress ?? 0, correct: m?.cycles.correct ?? 0,
      failed: m?.cycles.failed ?? 0, aborted: m?.cycles.aborted ?? 0, unverified: m?.cycles.unverified ?? 0,
      firstAttemptSuccesses: m?.firstAttemptSuccesses ?? 0, recoveredCycles: m?.recoveredCycles ?? 0,
      extraInspections: m?.additionalInspections ?? 0 },
    attemptCounts: { total: m?.attempts.total ?? 0, finished: m?.attempts.finished ?? 0,
      inProgress: m?.attempts.inProgress ?? 0, successful: m?.attempts.successful ?? 0,
      failed: m?.attempts.failed ?? 0, aborted: m?.attempts.aborted ?? 0,
      unverified: m?.attempts.unverified ?? 0, retries: m?.retries ?? 0 },
    confusionMatrix: { tp: m?.detection.confusionMatrix.truePositive ?? 0,
      tn: m?.detection.confusionMatrix.trueNegative ?? 0,
      fn: m?.detection.confusionMatrix.falseNegative ?? 0,
      fp: m?.detection.confusionMatrix.falsePositive ?? 0,
      unlabeledCount: m ? m.detection.totalPopulation - m.detection.checked : 0,
      reviewRequiredCount: m?.detection.unresolved ?? 0 },
  };
}

function projectSession(session: DashboardState['sessions'][number]): Session {
  return { ...session, displayTimezone: DISPLAY_TIME_ZONE,
    // Session metadata is unconstrained JSON in M06. Exact model runs are exposed separately.
    modelRuns: [] };
}
function components(): ComponentStatusRecord[] {
  return [
    ['robot', 'SO-101 / local runtime', 'Physical manipulation and verification', 'local_station'],
    ['studio', 'Physical AI Studio / learned policy', 'Execution of demonstrated skills', 'local_station'],
    ['anomalib', 'Anomalib / OpenVINO', 'Frame-linked defect measurements', 'local_station'],
    ['nemotron', 'NVIDIA Nemotron 3.5 Super VL', 'Required visual observation integration', 'cloud_api'],
    ['gemini', 'Gemini Decision 1', 'Required fixed-choice task selection', 'cloud_api'],
    ['elevenlabs', 'ElevenLabs Scribe v3 Live', 'Required spoken operator input', 'cloud_api'],
  ].map(([id, name, roleDescription, deploymentLocation]) => ({
    id, name, roleDescription, deploymentLocation: deploymentLocation as 'local_station' | 'cloud_api',
    configuredIdentity: 'Not verified by this station API', capabilityStatus: 'unavailable',
    connectionState: 'unverified', statusBadgeText: 'UNAVAILABLE',
    calibrationOrNote: 'M06 exposes persisted records. This hardware/provider capability is not integrated.',
    latestError: null,
  }));
}
const latest = (runs: ModelRun[]) => [...runs].sort((a, b) => Date.parse(b.requestedAt) - Date.parse(a.requestedAt))[0];
const isNemotron = (run: ModelRun) => /nemotron/i.test(run.modelId);
const isGemini = (run: ModelRun) => /gemini/i.test(run.modelId);
function objectStrings(value: unknown): string[] {
  return Array.isArray(value) && value.every(v => typeof v === 'string') ? [...value] : [];
}
function eventTone(event: StationEvent): 'good' | 'warn' | 'bad' | 'neutral' {
  const value = (event.payload as { outcome?: string }).outcome;
  return value === 'correct' || value === 'successful' ? 'good' : value === 'failed' ? 'bad' :
    value === 'unverified' || value === 'aborted' ? 'warn' : 'neutral';
}

export function projectM06State(state: DashboardState, now = Date.now()): StationSnapshot {
  const data: SessionExport | null = state.sessionExport;
  if (data && (data.session.id !== state.session?.id || data.session.sourceMode !== state.selection.sourceMode)) {
    throw new Error('Cannot project a session export from another source or session.');
  }
  const records = data?.records;
  const rawCycles = records?.cycle ?? [];
  const attempts = records?.attempt ?? [];
  const inspections = records?.inspection ?? [];
  const modelRuns = records?.model_run ?? [];
  const decisions = records?.decision ?? [];
  const executions = records?.execution ?? [];
  const confirmations = records?.confirmation ?? [];
  const evidence = new Map((records?.evidence ?? []).map(e => [e.id, e]));
  const runs = new Map(modelRuns.map(run => [run.id, run]));
  const cycles: Cycle[] = rawCycles.map(cycle => {
    const cycleRuns = modelRuns.filter(run => run.cycleId === cycle.id);
    const inspection = inspections.find(i => i.id === cycle.inspectionId);
    const ms = duration(cycle.startedAt, cycle.endedAt);
    return { ...cycle, activePhase: null, faultedPhase: null, phaseElapsedSec: null,
      attemptIds: attempts.filter(a => a.cycleId === cycle.id).sort((a,b) => a.ordinal - b.ordinal).map(a => a.id),
      inspectionIds: inspections.filter(i => i.cycleId === cycle.id).map(i => i.id),
      decisionIds: decisions.filter(d => d.cycleId === cycle.id).map(d => d.id),
      nemotronIds: cycleRuns.filter(isNemotron).map(run => run.id),
      plannedDestination: null, fullCycleDurationSec: ms === null ? null : ms / 1000,
      timingBreakdown: {
        anomalibMs: inspection ? runs.get(inspection.modelRunId)?.latencyMs ?? null : null,
        nemotronMs: latest(cycleRuns.filter(isNemotron))?.latencyMs ?? null,
        geminiMs: latest(cycleRuns.filter(isGemini))?.latencyMs ?? null,
        motionMs: null, verificationMs: null, cloudWaitIncluded: true,
      },
    };
  });
  const projectedDecisions: DecisionRecord[] = decisions.filter(d => d.cycleId !== null).map(d => {
    const run = runs.get(d.modelRunId);
    return { ...d, cycleId: d.cycleId!, attemptId: null,
      kind: d.kind === 'goal' ? 'goal_selection' : 'task_selection',
      modelId: run?.modelId ?? 'Unavailable', selectedChoice: d.selectedChoice,
      probabilities: {}, deadlineAt: null, validatorAccepted: d.accepted,
      validatorReason: d.rejectionReason, rawInput: run?.input, rawOutput: run?.output ?? null };
  });
  const projectedExecutions: SkillExecution[] = executions.map(ex => {
    const attempt = attempts.find(a => a.id === ex.attemptId);
    const confirmation = confirmations.find(c => c.id === attempt?.confirmationId && c.attemptId === ex.attemptId);
    return { ...ex, policyVersion: null, requestedAt: ex.requestedAt, commandSentAt: null,
      motionStartedAt: null, motionEndedAt: null,
      controllerStatus: ex.status,
      physicalOutcome: confirmation ? confirmation.physicalSuccess ? 'verified' : 'failed' :
        attempt?.outcome === 'in_progress' ? 'pending' : 'unverified' };
  });
  const utterances: VoiceUtterance[] = (records?.utterance ?? []).map(utterance => ({
    id: utterance.id, sessionId: utterance.sessionId,
    source: utterance.source === 'typed' ? 'typed' : utterance.modelId === 'scribe_v3_live' ? 'scribe_v3_live' : 'voice',
    language: utterance.language ?? 'Unavailable',
    partialTranscript: utterance.status === 'partial' ? utterance.text : '',
    committedSegments: [], finalizedText: utterance.status === 'finalized' ? utterance.text : null,
    timestampsEnriched: false, enrichmentTimestamps: [], selectedGoal: null, goalProbabilities: {},
    effectiveBoundary: 'Not recorded', state: utterance.status === 'rejected' ? 'rejected' : 'unavailable',
    createdAt: utterance.startedAt, finalizedAt: utterance.status === 'finalized' ? utterance.completedAt : null,
    transcriptionMs: null, goalDecisionMs: null,
  }));
  return {
    canonicalSource: true, viewMode: state.selection.sourceMode, sourceMode: state.selection.sourceMode,
    dataConnection: state.connection, dataStale: state.stale, receivedAt: state.receivedAt,
    canControl: false, stationConnected: false,
    activeSession: state.session ? projectSession(state.session) : null,
    sessions: state.sessions.map(projectSession), stateVersion: state.snapshot?.stateVersion ?? null,
    goalState: { activeGoal: null, activeGoalLabel: 'Unavailable', goalVersion: null,
      queuedGoal: null, queuedGoalLabel: null, queuedBoundary: null, updatedAt: null },
    pauseState: { requested: false, acknowledged: false, requestedAt: null, acknowledgedAt: null },
    stopRecord: null, activeCycle: cycles.find(c => c.id === state.snapshot?.cycle?.id) ?? null,
    cycles,
    attempts: attempts.map(a => ({ ...a, executionIds: executions.filter(e => e.attemptId === a.id).map(e => e.id) })),
    inspections: inspections.map(i => ({ ...i, scoreRange: null,
      isDecisionInspection: rawCycles.find(c => c.id === i.cycleId)?.inspectionId === i.id })),
    frames: (records?.frame ?? []).map(f => {
      const stored = evidence.get(f.evidenceId);
      const image = stored?.mediaType === 'image/png' || stored?.mediaType === 'image/jpeg';
      return { ...f, imageUrl: image ? `/api/v1/evidence/${encodeURIComponent(f.evidenceId)}` : '',
        sha256: stored?.sha256 ?? '', fps: null,
        stale: state.stale || (state.selection.sourceMode === 'live' && (age(f.capturedAt, now) > 5_000 || age(f.capturedAt, now) < -1_000)) };
    }),
    confirmations: confirmations.map(c => ({ ...c,
      notes: `Physical success: ${c.physicalSuccess ? 'confirmed' : 'not achieved'}; observed destination: ${c.observedDestination ?? 'unavailable'}.` })),
    referenceLabels: (records?.reference_label ?? []).map(r => ({ ...r, reason: null })),
    corrections: (records?.correction ?? []).map(c => ({ ...c })),
    nemotronObservations: modelRuns.filter(run => run.cycleId !== null && isNemotron(run)).map(run => ({
      id: run.id, cycleId: run.cycleId!, frameIds: run.frameIds, modelId: run.modelId,
      requestedAt: run.requestedAt, completedAt: run.completedAt,
      status: run.error ? 'rejected' : run.completedAt ? 'completed' : 'waiting',
      observations: objectStrings(run.output?.observations), hypotheses: objectStrings(run.output?.hypotheses),
      uncertainty: typeof run.output?.uncertainty === 'string' ? run.output.uncertainty : null,
      rawArtifact: JSON.stringify({ input: run.input, output: run.output, error: run.error }), parseError: null,
    })),
    decisions: projectedDecisions, skillExecutions: projectedExecutions, utterances, modelRuns,
    recentEvents: [...(data?.events ?? [])].reverse().map(event => ({ ...event, schemaVersion: 1,
      attemptId: 'attemptId' in event.payload && typeof event.payload.attemptId === 'string' ? event.payload.attemptId : null,
      summary: `${event.type} · ${event.entityId}`, statusTone: eventTone(event), payload: { ...event.payload } })),
    lastEventSequence: state.lastEventSequence, components: components(),
    joints: ['Base', 'Shoulder', 'Elbow', 'Wrist flex', 'Wrist roll', 'Gripper'].map(jointName => ({
      jointName, isPlaceholderName: true, measured: unavailable('°'), commanded: unavailable('°'), deviation: unavailable('°') })),
    hardwareSummary: { cpuLoad: unavailable('%'), memory: unavailable('GB'), controlRate: unavailable('Hz') },
    metrics: projectMetrics(state), activeFaultBanner: state.error,
  };
}
