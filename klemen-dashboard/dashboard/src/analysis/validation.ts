import type { AnalysisContext, AnalysisReport, EvidenceBrief } from "./types.ts";

const object = (value: unknown): value is Record<string, any> => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const number = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(text);
const optionalText = (value: unknown) => value === undefined || value === null || text(value);
const source = (value: unknown) => object(value) && text(value.recordType) && text(value.entityId) && number(value.revision)
  && text(value.sessionId) && optionalText(value.cycleId) && text(value.fieldPath);
const sources = (value: unknown) => Array.isArray(value) && value.every(source);

/** Structural checks prevent unreadable transport data from escaping into the dashboard render. */
export function isAnalysisContext(value: unknown): value is AnalysisContext {
  if (!object(value)) return false;
  return text(value.contextVersion) && ["cycle_explanation", "session_comparison"].includes(value.kind)
    && ["live", "simulation"].includes(value.sourceMode) && strings(value.sessionIds) && optionalText(value.cycleId)
    && text(value.asOf) && Number.isFinite(Date.parse(value.asOf)) && number(value.sourceEventWatermark) && text(value.contentDigest)
    && Array.isArray(value.facts) && value.facts.every((item: unknown) => object(item) && text(item.factId) && text(item.text) && sources(item.sourceRefs))
    && Array.isArray(value.metrics) && value.metrics.every((item: unknown) => object(item) && text(item.metricId) && text(item.label)
      && (item.numerator === undefined || number(item.numerator)) && (item.denominator === undefined || number(item.denominator))
      && text(item.definition) && text(item.sessionId) && strings(item.includedIds) && strings(item.excludedIds))
    && Array.isArray(value.knownGaps) && value.knownGaps.every((item: unknown) => object(item) && text(item.key) && text(item.text))
    && Array.isArray(value.reviewTargets) && value.reviewTargets.every((item: unknown) => object(item) && text(item.id) && text(item.label) && sources(item.sourceRefs))
    && object(value.sampling) && strings(value.sampling.shownCycleIds) && number(value.sampling.totalCycles) && strings(value.sampling.omittedCycleIds)
    && (value.compatibility === null || (object(value.compatibility) && ["unknown", "compatible", "incompatible"].includes(value.compatibility.state) && strings(value.compatibility.reasons) && optionalText(value.compatibility.comparisonSpecId)))
    && (value.comparisonRoles === null || (object(value.comparisonRoles) && text(value.comparisonRoles.baselineSessionId) && text(value.comparisonRoles.adaptiveSessionId)))
    && (value.untrustedExcerpts === undefined || (Array.isArray(value.untrustedExcerpts) && value.untrustedExcerpts.every((item: unknown) => object(item) && item.untrusted === true && source(item.sourceRef) && text(item.text))))
    && (value.descriptiveDeltas === undefined || (Array.isArray(value.descriptiveDeltas) && value.descriptiveDeltas.every((item: unknown) => object(item) && text(item.key) && (item.percentagePoints === null || number(item.percentagePoints)) && text(item.definition))));
}

export function isEvidenceBrief(value: unknown): value is EvidenceBrief {
  return object(value) && value.contractVersion === "gemma-brief-v1" && ["supported", "insufficient_evidence"].includes(value.answerState) && text(value.headline)
    && Array.isArray(value.interpretations) && value.interpretations.every((item: unknown) => object(item) && text(item.text) && strings(item.factIds) && strings(item.metricIds))
    && Array.isArray(value.hypotheses) && value.hypotheses.every((item: unknown) => object(item) && text(item.text) && strings(item.factIds) && strings(item.gapKeys))
    && strings(value.evidenceGapKeys) && strings(value.suggestedReviewTargetIds);
}

export function isAnalysisReport(value: unknown): value is AnalysisReport {
  return object(value) && text(value.reportId) && ["queued", "running", "ready", "rejected", "failed", "interrupted"].includes(value.status)
    && ["current", "stale"].includes(value.freshness) && isAnalysisContext(value.context)
    && object(value.request) && text(value.request.requestId) && text(value.request.question) && text(value.request.expectedSelectionDigest)
    && ["cycle_explanation", "session_comparison"].includes(value.request.kind) && ["live", "simulation"].includes(value.request.sourceMode) && strings(value.request.sessionIds)
    && (value.output === null || isEvidenceBrief(value.output))
    && object(value.validation) && typeof value.validation.accepted === "boolean" && strings(value.validation.reasons)
    && object(value.provenance) && text(value.provenance.requestedModel) && (value.provenance.returnedModel === null || text(value.provenance.returnedModel))
    && text(value.provenance.promptVersion) && text(value.provenance.contractVersion)
    && object(value.timings) && ["providerLatencyMs", "validationMs", "reportTotalMs"].every(key => value.timings[key] === null || number(value.timings[key]))
    && object(value.timestamps) && Object.values(value.timestamps).every(item => item === null || text(item))
    && (value.error === null || (object(value.error) && text(value.error.code) && text(value.error.message)));
}
