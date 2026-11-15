import React, { useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { DISPLAY_TIME_ZONE, EvidenceImage, formatTimestamp } from "../components/EvidenceImage.tsx";
import type { StationSnapshot } from "../types/morph.ts";
import { analysisErrorMessage, createAnalysisApi } from "./client.ts";
import { AnalystController, hasEligibleRecords, reportIsStale, selectionScope, type AnalystState } from "./controller.ts";
import { readQuestionDraft, saveQuestionDraft } from "./drafts.ts";
import { isApplicationAuditSummary, readSavedCorrection, type SavedCorrection } from "./audit.ts";
import { isEvidenceBrief } from "./validation.ts";
import type { AnalysisApi, AnalysisContext, AnalysisFact, AnalysisKind, AnalysisReport, AnalysisSelection, AnalysisSource } from "./types.ts";

const buttonClass = "min-h-[36px] rounded-[5px] border border-[#484137] px-3 py-2 text-[11px] text-[#F2EEE6] hover:bg-[#29241c] disabled:cursor-not-allowed disabled:opacity-40";
const fieldClass = "min-h-[36px] w-full rounded-[5px] border border-[#3e3b34] bg-[#101010] px-3 py-2 text-[12px] text-[#F2EEE6]";
const blankState: AnalystState = { selection: null, phase: "empty", context: null, reports: [], report: null, error: null, uncertainRequest: null, readHealthy: false, warnings: [] };
const valueText = (value: unknown): string => value === null || value === undefined ? "Unavailable"
  : typeof value === "string" ? value : JSON.stringify(value);

function SourceLinks({ fact, context, onOpenSource }: { fact: AnalysisFact; context?: AnalysisContext; onOpenSource: (source: AnalysisSource) => void }) {
  const [selectedSource, setSelectedSource] = useState<AnalysisSource | null>(null);
  return <><details className="rounded border border-[#353128] px-2 py-1 text-[11px] text-[#C7A477]">
    <summary className="cursor-pointer break-words">{fact.factId} · {fact.text}</summary>
    <div className="mt-2 space-y-2 text-[#A7A39A]">
      <pre className="whitespace-pre-wrap break-words font-mono-tech text-[10px]">{valueText(fact.value)}</pre>
      {fact.sourceRefs.map((source, index) => <button key={`${source.entityId}:${source.fieldPath}:${index}`} type="button"
        onClick={() => setSelectedSource(source)} className={`${buttonClass} block max-w-full break-all text-left`}
        aria-label={`Open ${source.recordType} ${source.entityId}, revision ${source.revision}, ${source.fieldPath}`}>
        Open {source.recordType} · {source.entityId} · revision {source.revision} · {source.fieldPath}
      </button>)}
    </div>
  </details>{selectedSource && <SourceEvidenceDialog fact={fact} context={context} source={selectedSource} onClose={() => setSelectedSource(null)} onOpenSource={onOpenSource} />}</>;
}

export function SourceEvidenceDialog({ fact, context, source, onClose, onOpenSource }: { fact: AnalysisFact; context?: AnalysisContext; source: AnalysisSource; onClose: () => void; onOpenSource: (source: AnalysisSource) => void }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const titleId = useId();
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); }
      if (event.key === "Tab") {
        const items = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("button:not([disabled]), [tabindex='0']") ?? []);
        const first = items[0], last = items.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); previouslyFocused?.focus(); };
  }, []);
  const excerpts = context?.untrustedExcerpts?.filter(item => item.sourceRef.entityId === source.entityId && item.sourceRef.recordType === source.recordType && item.sourceRef.revision === source.revision) ?? [];
  const fields = fact.value && typeof fact.value === "object" ? fact.value as Record<string, unknown> : {};
  const evidenceId = source.recordType === "evidence" ? source.entityId : source.recordType === "frame" && typeof fields.evidenceId === "string" ? fields.evidenceId : null;
  const evidenceFact = source.recordType === "evidence" ? fact : context?.facts.find(item => item.sourceRefs.some(ref => ref.recordType === "evidence" && ref.entityId === evidenceId));
  const evidenceFields = evidenceFact?.value && typeof evidenceFact.value === "object" ? evidenceFact.value as Record<string, unknown> : {};
  const isImage = typeof evidenceFields.mediaType === "string" && evidenceFields.mediaType.startsWith("image/");
  return <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/75 p-4">
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-[#514633] bg-[#101010] p-5 shadow-xl">
      <div className="flex items-start justify-between gap-3"><h3 id={titleId} className="text-[17px] text-[#F2EEE6]">Cited evidence snapshot</h3><button type="button" className={buttonClass} onClick={onClose}>Close</button></div>
      <p className="mt-3 text-[12px] text-[#D4D0C8]">{fact.text}</p>
      <dl className="mt-3 space-y-1 break-all text-[11px] text-[#A7A39A]">
        <div><dt className="inline">Record: </dt><dd className="inline">{source.recordType} · {source.entityId}</dd></div>
        <div><dt className="inline">Revision: </dt><dd className="inline">{source.revision}</dd></div>
        <div><dt className="inline">Session: </dt><dd className="inline">{source.sessionId}</dd></div>
        {source.cycleId && <div><dt className="inline">Cycle: </dt><dd className="inline">{source.cycleId}</dd></div>}
        <div><dt className="inline">Selected field: </dt><dd className="inline">{source.fieldPath}</dd></div>
        <div><dt className="inline">Saved fact: </dt><dd className="inline">{fact.factId}</dd></div>
        {context && <div><dt className="inline">Evidence as of: </dt><dd className="inline">{formatTimestamp(context.asOf)} ({DISPLAY_TIME_ZONE})</dd></div>}
      </dl>
      <h4 className="mt-4 text-[12px] text-[#C7A477]">Captured evidence values</h4>
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded border border-[#353128] p-3 font-mono-tech text-[11px] text-[#D4D0C8]">{typeof fact.value === "object" && fact.value !== null ? JSON.stringify(fact.value, null, 2) : valueText(fact.value)}</pre>
      {excerpts.length > 0 && <div className="mt-3"><h4 className="text-[12px] text-[#D6B775]">Recorded notes · untrusted explanatory text</h4>{excerpts.map((item, index) => <div className="mt-2" key={index}><p className="text-[10px] text-[#A7A39A]">{item.sourceRef.fieldPath}</p><p className="whitespace-pre-wrap break-words text-[12px] text-[#D4D0C8]">{item.text}</p></div>)}</div>}
      {evidenceId && <div className="mt-3"><h4 className="text-[12px] text-[#C7A477]">Recorded image evidence</h4>
        {isImage ? <EvidenceImage src={`/api/v1/evidence/${encodeURIComponent(evidenceId)}`} alt={`Saved evidence ${evidenceId}`} className="mt-2 max-h-[260px] w-full object-contain" /> : <p className="mt-2 text-[11px] text-[#A7A39A]">Image bytes are unavailable or this record is not an image.</p>}
        <p className="mt-2 break-all text-[10px] text-[#A7A39A]">Evidence: {evidenceId} · Frame: {source.recordType === "frame" ? source.entityId : "See linked frame facts"} · Captured: {typeof fields.capturedAt === "string" ? formatTimestamp(fields.capturedAt) : "Unavailable"} · SHA-256: {typeof evidenceFields.sha256 === "string" ? evidenceFields.sha256 : "Unavailable"}</p>
      </div>}
      <p className="mt-3 text-[11px] text-[#A7A39A]">These selected fields were saved with the analysis context. They preserve the cited revision. The current cycle trace may contain later corrections.</p>
      {source.cycleId && <button type="button" className={`${buttonClass} mt-3`} onClick={() => { onClose(); onOpenSource(source); }}>Open current cycle trace</button>}
    </div>
  </div>;
}

function MetricValue({ value }: { value: unknown }) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const fields = value as Record<string, unknown>;
    if (typeof fields.checked === "number" && typeof fields.correct === "number" && typeof fields.totalPopulation === "number") return <div className="mt-1 space-y-1 text-[11px] text-[#D4D0C8]">
      <p>Correct / checked: {fields.checked > 0 ? `${fields.correct} / ${fields.checked}` : "No data yet"}</p>
      <p>Checked / total population: {fields.checked} / {fields.totalPopulation}</p>
      <p>Unresolved: {valueText(fields.unresolved)}</p>
      <details className="text-[#A7A39A]"><summary className="cursor-pointer">Saved detection breakdown</summary><pre className="whitespace-pre-wrap break-words text-[10px]">{JSON.stringify({ confusionMatrix: fields.confusionMatrix, defectEscape: fields.defectEscape }, null, 2)}</pre></details>
    </div>;
    if (typeof fields.sampleCount === "number" && Array.isArray(fields.valuesMs)) return <div className="mt-1 space-y-1 text-[11px] text-[#D4D0C8]">
      <p>Timing samples: {fields.sampleCount}</p>
      <p>Saved durations (ms): {fields.valuesMs.length ? fields.valuesMs.slice(0, 10).map(valueText).join(" · ") : "Unavailable"}</p>
      {fields.valuesMs.length > 10 && <p className="text-[#A7A39A]">Showing the first 10 of {fields.valuesMs.length} supplied durations.</p>}
    </div>;
  }
  if (value && typeof value === "object" && !Array.isArray(value)) return <dl className="mt-1 space-y-1 text-[11px] text-[#D4D0C8]">{Object.entries(value).map(([key, item]) => <div key={key}><dt className="inline text-[#A7A39A]">{key.replace(/([a-z])([A-Z])/g, "$1 $2")}: </dt><dd className="inline break-words">{valueText(item)}</dd></div>)}</dl>;
  return <>{valueText(value)}</>;
}

export function SavedCorrectionAudit({ context, onOpenSource }: { context: AnalysisContext; onOpenSource: (source: AnalysisSource) => void }) {
  const corrections = context.facts.map(fact => readSavedCorrection(fact, context))
    .filter((item): item is SavedCorrection => item !== null);
  const [selected, setSelected] = useState<SavedCorrection | null>(null);
  if (corrections.length === 0) return null;

  return (
    <section aria-label="Saved correction records" className="mt-4 rounded border border-[#514633] bg-[#15130f] p-3">
      <h4 className="text-[13px] font-medium text-[#D6B775]">Saved correction records</h4>
      <p className="mt-1 text-[11px] text-[#A7A39A]">
        Exact values captured with this evidence snapshot. These are recorded field changes, separate from Gemma's explanation.
      </p>
      <ul className="mt-3 space-y-3">
        {corrections.map(correction => (
          <li key={correction.fact.factId} className="border-t border-[#353128] pt-3">
            <p className="break-all text-[11px] text-[#D4D0C8]">
              {correction.entityType} · {correction.entityId} · <strong>{correction.field}</strong>
            </p>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
              <div className="min-w-0">
                <dt className="text-[#A7A39A]">Before</dt>
                <dd className="mt-1 whitespace-pre-wrap break-all font-mono-tech text-[#F2EEE6]">{correction.previousLiteral}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-[#A7A39A]">After</dt>
                <dd className="mt-1 whitespace-pre-wrap break-all font-mono-tech text-[#F2EEE6]">{correction.newLiteral}</dd>
              </div>
            </dl>
            <p className="mt-2 break-all text-[10px] text-[#A7A39A]">
              Session {correction.source.sessionId} · {correction.authorId} · {formatTimestamp(correction.createdAt)} ({DISPLAY_TIME_ZONE})
            </p>
            <button
              type="button"
              className={`${buttonClass} mt-2 max-w-full break-all text-left`}
              onClick={() => setSelected(correction)}
              aria-label={`Open saved correction ${correction.source.entityId}, revision ${correction.source.revision}`}
            >
              {correction.fact.factId} · Correction {correction.source.entityId} · revision {correction.source.revision}
            </button>
          </li>
        ))}
      </ul>
      {selected && (
        <SourceEvidenceDialog
          fact={selected.fact}
          context={context}
          source={selected.source}
          onClose={() => setSelected(null)}
          onOpenSource={onOpenSource}
        />
      )}
    </section>
  );
}

export function RecordedFacts({ context, onOpenSource }: { context: AnalysisContext; onOpenSource: (source: AnalysisSource) => void }) {
  return <section aria-label="Recorded facts" className="mt-5">
    <h3 className="text-[15px] font-medium text-[#F2EEE6]">Recorded facts</h3>
    <p className="mt-1 break-words text-[11px] text-[#A7A39A]">{context.sourceMode === "simulation" ? "Persisted simulation" : "Live records"} · {context.sessionIds.join(" / ")}
      {context.cycleId ? ` · Cycle ${context.cycleId}` : ""} · Evidence as of {formatTimestamp(context.asOf)} ({DISPLAY_TIME_ZONE})</p>
    {context.kind === "session_comparison" ? <div className="mt-3 overflow-x-auto"><table className="w-full border-collapse text-left text-[11px] text-[#D4D0C8]">
      <thead><tr className="border-b border-[#423d33]"><th className="p-2">Recorded metric</th><th className="p-2">Baseline · {context.comparisonRoles?.baselineSessionId ?? context.sessionIds[0]}</th><th className="p-2">Adaptive · {context.comparisonRoles?.adaptiveSessionId ?? context.sessionIds[1]}</th></tr></thead>
      <tbody>{[...new Set(context.metrics.map(metric => metric.label))].map(label => <tr key={label} className="border-b border-[#252421]"><th scope="row" className="p-2 font-normal">{label}</th>{context.sessionIds.map(sessionId => {
        const metric = context.metrics.find(item => item.sessionId === sessionId && item.label === label);
        return <td key={sessionId} className="p-2 align-top">{metric ? <><div className="font-mono-tech">{metric.denominator !== undefined ? metric.denominator > 0 ? `${metric.numerator} / ${metric.denominator}` : "No data yet" : <MetricValue value={metric.value} />}</div><p className="mt-1 text-[10px] text-[#A7A39A]">{metric.definition}</p></> : "Unavailable"}</td>;
      })}</tr>)}</tbody>
    </table></div> : <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {context.metrics.map(metric => <div key={metric.metricId} className="rounded border border-[#353128] bg-[#101010] p-3">
        <div className="text-[11px] text-[#A7A39A]">{metric.label}</div>
        <div className="mt-1 break-words font-mono-tech text-[20px] text-[#F2EEE6]">
          {metric.denominator !== undefined ? metric.denominator > 0 ? `${metric.numerator} / ${metric.denominator}` : "No data yet" : <MetricValue value={metric.value} />}
        </div>
        <p className="mt-1 text-[10px] text-[#A7A39A]">{metric.definition}</p>
        <p className="mt-1 break-all font-mono-tech text-[9px] text-[#817d74]">{metric.metricId} · {metric.sessionId}</p>
      </div>)}
    </div>}
    {context.kind === "session_comparison" && <div className="mt-3 rounded border border-[#514633] bg-[#211d16] p-3 text-[12px] text-[#D6B775]" role="status">
      <strong>{context.compatibility?.state === "compatible" ? "Compatible descriptive comparison" : "Insufficient comparison evidence"}</strong>
      <p className="mt-1">Compatibility: {context.compatibility?.state ?? "unknown"}. Baseline: {context.comparisonRoles?.baselineSessionId ?? context.sessionIds[0]}. Adaptive: {context.comparisonRoles?.adaptiveSessionId ?? context.sessionIds[1]}.</p>
      {context.compatibility?.reasons.map((reason, index) => <p className="mt-1" key={index}>{reason}</p>)}
      {context.compatibility?.state !== "compatible" && <p className="mt-1">These are descriptive session results. The available evidence does not establish an improvement or a winning configuration.</p>}
      {context.compatibility?.state === "compatible" && context.descriptiveDeltas?.map(delta => <p key={delta.key} className="mt-1">{delta.key}: {delta.percentagePoints === null ? "Unavailable" : `${delta.percentagePoints} percentage points`}. {delta.definition}</p>)}
    </div>}
    <p className="mt-3 text-[11px] text-[#A7A39A]">Examples shown: {context.sampling.shownCycleIds.length} / {context.sampling.totalCycles} cycles. Omitted: {context.sampling.omittedCycleIds.length}. Population metrics are computed before example selection.</p>
    <SavedCorrectionAudit key={context.contentDigest} context={context} onOpenSource={onOpenSource} />
    <details className="mt-3 text-[12px] text-[#A7A39A]">
      <summary className="cursor-pointer">Evidence ledger · {context.facts.length} facts</summary>
      <div className="mt-2 space-y-2">{context.facts.map(fact => <SourceLinks key={fact.factId} fact={fact} context={context} onOpenSource={onOpenSource} />)}</div>
    </details>
    {context.knownGaps.length > 0 && <div className="mt-3">
      <h4 className="text-[12px] text-[#D6B775]">Missing evidence</h4>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] text-[#A7A39A]">{context.knownGaps.map(gap => <li key={gap.key}>{gap.text}</li>)}</ul>
    </div>}
  </section>;
}

/** Additional rendering guard; local backend validation remains authoritative. */
export function canRenderBrief(report: AnalysisReport): boolean {
  const answer = report.output;
  if (report.status !== "ready" || !report.validation.accepted || !isEvidenceBrief(answer)) return false;
  const facts = new Set(report.context.facts.map(fact => fact.factId));
  const metrics = new Set(report.context.metrics.map(metric => metric.metricId));
  const gaps = new Set(report.context.knownGaps.map(gap => gap.key));
  const targets = new Set(report.context.reviewTargets.map(target => target.id));
  return answer.interpretations.every(item => item.factIds.length > 0 && item.factIds.every(id => facts.has(id)) && item.metricIds.every(id => metrics.has(id)))
    && answer.hypotheses.every(item => item.factIds.length > 0 && item.factIds.every(id => facts.has(id)) && item.gapKeys.every(id => gaps.has(id)))
    && answer.evidenceGapKeys.every(id => gaps.has(id)) && answer.suggestedReviewTargetIds.every(id => targets.has(id));
}

export function formatAnalysisLatency(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "Unavailable";
  return value < 1000 ? `${Number(value.toFixed(1))} ms` : `${(value / 1000).toFixed(2)} s (${Math.round(value)} ms)`;
}

export function AnalysisReportView({ report, stale, onOpenSource }: { report: AnalysisReport; stale: boolean; onOpenSource: (source: AnalysisSource) => void }) {
  const answer = report.output;
  const factMap = new Map(report.context.facts.map(fact => [fact.factId, fact]));
  const metricMap = new Map(report.context.metrics.map(metric => [metric.metricId, metric]));
  const gapMap = new Map(report.context.knownGaps.map(gap => [gap.key, gap.text]));
  return <section aria-label="Saved Gemma report" className="mt-5 border-t border-[#353128] pt-5">
    <div className="flex flex-wrap items-center gap-2 text-[11px]">
      <span className="rounded border border-[#484137] px-2 py-1 font-mono-tech text-[#C7A477]">{report.status.toUpperCase()}</span>
      <span className={stale ? "text-[#D6B775]" : "text-[#91B99C]"}>{stale ? "Stale evidence snapshot" : "Matches selected evidence"}</span>
      <span className="break-all text-[#A7A39A]">Report {report.reportId}</span>
    </div>
    {stale && <p className="mt-2 text-[12px] text-[#D6B775]" role="status">This saved report retains its original facts and record revisions. Review current facts and explicitly generate an updated explanation.</p>}
    <h3 className="mt-4 text-[15px] font-medium text-[#F2EEE6]">Gemma interpretation</h3>
    <p className="mt-2 break-words text-[11px] text-[#A7A39A]">Saved question: {report.request.question}</p>
    {canRenderBrief(report) && answer ? <>
      <p className="mt-2 break-words text-[14px] text-[#F2EEE6]">{answer.headline}</p>
      {answer.answerState === "insufficient_evidence" && <p role="status" className="mt-2 text-[12px] text-[#D6B775]">Insufficient evidence to answer the full question.</p>}
      {answer.interpretations.map((item, index) => <div key={index} className="mt-4">
        {isApplicationAuditSummary(report, item) && (
          <div className="mb-2">
            <h4 className="text-[13px] font-medium text-[#D6B775]">Application audit summary</h4>
            <p className="mt-1 text-[10px] text-[#A7A39A]">Fixed application wording. Exact field changes are shown in the saved correction records.</p>
          </div>
        )}
        <p className="break-words text-[12px] leading-relaxed text-[#D4D0C8]">{item.text}</p>
        <div className="mt-2 space-y-1">{item.factIds.map(id => <SourceLinks key={id} fact={factMap.get(id)!} context={report.context} onOpenSource={onOpenSource} />)}</div>
        {item.metricIds.length > 0 && <p className="mt-1 text-[10px] text-[#A7A39A]">Recorded metrics: {item.metricIds.map(id => `${metricMap.get(id)!.label} (${id})`).join(" · ")}</p>}
      </div>)}
      {answer.hypotheses.length > 0 && <div className="mt-5 border-l-2 border-[#514633] pl-3">
        <h4 className="text-[12px] text-[#D6B775]">Possible explanation — not verified</h4>
        {answer.hypotheses.map((item, index) => <div key={index} className="mt-2">
          <p className="break-words text-[12px] text-[#D4D0C8]">{item.text}</p>
          <div className="mt-2 space-y-1">{item.factIds.map(id => <SourceLinks key={id} fact={factMap.get(id)!} context={report.context} onOpenSource={onOpenSource} />)}</div>
          {item.gapKeys.map(key => <p key={key} className="mt-1 text-[11px] text-[#A7A39A]">{gapMap.get(key)}</p>)}
        </div>)}
      </div>}
      {answer.evidenceGapKeys.length > 0 && <ul className="mt-3 list-disc pl-4 text-[11px] text-[#D6B775]">{answer.evidenceGapKeys.map(key => <li key={key}>{gapMap.get(key)}</li>)}</ul>}
      {answer.suggestedReviewTargetIds.length > 0 && <div className="mt-4">
        <h4 className="text-[12px] text-[#A7A39A]">Review the supplied records</h4>
        <div className="mt-2 flex flex-wrap gap-2">{answer.suggestedReviewTargetIds.map(id => {
          const target = report.context.reviewTargets.find(item => item.id === id)!;
          return target.sourceRefs.map((source, index) => <button type="button" key={`${id}:${index}`} className={buttonClass} title={target.label} onClick={() => onOpenSource(source)}>Open current {source.recordType} trace · cited revision {source.revision}</button>);
        })}</div>
      </div>}
    </> : <p role="status" className="mt-2 text-[12px] text-[#D6B775]">
      {report.status === "queued" || report.status === "running" ? "Gemma is reviewing this saved evidence. Physical control continues independently."
        : `Gemma explanation unavailable. ${report.error ? analysisErrorMessage(report.error) : "The reply did not pass local evidence validation."}`}
    </p>}
    {report.validation.reasons.length > 0 && <details className="mt-2 text-[11px] text-[#A7A39A]"><summary className="cursor-pointer">Validation result</summary><ul className="mt-1 list-disc pl-4">{report.validation.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul></details>}
    <dl className="mt-4 grid gap-1 break-words border-t border-[#252421] pt-3 text-[10px] text-[#A7A39A] sm:grid-cols-2">
      <div><dt className="inline">Requested model: </dt><dd className="inline font-mono-tech">{report.provenance.requestedModel}</dd></div>
      <div><dt className="inline">Returned model: </dt><dd className="inline font-mono-tech">{report.provenance.returnedModel ?? "Not returned"}</dd></div>
      <div><dt className="inline">Measured provider latency: </dt><dd className="inline">{formatAnalysisLatency(report.timings.providerLatencyMs)}</dd></div>
      <div><dt className="inline">Measured report total: </dt><dd className="inline">{formatAnalysisLatency(report.timings.reportTotalMs)}</dd></div>
      <div><dt className="inline">Evidence as of: </dt><dd className="inline">{formatTimestamp(report.context.asOf)} ({DISPLAY_TIME_ZONE})</dd></div>
      <div><dt className="inline">Prompt / contract: </dt><dd className="inline">{report.provenance.promptVersion} / {report.provenance.contractVersion}</dd></div>
      <div className="break-all sm:col-span-2"><dt className="inline">Evidence digest: </dt><dd className="inline font-mono-tech">{report.context.contentDigest}</dd></div>
    </dl>
    {report.cacheReused && <p className="mt-2 text-[10px] text-[#A7A39A]">An existing report for identical evidence was reused. The latency belongs to its original provider request.</p>}
  </section>;
}

export interface EvidenceAnalystPanelProps {
  snapshot: StationSnapshot;
  onOpenSource: (source: AnalysisSource) => void;
  api?: AnalysisApi;
}

export function EvidenceAnalystPanel(props: EvidenceAnalystPanelProps) {
  return <AnalystSelectionPanel key={`${props.snapshot.activeSession?.id}:${props.snapshot.sourceMode}:${props.snapshot.viewMode}`} {...props} />;
}

function AnalystSelectionPanel({ snapshot, onOpenSource, api }: EvidenceAnalystPanelProps) {
  const [controller] = useState(() => new AnalystController(api ?? createAnalysisApi()));
  const state = useSyncExternalStore(controller.subscribe, controller.getState, controller.getState);
  const [kind, setKind] = useState<AnalysisKind>("cycle_explanation");
  const [cycleId, setCycleId] = useState(snapshot.cycles.at(-1)?.id ?? "");
  const [baselineId, setBaselineId] = useState(snapshot.activeSession?.id ?? "");
  const [adaptiveId, setAdaptiveId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const sourceMode = snapshot.sourceMode ?? snapshot.activeSession?.sourceMode;
  const availableSessions = snapshot.sessions.filter(session => session.sourceMode === sourceMode);
  const cycles = snapshot.cycles.filter(cycle => cycle.sessionId === snapshot.activeSession?.id);
  const eligible = kind === "cycle_explanation" ? cycles.some(cycle => cycle.id === cycleId)
    : baselineId !== adaptiveId && availableSessions.some(session => session.id === baselineId) && availableSessions.some(session => session.id === adaptiveId);
  // Ignore connection receipt times and replay cursor position: neither changes persisted facts.
  const recordKey = JSON.stringify([snapshot.lastEventSequence, snapshot.activeSession, snapshot.cycles, snapshot.attempts,
    snapshot.inspections, snapshot.confirmations, snapshot.referenceLabels, snapshot.corrections, snapshot.frames]);
  const selectionJson = JSON.stringify(eligible && sourceMode && snapshot.activeSession ? {
    kind, sessionIds: kind === "cycle_explanation" ? [snapshot.activeSession.id] : [baselineId, adaptiveId],
    ...(kind === "cycle_explanation" ? { cycleId } : { baselineSessionId: baselineId, adaptiveSessionId: adaptiveId }),
    sourceMode, recordKey, snapshotWatermark: snapshot.lastEventSequence, readOnly: snapshot.viewMode === "replay", connected: snapshot.dataConnection === "connected" && !snapshot.dataStale,
  } satisfies AnalysisSelection : null);
  const selection: AnalysisSelection | null = useMemo(() => JSON.parse(selectionJson), [selectionJson]);
  useEffect(() => { void controller.select(selection); }, [controller, selection]);
  useEffect(() => () => controller.dispose(), [controller]);
  const visible = selection && state.selection && selectionScope(selection) === selectionScope(state.selection) ? state : blankState;
  const draftScope = selection ? selectionScope(selection) : "";
  const question = visible.uncertainRequest?.question ?? drafts[draftScope] ?? readQuestionDraft(draftScope);
  const setQuestion = (value: string) => { setDrafts(previous => ({ ...previous, [draftScope]: value })); saveQuestionDraft(draftScope, value); };
  const busy = visible.phase === "submitting" || visible.phase === "waiting" || visible.phase === "loading";
  const stale = reportIsStale(visible) || Boolean(visible.report && visible.selection?.recordKey !== selection?.recordKey);
  const facts = visible.report?.context ?? visible.context;
  const fallbackQuestion = kind === "cycle_explanation" ? "Explain this cycle, its earlier attempts, and any gaps in the saved evidence." : "What can the saved evidence establish about these baseline and adaptive sessions?";
  return <section aria-label="Gemma evidence analyst" className="mt-6 rounded-[8px] border border-[#423d33] bg-[#080808] p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-[18px] font-medium tracking-[-0.025em] text-[#F2EEE6]">Gemma evidence analyst</h2>
        <p className="mt-1 text-[12px] text-[#A7A39A]">Review saved evidence with cited explanations. Start an analysis with an explicit action.</p></div>
      <span className="rounded border border-[#484137] px-2 py-1 font-mono-tech text-[10px] text-[#C7A477]">{snapshot.viewMode === "replay" ? "READ-ONLY REPLAY" : sourceMode === "simulation" ? "PERSISTED SIMULATION" : "LIVE RECORDS"}</span>
    </div>
    <div className="mt-4 flex flex-wrap gap-2" aria-label="Analysis type">
      <button type="button" className={buttonClass} aria-pressed={kind === "cycle_explanation"} onClick={() => setKind("cycle_explanation")}>Explain this cycle</button>
      <button type="button" className={buttonClass} aria-pressed={kind === "session_comparison"} onClick={() => setKind("session_comparison")}>Compare sessions</button>
    </div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      {kind === "cycle_explanation" ? <label className="text-[11px] text-[#A7A39A]">Saved cycle
        <select aria-label="Saved cycle" value={cycleId} onChange={event => setCycleId(event.target.value)} className={`${fieldClass} mt-1`}>
          <option value="">Select a saved cycle</option>{cycles.map(cycle => <option key={cycle.id} value={cycle.id}>{cycle.objectId} · {cycle.outcome} · {cycle.id}</option>)}
        </select>
      </label> : <>
        <label className="text-[11px] text-[#A7A39A]">Baseline session<select aria-label="Baseline session" value={baselineId} onChange={event => setBaselineId(event.target.value)} className={`${fieldClass} mt-1`}>
          <option value="">Select baseline</option>{availableSessions.map(session => <option key={session.id} value={session.id}>{session.name} · {session.id}</option>)}
        </select></label>
        <label className="text-[11px] text-[#A7A39A]">Adaptive session<select aria-label="Adaptive session" value={adaptiveId} onChange={event => setAdaptiveId(event.target.value)} className={`${fieldClass} mt-1`}>
          <option value="">Select adaptive</option>{availableSessions.filter(session => session.id !== baselineId).map(session => <option key={session.id} value={session.id}>{session.name} · {session.id}</option>)}
        </select></label>
      </>}
    </div>
    {!eligible && <p role="status" className="mt-3 text-[12px] text-[#A7A39A]">{kind === "session_comparison" ? "Select two distinct saved sessions from the same source. Missing comparison metadata will be shown as insufficient evidence." : "No data yet. Select a saved cycle to review its evidence."}</p>}
    {eligible && <>
      {snapshot.viewMode === "replay" ? <p role="status" className="mt-3 text-[12px] text-[#D6B775]">Replay shows only saved reports matching a previously captured evidence snapshot. Return to normal history to generate an explanation.</p> : <label className="mt-3 block text-[11px] text-[#A7A39A]">Optional evidence question · {question.length}/500
        <textarea maxLength={500} value={question} onChange={event => setQuestion(event.target.value)} placeholder={fallbackQuestion} disabled={Boolean(visible.uncertainRequest)} className={`${fieldClass} mt-1 min-h-[70px] resize-y`} />
      </label>}
      <div className="mt-3 flex flex-wrap gap-2">
        {snapshot.viewMode !== "replay" && <button type="button" className={`${buttonClass} border-[#806745] bg-[#292117]`} disabled={busy || !visible.context || !visible.readHealthy || !selection?.connected || (!visible.uncertainRequest && !hasEligibleRecords(visible.context))}
          onClick={() => { void (visible.uncertainRequest ? controller.retryUnconfirmed() : controller.submit(question.trim() || fallbackQuestion)); }}>
          {visible.phase === "submitting" ? "Submitting analysis…" : visible.phase === "waiting" ? "Analysis running…" : visible.uncertainRequest ? "Retry the same request" : kind === "cycle_explanation" ? "Generate cycle explanation" : "Generate session comparison"}
        </button>}
        <button type="button" className={buttonClass} disabled={!selection?.connected || visible.phase === "submitting"} onClick={() => { void controller.refresh(); }}>Refresh saved facts and reports</button>
        {visible.uncertainRequest && !busy && snapshot.viewMode !== "replay" && <button type="button" className={buttonClass} onClick={() => controller.abandonUnconfirmed()}>Discard unconfirmed request</button>}
      </div>
      {visible.uncertainRequest && !busy && snapshot.viewMode !== "replay" && <div className="mt-2 text-[11px] text-[#A7A39A]">
        <p>This request is retained in this browser session for an idempotent retry. Discarding it releases the selection for a new request; any job already accepted by the server remains in saved history.</p>
        <p className="mt-1 break-all">Request ID: <code>{visible.uncertainRequest.requestId}</code></p>
      </div>}
      {visible.context && !hasEligibleRecords(visible.context) && <p role="status" className="mt-2 text-[12px] text-[#A7A39A]">No data yet: no finished cycles or attempts are eligible for analysis.</p>}
      {!selection?.connected && <p role="status" className="mt-2 text-[12px] text-[#D6B775]">Records are disconnected or stale. Saved evidence may be shown; new analysis is unavailable.</p>}
      {visible.phase === "loading" && <p role="status" className="mt-2 text-[12px] text-[#A7A39A]">Loading saved facts and reports…</p>}
      {visible.phase === "submitting" && <p role="status" className="mt-2 text-[12px] text-[#A7A39A]">Saving the explicitly requested analysis job…</p>}
      {visible.error && <p role="alert" className="mt-3 text-[12px] text-[#D6B775]">{analysisErrorMessage(visible.error)} <span className="font-mono-tech text-[10px]">({visible.error.code})</span></p>}
      {visible.warnings.map((warning, index) => <p key={`${warning.code}:${index}`} role="alert" className="mt-3 text-[12px] text-[#D6B775]">{warning.message} <span className="font-mono-tech text-[10px]">({warning.code})</span></p>)}
      {snapshot.viewMode === "replay" && visible.phase !== "loading" && !visible.report && <p role="status" className="mt-3 text-[12px] text-[#A7A39A]">No saved report with a verified matching historical digest is available.</p>}
      {visible.reports.length > 0 && <label className="mt-3 block text-[11px] text-[#A7A39A]">Saved reports<select aria-label="Saved reports" className={`${fieldClass} mt-1`} value={visible.report?.reportId ?? ""} onChange={event => controller.chooseReport(event.target.value)}>
        {visible.reports.map(report => <option key={report.reportId} value={report.reportId}>{report.status} · {formatTimestamp(report.context.asOf)} · {report.reportId}</option>)}
      </select></label>}
      {facts && <RecordedFacts key={facts.contentDigest} context={facts} onOpenSource={onOpenSource} />}
      {visible.report && <AnalysisReportView key={`${visible.report.reportId}:${visible.report.context.contentDigest}`} report={visible.report} stale={stale} onOpenSource={onOpenSource} />}
      {stale && visible.context && visible.context.contentDigest !== visible.report?.context.contentDigest && <details className="mt-4 text-[12px] text-[#A7A39A]"><summary className="cursor-pointer">Current facts for explicit regeneration</summary><RecordedFacts context={visible.context} onOpenSource={onOpenSource} /></details>}
    </>}
  </section>;
}
