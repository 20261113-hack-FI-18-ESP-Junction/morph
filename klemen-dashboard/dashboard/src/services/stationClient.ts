/** Canonical records, explicit human review and frozen read-only replay through the local proxy. */
import { DashboardStore, StationClient as RecordsClient } from '@morph/station-client';
import type { CycleDetail, CycleReviewRequest, CycleReviewResult, DashboardState, SessionExport } from '@morph/station-client';
import type { StationSnapshot } from '../types/morph.ts';
import { projectM06State } from './m06Projection.ts';
import { replaySnapshot } from './history.ts';

function emptyState(): DashboardState {
  return { selection: { sourceMode: 'live' }, connection: 'idle', stream: 'idle', stale: true,
    error: null, receivedAt: null, lastEventSequence: 0, sessions: [], session: null,
    snapshot: null, metrics: null, cycles: null, currentDetail: null, detail: null,
    cameras: null, sessionExport: null };
}
function freeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}

export class MorphStationClient {
  private client: RecordsClient | null = null;
  private store: DashboardStore | null = null;
  private snapshot = freeze(projectM06State(emptyState()));
  private listeners = new Set<() => void>();
  private replayBase: StationSnapshot | null = null;
  private replayExport: SessionExport | null = null;

  getState = (): StationSnapshot => this.snapshot;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private ensure(): DashboardStore {
    if (!this.store) {
      if (typeof window === 'undefined') throw new Error('Connect the station from its browser application.');
      this.client = new RecordsClient({ baseUrl: window.location.origin, authMode: 'same-origin-proxy' });
      this.store = new DashboardStore(this.client, { loadSessionExport: true });
      this.store.subscribe(() => {
        if (this.replayBase) return;
        this.publish(projectM06State(this.store!.getState()));
      });
    }
    return this.store;
  }
  private publish(snapshot: StationSnapshot): void {
    this.snapshot = freeze(snapshot);
    for (const listener of this.listeners) listener();
  }
  async startReplay(): Promise<void> {
    const store = this.ensure();
    if (!this.snapshot.activeSession || this.snapshot.dataConnection !== 'connected' || this.snapshot.dataStale) throw new Error('Load current persisted records before replaying.');
    this.replayBase = this.snapshot;
    this.replayExport = store.getState().sessionExport;
    store.stop();
    this.publish(replaySnapshot(this.replayBase));
  }
  seekReplay(index: number): void {
    if (!this.replayBase) throw new Error('Open a replay first.');
    this.publish(replaySnapshot(this.replayBase, index));
  }
  async reviewCycle(cycleId: string, request: CycleReviewRequest): Promise<CycleReviewResult> {
    this.ensure();
    if (this.replayBase) throw new Error('Replay is read-only.');
    if (this.snapshot.dataStale || this.snapshot.dataConnection !== 'connected') throw new Error('Refresh current records before reviewing.');
    if (!this.snapshot.cycles.some(c => c.id === cycleId && c.sessionId === this.snapshot.activeSession?.id)) throw new Error('Select the review cycle in its session.');
    const result = await this.client!.reviewCycle(cycleId, request);
    await this.store!.refresh();
    return result;
  }
  async start(): Promise<void> { this.replayBase = null; this.replayExport = null; await this.ensure().start({ sourceMode: 'live' }); }
  stop(): void { this.store?.stop(); }
  async selectMode(mode: 'live' | 'simulation', sessionId?: string): Promise<void> {
    this.replayBase = null; this.replayExport = null;
    await this.ensure().select({ sourceMode: mode, sessionId });
  }
  async refresh(): Promise<void> { if (!this.replayBase) await this.ensure().refresh(); }
  async refreshReview(cycleId: string): Promise<CycleDetail> {
    if (this.replayBase) throw new Error('Replay is read-only.');
    await this.ensure().refresh();
    return this.client!.getCycle(cycleId);
  }
  async selectCycle(cycleId?: string): Promise<void> { await this.ensure().selectCycle(cycleId); }
  async getEvidence(id: string): Promise<Blob> { this.ensure(); return this.client!.getEvidence(id); }
  private selectedSession(id?: string): string {
    const selected = id ?? this.snapshot.activeSession?.id;
    if (!selected) throw new Error('Select a persisted session before exporting.');
    return selected;
  }
  async exportCsv(id?: string): Promise<string> {
    if (this.replayBase) throw new Error('Use JSON to export the frozen replay; CSV is available in record views.');
    this.ensure(); return this.client!.exportSession(this.selectedSession(id), 'csv');
  }
  async exportJson(id?: string): Promise<string> {
    if (this.replayExport) return JSON.stringify(this.replayExport, null, 2);
    this.ensure(); return JSON.stringify(await this.client!.exportSession(this.selectedSession(id), 'json'), null, 2);
  }
}

export const stationClient = new MorphStationClient();
