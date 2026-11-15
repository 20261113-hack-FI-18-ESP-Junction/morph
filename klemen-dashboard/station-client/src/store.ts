/** One read-only, authoritative state shared by the three dashboard views. */
import { StationAccessError, StationHttpError, StationProtocolError } from './client.ts';
import type { StationClient } from './client.ts';
import type { CameraResponse, CycleDetail, CyclePage, Metrics, Session, SessionExport, Snapshot, SourceMode } from './types.ts';

export interface Selection { sourceMode: SourceMode; sessionId?: string }
export type Connection = 'idle' | 'loading' | 'connected' | 'disconnected' | 'unauthorized' | 'incompatible';
export interface DashboardState {
  selection: Selection;
  connection: Connection;
  stream: 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'unavailable';
  stale: boolean;
  error: string | null;
  receivedAt: string | null;
  lastEventSequence: number;
  sessions: Session[];
  session: Session | null;
  snapshot: Snapshot | null;
  metrics: Metrics | null;
  cycles: CyclePage | null;
  currentDetail: CycleDetail | null;
  detail: CycleDetail | null;
  cameras: CameraResponse | null;
  /** Optional full persisted history from the same snapshot watermark as the visible metrics. */
  sessionExport: SessionExport | null;
}
type ReadClient = Pick<StationClient, 'getSnapshot' | 'listSessions' | 'getMetrics' | 'listCycles' | 'getCycle' | 'getCameras' | 'events'>
  & Partial<Pick<StationClient, 'exportSession'>>;
export interface StoreOptions {
  pollIntervalMs?: number;
  staleAfterMs?: number;
  reconnectDelayMs?: number;
  now?: () => number;
  loadSessionExport?: boolean;
}

function freeze<T>(value: T): T {
  if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}
function empty(selection: Selection): DashboardState {
  return { selection: { ...selection }, connection: 'idle', stream: 'idle', stale: true, error: null,
    receivedAt: null, lastEventSequence: 0, sessions: [], session: null, snapshot: null,
    metrics: null, cycles: null, currentDetail: null, detail: null, cameras: null, sessionExport: null };
}
function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const finish = () => { clearTimeout(timer); signal.removeEventListener('abort', finish); resolve(); };
    const timer = setTimeout(finish, ms);
    signal.addEventListener('abort', finish, { once: true });
  });
}

/** Construction and subscription perform no requests. start() only reads records. */
export class DashboardStore {
  private readonly client: ReadClient;
  private readonly options: Required<StoreOptions>;
  private state: DashboardState = freeze(empty({ sourceMode: 'live' }));
  private listeners = new Set<() => void>();
  private controller: AbortController | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private freshTimer: ReturnType<typeof setInterval> | null = null;
  private generation = 0;
  private cursor = 0;
  private focusedCycleId: string | undefined;
  private refreshPromise: Promise<void> | null = null;
  private dirty = false;

  constructor(client: ReadClient, options: StoreOptions = {}) {
    this.client = client;
    this.options = { pollIntervalMs: 15_000, staleAfterMs: 30_000, reconnectDelayMs: 1_000,
      now: Date.now, loadSessionExport: false, ...options };
    if (typeof this.options.loadSessionExport !== 'boolean' ||
      (this.options.loadSessionExport && typeof client.exportSession !== 'function')) {
      throw new TypeError('Full session loading requires an export-capable station client');
    }
    for (const key of ['pollIntervalMs', 'staleAfterMs', 'reconnectDelayMs'] as const) {
      if (!Number.isFinite(this.options[key]) || this.options[key] < 1) throw new RangeError(`${key} must be positive`);
    }
  }

  /** Stable functions also work with React useSyncExternalStore. State is deeply frozen. */
  getState = (): DashboardState => this.state;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  private publish(patch: Partial<DashboardState>) {
    this.state = freeze({ ...this.state, ...patch });
    for (const listener of this.listeners) listener();
  }
  private active(generation: number) {
    return generation === this.generation && this.controller !== null && !this.controller.signal.aborted;
  }
  private terminalConnection(): boolean {
    return ['unauthorized', 'incompatible'].includes(this.state.connection);
  }
  private cancel() {
    this.generation++;
    this.controller?.abort();
    this.controller = null;
    if (this.timer) clearInterval(this.timer);
    if (this.freshTimer) clearInterval(this.freshTimer);
    this.timer = this.freshTimer = null;
    this.refreshPromise = null;
    this.dirty = false;
  }
  async start(selection: Selection = this.state.selection): Promise<void> {
    if (!['live', 'simulation'].includes(selection.sourceMode)) throw new RangeError('Choose live or simulation');
    this.cancel();
    this.focusedCycleId = undefined;
    this.cursor = 0;
    this.controller = new AbortController();
    this.state = freeze(empty(selection));
    this.publish({ connection: 'loading' });
    const generation = this.generation;
    await this.refresh();
    if (!this.active(generation)) return;
    if (this.terminalConnection()) { this.publish({ stream: 'unavailable' }); return; }
    this.timer = setInterval(() => { void this.refresh(); }, this.options.pollIntervalMs);
    this.freshTimer = setInterval(() => this.checkFreshness(), Math.min(1_000, this.options.staleAfterMs));
    void this.watch(generation, this.controller!.signal);
  }
  async select(selection: Selection): Promise<void> { await this.start(selection); }
  async selectCycle(cycleId?: string): Promise<void> {
    this.focusedCycleId = cycleId;
    this.publish({ detail: null });
    await this.refresh();
  }
  stop(): void {
    this.cancel();
    this.publish({ connection: 'disconnected', stream: 'idle', stale: true });
  }
  /** Freshness is receipt age, not camera age. Analyzed frame age is exposed separately. */
  checkFreshness(): void {
    if (this.state.receivedAt && this.options.now() - Date.parse(this.state.receivedAt) > this.options.staleAfterMs) {
      if (!this.state.stale) this.publish({ stale: true });
    }
  }
  private failed(error: unknown) {
    if (error instanceof StationAccessError || (error instanceof StationHttpError && (error.status === 401 || error.status === 403))) {
      this.publish({ connection: 'unauthorized', stale: true, error: 'Station access was rejected. Reconnect with a valid station token.' });
    } else if (error instanceof StationProtocolError) {
      this.publish({ connection: 'incompatible', stale: true, error: 'Station response is incompatible with this client. Review the API version.' });
    } else {
      // Do not surface arbitrary remote payloads, network URLs or credentials in UI errors.
      this.publish({ connection: 'disconnected', stale: true, error: 'Station data could not be refreshed. Retained values are not current.' });
    }
    if (this.terminalConnection()) {
      if (this.timer) clearInterval(this.timer);
      if (this.freshTimer) clearInterval(this.freshTimer);
      this.timer = this.freshTimer = null;
    }
  }
  async refresh(): Promise<void> {
    if (!this.controller || this.controller.signal.aborted) return;
    this.dirty = true;
    if (this.refreshPromise) return this.refreshPromise;
    const generation = this.generation;
    const signal = this.controller.signal;
    const promise = (async () => {
      while (this.dirty && this.active(generation)) {
        this.dirty = false;
        try { await this.load(generation, signal); }
        catch (error) { if (this.active(generation)) this.failed(error); }
      }
    })();
    this.refreshPromise = promise;
    await promise;
    if (this.active(generation) && this.refreshPromise === promise) {
      this.refreshPromise = null;
      if (this.dirty) await this.refresh();
    }
  }
  private async load(generation: number, signal: AbortSignal): Promise<void> {
    const selection = { ...this.state.selection };
    let focus = this.focusedCycleId;
    // Endpoint reads are separate transactions. Bracket them with the global event
    // watermark and retry, publishing no mixture of old metrics and new records.
    for (let attempt = 0; attempt < 3; attempt++) {
      const before = await this.client.getSnapshot(undefined, signal);
      const allSessions = await this.client.listSessions(signal);
      if (!this.active(generation)) return;
      const sessions = allSessions.filter((s) => s.sourceMode === selection.sourceMode)
        .sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt) || b.id.localeCompare(a.id));
      const selected = selection.sessionId ? sessions.find((s) => s.id === selection.sessionId) : sessions[0];
      if (selection.sessionId && !selected) throw new StationProtocolError('Selected session is unavailable in this source');
      // Auto-follow may advance to a newly started session. A historical focus
      // belongs to its original session and must not poison the new read bundle.
      if (this.state.session && selected?.id !== this.state.session.id) {
        this.focusedCycleId = undefined;
        focus = undefined;
      }
      const snapshot = selected ? await this.client.getSnapshot(selected.id, signal) : null;
      if (snapshot && (snapshot.session?.id !== selected!.id || snapshot.sourceMode !== selection.sourceMode)) {
        throw new StationProtocolError('Snapshot session/source mismatch');
      }
      const currentId = snapshot?.cycle?.id;
      const detailId = focus ?? currentId;
      const [metrics, cycles, cameras, currentDetail, detail, sessionExport] = await Promise.all([
        selected ? this.client.getMetrics({ sessionId: selected.id, includeSimulation: selection.sourceMode === 'simulation' }, signal) : null,
        selected ? this.client.listCycles({ sessionId: selected.id, sourceMode: selection.sourceMode, includeSimulation: selection.sourceMode === 'simulation', limit: 100 }, signal) : null,
        this.client.getCameras(signal),
        currentId ? this.client.getCycle(currentId, signal) : null,
        detailId && detailId !== currentId ? this.client.getCycle(detailId, signal) : null,
        selected && this.options.loadSessionExport ? this.client.exportSession!(selected.id, 'json', signal) : null,
      ]);
      if (sessionExport && (sessionExport.schemaVersion !== 1 || sessionExport.session.id !== selected?.id ||
        sessionExport.session.sourceMode !== selection.sourceMode)) throw new StationProtocolError('Session export scope/schema mismatch');
      if ([currentDetail, detail].some((d) => d && d.cycle.sessionId !== selected?.id)) throw new StationProtocolError('Cycle session mismatch');
      if (metrics && (metrics.filters.sessionId !== selected?.id ||
        metrics.filters.includedSessionIds.some((id) => id !== selected?.id))) throw new StationProtocolError('Metric filter mismatch');
      const after = await this.client.getSnapshot(selected?.id, signal);
      if (!this.active(generation)) return;
      if (focus !== this.focusedCycleId) { this.dirty = true; return; }
      if (before.lastEventSequence !== after.lastEventSequence ||
        (snapshot && snapshot.lastEventSequence !== after.lastEventSequence)) continue;
      this.cursor = after.lastEventSequence;
      this.publish({ connection: 'connected', stale: false, error: null,
        receivedAt: new Date(this.options.now()).toISOString(), lastEventSequence: this.cursor,
        sessions, session: snapshot?.session ?? null, snapshot, metrics, cycles, cameras,
        currentDetail, detail: detail ?? currentDetail, sessionExport });
      return;
    }
    throw new Error('Station changed during reads; retry the complete snapshot');
  }
  private async watch(generation: number, signal: AbortSignal): Promise<void> {
    let failures = 0;
    while (this.active(generation)) {
      if (this.terminalConnection()) {
        this.publish({ stream: 'unavailable' });
        return;
      }
      this.publish({ stream: failures ? 'reconnecting' : 'connecting' });
      try {
        for await (const event of this.client.events({ after: this.cursor, signal,
          onOpen: () => { if (this.active(generation)) this.publish({ stream: 'connected' }); },
        })) {
          if (!this.active(generation)) return;
          this.publish({ stream: 'connected' });
          if (event.sequence <= this.cursor) continue;
          await this.refresh();
          if (!this.active(generation)) return;
          if (this.state.connection !== 'connected') throw new Error('Refresh after event failed');
          // Counters are never modified using event payloads. The snapshot's cursor
          // acknowledges all incorporated records, including duplicates and gaps.
          failures = 0;
        }
        if (!this.active(generation)) return;
        throw new Error('Event stream closed');
      } catch (error) {
        if (!this.active(generation)) return;
        if (error instanceof StationHttpError && error.status === 409) {
          // A replaced/restored DB can have a lower sequence. Refresh, never re-ingest.
          await this.refresh();
        } else this.failed(error);
        if (this.terminalConnection()) {
          this.publish({ stream: 'unavailable' }); return;
        }
        this.publish({ stream: 'reconnecting' });
        failures++;
        await delay(Math.min(30_000, this.options.reconnectDelayMs * 2 ** Math.min(failures - 1, 5)), signal);
        if (this.active(generation)) await this.refresh();
      }
    }
  }
}
