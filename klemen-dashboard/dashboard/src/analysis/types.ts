import type { SourceMode } from "../types/morph.ts";

export type AnalysisKind = "cycle_explanation" | "session_comparison";
export type ReportStatus = "queued" | "running" | "ready" | "rejected" | "failed" | "interrupted";

export interface AnalysisSource {
  recordType: string;
  entityId: string;
  revision: number;
  sessionId: string;
  cycleId?: string;
  fieldPath: string;
}

export interface AnalysisFact {
  factId: string;
  text: string;
  value: unknown;
  sourceRefs: AnalysisSource[];
}

export interface AnalysisMetric {
  metricId: string;
  key?: string;
  label: string;
  value: unknown;
  numerator?: number;
  denominator?: number;
  definition: string;
  sessionId: string;
  includedIds: string[];
  excludedIds: string[];
}

export interface AnalysisContext {
  contextVersion: string;
  kind: AnalysisKind;
  sourceMode: SourceMode;
  sessionIds: string[];
  cycleId?: string | null;
  asOf: string;
  sourceEventWatermark: number;
  contentDigest: string;
  facts: AnalysisFact[];
  metrics: AnalysisMetric[];
  knownGaps: { key: string; text: string }[];
  reviewTargets: { id: string; label: string; sourceRefs: AnalysisSource[] }[];
  sampling: { shownCycleIds: string[]; totalCycles: number; omittedCycleIds: string[] };
  compatibility: { state: "unknown" | "compatible" | "incompatible"; reasons: string[]; comparisonSpecId?: string | null } | null;
  comparisonRoles: { baselineSessionId: string; adaptiveSessionId: string } | null;
  untrustedExcerpts?: { untrusted: true; sourceRef: AnalysisSource; text: string }[];
  descriptiveDeltas?: { key: string; percentagePoints: number | null; definition: string }[];
}

export interface EvidenceBrief {
  contractVersion: "gemma-brief-v1";
  answerState: "supported" | "insufficient_evidence";
  headline: string;
  interpretations: { text: string; factIds: string[]; metricIds: string[] }[];
  hypotheses: { text: string; factIds: string[]; gapKeys: string[] }[];
  evidenceGapKeys: string[];
  suggestedReviewTargetIds: string[];
}

export interface AnalysisRequest {
  requestId: string;
  kind: AnalysisKind;
  sessionIds: string[];
  cycleId?: string;
  sourceMode: SourceMode;
  question: string;
  expectedSelectionDigest: string;
  comparisonSpecId?: string;
  baselineSessionId?: string;
  adaptiveSessionId?: string;
}

export interface AnalysisReport {
  reportId: string;
  status: ReportStatus;
  freshness: "current" | "stale";
  request: AnalysisRequest;
  context: AnalysisContext;
  output: EvidenceBrief | null;
  validation: { accepted: boolean; reasons: string[] };
  provenance: { requestedModel: string; returnedModel: string | null; promptVersion: string; contractVersion: string };
  timestamps: Record<string, string | null>;
  timings: { providerLatencyMs: number | null; validationMs: number | null; reportTotalMs: number | null };
  error: { code: string; message: string } | null;
  cacheReused?: boolean;
}

export interface AnalysisSelection {
  kind: AnalysisKind;
  sessionIds: string[];
  cycleId?: string;
  sourceMode: SourceMode;
  comparisonSpecId?: string;
  baselineSessionId?: string;
  adaptiveSessionId?: string;
  /** A local immutable-record fingerprint, never sent as a backend digest. */
  recordKey: string;
  snapshotWatermark?: number;
  readOnly: boolean;
  connected: boolean;
}

export interface AnalysisApi {
  context(selection: AnalysisSelection, signal: AbortSignal): Promise<AnalysisContext>;
  list(selection: AnalysisSelection, signal: AbortSignal): Promise<AnalysisReport[] | AnalysisReportList>;
  create(request: AnalysisRequest, signal: AbortSignal): Promise<AnalysisReport>;
  read(reportId: string, signal: AbortSignal): Promise<AnalysisReport>;
}

export interface AnalysisWarning { code: string; message: string }
export interface AnalysisReportList { reports: AnalysisReport[]; warnings?: AnalysisWarning[] }
