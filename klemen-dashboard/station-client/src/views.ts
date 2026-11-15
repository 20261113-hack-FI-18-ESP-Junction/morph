/** Presentation helpers: no local reliability counters or fabricated telemetry. */
import type { DashboardState } from './store.ts';
import type { Ratio } from './types.ts';

export function formatRatio(ratio: Ratio | null): { value: string; counts: string; definition: string | null } {
  if (!ratio) return { value: 'No data yet', counts: '0 / 0', definition: null };
  return {
    value: ratio.denominator === 0 || ratio.value === null ? 'No data yet' : `${(ratio.value * 100).toFixed(1)}%`,
    counts: `${ratio.numerator} / ${ratio.denominator}`,
    definition: ratio.definition,
  };
}

export function formatTimestamp(value: string | null, timeZone = 'Europe/Ljubljana'): string {
  if (value === null) return 'Unavailable';
  if (!Number.isFinite(Date.parse(value))) return 'Invalid timestamp';
  return `${new Intl.DateTimeFormat('en-GB', { timeZone, dateStyle: 'medium', timeStyle: 'long' }).format(new Date(value))} (${timeZone})`;
}

export function frameFreshness(capturedAt: string, now: number, sourceMode: 'live' | 'simulation', staleAfterMs = 5_000) {
  const ageMs = now - Date.parse(capturedAt);
  if (!Number.isFinite(ageMs) || ageMs < -1_000) return { status: 'invalid_timestamp' as const, ageMs: null };
  if (sourceMode === 'simulation') return { status: 'simulation' as const, ageMs: Math.max(0, ageMs) };
  return { status: ageMs > staleAfterMs ? 'stale' as const : 'fresh' as const, ageMs: Math.max(0, ageMs) };
}

/** All views receive the same source/session and atomically published read state. */
export function projectViews(state: DashboardState, now = Date.now()) {
  const detail = state.currentDetail;
  const inspection = detail?.inspections.find((item) => item.id === detail.cycle.inspectionId) ??
    [...(detail?.inspections ?? [])].sort((a, b) => Date.parse(b.completedAt) - Date.parse(a.completedAt) || b.id.localeCompare(a.id))[0] ?? null;
  const frameIds = new Set(inspection?.frameIds ?? []);
  const shared = { sourceMode: state.selection.sourceMode, session: state.session,
    connection: state.connection, stale: state.stale, receivedAt: state.receivedAt };
  return {
    live: { ...shared,
      cycle: state.snapshot?.cycle ?? null,
      inspection,
      inspectionRole: inspection ? inspection.id === detail?.cycle.inspectionId ? 'decision' as const : 'latest' as const : null,
      analyzedFrames: (detail?.frames ?? []).filter((frame) => frameIds.has(frame.id)).map((frame) => ({
        ...frame, freshness: frameFreshness(frame.capturedAt, now, state.selection.sourceMode),
      })),
      liveVideo: { status: 'unavailable' as const, reason: state.cameras?.reason ?? 'Camera integration has not been verified.' },
      modelRuns: detail?.modelRuns ?? [], decisions: detail?.decisions ?? [],
      executions: detail?.executions ?? [], confirmations: detail?.confirmations ?? [],
      availableActions: state.snapshot?.availableActions ?? [],
    },
    system: { ...shared, capabilities: state.snapshot?.capabilities ?? null,
      cameras: state.cameras, telemetry: null, telemetryLabel: 'Unavailable',
      benchmark: null, benchmarkLabel: 'Benchmark not recorded' },
    quality: { ...shared, metrics: state.metrics,
      endToEnd: formatRatio(state.metrics?.endToEnd ?? null),
      physicalExecution: formatRatio(state.metrics?.physicalExecution ?? null),
      detection: formatRatio(state.metrics?.detection.rate ?? null),
      detectionCoverage: state.metrics ? `${state.metrics.detection.correct} correct / ${state.metrics.detection.checked} checked; ${state.metrics.detection.totalPopulation} objects total` : 'No data yet',
      cycles: state.cycles, selectedCycle: state.detail },
  };
}
