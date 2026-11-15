import type { AnalysisApi, AnalysisRequest, AnalysisWarning } from "./types.ts";
import { isAnalysisContext, isAnalysisReport } from "./validation.ts";

export class AnalysisApiError extends Error {
  constructor(public code: string, message: string, public status: number | null = null) {
    super(message);
    this.name = "AnalysisApiError";
  }
}

export function analysisErrorMessage(error: { code: string; message: string }): string {
  const known: Record<string, string> = {
    missing_key: "Gemma access is not configured on this station.",
    credentials_missing: "Gemma access is not configured on this station.",
    unauthorized: "Gemma or the records API refused authorization.",
    provider_unauthorized: "Gemma refused authorization.",
    quota_exceeded: "Gemma quota is exhausted. Retry after access is restored.",
    rate_limited: "Gemma is rate limited. Retry after the limit clears.",
    timeout: "Gemma did not finish before the provider deadline.",
    provider_timeout: "Gemma did not finish before the provider deadline.",
    invalid_output: "Gemma returned an explanation that failed local evidence validation.",
    unsupported_cycle_headline: "Gemma's reply did not pass the evidence checks. The saved facts remain available.",
    missing_required_facts: "Gemma's reply did not link its claims to enough saved evidence. The saved facts remain available.",
    missing_metric_evidence: "Gemma's reply did not link its claims to enough saved evidence. The saved facts remain available.",
    unsupported_hypothesis: "Gemma's reply went beyond what the saved evidence supports. The saved facts remain available.",
    source_mismatch: "The selected evidence changed. Review the updated facts before generating again.",
    stale_selection: "The selected evidence changed. Review the updated facts before generating again.",
    interrupted: "The analysis job was interrupted. Its saved facts remain available.",
    transport: "The connection ended before the result was confirmed. Retry the same request to avoid a duplicate job.",
    too_large: "This selection exceeds the bounded evidence limit.",
    invalid_response: "The analysis API returned an unreadable report.",
    request_timeout: "The analysis API did not respond in time. Refresh saved reports; an unconfirmed submission can be retried with the same request ID.",
  };
  return known[error.code] ?? error.message;
}

export function createAnalysisApi(fetcher: typeof fetch = globalThis.fetch, options: { timeoutMs?: number } = {}): AnalysisApi {
  async function request<T>(path: string, signal: AbortSignal, body?: AnalysisRequest): Promise<T> {
    let response: Response;
    const deadline = new AbortController();
    const timer = setTimeout(() => deadline.abort(), options.timeoutMs ?? 40000);
    const requestSignal = AbortSignal.any([signal, deadline.signal]);
    try {
      try {
        response = await fetcher(`/api/v1/analysis/${path}`, {
          method: body ? "POST" : "GET", signal: requestSignal, credentials: "same-origin",
          headers: body ? { "Content-Type": "application/json", "X-Morph-Intent": "evidence-analysis" } : undefined,
          body: body ? JSON.stringify(body) : undefined,
        });
      } catch (error) {
        if (signal.aborted) throw error;
        if (deadline.signal.aborted) throw new AnalysisApiError("request_timeout", "The analysis API response deadline expired.");
        throw new AnalysisApiError("transport", "The analysis API connection was interrupted.");
      }
      let result: any;
      try { result = await response.json(); }
      catch (error) {
        if (signal.aborted) throw error;
        if (deadline.signal.aborted) throw new AnalysisApiError("request_timeout", "The analysis API response deadline expired.");
        throw new AnalysisApiError("invalid_response", "The analysis API did not return JSON.", response.status);
      }
      if (!response.ok) {
        const detail = result?.detail ?? result?.error ?? result;
        const code = typeof detail?.code === "string" ? detail.code
          : response.status === 401 || response.status === 403 ? "unauthorized"
          : response.status === 409 ? "source_mismatch" : `http_${response.status}`;
        const message = typeof detail?.message === "string" ? detail.message : typeof detail === "string" ? detail : `Analysis API returned HTTP ${response.status}.`;
        throw new AnalysisApiError(code, message, response.status);
      }
      return result as T;
    } finally { clearTimeout(timer); }
  }
  return {
    async context(selection, signal) {
      const query = new URLSearchParams({ kind: selection.kind, sourceMode: selection.sourceMode });
      selection.sessionIds.forEach(id => query.append("sessionIds", id));
      if (selection.cycleId) query.set("cycleId", selection.cycleId);
      if (selection.comparisonSpecId) query.set("comparisonSpecId", selection.comparisonSpecId);
      if (selection.baselineSessionId) query.set("baselineSessionId", selection.baselineSessionId);
      if (selection.adaptiveSessionId) query.set("adaptiveSessionId", selection.adaptiveSessionId);
      const result = await request<unknown>(`context?${query}`, signal);
      if (!isAnalysisContext(result)) throw new AnalysisApiError("invalid_response", "The selected evidence context is unreadable.");
      return result;
    },
    async list(selection, signal) {
      const query = new URLSearchParams({ sessionId: selection.sessionIds[0] });
      if (selection.cycleId) query.set("cycleId", selection.cycleId);
      const result = await request<{ reports: unknown[]; warnings?: AnalysisWarning[] }>(`reports?${query}`, signal);
      if (!Array.isArray(result?.reports)) throw new AnalysisApiError("invalid_response", "The saved-report list is unreadable.");
      if (result.warnings !== undefined && (!Array.isArray(result.warnings) || result.warnings.some(item => !item || typeof item.code !== "string" || typeof item.message !== "string")))
        throw new AnalysisApiError("invalid_response", "The saved-report status is unreadable.");
      const reports = result.reports.filter(isAnalysisReport);
      const warnings = [...(result.warnings ?? [])];
      if (reports.length !== result.reports.length) warnings.push({ code: "invalid_response", message: "Some saved reports have an unreadable format. Valid saved facts remain available; refresh after the records API is repaired." });
      return { reports, warnings };
    },
    async create(body, signal) {
      const result = await request<unknown>("reports", signal, body);
      if (!isAnalysisReport(result)) throw new AnalysisApiError("invalid_response", "The submitted report is unreadable.");
      return result;
    },
    async read(id, signal) {
      const result = await request<unknown>(`reports/${encodeURIComponent(id)}`, signal);
      if (!isAnalysisReport(result)) throw new AnalysisApiError("invalid_response", "The saved report is unreadable.");
      return result;
    },
  };
}
