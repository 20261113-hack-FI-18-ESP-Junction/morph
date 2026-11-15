import { AnalysisApiError } from "./client.ts";
import type { AnalysisApi, AnalysisContext, AnalysisReport, AnalysisRequest, AnalysisSelection, AnalysisWarning } from "./types.ts";

export interface AnalystState {
  selection: AnalysisSelection | null;
  phase: "empty" | "loading" | "ready" | "submitting" | "waiting" | "error";
  context: AnalysisContext | null;
  reports: AnalysisReport[];
  report: AnalysisReport | null;
  error: { code: string; message: string } | null;
  uncertainRequest: AnalysisRequest | null;
  readHealthy: boolean;
  warnings: AnalysisWarning[];
}

const capturedContexts = new Map<string, AnalysisContext>();
const active = (report: AnalysisReport) => report.status === "queued" || report.status === "running";
export const selectionScope = (selection: AnalysisSelection) => JSON.stringify([
  selection.kind, selection.sourceMode, selection.sessionIds, selection.cycleId ?? null,
  selection.comparisonSpecId ?? null, selection.baselineSessionId ?? null, selection.adaptiveSessionId ?? null,
]);
const captureKey = (selection: AnalysisSelection) => `${selectionScope(selection)}:${selection.recordKey}`;
type PendingStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
const pendingKey = (selection: AnalysisSelection) => `morph.analysis.pending.v1:${selectionScope(selection)}`;
function defaultStorage(): PendingStorage | undefined {
  try { return typeof window === "undefined" ? undefined : window.sessionStorage; } catch { return undefined; }
}
function parsePending(raw: string | null, selection: AnalysisSelection): AnalysisRequest | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw);
    const allowed = new Set(["requestId", "kind", "sessionIds", "cycleId", "sourceMode", "question", "expectedSelectionDigest", "comparisonSpecId", "baselineSessionId", "adaptiveSessionId"]);
    if (!value || !Object.keys(value).every(key => allowed.has(key)) || typeof value.requestId !== "string" || !value.requestId || value.requestId.length > 200
      || !["cycle_explanation", "session_comparison"].includes(value.kind) || !["live", "simulation"].includes(value.sourceMode)
      || !Array.isArray(value.sessionIds) || value.sessionIds.length < 1 || value.sessionIds.length > 2 || !value.sessionIds.every((id: unknown) => typeof id === "string" && id.length > 0 && id.length <= 200)
      || typeof value.question !== "string" || !value.question.length || value.question.length > 500
      || typeof value.expectedSelectionDigest !== "string" || !/^[0-9a-f]{64}$/.test(value.expectedSelectionDigest)) return null;
    if (["cycleId", "comparisonSpecId", "baselineSessionId", "adaptiveSessionId"].some(key => value[key] !== undefined && (typeof value[key] !== "string" || !value[key].length || value[key].length > 200))) return null;
    return selectionScope(value as AnalysisSelection) === selectionScope(selection) ? value as AnalysisRequest : null;
  } catch { return null; }
}

export function hasEligibleRecords(context: AnalysisContext): boolean {
  return context.metrics.some(metric => metric.denominator !== undefined && metric.denominator > 0);
}

export function contextMatchesSelection(context: AnalysisContext, selection: AnalysisSelection): boolean {
  return context?.kind === selection.kind && context.sourceMode === selection.sourceMode
    && JSON.stringify(context.sessionIds) === JSON.stringify(selection.sessionIds)
    && (context.cycleId ?? undefined) === selection.cycleId
    && (context.compatibility?.comparisonSpecId ?? undefined) === selection.comparisonSpecId
    && (context.comparisonRoles?.baselineSessionId ?? undefined) === selection.baselineSessionId
    && (context.comparisonRoles?.adaptiveSessionId ?? undefined) === selection.adaptiveSessionId;
}

export function reportIsStale(state: AnalystState): boolean {
  return Boolean(state.report && (state.report.freshness === "stale" || !state.selection?.connected
    || !state.context || state.report.context.contentDigest !== state.context.contentDigest));
}

/** Read-only record selection and separately persisted report jobs. No station store is mutated. */
export class AnalystController {
  private state: AnalystState = { selection: null, phase: "empty", context: null, reports: [], report: null, error: null, uncertainRequest: null, readHealthy: false, warnings: [] };
  private listeners = new Set<() => void>();
  private generation = 0;
  private abort: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private submitting = false;
  constructor(
    private api: AnalysisApi,
    private options: { requestId?: () => string; pollMs?: number; cache?: Map<string, AnalysisContext>; pendingStorage?: PendingStorage } = {},
  ) {}
  private pending(selection: AnalysisSelection, request?: AnalysisRequest | null): AnalysisRequest | null {
    const storage = this.options.pendingStorage ?? defaultStorage();
    try {
      if (request === null) { storage?.removeItem(pendingKey(selection)); return null; }
      if (request) { storage?.setItem(pendingKey(selection), JSON.stringify(request)); return request; }
      return parsePending(storage?.getItem(pendingKey(selection)) ?? null, selection);
    } catch { return null; }
  }
  getState = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private update(patch: Partial<AnalystState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach(listener => listener());
  }
  private resetNetwork() {
    this.generation += 1;
    this.abort?.abort();
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.abort = new AbortController();
    this.submitting = false;
    return { generation: this.generation, signal: this.abort.signal };
  }
  dispose = () => { this.resetNetwork(); this.abort?.abort(); };
  private valid(generation: number, signal: AbortSignal) { return generation === this.generation && !signal.aborted; }
  private error(error: unknown) {
    return error instanceof AnalysisApiError ? { code: error.code, message: error.message }
      : { code: "invalid_response", message: "The analysis result could not be read. Recorded facts remain available." };
  }

  async select(selection: AnalysisSelection | null): Promise<void> {
    const previous = this.state;
    const sameScope = selection && previous.selection && selectionScope(selection) === selectionScope(previous.selection);
    const { generation, signal } = this.resetNetwork();
    if (!selection) {
      this.update({ selection: null, phase: "empty", context: null, reports: [], report: null, error: null, uncertainRequest: null, readHealthy: false, warnings: [] });
      return;
    }
    const cache = this.options.cache ?? capturedContexts;
    const cached = cache.get(captureKey(selection)) ?? null;
    const sameRecords = sameScope && previous.selection?.recordKey === selection.recordKey;
    this.update({ selection, phase: selection.connected ? "loading" : "ready", context: cached ?? (sameRecords && !selection.readOnly ? previous.context : null),
      reports: sameScope && !selection.readOnly ? previous.reports : [],
      report: sameScope && !selection.readOnly ? previous.report : null,
      error: null, readHealthy: false, warnings: sameScope ? previous.warnings : [], uncertainRequest: (sameScope ? previous.uncertainRequest : null) ?? this.pending(selection) });
    if (!selection.connected) return;
    try {
      // Replay never replaces its frozen context with a fresh read of canonical records.
      const context = selection.readOnly ? cached : await this.api.context(selection, signal);
      if (!this.valid(generation, signal)) return;
      if (context && !contextMatchesSelection(context, selection)) throw new AnalysisApiError("source_mismatch", "The returned facts do not belong to this selection.");
      // A read racing a canonical change may explain normal history, but cannot attest an older frozen replay.
      if (context && selection.snapshotWatermark !== undefined && context.sourceEventWatermark === selection.snapshotWatermark) {
        cache.set(captureKey(selection), context);
        while (cache.size > 16) cache.delete(cache.keys().next().value!);
      }
      this.update({ context });
      const listed = await this.api.list(selection, signal);
      const warnings = Array.isArray(listed) ? [] : listed.warnings ?? [];
      const reports = (Array.isArray(listed) ? listed : listed.reports).filter(report => contextMatchesSelection(report.context, selection)
        && (!selection.readOnly || (context && report.context.contentDigest === context.contentDigest)));
      if (!this.valid(generation, signal)) return;
      const recovered = reports.find(report => report.request.requestId === this.state.uncertainRequest?.requestId);
      const selected = recovered ?? reports.find(report => report.reportId === previous.report?.reportId)
        ?? reports.find(report => report.context.contentDigest === context?.contentDigest)
        ?? reports[0] ?? null;
      if (recovered && !selection.readOnly) this.pending(selection, null);
      this.update({ phase: selected && active(selected) ? "waiting" : "ready", reports, report: selected, error: null, readHealthy: warnings.length === 0, warnings,
        uncertainRequest: recovered && !selection.readOnly ? null : this.state.uncertainRequest });
      if (selected && active(selected) && !selection.readOnly) this.schedulePoll(selected.reportId, generation, signal);
    } catch (error) {
      if (this.valid(generation, signal)) this.update({ phase: "error", error: this.error(error), readHealthy: false });
    }
  }

  async refresh(): Promise<void> { await this.select(this.state.selection); }

  chooseReport(reportId: string): void {
    const report = this.state.reports.find(item => item.reportId === reportId);
    if (!report) return;
    const { generation, signal } = this.resetNetwork();
    this.update({ report, phase: active(report) ? "waiting" : this.state.readHealthy ? "ready" : "error", error: this.state.readHealthy ? null : this.state.error });
    if (active(report) && !this.state.selection?.readOnly) this.schedulePoll(report.reportId, generation, signal);
  }

  async submit(question: string): Promise<void> {
    const { selection, context, uncertainRequest } = this.state;
    if (!selection || selection.readOnly || !selection.connected || !context || !this.state.readHealthy || this.submitting || this.state.phase === "waiting" || uncertainRequest) return;
    if (!hasEligibleRecords(context)) { this.update({ error: { code: "no_eligible_records", message: "No data yet: no finished cycles or attempts are eligible for analysis." } }); return; }
    if (question.length > 500) { this.update({ error: { code: "question_too_long", message: "Keep the question within 500 characters." } }); return; }
    const request: AnalysisRequest = {
      requestId: this.options.requestId?.() ?? crypto.randomUUID(), kind: selection.kind,
      sessionIds: [...selection.sessionIds], sourceMode: selection.sourceMode, question,
      expectedSelectionDigest: context.contentDigest,
      ...(selection.cycleId ? { cycleId: selection.cycleId } : {}),
      ...(selection.comparisonSpecId ? { comparisonSpecId: selection.comparisonSpecId } : {}),
      ...(selection.baselineSessionId ? { baselineSessionId: selection.baselineSessionId } : {}),
      ...(selection.adaptiveSessionId ? { adaptiveSessionId: selection.adaptiveSessionId } : {}),
    };
    await this.send(request);
  }

  async retryUnconfirmed(): Promise<void> {
    const { selection, uncertainRequest } = this.state;
    if (!uncertainRequest || !selection?.connected || selection.readOnly || !this.state.readHealthy || this.submitting) return;
    await this.send(uncertainRequest);
  }

  abandonUnconfirmed(): void {
    if (!this.state.selection || this.state.selection.readOnly || this.submitting) return;
    this.pending(this.state.selection, null);
    this.update({ uncertainRequest: null, error: null });
  }

  private async send(request: AnalysisRequest): Promise<void> {
    const { generation, signal } = this.resetNetwork();
    this.submitting = true;
    this.pending(this.state.selection!, request);
    this.update({ phase: "submitting", error: null, uncertainRequest: request });
    try {
      const report = await this.api.create(request, signal);
      if (!this.valid(generation, signal)) return;
      if (!contextMatchesSelection(report.context, this.state.selection!) || report.context.contentDigest !== request.expectedSelectionDigest)
        throw new AnalysisApiError("source_mismatch", "The returned report does not match the requested facts.");
      this.pending(this.state.selection!, null);
      this.update({ report, reports: [report, ...this.state.reports.filter(item => item.reportId !== report.reportId)],
        phase: active(report) ? "waiting" : "ready", uncertainRequest: null, error: null,
        ...(report.error?.code === "analysis_storage_unavailable" ? { readHealthy: false, warnings: [report.error] } : {}) });
      if (active(report)) this.schedulePoll(report.reportId, generation, signal);
    } catch (error) {
      if (this.valid(generation, signal)) {
        const failure = this.error(error);
        this.update({ phase: "error", error: failure, uncertainRequest: request,
          ...(failure.code === "analysis_storage_unavailable" ? { readHealthy: false } : {}) });
      }
    } finally { if (this.valid(generation, signal)) this.submitting = false; }
  }

  private schedulePoll(reportId: string, generation: number, signal: AbortSignal) {
    this.timer = setTimeout(async () => {
      if (!this.valid(generation, signal)) return;
      try {
        const report = await this.api.read(reportId, signal);
        if (!this.valid(generation, signal)) return;
        if (report.reportId !== reportId || !contextMatchesSelection(report.context, this.state.selection!))
          throw new AnalysisApiError("source_mismatch", "The saved report does not match this selection.");
        this.update({ report, reports: this.state.reports.map(item => item.reportId === reportId ? report : item), phase: active(report) ? "waiting" : "ready", error: null,
          ...(report.error?.code === "analysis_storage_unavailable" ? { readHealthy: false, warnings: [report.error] } : {}) });
        if (active(report)) this.schedulePoll(reportId, generation, signal);
      } catch (error) { if (this.valid(generation, signal)) this.update({ phase: "error", error: this.error(error), readHealthy: false }); }
    }, this.options.pollMs ?? 1000);
  }
}
