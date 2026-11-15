import type { AnalysisFact, AnalysisReport, AnalysisSource, EvidenceBrief } from "./types.ts";

// Exact application-owned wording from the reviewed backend v12 contract, not a model paraphrase.
export const AUDIT_PRESERVATION_TEXT = "The audit preserves each recorded field, its previous value and its replacement value.";

export function isApplicationAuditSummary(report: AnalysisReport, interpretation: EvidenceBrief["interpretations"][number]): boolean {
  return report.provenance.promptVersion === "gemma-evidence-v12"
    && interpretation.text === AUDIT_PRESERVATION_TEXT && interpretation.metricIds.length === 0 && interpretation.factIds.length > 0
    && interpretation.factIds.every(id => {
      const fact = report.context.facts.find(item => item.factId === id);
      return Boolean(fact?.sourceRefs.length && fact.sourceRefs.every(source => source.recordType === "correction"));
    });
}

export interface SavedCorrection {
  fact: AnalysisFact;
  source: AnalysisSource;
  entityType: string;
  entityId: string;
  field: string;
  previousLiteral: string;
  newLiteral: string;
  authorId: string;
  createdAt: string;
}

function isJsonValue(value: unknown, depth = 0): boolean {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (!value || typeof value !== "object" || depth > 32) return false;
  return Object.values(value).every(item => isJsonValue(item, depth + 1));
}

/** Display only complete captured corrections; unknown shapes remain in the generic evidence ledger. */
export function readSavedCorrection(fact: AnalysisFact): SavedCorrection | null {
  if (!fact.value || typeof fact.value !== "object" || Array.isArray(fact.value)) return null;
  const value = fact.value as Record<string, unknown>;
  if (!["entityType", "entityId", "field", "authorId", "createdAt"].every(key => typeof value[key] === "string" && value[key] !== "")
    || !Number.isFinite(Date.parse(value.createdAt as string))
    || !Object.hasOwn(value, "previousValue") || !Object.hasOwn(value, "newValue")
    || !isJsonValue(value.previousValue) || !isJsonValue(value.newValue)) return null;
  const source = fact.sourceRefs.find(item => item.recordType === "correction" && item.fieldPath.replace(/^\//, "") === "previousValue");
  if (!source || !Number.isInteger(source.revision) || source.revision < 1
    || !fact.sourceRefs.every(item => item.recordType === "correction" && item.entityId === source.entityId && item.revision === source.revision && item.sessionId === source.sessionId)) return null;
  const capturedFields = new Set(fact.sourceRefs.map(item => item.fieldPath.replace(/^\//, "")));
  if (!["entityType", "entityId", "field", "previousValue", "newValue", "authorId", "createdAt"].every(field => capturedFields.has(field))) return null;
  return { fact, source, entityType: value.entityType as string, entityId: value.entityId as string, field: value.field as string,
    previousLiteral: JSON.stringify(value.previousValue), newLiteral: JSON.stringify(value.newValue), authorId: value.authorId as string, createdAt: value.createdAt as string };
}
