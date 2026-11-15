import React, { useEffect, useRef, useState } from "react";
import { CycleReviewForm } from "./CycleReviewForm.tsx";
import type { CycleDetail, CycleReviewRequest, CycleReviewResult } from "@morph/station-client";
import { EvidenceImage, formatTimestamp, DISPLAY_TIME_ZONE } from "./EvidenceImage.tsx";
import type {
  Attempt,
  Confirmation,
  Correction,
  Cycle,
  DecisionRecord,
  Frame,
  Inspection,
  NemotronObservation,
  ReferenceLabel,
  SkillExecution,
  ViewMode,
} from "../types/morph.ts";

interface CycleDetailDrawerProps {
  cycle: Cycle | null;
  viewMode: ViewMode;
  sessionName: string;
  attempts: Attempt[];
  inspections: Inspection[];
  frames: Frame[];
  nemotronObservations: NemotronObservation[];
  decisions: DecisionRecord[];
  skillExecutions: SkillExecution[];
  referenceLabel: ReferenceLabel | null;
  confirmation: Confirmation | null;
  confirmations: Confirmation[];
  corrections: Correction[];
  onClose: () => void;
  reviewAvailable: boolean;
  onSubmitReview: (cycleId: string, request: CycleReviewRequest) => Promise<CycleReviewResult>;
  onRefresh: () => Promise<CycleDetail>;
}

export const CycleDetailDrawer: React.FC<CycleDetailDrawerProps> = ({
  cycle,
  viewMode,
  sessionName,
  attempts,
  inspections,
  frames,
  nemotronObservations,
  decisions,
  skillExecutions,
  referenceLabel,
  confirmation, confirmations,
  corrections,
  onClose, reviewAvailable, onSubmitReview, onRefresh,
}) => {
  const [fullScreen, setFullScreen] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!cycle) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const dialog = dialogRef.current;
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>(
      'button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
    ) ?? []).filter((element) => element.getClientRects().length > 0);
    const focusFirst = () => (closeRef.current ?? focusable()[0] ?? dialog)?.focus();
    focusFirst();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onCloseRef.current(); }
      if (event.key !== "Tab") return;
      const items = focusable(), first = items[0], last = items.at(-1);
      if (document.activeElement && !dialog?.contains(document.activeElement)) { event.preventDefault(); focusFirst(); return; }
      if (!first) { event.preventDefault(); dialog?.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    const focusin = (event: FocusEvent) => {
      if (dialog && event.target instanceof Node && !dialog.contains(event.target)) focusFirst();
    };
    document.addEventListener("keydown", keydown);
    document.addEventListener("focusin", focusin);
    return () => {
      document.removeEventListener("keydown", keydown);
      document.removeEventListener("focusin", focusin);
      document.body.style.overflow = previousOverflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [cycle?.id]);

  if (!cycle) return null;

  const orderedAttempts = [...attempts].sort((a, b) => a.ordinal - b.ordinal);
  const extraInspectionsCount = inspections.filter(
    (i) => i.additionalInspectionOfId !== null
  ).length;
  const decisionIns =
    inspections.find((i) => i.id === cycle.inspectionId) ??
    inspections.find((i) => i.isDecisionInspection) ??
    inspections[inspections.length - 1] ??
    null;
  const primaryFrame =
    frames.find((f) => decisionIns?.frameIds.includes(f.id)) ??
    null;

  const isRecovered =
    cycle.outcome === "correct" &&
    attempts.length > 1 &&
    orderedAttempts.slice(0, -1).some((a) => a.outcome === "failed");

  const outcomeBadge = (outcome: Cycle["outcome"]) => {
    const map: Record<Cycle["outcome"], { cls: string; text: string }> = {
      correct: {
        cls: "text-[#91B99C] border-[#344b39] bg-[#152019]",
        text: "Confirmed correct",
      },
      failed: {
        cls: "text-[#E36363] border-[#603332] bg-[#281817]",
        text: "Failed",
      },
      aborted: {
        cls: "text-[#b8b4ab] border-[#33332f] bg-[#1c1c1a]",
        text: "Aborted",
      },
      unverified: {
        cls: "text-[#D6B775] border-[#514633] bg-[#211d16]",
        text: "Unverified",
      },
      in_progress: {
        cls: "text-[#C7A477] border-[#484137] bg-[#211c15]",
        text: "In progress",
      },
    };
    const item = map[outcome];
    return (
      <span
        className={`font-mono-tech inline-block rounded-[3px] border px-2 py-1 text-[9px] tracking-[0.05em] ${item.cls}`}
      >
        {item.text}
      </span>
    );
  };

  const trace: { id: string; time: string; title: string; detail: string; tone?: string }[] = [];
  for (const attempt of orderedAttempts) {
    trace.push({ id: `${attempt.id}:start`, time: attempt.startedAt, title: `Attempt ${attempt.id} (#${attempt.ordinal}) started`,
      detail: attempt.retryReason ? `Retry reason: ${attempt.retryReason}` : "Execution attempt recorded." });
    if (attempt.endedAt) trace.push({ id: `${attempt.id}:end`, time: attempt.endedAt,
      title: `Attempt ${attempt.id} · ${attempt.outcome}`, detail: attempt.errorCode ? `Error: ${attempt.errorCode}` : `Recorded outcome: ${attempt.outcome}`,
      tone: attempt.outcome === "successful" ? "text-[#91B99C]" : attempt.outcome === "failed" ? "text-[#E36363]" : "text-[#D6B775]" });
  }
  for (const inspection of inspections) trace.push({ id: inspection.id, time: inspection.completedAt,
    title: `Inspection ${inspection.id} · ${inspection.classification}`,
    detail: `Score ${inspection.score} / threshold ${inspection.threshold}; frames ${inspection.frameIds.join(", ")}.` });
  for (const observation of nemotronObservations) trace.push({ id: observation.id, time: observation.completedAt ?? observation.requestedAt,
    title: `${observation.modelId} · ${observation.status}`, detail: observation.observations.join(" ") || "No visual observation output recorded." });
  for (const decision of decisions) trace.push({ id: decision.id, time: decision.completedAt ?? decision.requestedAt,
    title: `${decision.modelId} → ${decision.selectedChoice ?? "No selection recorded"}`,
    detail: `State v${decision.stateVersion} / goal v${decision.goalVersion}. Validation: ${decision.validatorReason ?? "Unavailable"}` });
  for (const execution of skillExecutions) {
    if (execution.requestedAt) trace.push({ id: `${execution.id}:requested`, time: execution.requestedAt,
      title: `Execution requested · ${execution.taskId}`, detail: `Execution ${execution.id}; policy ${execution.policyId}. A request alone does not confirm a command was sent.` });
    if (execution.commandSentAt) trace.push({ id: `${execution.id}:sent`, time: execution.commandSentAt, title: `Command sent · ${execution.taskId}`,
      detail: `Execution ${execution.id}; policy ${execution.policyId}.` });
    if (execution.acknowledgedAt) trace.push({ id: `${execution.id}:ack`, time: execution.acknowledgedAt,
      title: `Command acknowledged · ${execution.id}`, detail: "Controller acknowledgment recorded." });
    if (execution.finishedAt) trace.push({ id: `${execution.id}:finished`, time: execution.finishedAt,
      title: `Execution finished · ${execution.id}`, detail: `Controller status: ${execution.controllerStatus}; physical outcome: ${execution.physicalOutcome}.` });
  }
  for (const observed of confirmations) trace.push({ id: observed.id, time: observed.confirmedAt,
    title: `Outcome confirmation · ${observed.source}${observed.attemptId ? ` · ${observed.attemptId}` : ''}`,
    detail: `Physical result: ${observed.physicalSuccess === true ? "confirmed successful" : observed.physicalSuccess === false ? "confirmed failed" : "unavailable"}. Observed destination: ${observed.observedDestination ?? "Unavailable"}. Author: ${observed.authorId ?? 'Not recorded'}. Evidence: ${observed.evidenceIds.join(", ") || "No attached artifact"}.` });
  if (cycle.endedAt) trace.push({ id: `${cycle.id}:ended`, time: cycle.endedAt,
    title: `Cycle ${cycle.outcome}${isRecovered ? " · recovered success" : ""}`, detail: "Persisted cycle outcome; earlier attempts remain in the record." });
  trace.sort((a, b) => Date.parse(a.time) - Date.parse(b.time) || a.id.localeCompare(b.id));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/82 p-4"
      ref={dialogRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cycle-detail-title"
    >
      <div
        className={`overflow-y-auto rounded-[12px] border border-[#453a2d] bg-[#121210] text-[#F2EEE6] shadow-2xl ${
          fullScreen
            ? "h-[96vh] w-[96vw] max-w-none"
            : "max-h-[94vh] w-full max-w-[720px]"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[#252421] px-7 py-6">
          <div>
            <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477] uppercase">
              {viewMode === "replay" ? "READ-ONLY REPLAY EVIDENCE" : viewMode === "simulation" ? "PERSISTED SIMULATION EVIDENCE" : "PERSISTED LIVE EVIDENCE"} /{" "}
              {sessionName.toUpperCase()} · REV {cycle.revision}
            </span>
            <h2
              id="cycle-detail-title"
              className="my-1.5 text-[30px] font-normal tracking-[-0.04em] text-[#F2EEE6]"
            >
              {cycle.id}{" "}
              <span className="text-[#A7A39A]">/ Duplo {cycle.objectId}</span>
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {outcomeBadge(cycle.outcome)}
              {isRecovered && (
                <span className="font-mono-tech inline-block rounded-[3px] border border-[#33332f] bg-[#1c1c1a] px-2 py-1 text-[9px] tracking-[0.05em] text-[#b8b4ab]">
                  RECOVERED SUCCESS
                </span>
              )}
              {cycle.outcome === "failed" &&
                referenceLabel?.quality === "defective" &&
                decisionIns?.classification === "good" && (
                  <span className="font-mono-tech inline-block rounded-[3px] border border-[#603332] bg-[#281817] px-2 py-1 text-[9px] tracking-[0.05em] text-[#E36363]">
                    DEFECT ESCAPE (WRONG BIN)
                  </span>
                )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFullScreen(!fullScreen)}
              className="rounded-[4px] border border-[#3e3b34] px-2.5 py-1 text-[11px] text-[#A7A39A] hover:bg-[#22201b] hover:text-[#F2EEE6]"
            >
              {fullScreen ? "Standard drawer" : "Full screen ↗"}
            </button>
            <button
              type="button"
              onClick={onClose}
              ref={closeRef}
              aria-label="Close cycle details"
              className="px-2 py-0.5 text-[26px] leading-none text-[#A7A39A] hover:text-[#F2EEE6]"
            >
              ×
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-7 py-6">
          {/* 6 Key Facts */}
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-[10px] text-[#A7A39A]">
                Physical attempts
              </label>
              <b className="font-mono-tech text-[12px] font-medium text-[#F2EEE6]">
                {attempts.length}
              </b>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-[#A7A39A]">
                Additional inspections
              </label>
              <b className="font-mono-tech text-[12px] font-medium text-[#F2EEE6]">
                {extraInspectionsCount}
              </b>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-[#A7A39A]">
                Full cycle
              </label>
              <b className="font-mono-tech text-[12px] font-medium text-[#F2EEE6]">
                {cycle.fullCycleDurationSec === null
                  ? cycle.outcome === "in_progress" ? "In progress" : "Unavailable"
                  : `${cycle.fullCycleDurationSec.toFixed(1)} s`}
              </b>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-[#A7A39A]">
                Reference quality
              </label>
              <b className="font-mono-tech text-[12px] font-medium text-[#F2EEE6]">
                {referenceLabel?.quality ?? "Not supplied"}
              </b>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-[#A7A39A]">
                Commanded destination
              </label>
              <b className="font-mono-tech text-[12px] font-medium text-[#F2EEE6]">
                {cycle.commandedDestination ?? "Not dispatched"}
              </b>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-[#A7A39A]">
                Observed destination
              </label>
              <b className="font-mono-tech text-[12px] font-medium text-[#F2EEE6]">
                {cycle.observedDestination ?? "Unverified"}
              </b>
            </div>
          </div>

          {/* Analyzed Frame & Inspection Snapshot */}
          {primaryFrame && (
            <div className="my-4 flex items-center gap-4 rounded-[6px] border border-[#252421] bg-[#101010] p-3.5">
              <div className="relative h-[75px] w-[85px] shrink-0 overflow-hidden rounded-[4px] border border-[#474132] bg-[#282b25]">
                <EvidenceImage src={primaryFrame.imageUrl} alt={`Analyzed snapshot ${primaryFrame.id} for object ${cycle.objectId}`} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="m-0 text-[12px] font-medium text-[#F2EEE6]">
                  Analyzed frame {primaryFrame.id}{" "}
                  {primaryFrame.stale && (
                    <span className="ml-2 text-[10px] text-[#D6B775]">
                      (Historical capture)
                    </span>
                  )}
                </p>
                <small className="font-mono-tech mt-1 block text-[10px] text-[#A7A39A]">
                  Captured {formatTimestamp(primaryFrame.capturedAt)} · {DISPLAY_TIME_ZONE}<br />
                  Anomaly score{" "}
                  {decisionIns ? decisionIns.score.toFixed(2) : "—"} / threshold{" "}
                  {decisionIns ? decisionIns.threshold.toFixed(2) : "Unavailable"} · Predicted:{" "}
                  {decisionIns?.classification ?? "unavailable"}
                  <br />
                  {referenceLabel
                    ? `Reference (${referenceLabel.quality}) supplied independently by ${referenceLabel.authorId}`
                    : "Independent reference label not yet supplied"}
                </small>
              </div>
            </div>
          )}

          {!primaryFrame && <p className="my-4 rounded-[6px] border border-[#252421] bg-[#101010] p-3.5 text-[11px] text-[#A7A39A]">Analyzed image unavailable — no linked frame was recorded.</p>}

          {frames.length > 1 && <details className="my-4 rounded border border-[#403729] p-3 text-[11px]">
            <summary className="cursor-pointer text-[#C7A477]">All recorded images ({frames.length})</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">{frames.map(frame=><figure key={frame.id} className="min-w-0">
              <div className="h-36 overflow-hidden rounded border border-[#403729]"><EvidenceImage src={frame.imageUrl} alt={`Recorded frame ${frame.id} for ${cycle.objectId}`}/></div>
              <figcaption className="mt-1 break-all">{frame.id} · {formatTimestamp(frame.capturedAt)} · {DISPLAY_TIME_ZONE}</figcaption>
            </figure>)}</div>
          </details>}

          {/* Ordered Execution Trace */}
          <div className="mt-6 mb-3 flex items-center justify-between text-[11px]">
            <span className="font-medium text-[#F2EEE6]">Execution trace</span>
            <span className="font-mono-tech text-[9px] text-[#A7A39A]">
              {DISPLAY_TIME_ZONE}
            </span>
          </div>

          <div className="border-b border-[#252421]">
            {trace.length === 0 && <p className="py-3 text-[11px] text-[#A7A39A]">No execution or inspection trace recorded.</p>}
            {trace.map((entry) => <div key={entry.id} className="grid grid-cols-[120px_1fr] gap-4 border-t border-[#252421] py-3">
              <time dateTime={entry.time} className="font-mono-tech text-[10px] text-[#A7A39A]">{formatTimestamp(entry.time)}</time>
              <div><b className={`text-[12px] font-medium ${entry.tone ?? "text-[#F2EEE6]"}`}>{entry.title}</b>
                <p className="mt-1 text-[11px] text-[#A7A39A]">{entry.detail}</p>
              </div>
            </div>)}
          </div>

          {/* Timing Breakdown */}
          <div className="mt-5 grid grid-cols-2 gap-3 rounded-[6px] border border-[#252421] bg-[#101010] p-3.5 text-[11px] sm:grid-cols-5">
            <div>
              <span className="block text-[9px] text-[#A7A39A]">Anomalib</span>
              <span className="font-mono-tech text-[#F2EEE6]">
                {cycle.timingBreakdown.anomalibMs !== null
                  ? `${cycle.timingBreakdown.anomalibMs} ms`
                  : "Unavailable"}
              </span>
            </div>
            <div>
              <span className="block text-[9px] text-[#A7A39A]">Nemotron VL</span>
              <span className="font-mono-tech text-[#F2EEE6]">
                {cycle.timingBreakdown.nemotronMs !== null
                  ? `${cycle.timingBreakdown.nemotronMs} ms`
                  : "Unavailable"}
              </span>
            </div>
            <div>
              <span className="block text-[9px] text-[#A7A39A]">Gemini Decision 1</span>
              <span className="font-mono-tech text-[#F2EEE6]">
                {cycle.timingBreakdown.geminiMs !== null
                  ? `${cycle.timingBreakdown.geminiMs} ms`
                  : "Unavailable"}
              </span>
            </div>
            <div>
              <span className="block text-[9px] text-[#A7A39A]">Motion</span>
              <span className="font-mono-tech text-[#F2EEE6]">
                {cycle.timingBreakdown.motionMs !== null
                  ? `${(cycle.timingBreakdown.motionMs / 1000).toFixed(1)} s`
                  : "Unavailable"}
              </span>
            </div>
            <div>
              <span className="block text-[9px] text-[#A7A39A]">Verification</span>
              <span className="font-mono-tech text-[#F2EEE6]">
                {cycle.timingBreakdown.verificationMs !== null
                  ? `${cycle.timingBreakdown.verificationMs} ms`
                  : "Unverified"}
              </span>
            </div>
          </div>

          {/* Audit Trail & Corrections */}
          <div className="mt-5 rounded-[5px] border border-[#403729] bg-[#1b1914] p-4 text-[11px] text-[#A7A39A]">
            <b className="text-[#F2EEE6]">Audit trail</b>
            {corrections.length > 0 ? (
              <div className="mt-2 space-y-2">
                {corrections.map((cor) => (
                  <div key={cor.id} className="border-t border-[#2f2920] pt-2">
                    <span className="font-mono-tech text-[10px] text-[#C7A477]">
                      {cor.entityType} {cor.entityId} / {cor.field}: {JSON.stringify(cor.previousValue)} → {JSON.stringify(cor.newValue)} ·{" "}
                      {cor.authorId} · {formatTimestamp(cor.createdAt)} · {DISPLAY_TIME_ZONE}
                    </span>
                    <div className="text-[11px] text-[#A7A39A]">Reason: {cor.reason}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-1 mb-0">
                No manual corrections recorded yet. Reference labels are independent of model
                predictions.
              </p>
            )}

            {viewMode === "replay" ? <p className="mt-4">Historical replay is read-only. Return to the record source to submit an audited review.</p> :
              <CycleReviewForm key={cycle.id} cycle={cycle} attempts={attempts} label={referenceLabel}
                evidenceIds={[...new Set(frames.map(frame => frame.evidenceId).filter((id): id is string => Boolean(id)))]}
                available={reviewAvailable} onSubmit={onSubmitReview} onRefresh={onRefresh}/>}

          </div>
        </div>
      </div>
    </div>
  );
};
