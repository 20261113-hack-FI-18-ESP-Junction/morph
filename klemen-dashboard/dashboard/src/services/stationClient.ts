/** Canonical live reads, on-demand saved history, explicit review and frozen replay. */
import { DashboardStore, StationClient as RecordsClient } from '@morph/station-client';
import type { CycleDetail, CycleReviewRequest, CycleReviewResult, DashboardState, SessionExport, Session } from '@morph/station-client';
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
  private client: RecordsClient | null;
  private store: DashboardStore | null = null;
  private snapshot = freeze(projectM06State(emptyState()));
  private listeners = new Set<() => void>();
  private replayBase: StationSnapshot | null = null;
  private replayExport: SessionExport | null = null;
  private replayRequest: Promise<void> | null = null;
  private replayController: AbortController | null = null;
  private historyVisible = false;
  private historyData: SessionExport | null = null;
  private historyStatus: 'idle' | 'loading' | 'ready' | 'error' = 'idle';
  private historyError: string | null = null;
  private historyWatermark = 0;
  private historyReceivedAt: string | null = null;
  private historyRequest: Promise<void> | null = null;
  private historyController: AbortController | null = null;
  private operationVersion = 0;
  private observedSelectionKey: string | null = null;
  private sessionCatalog: Session[] | null = null;

  /** An injected records client is used by isolated transport/regression tests. */
  constructor(client?: RecordsClient) { this.client = client ?? null; }
  getState = (): StationSnapshot => this.snapshot;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private ensure(): DashboardStore {
    if (!this.store) {
      if (!this.client) {
        if (typeof window === 'undefined') throw new Error('Connect the station from its browser application.');
        this.client = new RecordsClient({ baseUrl: window.location.origin, authMode: 'same-origin-proxy' });
      }
      this.store = new DashboardStore(this.client, { preferDashboard: true, loadSessionExport: false,
        pollIntervalMs: 2_000, staleAfterMs: 10_000 });
      this.store.subscribe(() => {
        if (this.replayBase) return;
        const state = this.store!.getState();
        const selectionKey = `${state.selection.sourceMode}:${state.session?.id ?? ''}`;
        if (selectionKey !== this.observedSelectionKey) {
          // A first history export may still be pending when auto-follow advances.
          // Invalidate it even before any historyData has been installed.
          this.clearHistory(); this.observedSelectionKey = selectionKey;
        }
        this.projectCurrent();
        if (this.historyVisible && this.historyStatus === 'idle' && state.session && !state.stale && state.connection === 'connected') {
          queueMicrotask(() => { void this.loadHistory().catch(() => {}); });
        }
      });
    }
    return this.store;
  }
  private publish(snapshot: StationSnapshot): void {
    this.snapshot = freeze(snapshot);
    for (const listener of this.listeners) listener();
  }
  private projectSaved(data: SessionExport, state: DashboardState, receivedAt: string): StationSnapshot {
    // The export owns both its records and its metrics. Do not mix current totals into an older saved view.
    return { ...projectM06State({ ...state, session: data.session, snapshot: null, metrics: data.metrics,
      receivedAt, currentDetail: null, detail: null, sessionExport: data,
      lastEventSequence: Math.max(0, ...data.events.map(event => event.sequence)),
      cycles: { items: data.records.cycle, total: data.records.cycle.length, offset: 0, limit: Math.max(1, data.records.cycle.length) } }), generatedAt: data.exportedAt };
  }
  private projectCurrent(): void {
    if (this.replayBase) return;
    let state = this.store?.getState() ?? emptyState();
    if (this.sessionCatalog) {
      const sessions = [...new Map([...this.sessionCatalog, ...state.sessions].map(session => [session.id, session])).values()]
        .filter(session => session.sourceMode === state.selection.sourceMode)
        .sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt) || b.id.localeCompare(a.id));
      state = { ...state, sessions, sessionCatalog: { total: sessions.length, hasMore: false } };
    }
    const saved = this.historyVisible ? this.historyData : null;
    const projected = saved ? this.projectSaved(saved, state, this.historyReceivedAt!) : projectM06State(state);
    this.publish({ ...projected, historyStatus: this.historyStatus, historyError: this.historyError,
      historyLoadedAt: saved?.exportedAt ?? null,
      historyUpdateAvailable: !!saved && state.lastEventSequence !== this.historyWatermark });
  }
  private clearHistory(): void {
    this.operationVersion++;
    this.replayController?.abort(); this.replayController = null; this.replayRequest = null;
    this.historyController?.abort(); this.historyController = null;
    this.historyRequest = null; this.historyData = null;
    this.historyReceivedAt = null;
    this.historyStatus = 'idle'; this.historyError = null;
  }
  async setHistoryVisible(visible: boolean): Promise<void> {
    this.historyVisible = visible;
    if (this.replayBase) return;
    this.projectCurrent();
    if (visible && !this.historyData && this.store?.getState().session) await this.loadHistory();
  }
  async loadOlderSessions(): Promise<void> {
    this.ensure();
    const catalog = await this.client!.listSessions();
    this.sessionCatalog = catalog;
    this.projectCurrent();
  }
  private async loadHistory(): Promise<void> {
    const store = this.ensure();
    if (this.historyRequest) return this.historyRequest;
    const state = store.getState();
    if (!state.session || state.stale || state.connection !== 'connected') {
      this.historyStatus = 'error'; this.historyError = 'Connect to the station to load a saved session snapshot.';
      this.projectCurrent(); return;
    }
    const version = this.operationVersion, sessionId = state.session.id, mode = state.selection.sourceMode;
    const watermark = state.lastEventSequence;
    const control = new AbortController(); this.historyController = control;
    this.historyStatus = 'loading'; this.historyError = null; this.projectCurrent();
    const request = (async () => {
      try {
        const data = await this.client!.exportSession(sessionId, 'json', control.signal);
        if (version !== this.operationVersion || store.getState().session?.id !== sessionId) return;
        if (data.session.sourceMode !== mode) throw new Error('Session source changed.');
        this.historyData = data; this.historyReceivedAt = new Date().toISOString();
        this.historyWatermark = watermark; this.historyStatus = 'ready';
      } catch {
        if (version !== this.operationVersion || control.signal.aborted) return;
        this.historyStatus = 'error';
        this.historyError = 'Full history could not be loaded. Check the station connection or export size; the previous snapshot, if shown, is retained.';
      } finally {
        if (version === this.operationVersion && this.historyController === control) {
          this.historyRequest = null; this.historyController = null; this.projectCurrent();
        }
      }
    })();
    this.historyRequest = request;
    return request;
  }
  async startReplay(): Promise<void> {
    if (this.replayBase) return;
    if (this.replayRequest) return this.replayRequest;
    const request = this.loadReplay();
    this.replayRequest = request;
    try { await request; }
    finally { if (this.replayRequest === request) { this.replayRequest = null; this.replayController = null; } }
  }
  private async loadReplay(): Promise<void> {
    const store = this.ensure(), state = store.getState();
    if (!state.session || state.connection !== 'connected' || state.stale) throw new Error('Load current persisted records before replaying.');
    const version = this.operationVersion;
    const controller = new AbortController(); this.replayController = controller;
    const data = await this.client!.exportSession(state.session.id, 'json', controller.signal);
    if (version !== this.operationVersion || store.getState().session?.id !== data.session.id || data.session.sourceMode !== state.selection.sourceMode)
      throw new Error('The selected session changed while loading replay.');
    this.replayExport = data;
    this.replayBase = freeze(this.projectSaved(data, state, new Date().toISOString()));
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
    if (this.historyVisible) await this.loadHistory();
    return result;
  }
  async start(): Promise<void> {
    this.replayBase = null; this.replayExport = null; this.clearHistory();
    await this.ensure().start({ sourceMode: 'live' });
  }
  stop(): void { this.clearHistory(); this.store?.stop(); }
  async selectMode(mode: 'live' | 'simulation', sessionId?: string): Promise<void> {
    this.replayBase = null; this.replayExport = null; this.clearHistory();
    await this.ensure().select({ sourceMode: mode, sessionId });
    if (this.historyVisible) await this.loadHistory();
  }
  async reconnect(): Promise<void> {
    if (this.replayBase) return;
    const { sourceMode, sessionId } = this.ensure().getState().selection;
    await this.selectMode(sourceMode, sessionId);
  }
  async refresh(): Promise<void> {
    if (this.replayBase) return;
    await this.ensure().refresh();
    if (this.historyVisible) await this.loadHistory();
  }
  async refreshReview(cycleId: string): Promise<CycleDetail> {
    if (this.replayBase) throw new Error('Replay is read-only.');
    await this.ensure().refresh();
    if (this.historyVisible) await this.loadHistory();
    return this.client!.getCycle(cycleId);
  }
  async selectCycle(cycleId?: string): Promise<void> {
    if (this.replayBase || (cycleId !== undefined && this.historyVisible && this.historyData)) return;
    await this.ensure().selectCycle(cycleId);
  }
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
    const selected = this.selectedSession(id);
    const saved = this.replayExport ?? (this.historyVisible ? this.historyData : null);
    if (saved) {
      if (selected !== saved.session.id) throw new Error('The requested session does not match the displayed saved snapshot.');
      return JSON.stringify(saved, null, 2);
    }
    this.ensure(); return JSON.stringify(await this.client!.exportSession(selected, 'json'), null, 2);
  }
}
export const stationClient = new MorphStationClient();
