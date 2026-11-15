/** History operations consume existing canonical records and never create measurements or counters. */
import type { Cycle, StationSnapshot } from '../types/morph.ts';

export interface HistoryFilters {
  query: string; outcome: string; reference: 'all' | 'labeled' | 'unlabeled';
  startedAfter: string; startedBefore: string; model: string; error: string;
}
export function filterHistory(snapshot: StationSnapshot, filters: HistoryFilters): Cycle[] {
  const query = filters.query.trim().toLowerCase();
  const after = filters.startedAfter ? Date.parse(`${filters.startedAfter}T00:00:00Z`) : -Infinity;
  const before = filters.startedBefore ? Date.parse(`${filters.startedBefore}T23:59:59.999Z`) : Infinity;
  return [...snapshot.cycles].filter(cycle => {
    if (filters.outcome === 'retry' ? cycle.attemptIds.length < 2 : filters.outcome !== 'all' && cycle.outcome !== filters.outcome) return false;
    if (query && !`${cycle.id} ${cycle.objectId}`.toLowerCase().includes(query)) return false;
    if (Date.parse(cycle.startedAt) < after || Date.parse(cycle.startedAt) > before) return false;
    if (filters.reference !== 'all' && Boolean(cycle.referenceLabelId) !== (filters.reference === 'labeled')) return false;
    if (filters.error.trim() && !snapshot.attempts.some(a => a.cycleId === cycle.id && a.errorCode?.toLowerCase().includes(filters.error.trim().toLowerCase()))) return false;
    if (filters.model.trim() && !snapshot.modelRuns?.some(m => m.cycleId === cycle.id && m.modelId.toLowerCase().includes(filters.model.trim().toLowerCase()))) return false;
    return true;
  }).sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt) || b.id.localeCompare(a.id));
}
export function historyPage<T>(items: T[], requestedPage: number, pageSize: number) {
  if (!Number.isSafeInteger(pageSize) || pageSize < 1) throw new RangeError('Page size must be positive.');
  const pages = Math.max(1, Math.ceil(items.length / pageSize));
  const page = Math.max(0, Math.min(pages - 1, requestedPage));
  return { items: items.slice(page * pageSize, (page + 1) * pageSize), page, pages, total: items.length };
}
export function replaySnapshot(source: StationSnapshot, index = 0): StationSnapshot {
  if (!source.activeSession) throw new Error('Select a persisted session before replaying.');
  const events = [...source.recentEvents].sort((a,b) => a.sequence - b.sequence);
  const cursor = Math.max(0, Math.min(events.length - 1, Math.trunc(index))) || 0;
  return { ...source, viewMode: 'replay', canControl: false,
    replay: { cursor, count: events.length, event: events[cursor] ?? null, savedAt: source.receivedAt ?? null } };
}
