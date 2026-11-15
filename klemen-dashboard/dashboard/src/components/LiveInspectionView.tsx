import React, { useEffect, useState } from "react";
import {
  ArrowUpRight,
  ChevronDown,
  Clock3,
  FileText,
  Layers,
  ScanLine,
} from "lucide-react";
import {
  EvidenceImage,
  formatTimestamp,
  DISPLAY_TIME_ZONE,
} from "./EvidenceImage.tsx";
import {
  DataPair,
  EmptyEvidence,
  StatusPill,
  destinationLabel,
  readableLabel,
  type StatusTone,
} from "./DashboardPrimitives.tsx";
import type { SimulationPresetId, StationSnapshot } from "../types/morph.ts";
import { LiveVideoPanel } from "./LiveVideoPanel.tsx";

interface LiveInspectionViewProps {
  snapshot: StationSnapshot;
  selectedPreset: SimulationPresetId;
  onSelectPreset: (presetId: SimulationPresetId) => void;
  onOpenSimulation: () => void;
  onShowDisconnected: () => void;
  onOpenCycleTrace: (cycleId: string) => void;
  onNavigateQuality: () => void;
  onStartCycle: () => Promise<void>;
  onAdvanceCycle: (
    mode: "complete_success" | "extra_inspection" | "failed_grasp_retry",
  ) => Promise<void>;
  onStartNewSession: (name: string) => Promise<void>;
  onEndActiveSession: () => Promise<void>;
  onSubmitVoiceGoal: (params: {
    utteranceId: string;
    source: "scribe_v3_live" | "typed";
    text: string;
    queueForNextBoundary: boolean;
  }) => Promise<void>;
  onEnrichVoiceTimestamps: (utteranceId: string) => Promise<void>;
  onCommitQueuedGoal: () => Promise<void>;
}

const outcomeTone = (value?: string): StatusTone =>
  value === "correct" || value === "successful"
    ? "good"
    : value === "failed"
      ? "bad"
      : value === "unverified" || value === "aborted"
        ? "warn"
        : "neutral";
const latency = (value: number | null | undefined) =>
  value == null
    ? "Unavailable"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms`;

export const LiveInspectionView: React.FC<LiveInspectionViewProps> = ({
  snapshot,
  onOpenSimulation,
  onOpenCycleTrace,
  onNavigateQuality,
}) => {
  const [heatmapOn, setHeatmapOn] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState(false);
  const currentCycle = snapshot.activeCycle;
  const m = snapshot.metrics;
  const isReplay = snapshot.viewMode === "replay";
  const stale = snapshot.dataStale || snapshot.dataConnection !== "connected";
  const inspections = snapshot.inspections
    .filter((i) => i.cycleId === currentCycle?.id)
    .sort((a, b) => Date.parse(a.completedAt) - Date.parse(b.completedAt));
  const inspection =
    inspections.find((i) => i.id === currentCycle?.inspectionId) ??
    inspections.find((i) => i.isDecisionInspection) ??
    inspections.at(-1) ??
    null;
  useEffect(() => setHeatmapOn(false), [inspection?.id]);
  const attempts = snapshot.attempts
    .filter((a) => a.cycleId === currentCycle?.id)
    .sort((a, b) => a.ordinal - b.ordinal);
  const attempt = attempts.at(-1);
  const frame = snapshot.frames.find(
    (f) =>
      f.cycleId === currentCycle?.id && inspection?.frameIds.includes(f.id),
  );
  const observation = snapshot.nemotronObservations
    .filter((n) => n.cycleId === currentCycle?.id)
    .sort((a, b) => Date.parse(b.requestedAt) - Date.parse(a.requestedAt))[0];
  const decision = snapshot.decisions
    .filter(
      (d) => d.cycleId === currentCycle?.id && d.kind === "task_selection",
    )
    .sort((a, b) => Date.parse(b.requestedAt) - Date.parse(a.requestedAt))[0];
  const execution = snapshot.skillExecutions
    .filter(
      (e) => e.cycleId === currentCycle?.id && e.attemptId === attempt?.id,
    )
    .sort(
      (a, b) =>
        Date.parse(b.requestedAt ?? b.commandSentAt ?? "") -
        Date.parse(a.requestedAt ?? a.commandSentAt ?? ""),
    )[0];
  const reference = snapshot.referenceLabels.find(
    (r) => r.id === currentCycle?.referenceLabelId,
  );
  const confirmation = snapshot.confirmations.find(
    (c) => c.id === currentCycle?.confirmationId,
  );
  const runs = (snapshot.modelRuns ?? []).filter(
    (r) => r.cycleId === currentCycle?.id,
  );
  const inspectionRun = runs.find((r) => r.id === inspection?.modelRunId);
  const utterance = snapshot.utterances
    .filter((u) => u.finalizedText)
    .sort(
      (a, b) =>
        Date.parse(b.finalizedAt ?? b.createdAt) -
        Date.parse(a.finalizedAt ?? a.createdAt),
    )[0];
  const confirmationText =
    confirmation?.physicalSuccess === true
      ? "Physical result confirmed"
      : confirmation?.physicalSuccess === false
        ? "Physical result not achieved"
        : currentCycle
          ? "Awaiting confirmation"
          : "No confirmation recorded";
  const imageSrc =
    heatmapOn && inspection?.mapEvidenceId
      ? `/api/v1/evidence/${encodeURIComponent(inspection.mapEvidenceId)}`
      : frame?.imageUrl;

  return (
    <div className="inspection-view">
      <div className="view-heading">
        <div>
          <span className="eyebrow">01 / INSPECTION WORKSPACE</span>
          <h1>
            Live inspection<span className="heading-period">.</span>
          </h1>
          <p>Follow the object from observation to a confirmed result.</p>
        </div>
        <button
          type="button"
          className="quiet-button"
          onClick={onNavigateQuality}
        >
          Quality &amp; history <ArrowUpRight size={15} />
        </button>
      </div>

      <div className="inspection-context">
        <div className="inspection-context-main">
          <StatusPill tone={isReplay ? "bronze" : stale ? "warn" : "good"} dot>
            {isReplay
              ? "Frozen replay"
              : stale
                ? "Records not current"
                : "Records connected"}
          </StatusPill>
          <span>
            {snapshot.selectedSessionId ? "Selected session" : "Latest session"}
            {" · "}{snapshot.activeSession?.name ?? "No session received"}
          </span>
        </div>
        <span className="timestamp-label">
          Last received {formatTimestamp(snapshot.receivedAt)} ·{" "}
          {DISPLAY_TIME_ZONE}
        </span>
      </div>

      {!isReplay && (
        <LiveVideoPanel
          sourceMode={
            snapshot.sourceMode ??
            (snapshot.viewMode === "simulation" ? "simulation" : "live")
          }
          selectedSessionName={snapshot.selectedSessionId
            ? snapshot.activeSession?.name ?? snapshot.selectedSessionId
            : null}
        />
      )}

      <div className="inspection-workbench">
        <section
          className="dashboard-panel evidence-panel"
          aria-label="Analyzed snapshot"
        >
          <div className="panel-heading">
            <div className="panel-title">
              <ScanLine size={16} />
              <h2>Analyzed snapshot</h2>
            </div>
            <StatusPill>Saved evidence</StatusPill>
          </div>
          <div
            className={`inspection-image${imageSrc ? "" : " inspection-image--empty"}`}
          >
            {imageSrc ? (
              <EvidenceImage
                src={imageSrc}
                alt={
                  heatmapOn && inspection?.mapEvidenceId
                    ? `Recorded anomaly map for inspection ${inspection.id}`
                    : `Analyzed frame ${frame?.id ?? "unavailable"} for object ${currentCycle?.objectId ?? "unavailable"}`
                }
              />
            ) : (
              <EmptyEvidence
                title="Waiting for analyzed evidence"
                detail="The inspection image will appear when the station records a frame for this object."
              />
            )}
            <div
              className="evidence-corner evidence-corner--tl"
              aria-hidden="true"
            />
            <div
              className="evidence-corner evidence-corner--tr"
              aria-hidden="true"
            />
            <div
              className="evidence-corner evidence-corner--bl"
              aria-hidden="true"
            />
            <div
              className="evidence-corner evidence-corner--br"
              aria-hidden="true"
            />
          </div>
          <div className="evidence-toolbar">
            <span>
              <span className="status-dot" aria-hidden="true" />
              Frozen capture · exact analyzed evidence
            </span>
            <div
              className="segmented-control"
              role="group"
              aria-label="Evidence image layer"
            >
              <button
                type="button"
                aria-pressed={!heatmapOn}
                onClick={() => setHeatmapOn(false)}
              >
                Image
              </button>
              <button
                type="button"
                aria-pressed={heatmapOn}
                disabled={!inspection?.mapEvidenceId}
                onClick={() => setHeatmapOn(true)}
              >
                Anomaly map
              </button>
            </div>
          </div>
          <dl className="frame-metadata">
            <DataPair label="Frame" mono>
              {frame?.id ?? "Not recorded"}
            </DataPair>
            <DataPair label="Camera" mono>
              {frame?.cameraId ?? "Unavailable"}
            </DataPair>
            <DataPair label="Captured">
              {formatTimestamp(frame?.capturedAt)}
              {frame && (
                <span className="muted-inline">
                  {" "}
                  · {frame.stale ? "Historical capture" : "Frozen capture"}
                </span>
              )}
            </DataPair>
          </dl>
        </section>

        <section
          className="dashboard-panel object-panel"
          aria-label="Current object and outcome"
        >
          <div className="panel-heading">
            <div className="panel-title">
              <Layers size={16} />
              <h2>Current object</h2>
            </div>
            <StatusPill tone={outcomeTone(currentCycle?.outcome)}>
              {readableLabel(currentCycle?.outcome, "No cycle")}
            </StatusPill>
          </div>
          {currentCycle ? (
            <div className="object-panel-body">
              <span className="eyebrow">OBJECT ID</span>
              <h2 className="object-identity">{currentCycle.objectId}</h2>
              <div className="object-cycle-id">
                Cycle <span>{currentCycle.id}</span> · revision{" "}
                {currentCycle.revision}
              </div>
              <div className="inspection-verdict">
                <span className="field-label">Inspection classification</span>
                <strong
                  className={
                    inspection?.classification === "defective"
                      ? "text-bad"
                      : inspection?.classification === "good"
                        ? "text-good"
                        : ""
                  }
                >
                  {readableLabel(
                    inspection?.classification,
                    "Not yet classified",
                  )}
                </strong>
                <div className="inspection-score">
                  <span>
                    Anomaly score{" "}
                    <b>{inspection ? inspection.score.toFixed(3) : "—"}</b>
                  </span>
                  <span>
                    Threshold{" "}
                    <b>{inspection ? inspection.threshold.toFixed(3) : "—"}</b>
                  </span>
                </div>
              </div>
              <dl className="object-facts">
                <DataPair label="Commanded destination">
                  {destinationLabel(currentCycle.commandedDestination)}
                </DataPair>
                <DataPair label="Observed destination">
                  {destinationLabel(currentCycle.observedDestination)}
                </DataPair>
                <DataPair label="Independent reference">
                  {reference
                    ? readableLabel(reference.quality)
                    : "Not yet labeled"}
                </DataPair>
                <DataPair label="Physical confirmation">
                  {confirmation
                    ? `${readableLabel(confirmation.source)} · ${confirmation.physicalSuccess === true ? "success" : confirmation.physicalSuccess === false ? "not achieved" : "unverified"}`
                    : "Not verified"}
                </DataPair>
                <DataPair label="Attempts / inspections">
                  {currentCycle.detailsLoaded === false
                    ? "Not loaded"
                    : `${attempts.length} / ${inspections.length}`}
                </DataPair>
              </dl>
              <button
                type="button"
                className="primary-outline-button object-trace-button"
                onClick={() => onOpenCycleTrace(currentCycle.id)}
              >
                Open evidence &amp; audit trail <ArrowUpRight size={15} />
              </button>
            </div>
          ) : (
            <div className="object-panel-body object-panel-body--empty">
              <span className="eyebrow">READY FOR RECORDS</span>
              <h2>No object recorded yet.</h2>
              <p>
                Select a session with recorded cycles to inspect its image,
                classification and outcome.
              </p>
              <dl className="object-facts">
                <DataPair label="Robot control">
                  Unavailable in this view
                </DataPair>
                <DataPair label="Source">
                  {snapshot.viewMode === "simulation"
                    ? "Persisted simulation"
                    : isReplay
                      ? "Saved replay"
                      : "Intel station records"}
                </DataPair>
              </dl>
              {snapshot.viewMode === "live" && (
                <button
                  type="button"
                  className="primary-outline-button"
                  onClick={onOpenSimulation}
                >
                  View persisted simulation <ArrowUpRight size={15} />
                </button>
              )}
            </div>
          )}
        </section>
      </div>

      <div className="section-intro">
        <div>
          <span className="eyebrow">OBJECT EVIDENCE</span>
          <h2>What happened, step by step.</h2>
        </div>
        <span className="section-note">
          Recorded phase:{" "}
          {readableLabel(currentCycle?.activePhase, "unavailable")}
        </span>
      </div>
      <section
        className="evidence-chain"
        aria-label="Recorded inspection, decision, execution and confirmation"
      >
        <article className="evidence-step">
          <div className="evidence-step-top">
            <span className="step-number">01</span>
            <span className="eyebrow">INSPECTION</span>
          </div>
          <h3>
            {inspection
              ? readableLabel(inspection.classification)
              : "No inspection recorded"}
          </h3>
          <p>{inspectionRun?.modelId ?? "Inspection model unavailable"}</p>
          <dl>
            <DataPair label="Completed">
              {formatTimestamp(inspection?.completedAt, false)}
            </DataPair>
            <DataPair label="Inference">
              {latency(inspectionRun?.latencyMs)}
            </DataPair>
          </dl>
        </article>
        <article className="evidence-step">
          <div className="evidence-step-top">
            <span className="step-number">02</span>
            <span className="eyebrow">TASK DECISION</span>
          </div>
          <h3>
            {readableLabel(
              decision?.selectedChoice,
              "No task decision recorded",
            )}
          </h3>
          <p>{decision?.modelId ?? "Decision model unavailable"}</p>
          <dl>
            <DataPair label="Validation">
              {decision?.validatorAccepted === true
                ? "Accepted"
                : decision?.validatorAccepted === false
                  ? "Rejected"
                  : "Not recorded"}
            </DataPair>
            <DataPair label="Completed">
              {formatTimestamp(decision?.completedAt, false)}
            </DataPair>
          </dl>
          {decision?.validatorReason && (
            <p className="step-note">{decision.validatorReason}</p>
          )}
        </article>
        <article className="evidence-step">
          <div className="evidence-step-top">
            <span className="step-number">03</span>
            <span className="eyebrow">EXECUTION</span>
          </div>
          <h3>
            {readableLabel(
              execution?.controllerStatus,
              "No execution recorded",
            )}
          </h3>
          <p>{execution?.policyId ?? "Learned policy unavailable"}</p>
          <dl>
            <DataPair label="Acknowledged">
              {formatTimestamp(execution?.acknowledgedAt, false)}
            </DataPair>
            <DataPair label="Finished">
              {formatTimestamp(execution?.finishedAt, false)}
            </DataPair>
          </dl>
          <p className="step-note">
            Controller completion is recorded separately from physical
            confirmation.
          </p>
        </article>
        <article
          className={`evidence-step evidence-step--outcome ${confirmation?.physicalSuccess === true ? "evidence-step--confirmed" : ""}`}
        >
          <div className="evidence-step-top">
            <span className="step-number">04</span>
            <span className="eyebrow">CONFIRMATION</span>
          </div>
          <h3>{confirmationText}</h3>
          <p>
            {confirmation
              ? `Source: ${confirmation.source}${confirmation.authorId ? ` · ${confirmation.authorId}` : ""}`
              : "Requires camera, sensor or operator evidence."}
          </p>
          <dl>
            <DataPair label="Observed">
              {destinationLabel(confirmation?.observedDestination)}
            </DataPair>
            <DataPair label="Confirmed at">
              {formatTimestamp(confirmation?.confirmedAt, false)}
            </DataPair>
          </dl>
        </article>
      </section>

      <div className="section-intro">
        <div>
          <span className="eyebrow">SESSION PERFORMANCE</span>
          <h2>Every attempt counts.</h2>
        </div>
        <StatusPill
          tone={snapshot.viewMode === "simulation" ? "bronze" : "neutral"}
        >
          {snapshot.viewMode === "simulation"
            ? "Simulation records"
            : isReplay
              ? "Saved session totals"
              : stale
                ? "Last received totals"
                : "Persisted session totals"}
        </StatusPill>
      </div>
      <section
        className="performance-grid"
        aria-label="Session reliability metrics"
      >
        <div className="performance-metric">
          <span className="field-label">Confirmed correct cycles</span>
          <strong>
            {m.confirmedCorrectCycles.value == null ? (
              "—"
            ) : (
              <>
                {m.confirmedCorrectCycles.value.toFixed(1)}
                <small>%</small>
              </>
            )}
          </strong>
          <p>
            {m.confirmedCorrectCycles.denominator
              ? `${m.confirmedCorrectCycles.numerator} correct / ${m.confirmedCorrectCycles.denominator} finished cycles`
              : "No data yet"}
          </p>
        </div>
        <div className="performance-metric">
          <span className="field-label">Successful physical attempts</span>
          <strong>
            {m.physicalExecution.value == null ? (
              "—"
            ) : (
              <>
                {m.physicalExecution.value.toFixed(1)}
                <small>%</small>
              </>
            )}
          </strong>
          <p>
            {m.physicalExecution.denominator
              ? `${m.physicalExecution.numerator} successful / ${m.physicalExecution.denominator} finished attempts`
              : "No data yet"}
          </p>
        </div>
        <div className="performance-metric">
          <span className="field-label">Detection quality</span>
          <strong>
            {m.detectionAccuracy.value == null ? (
              "—"
            ) : (
              <>
                {m.detectionAccuracy.value.toFixed(1)}
                <small>%</small>
              </>
            )}
          </strong>
          <p>
            {m.detectionAccuracy.denominator
              ? `${m.detectionAccuracy.numerator} correct / ${m.detectionAccuracy.denominator} checked`
              : "No reference-labeled data yet"}
            <span className="metric-population">
              {m.sessionId
                ? `${m.detectionAccuracy.totalPopulation} objects total`
                : "Population unavailable"}
            </span>
          </p>
        </div>
        <div className="performance-metric">
          <span className="field-label">Median full cycle</span>
          <strong>
            {m.medianFullCycleSec.value == null ? (
              "—"
            ) : (
              <>
                {m.medianFullCycleSec.value.toFixed(1)}
                <small>s</small>
              </>
            )}
          </strong>
          <p>
            {m.medianFullCycleSec.sampleCount
              ? `${m.medianFullCycleSec.sampleCount} finished cycles · includes cloud waits`
              : "No data yet"}
          </p>
        </div>
      </section>
      <div className="outcome-ledger">
        {m.sessionId ? (
          <>
            <div>
              <span className="field-label">Cycle outcomes</span>
              <span>
                <b>{m.cycleCounts.correct}</b> correct
              </span>
              <span>
                <b>{m.cycleCounts.failed}</b> failed
              </span>
              <span>
                <b>{m.cycleCounts.aborted}</b> aborted
              </span>
              <span>
                <b>{m.cycleCounts.unverified}</b> unverified
              </span>
              <span>
                <b>{m.cycleCounts.inProgress}</b> in progress
              </span>
            </div>
            <div>
              <span className="field-label">Attempt outcomes</span>
              <span>
                <b>{m.attemptCounts.successful}</b> successful
              </span>
              <span>
                <b>{m.attemptCounts.failed}</b> failed
              </span>
              <span>
                <b>{m.attemptCounts.aborted}</b> aborted
              </span>
              <span>
                <b>{m.attemptCounts.unverified}</b> unverified
              </span>
              <span>
                <b>{m.attemptCounts.inProgress}</b> in progress
              </span>
            </div>
            <div>
              <span className="field-label">Recovery &amp; repetition</span>
              <span>
                <b>{m.cycleCounts.firstAttemptSuccesses}</b> first attempt
              </span>
              <span>
                <b>{m.cycleCounts.recoveredCycles}</b> recovered
              </span>
              <span>
                <b>{m.attemptCounts.retries}</b> retries
              </span>
              <span>
                <b>{m.cycleCounts.extraInspections}</b> additional inspections
              </span>
              <span>
                Streak <b>{m.streak.hasData ? m.streak.current : "—"}</b> · best{" "}
                <b>{m.streak.hasData ? m.streak.best : "—"}</b>
              </span>
            </div>
          </>
        ) : (
          <div>No session outcome counts received yet.</div>
        )}
      </div>

      <div className="supporting-evidence-grid">
        <section className="dashboard-panel">
          <div className="panel-heading">
            <div className="panel-title">
              <FileText size={15} />
              <h2>Recorded model observation</h2>
            </div>
            <StatusPill>Model output</StatusPill>
          </div>
          <div className="supporting-panel-body">
            <p className="model-observation">
              {observation?.observations[0] ??
                "No visual model observation recorded for this object."}
            </p>
            <span className="timestamp-label">
              {observation
                ? `${observation.modelId} · ${observation.frameIds.length} linked frames`
                : "Frame-linked observations will appear here."}
            </span>
            {observation?.uncertainty && (
              <p className="step-note">
                Recorded uncertainty: {observation.uncertainty}
              </p>
            )}
            <button
              type="button"
              className="text-action"
              aria-expanded={expandedEvidence}
              onClick={() => setExpandedEvidence(!expandedEvidence)}
            >
              {expandedEvidence
                ? "Hide model payloads"
                : "Inspect model payloads"}
              <ChevronDown
                size={14}
                className={expandedEvidence ? "rotate-180" : ""}
              />
            </button>
          </div>
        </section>
        <section className="dashboard-panel">
          <div className="panel-heading">
            <div className="panel-title">
              <Clock3 size={15} />
              <h2>Timing for this object</h2>
            </div>
          </div>
          <dl className="supporting-panel-body timing-facts">
            <DataPair label="Full cycle">
              {currentCycle?.fullCycleDurationSec == null
                ? "Unavailable"
                : `${currentCycle.fullCycleDurationSec.toFixed(2)} s`}
            </DataPair>
            <DataPair label="Inspection inference">
              {latency(currentCycle?.timingBreakdown.anomalibMs)}
            </DataPair>
            <DataPair label="Nemotron / Gemini">
              {latency(currentCycle?.timingBreakdown.nemotronMs)} /{" "}
              {latency(currentCycle?.timingBreakdown.geminiMs)}
            </DataPair>
            <DataPair label="Motion / verification">
              {latency(currentCycle?.timingBreakdown.motionMs)} /{" "}
              {latency(currentCycle?.timingBreakdown.verificationMs)}
            </DataPair>
          </dl>
        </section>
      </div>

      {expandedEvidence && (
        <section className="dashboard-panel model-payloads">
          <div className="panel-heading">
            <h2>Exact recorded inputs &amp; outputs</h2>
            <span className="timestamp-label">{runs.length} model runs</span>
          </div>
          {runs.length === 0 ? (
            <p className="supporting-panel-body">
              No model payloads recorded for this cycle.
            </p>
          ) : (
            runs.map((run) => (
              <details key={run.id}>
                <summary>
                  <span>
                    {run.provider} / {run.modelId}
                  </span>
                  <span className="timestamp-label">
                    {latency(run.latencyMs)} ·{" "}
                    {run.error
                      ? "Error recorded"
                      : run.completedAt
                        ? "Completed"
                        : "Waiting"}
                  </span>
                </summary>
                <div className="payload-meta">
                  {run.id} · frames: {run.frameIds.join(", ") || "None"}
                  <br />
                  Requested: {formatTimestamp(run.requestedAt)} ·{" "}
                  {DISPLAY_TIME_ZONE}
                </div>
                <pre>
                  {JSON.stringify(
                    { input: run.input, output: run.output, error: run.error },
                    null,
                    2,
                  )}
                </pre>
              </details>
            ))
          )}
        </section>
      )}

      <section className="dashboard-panel recent-activity">
        <div className="panel-heading">
          <h2>Recent recorded activity</h2>
          <button
            type="button"
            className="text-action"
            onClick={onNavigateQuality}
          >
            Full history <ArrowUpRight size={14} />
          </button>
        </div>
        {snapshot.recentEvents.length ? (
          <div className="activity-list">
            {snapshot.recentEvents.slice(0, 4).map((event) => (
              <div key={event.eventId} className="activity-row">
                <span
                  className={`activity-dot activity-dot--${event.statusTone}`}
                  aria-hidden="true"
                />
                <time className="font-mono-tech" dateTime={event.occurredAt}>
                  {formatTimestamp(event.occurredAt, false)}
                </time>
                <span className="activity-summary">{event.summary}</span>
                {event.cycleId && (
                  <button
                    type="button"
                    className="text-action"
                    aria-label={`Open cycle ${event.cycleId}`}
                    onClick={() => onOpenCycleTrace(event.cycleId!)}
                  >
                    <ArrowUpRight size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="supporting-panel-body muted-inline">
            No persisted activity received yet.
          </p>
        )}
      </section>
      <div className="operator-record">
        <FileText size={15} />
        <div>
          <span className="eyebrow">RECORDED OPERATOR INPUT</span>
          <p>
            {utterance?.finalizedText ??
              "No finalized operator input recorded."}
          </p>
        </div>
        <span className="timestamp-label">
          Active goal:{" "}
          {snapshot.goalState.activeGoal
            ? snapshot.goalState.activeGoalLabel
            : "unavailable"}
        </span>
      </div>
    </div>
  );
};
