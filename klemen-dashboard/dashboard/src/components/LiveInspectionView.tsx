import React, { useState } from "react";
import { EvidenceImage, formatTimestamp, DISPLAY_TIME_ZONE } from "./EvidenceImage.tsx";
import type {
  CanonicalPhase,
  Cycle,
  SimulationPresetId,
  StationSnapshot,
} from "../types/morph.ts";

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
    mode: "complete_success" | "extra_inspection" | "failed_grasp_retry"
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

const CANONICAL_STAGE_LIST: { id: CanonicalPhase; label: string }[] = [
  { id: "observe", label: "Observe" },
  { id: "pick", label: "Pick" },
  { id: "verify_grasp", label: "Verify grasp" },
  { id: "present", label: "Present" },
  { id: "inspect", label: "Inspect" },
  { id: "choose_task", label: "Choose task" },
  { id: "place", label: "Place" },
  { id: "verify_outcome", label: "Verify outcome" },
];

export const LiveInspectionView: React.FC<LiveInspectionViewProps> = ({
  snapshot,
  onOpenSimulation,
  onOpenCycleTrace,
  onNavigateQuality,
}) => {
  const [heatmapOn, setHeatmapOn] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState(false);
  const isReplay = snapshot.viewMode === "replay";
  const m = snapshot.metrics;

  // Active Object & Evidence derivation
  const currentCycle: Cycle | null = snapshot.activeCycle;
  const cycInspections = currentCycle
    ? snapshot.inspections.filter((i) => i.cycleId === currentCycle.id).sort((a, b) => Date.parse(a.completedAt) - Date.parse(b.completedAt))
    : [];
  const latestInspection =
    cycInspections.find((i) => i.id === currentCycle?.inspectionId) ??
    cycInspections.find((i) => i.isDecisionInspection) ??
    cycInspections[cycInspections.length - 1] ??
    null;
  const cycAttempts = currentCycle
    ? snapshot.attempts.filter((a) => a.cycleId === currentCycle.id).sort((a, b) => a.ordinal - b.ordinal)
    : [];
  const latestAttempt = cycAttempts[cycAttempts.length - 1] ?? null;
  const cycFrames = currentCycle
    ? snapshot.frames.filter((f) => f.cycleId === currentCycle.id).sort((a, b) => Date.parse(a.capturedAt) - Date.parse(b.capturedAt))
    : [];
  const analyzedFrame =
    cycFrames.find((f) => latestInspection?.frameIds.includes(f.id)) ??
    null;
  const cycNemotron = currentCycle
    ? snapshot.nemotronObservations.filter((n) => n.cycleId === currentCycle.id).sort((a, b) => Date.parse(b.requestedAt) - Date.parse(a.requestedAt))[0] ?? null
    : null;
  const cycDecision = currentCycle
    ? snapshot.decisions.filter((d) => d.cycleId === currentCycle.id).sort((a, b) => Date.parse(b.requestedAt) - Date.parse(a.requestedAt))[0] ?? null
    : null;
  const cycExecution = latestAttempt
    ? snapshot.skillExecutions.find((e) =>
        latestAttempt.executionIds.includes(e.id)
      ) ?? null
    : null;
  const cycRefLabel = currentCycle
    ? snapshot.referenceLabels.find((r) => r.id === currentCycle.referenceLabelId) ?? null
    : null;
  const latestUtterance =
    snapshot.utterances[snapshot.utterances.length - 1] ?? null;

  const activeStageIndex = currentCycle
    ? CANONICAL_STAGE_LIST.findIndex((s) => s.id === currentCycle.activePhase)
    : -1;

  return (
    <div>
      {/* Page Heading */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            01 / MORPH CONTROL ROOM
          </span>
          <h1 className="my-2 text-[30px] font-[450] leading-[1.15] tracking-[-0.055em] text-[#F2EEE6]">
            Live inspection
          </h1>
          <p className="m-0 text-[12px] text-[#A7A39A]">
            One object. Every observation, decision and outcome.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {snapshot.viewMode === "live" && <button type="button" onClick={onOpenSimulation}
            className="min-h-[32px] rounded-[5px] border border-[#3e3b34] px-3 py-1.5 text-[11px] text-[#F2EEE6] hover:bg-[#22201b]">
            View persisted simulation
          </button>}
          <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] bg-[#211c15] px-2 py-1 text-[9px] tracking-[0.05em] text-[#C7A477]">
            {isReplay ? "READ-ONLY REPLAY" : snapshot.sourceMode === "simulation" ? "PERSISTED SIMULATION" : "LIVE RECORDS"}
          </span>
        </div>
      </div>

      {/* Active Fault / Exception Banner */}
      {snapshot.activeFaultBanner && (
        <div
          role="status"
          className="mb-5 flex items-center justify-between gap-4 rounded-[6px] border border-[#603332] bg-[#231614] px-4 py-3 text-[12px] text-[#F2EEE6]"
        >
          <div>
            <span className="font-mono-tech mr-2 text-[10px] text-[#E36363] uppercase">
              ACTIVE STATION EXCEPTION:
            </span>
            <span>{snapshot.activeFaultBanner}</span>
          </div>
          {currentCycle && (
            <button
              type="button"
              onClick={() => onOpenCycleTrace(currentCycle.id)}
              className="shrink-0 rounded-[4px] border border-[#603332] px-2.5 py-1 text-[11px] text-[#E36363] hover:bg-[#2b1816]"
            >
              Inspect {currentCycle.id} trace ↗
            </button>
          )}
        </div>
      )}

      <div role="status" className="mb-5 rounded-[5px] border border-[#403c32] bg-[#15140f] px-4 py-3 text-[11px] text-[#A7A39A]">
        Records API: {snapshot.dataConnection} · {snapshot.dataStale ? "Saved values may be stale" : "Records current"}.
        {" "}Physical robot, live video and task controls are unavailable.
        <span className="mt-1 block font-mono-tech text-[9px]">Last refresh: {formatTimestamp(snapshot.receivedAt)} · {DISPLAY_TIME_ZONE}</span>
      </div>

      {/* 4 Concise Metric Summaries */}
      <div className="mb-6 grid grid-cols-2 border-y border-[#252421] py-5 lg:grid-cols-4">
        <div className="border-r border-[#252421] pr-6">
          <div className="text-[11px] text-[#A7A39A]">Confirmed correct cycles</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.confirmedCorrectCycles.value !== null ? (
              <>
                {m.confirmedCorrectCycles.value.toFixed(1)}
                <span className="ml-1 text-[18px] text-[#A7A39A]">%</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.confirmedCorrectCycles.denominator > 0
              ? `${m.confirmedCorrectCycles.numerator} correct / ${m.confirmedCorrectCycles.denominator} finished cycles`
              : "No data yet"}
          </div>
        </div>

        <div className="border-r-0 px-6 lg:border-r lg:border-[#252421]">
          <div className="text-[11px] text-[#A7A39A]">Physical execution</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.physicalExecution.value !== null ? (
              <>
                {m.physicalExecution.value.toFixed(1)}
                <span className="ml-1 text-[18px] text-[#A7A39A]">%</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.physicalExecution.denominator > 0
              ? `${m.physicalExecution.numerator} successful / ${m.physicalExecution.denominator} finished attempts`
              : "No data yet"}
          </div>
        </div>

        <div className="mt-4 border-r border-[#252421] pr-6 lg:mt-0 lg:px-6">
          <div className="text-[11px] text-[#A7A39A]">Confirmed success streak</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.streak.hasData ? (
              <>
                {m.streak.current}{" "}
                <span className="text-[18px] text-[#A7A39A]">cycles</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.streak.hasData
              ? `Current ${m.streak.current} / session best ${m.streak.best}`
              : "No data yet"}
          </div>
        </div>

        <div className="mt-4 pl-6 lg:mt-0">
          <div className="text-[11px] text-[#A7A39A]">Median full cycle</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.medianFullCycleSec.value !== null ? (
              <>
                {m.medianFullCycleSec.value.toFixed(1)}{" "}
                <span className="text-[18px] text-[#A7A39A]">s</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.medianFullCycleSec.sampleCount > 0
              ? `${m.medianFullCycleSec.sampleCount} finished cycles · includes cloud waits`
              : "No data yet"}
          </div>
        </div>
      </div>

      {/* Main Live Grid: Camera (1.85fr) + Current Object (1fr) */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.85fr)_minmax(310px,1fr)]">
        {/* Persisted analyzed evidence remains separate from unavailable live video. */}
        <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
          <div className="flex min-h-[56px] flex-wrap items-center justify-between gap-3 border-b border-[#252421] px-4.5 py-3">
            <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">Analyzed snapshot</h2>
            <button type="button" disabled={!latestInspection?.mapEvidenceId} aria-pressed={heatmapOn && Boolean(latestInspection?.mapEvidenceId)}
              onClick={() => setHeatmapOn(!heatmapOn)} className="rounded-[3px] px-2.5 py-1 text-[10px] text-[#A7A39A] disabled:opacity-40">
              Anomaly map {latestInspection?.mapEvidenceId ? (heatmapOn ? "on" : "off") : "unavailable"}
            </button>
          </div>
          <div className="relative h-[300px] overflow-hidden bg-[#161915]">
            <EvidenceImage
              src={heatmapOn && latestInspection?.mapEvidenceId ? `/api/v1/evidence/${encodeURIComponent(latestInspection.mapEvidenceId)}` : analyzedFrame?.imageUrl}
              alt={heatmapOn && latestInspection?.mapEvidenceId ? `Recorded anomaly map for inspection ${latestInspection.id}` : `Analyzed frame ${analyzedFrame?.id ?? "unavailable"} for object ${currentCycle?.objectId ?? "unavailable"}`}
            />
            {analyzedFrame && <span className="font-mono-tech absolute top-4 left-4.5 border border-[#58604c] bg-[#10150fde] px-2.5 py-1.5 text-[9px] text-[#cbd1c2]">
              {snapshot.sourceMode === "simulation" ? "PERSISTED SIMULATION IMAGE" : "CAPTURED EVIDENCE"}
            </span>}
          </div>
          <div className="space-y-1 px-4.5 py-3 text-[11px] text-[#A7A39A]">
            <p className="m-0">{analyzedFrame ? `Frame ${analyzedFrame.id} · camera ${analyzedFrame.cameraId}` : "No analyzed frame recorded for this cycle."}</p>
            <p className="m-0 font-mono-tech text-[9px]">Captured: {formatTimestamp(analyzedFrame?.capturedAt)} · {DISPLAY_TIME_ZONE}</p>
            {analyzedFrame && <p className="m-0 text-[10px]">{analyzedFrame.stale ? "Historical capture — not a current camera view." : "Frozen capture — not live video."}</p>}
          </div>
          <div className="border-t border-[#252421] px-4.5 py-3 text-[11px] text-[#A7A39A]">
            <b className="font-medium text-[#F2EEE6]">Live video: unavailable</b> · Camera streaming and FPS are not supplied.
          </div>
        </section>

        {/* Current Object / Anomalib Panel */}
        <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
          <div className="flex items-center justify-between border-b border-[#252421] px-5 py-4">
            <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
              Current object / Anomalib
            </h2>
            <span className="font-mono-tech text-[9px] text-[#A7A39A]">
              {currentCycle ? `CYCLE ${currentCycle.id}` : "NO ACTIVE CYCLE"}
            </span>
          </div>

          {currentCycle ? (
            <div className="p-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="m-0 mb-1 text-[23px] font-[450] tracking-[-0.035em] text-[#F2EEE6]">
                    Duplo {currentCycle.objectId}
                  </h3>
                  <p className="font-mono-tech m-0 text-[9px] text-[#A7A39A]">
                    INSPECTIONS {cycInspections.length} · ATTEMPTS {cycAttempts.length}
                  </p>
                </div>
                <span
                  className={`font-mono-tech inline-block rounded-[3px] border px-2 py-1 text-[9px] tracking-[0.05em] uppercase ${
                    latestInspection?.classification === "defective"
                      ? "border-[#514633] bg-[#211d16] text-[#D6B775]"
                      : latestInspection?.classification === "good" ? "border-[#344b39] bg-[#152019] text-[#91B99C]" : "border-[#33332f] bg-[#1c1c1a] text-[#A7A39A]"
                  }`}
                >
                  {latestInspection?.classification ?? "UNCLASSIFIED"}
                </span>
              </div>

              {/* Exact Analyzed Snapshot kept fixed beside stream */}
              <div className="my-4 flex items-center gap-3.5">
                <div className="relative h-[75px] w-[85px] shrink-0 overflow-hidden rounded-[4px] border border-[#474132] bg-[#282b25]">
                  <EvidenceImage src={analyzedFrame?.imageUrl} alt={`Analyzed frame ${analyzedFrame?.id ?? "unavailable"}`} />
                </div>
                <div>
                  <p className="m-0 mb-1 text-[11px] text-[#F2EEE6]">Analyzed snapshot</p>
                  <small className="font-mono-tech block text-[9px] leading-relaxed text-[#A7A39A]">
                    {analyzedFrame?.id ?? "Unavailable"} · {formatTimestamp(analyzedFrame?.capturedAt)}
                    <br />
                    {DISPLAY_TIME_ZONE} · recorded evidence
                  </small>
                </div>
              </div>

              {/* Anomaly Score & Threshold */}
              <div>
                <div className="flex items-baseline justify-between">
                  <label className="text-[11px] text-[#A7A39A]">Anomaly score</label>
                  <strong className="font-mono-tech text-[20px] font-normal text-[#F2EEE6]">
                    {latestInspection ? latestInspection.score.toFixed(2) : "Unavailable"}
                  </strong>
                </div>
                <div className="font-mono-tech mt-2 flex justify-between text-[9px] text-[#A7A39A]">
                  <span>{latestInspection?.scoreRange ? `Scale ${latestInspection.scoreRange[0]}–${latestInspection.scoreRange[1]}` : "Score scale unavailable"}</span>
                  <span>Threshold {latestInspection ? latestInspection.threshold.toFixed(2) : "Unavailable"}</span>
                </div>
              </div>

              {/* Distinct Planned, Commanded, Observed Destinations & Reference Label */}
              <div className="mt-4 border-t border-[#252421] pt-3.5 text-[11px] text-[#A7A39A] space-y-1.5">
                <p className="m-0">
                  Planned destination{" "}
                  <b className="font-medium text-[#F2EEE6]">
                    {currentCycle.plannedDestination === "defective_bin"
                      ? "Defective bin"
                      : currentCycle.plannedDestination === "good_bin"
                      ? "Good bin"
                      : "Unavailable"}
                  </b>
                </p>
                {currentCycle.commandedDestination && (
                  <p className="m-0">
                    Commanded destination{" "}
                    <b className="font-medium text-[#F2EEE6]">
                      {currentCycle.commandedDestination === "defective_bin"
                        ? "Defective bin"
                        : currentCycle.commandedDestination === "good_bin" ? "Good bin" : currentCycle.commandedDestination}
                    </b>
                  </p>
                )}
                <p className="m-0">
                  Observed destination{" "}
                  <b className="font-medium text-[#F2EEE6]">
                    {currentCycle.observedDestination === "defective_bin"
                      ? "Defective bin"
                      : currentCycle.observedDestination === "good_bin"
                      ? "Good bin"
                      : currentCycle.observedDestination === "other" ? "Other location" : "Not verified"}
                  </b>
                </p>
                <p className="m-0">
                  Reference label{" "}
                  <b className="font-medium text-[#F2EEE6]">
                    {cycRefLabel ? cycRefLabel.quality : "Not yet supplied"}
                  </b>
                </p>
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => onOpenCycleTrace(currentCycle.id)}
                    className="rounded-[4px] border border-[#3e3b34] px-2.5 py-1 text-[10px] text-[#C7A477] hover:bg-[#22201b]"
                  >
                    Open {currentCycle.id} trace & audit ↗
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[260px] flex-col items-center justify-center p-6 text-center">
              <strong className="text-[16px] font-normal text-[#F2EEE6]">
                No cycles in this session yet
              </strong>
              <p className="mt-1 mb-4 text-[11px] text-[#A7A39A]">
                No physical cycle can be started from this read-only records view.
              </p>
              <button type="button" disabled className="min-h-[34px] cursor-not-allowed rounded-[5px] border border-[#3e3b34] px-3.5 py-1.5 text-[11px] text-[#A7A39A] opacity-45">Start cycle unavailable</button>
            </div>
          )}
        </section>
      </div>

      {/* Canonical 8-Stage Process & Model Contribution Pipeline */}
      <section className="mt-5 overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#252421] px-5 py-4">
          <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
            Cycle progress
          </h2>
          <div className="flex items-center gap-3">
            <span className="font-mono-tech text-[9px] text-[#A7A39A]">
              {currentCycle?.activePhase ? currentCycle.activePhase.replaceAll("_", " ").toUpperCase() : "PHASE UNAVAILABLE"}{" "}
              · {currentCycle?.phaseElapsedSec != null ? `${currentCycle.phaseElapsedSec.toFixed(1)} s` : "TIMING UNAVAILABLE"}
            </span>
            <button
              type="button"
              onClick={() => setExpandedEvidence(!expandedEvidence)}
              className="text-[10px] text-[#C7A477] hover:underline"
            >
              {expandedEvidence ? "Hide model payloads" : "Inspect model payloads ↗"}
            </button>
          </div>
        </div>

        <div className="p-5">
          {/* 8 Canonical Steps */}
          <div className="mb-5 grid grid-cols-4 gap-3 sm:grid-cols-8">
            {CANONICAL_STAGE_LIST.map((stage, idx) => {
              const isDone = false; // A later phase does not prove earlier physical outcomes.
              const isActive = idx === activeStageIndex;
              const isFaulted = currentCycle?.faultedPhase === stage.id;
              return (
                <div key={stage.id} className="relative min-w-0">
                  <span
                    className={`font-mono-tech mb-2 flex h-[20px] w-[20px] items-center justify-center rounded-full border text-[9px] ${
                      isFaulted
                        ? "border-[#E36363] bg-[#281817] text-[#E36363]"
                        : isDone
                        ? "border-[#637861] text-[#91B99C]"
                        : isActive
                        ? "border-[#C7A477] bg-[#C7A477] text-[#18130d] shadow-[0_0_0_4px_rgba(199,164,119,0.08)]"
                        : "border-[#454236] text-[#a59b8b]"
                    }`}
                  >
                    {isFaulted ? "!" : isDone ? "✓" : idx + 1}
                  </span>
                  <p
                    className={`m-0 text-[11px] leading-snug ${
                      isFaulted
                        ? "text-[#E36363]"
                        : isActive
                        ? "text-[#C7A477]"
                        : isDone
                        ? "text-[#F2EEE6]"
                        : "text-[#89867f]"
                    }`}
                  >
                    {stage.label}
                  </p>
                </div>
              );
            })}
          </div>

          {/* 3 Model Contribution Columns */}
          <div className="grid grid-cols-1 gap-4 border-t border-[#252421] pt-4 md:grid-cols-3">
            <div className="border-b border-[#252421] pb-3 md:border-r md:border-b-0 md:pr-4 md:pb-0">
              <label className="font-mono-tech text-[9px] text-[#C7A477]">
                NEMOTRON / VISUAL OBSERVATION
              </label>
              <p className="my-1.5 text-[11px] text-[#d4d0c7]">
                “
                {cycNemotron?.observations[0] ??
                  "Unavailable — no model observation recorded."}
                ”
              </p>
              <small className="block text-[10px] text-[#A7A39A]">
                Recorded model frames: {cycNemotron?.frameIds.join(", ") || "Unavailable"}
              </small>
              {expandedEvidence && cycNemotron && (
                <div className="font-mono-tech mt-2 rounded-[4px] border border-[#252421] bg-[#0b0b0a] p-2 text-[9px] text-[#A7A39A]">
                  <div>Model: {cycNemotron.modelId}</div>
                  <div>Status: {cycNemotron.status}</div>
                  {cycNemotron.hypotheses[0] && (
                    <div className="text-[#C7A477]">{cycNemotron.hypotheses[0]}</div>
                  )}
                  {cycNemotron.uncertainty && (
                    <div className="text-[#D6B775]">
                      Uncertainty: {cycNemotron.uncertainty}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="border-b border-[#252421] pb-3 md:border-r md:border-b-0 md:pr-4 md:pb-0">
              <label className="font-mono-tech text-[9px] text-[#C7A477]">
                GEMINI / SELECTED TASK
              </label>
              <p className="my-1.5 text-[11px] text-[#d4d0c7]">
                {cycDecision?.selectedChoice === "reinspect_other_view"
                  ? "Reinspect from another view"
                  : cycDecision?.selectedChoice === "place_defective"
                  ? "Place in defective bin"
                  : cycDecision?.selectedChoice === "place_good"
                  ? "Place in good bin"
                  : cycDecision?.selectedChoice ?? "Unavailable — no decision recorded"}
              </p>
              <small className="block text-[10px] text-[#A7A39A]">
                {cycDecision?.validatorReason ??
                  "Validation result unavailable"}
              </small>
              {expandedEvidence && cycDecision && (
                <div className="font-mono-tech mt-2 rounded-[4px] border border-[#252421] bg-[#0b0b0a] p-2 text-[9px] text-[#A7A39A]">
                  <div>
                    Model: {cycDecision.modelId} (state v{cycDecision.stateVersion} / goal v
                    {cycDecision.goalVersion})
                  </div>
                  <div>
                    Recorded scores:{" "}
                    {Object.entries(cycDecision.probabilities)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(", ") || "Unavailable"}
                  </div>
                  <div
                    className={
                      cycDecision.validatorAccepted === true ? "text-[#91B99C]" : cycDecision.validatorAccepted === false ? "text-[#E36363]" : "text-[#A7A39A]"
                    }
                  >
                    Validator accepted: {cycDecision.validatorAccepted == null ? "Unavailable" : String(cycDecision.validatorAccepted)}
                  </div>
                </div>
              )}
            </div>

            <div>
              <label className="font-mono-tech text-[9px] text-[#C7A477]">
                LOCAL POLICY / EXECUTION
              </label>
              <p className="my-1.5 text-[11px] text-[#d4d0c7]">
                {cycExecution?.physicalOutcome === "verified"
                  ? `Verified execution (${cycExecution.taskId})`
                  : cycExecution ? `Recorded controller status: ${cycExecution.controllerStatus}` : "Unavailable — no execution recorded"}
              </p>
              <small className="font-mono-tech block text-[10px] text-[#A7A39A]">
                Sent {cycExecution?.commandSentAt ? "✓" : "—"} &nbsp; Ack{" "}
                {cycExecution?.acknowledgedAt ? "✓" : "—"} &nbsp; Finished{" "}
                {cycExecution?.finishedAt ? "✓" : "—"} &nbsp; Verified{" "}
                {cycExecution?.physicalOutcome === "verified" ? "✓" : "—"}
              </small>
              {expandedEvidence && (
                <div className="font-mono-tech mt-2 rounded-[4px] border border-[#252421] bg-[#0b0b0a] p-2 text-[9px] text-[#A7A39A]">
                  <div>Policy: {cycExecution?.policyId ?? "Unavailable"}</div>
                  <div>Execution ID: {cycExecution?.id ?? "Unavailable"}</div>
                  <div>
                    Physical outcome:{" "}
                    {cycExecution?.physicalOutcome ?? "pending confirmation"}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {expandedEvidence && <section className="mt-3 rounded-[6px] border border-[#252421] bg-[#101010] p-5">
        <h3 className="m-0 text-[12px] font-medium text-[#F2EEE6]">Recorded model inputs and outputs</h3>
        {(snapshot.modelRuns ?? []).filter((run) => run.cycleId === currentCycle?.id).length === 0 && <p className="mb-0 text-[11px] text-[#A7A39A]">Unavailable — no model run recorded for this cycle.</p>}
        {(snapshot.modelRuns ?? []).filter((run) => run.cycleId === currentCycle?.id).map((run) => <div key={run.id} className="mt-3 border-t border-[#252421] pt-3">
          <p className="font-mono-tech text-[10px] text-[#C7A477]">{run.provider} / {run.modelId} · {run.id}</p>
          <p className="font-mono-tech text-[9px] text-[#A7A39A]">Frames: {run.frameIds.join(", ") || "None recorded"} · Requested: {formatTimestamp(run.requestedAt)} · {DISPLAY_TIME_ZONE}</p>
          <pre className="max-h-[260px] overflow-auto whitespace-pre-wrap break-words rounded-[4px] bg-[#0b0b0a] p-3 text-[10px] text-[#A7A39A]">{JSON.stringify({ input: run.input, output: run.output, latencyMs: run.latencyMs, error: run.error }, null, 2)}</pre>
        </div>)}
      </section>}

      {/* Persisted transcript is evidence; this read-only view cannot issue goals. */}
      <section className="mt-5 rounded-[6px] border border-[#3d3428] bg-[#171510] px-5 py-3.5">
        <div className="flex flex-wrap items-center gap-4">
          <span className="text-[19px] text-[#C7A477]" aria-hidden="true">◉</span>
          <div className="min-w-[220px] flex-1">
            <span className="font-mono-tech text-[8px] tracking-[0.1em] text-[#C7A477] uppercase">OPERATOR TRANSCRIPT / RECORDED INPUT</span>
            <p className="my-1 text-[12px] text-[#F2EEE6]">{latestUtterance?.finalizedText ?? "Unavailable — no finalized utterance recorded."}</p>
            <small className="block text-[10px] text-[#A7A39A]">Active goal: {snapshot.goalState.activeGoal ? snapshot.goalState.activeGoalLabel : "Unavailable"} · Goal version: {snapshot.goalState.goalVersion ?? "Unavailable"}</small>
          </div>
          <button type="button" disabled className="min-h-[32px] cursor-not-allowed rounded-[5px] border border-[#3e3b34] px-3 py-1.5 text-[11px] text-[#A7A39A] opacity-45">Voice input unavailable</button>
        </div>
      </section>

      {/* Expandable / Visible Count Strips */}
      <div className="mt-3 flex flex-wrap justify-between gap-3 pt-2 text-[11px] text-[#A7A39A]">
        <span>
          <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.started}</b> started ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.inProgress}</b> in
          progress · <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.correct}</b>{" "}
          correct · <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.failed}</b>{" "}
          failed · <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.aborted}</b>{" "}
          aborted ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.unverified}</b> unverified
        </span>
        <span>
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.total}</b> attempts ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.retries}</b> retries ·{" "}
          <b className="font-medium text-[#d1ccc2]">
            {m.cycleCounts.firstAttemptSuccesses}
          </b>{" "}
          first-attempt successes ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.recoveredCycles}</b>{" "}
          recovered ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.cycleCounts.extraInspections}</b>{" "}
          extra inspections
        </span>
      </div>

      <div className="flex flex-wrap justify-between gap-3 pt-1.5 text-[11px] text-[#A7A39A]">
        <span>
          Attempt outcomes:{" "}
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.successful}</b>{" "}
          successful ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.failed}</b> failed ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.aborted}</b> aborted ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.unverified}</b>{" "}
          unverified ·{" "}
          <b className="font-medium text-[#d1ccc2]">{m.attemptCounts.inProgress}</b> in
          progress
        </span>
      </div>

      {/* Compact Recent Events List with 1-Click Full History */}
      <div className="mt-5 flex flex-wrap items-center gap-6 text-[10px]">
        <span className="font-mono-tech text-[8px] tracking-[0.1em] text-[#A7A39A]">
          RECENT EVENTS · {DISPLAY_TIME_ZONE}
        </span>
        {snapshot.recentEvents.slice(0, 3).map((evt) => (
          <span key={evt.eventId} className="flex items-center gap-2">
            <span className="font-mono-tech text-[9px] text-[#A7A39A]">
              {formatTimestamp(evt.occurredAt, false)}
            </span>
            <span className="text-[#F2EEE6]">{evt.summary}</span>
            <span
              className={
                evt.statusTone === "good"
                  ? "text-[#91B99C]"
                  : evt.statusTone === "warn"
                  ? "text-[#D6B775]"
                  : evt.statusTone === "bad"
                  ? "text-[#E36363]"
                  : "text-[#A7A39A]"
              }
            >
              {evt.statusTone === "good"
                ? "✓"
                : evt.statusTone === "warn"
                ? "○"
                : "■"}
            </span>
          </span>
        ))}
        <button
          type="button"
          onClick={onNavigateQuality}
          className="ml-auto text-[11px] text-[#C7A477] hover:underline"
        >
          Full history ↗
        </button>
      </div>
    </div>
  );
};
