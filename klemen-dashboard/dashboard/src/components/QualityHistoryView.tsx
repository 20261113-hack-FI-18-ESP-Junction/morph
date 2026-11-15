import React, { useEffect, useState } from "react";
import { formatTimestamp, DISPLAY_TIME_ZONE } from "./EvidenceImage.tsx";
import { filterHistory, historyPage } from "../services/history.ts";
import type { Cycle, StationSnapshot } from "../types/morph.ts";

interface QualityHistoryViewProps {
  snapshot: StationSnapshot;
  onOpenCycleTrace: (cycleId: string) => void;
  onExportCsv: () => void;
  onExportJson: () => void;
}

export const QualityHistoryView: React.FC<QualityHistoryViewProps> = ({
  snapshot,
  onOpenCycleTrace,
  onExportCsv,
  onExportJson,
}) => {
  const [outcomeFilter, setOutcomeFilter] = useState<
    "all" | "failed" | "retry" | "unverified" | "correct" | "aborted" | "in_progress"
  >("all");
  const [searchObject, setSearchObject] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [referenceFilter, setReferenceFilter] = useState<'all' | 'labeled' | 'unlabeled'>('all');
  const [startedAfter, setStartedAfter] = useState('');
  const [startedBefore, setStartedBefore] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [errorFilter, setErrorFilter] = useState('');
  useEffect(() => setPage(0), [outcomeFilter, searchObject, referenceFilter, startedAfter, startedBefore, modelFilter, errorFilter, pageSize, snapshot.activeSession?.id]);

  const m = snapshot.metrics;
  const cm = m.confusionMatrix;

  const filteredCycles = filterHistory(snapshot, { query: searchObject, outcome: outcomeFilter,
    reference: referenceFilter, startedAfter, startedBefore, model: modelFilter, error: errorFilter });
  const pagination = historyPage(filteredCycles, page, pageSize);
  const visibleCycles = pagination.items;

  const refMap = new Map(
    snapshot.referenceLabels.map((r) => [r.id, r.quality])
  );

  const renderOutcomeBadge = (outcome: Cycle["outcome"]) => {
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

  return (
    <div>
      {/* Page Heading */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            03 / MORPH CONTROL ROOM
          </span>
          <h1 className="my-2 text-[30px] font-[450] leading-[1.15] tracking-[-0.055em] text-[#F2EEE6]">
            Quality &amp; history
          </h1>
          <p className="m-0 text-[12px] text-[#A7A39A]">
            Evidence that stays with the object.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] bg-[#211c15] px-2 py-1 text-[9px] tracking-[0.05em] text-[#C7A477]">
            {snapshot.viewMode === "replay"
              ? "READ-ONLY REPLAY"
              : snapshot.viewMode === "live"
              ? "LIVE RECORDS"
              : "PERSISTED SIMULATION"}
          </span>
          <button
            type="button"
            disabled={!snapshot.activeSession || snapshot.dataConnection !== "connected" || snapshot.viewMode === "replay"}
            title={snapshot.viewMode === "replay" ? "Use JSON to export the frozen replay" : undefined}
            onClick={onExportCsv}
            className="min-h-[32px] rounded-[5px] border border-[#3e3b34] px-3 py-1.5 text-[11px] text-[#F2EEE6] hover:bg-[#22201b]"
          >
            Export CSV
          </button>
          <button
            type="button"
            disabled={!snapshot.activeSession || snapshot.dataConnection !== "connected"}
            onClick={onExportJson}
            className="min-h-[32px] rounded-[5px] border border-[#3e3b34] px-3 py-1.5 text-[11px] text-[#F2EEE6] hover:bg-[#22201b]"
          >
            JSON ↗
          </button>
        </div>
      </div>

      <p role="status" className="mb-5 text-[11px] text-[#A7A39A]">{snapshot.viewMode === "replay" ? "Frozen historical records · Saved session totals" : `Records API: ${snapshot.dataConnection} · ${snapshot.dataStale ? "Saved results may be stale" : "Records current"}`}. Source: {snapshot.sourceMode}. Times: {DISPLAY_TIME_ZONE}.</p>

      {/* 4 Quality Metrics */}
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
          <div className="text-[11px] text-[#A7A39A]">Detection agreement</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.detectionAccuracy.value !== null ? (
              <>
                {m.detectionAccuracy.value.toFixed(1)}
                <span className="ml-1 text-[18px] text-[#A7A39A]">%</span>
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.detectionAccuracy.checkedPopulation > 0
              ? `${m.detectionAccuracy.numerator} correct / ${m.detectionAccuracy.checkedPopulation} checked; ${m.detectionAccuracy.totalPopulation} objects total`
              : "No data yet"}
          </div>
        </div>

        <div className="mt-4 border-r border-[#252421] pr-6 lg:mt-0 lg:px-6">
          <div className="text-[11px] text-[#A7A39A]">Defect escapes</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.defectEscape.denominator > 0 ? m.defectEscape.numerator : "—"}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.defectEscape.denominator > 0
              ? `${m.defectEscape.numerator} missed / ${m.defectEscape.denominator} reference-defective objects`
              : "No data yet"}
          </div>
        </div>

        <div className="mt-4 pl-6 lg:mt-0">
          <div className="text-[11px] text-[#A7A39A]">Recovery</div>
          <div className="font-mono-tech text-[34px] font-[420] leading-[1.4] tracking-[-0.04em] text-[#F2EEE6]">
            {m.cycleCounts.finished > 0 ? m.cycleCounts.recoveredCycles : "—"}
          </div>
          <div className="text-[11px] text-[#A7A39A]">
            {m.cycleCounts.finished > 0
              ? `${m.cycleCounts.recoveredCycles} recovered / ${m.cycleCounts.correct} confirmed correct cycles`
              : "No data yet"}
          </div>
        </div>
      </div>

      {/* Confusion Matrix + Baseline vs OpenVINO */}
      <div className="mb-5 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.2fr]">
        {/* Detection Confusion Matrix */}
        <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
          <div className="flex items-center justify-between border-b border-[#252421] px-5 py-4">
            <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
              Detection confusion matrix
            </h2>
            <span className="font-mono-tech text-[9px] text-[#A7A39A]">
              {m.detectionAccuracy.checkedPopulation} REFERENCE-LABELED OBJECTS
            </span>
          </div>

          <div className="p-5">
            <div className="my-3.5 grid grid-cols-[95px_1fr_1fr] gap-2">
              <div />
              <div className="self-center text-center text-[9px] text-[#A7A39A]">
                Predicted good
              </div>
              <div className="self-center text-center text-[9px] text-[#A7A39A]">
                Predicted defective
              </div>

              <div className="self-center text-center text-[9px] text-[#A7A39A]">
                Reference
                <br />
                good
              </div>
              <div className="font-mono-tech rounded-[5px] bg-[#182019] px-4 py-4.5 text-[26px] text-[#91B99C]">
                {cm.tn}
                <small className="mt-1 block font-sans text-[9px] text-[#c6c1b5]">
                  Correctly accepted
                </small>
              </div>
              <div className="font-mono-tech rounded-[5px] bg-[#282219] px-4 py-4.5 text-[26px] text-[#D6B775]">
                {cm.fp}
                <small className="mt-1 block font-sans text-[9px] text-[#c6c1b5]">
                  False rejection
                </small>
              </div>

              <div className="self-center text-center text-[9px] text-[#A7A39A]">
                Reference
                <br />
                defective
              </div>
              <div className="font-mono-tech rounded-[5px] bg-[#2b1816] px-4 py-4.5 text-[26px] text-[#E36363]">
                {cm.fn}
                <small className="mt-1 block font-sans text-[9px] text-[#c6c1b5]">
                  Defect escape
                </small>
              </div>
              <div className="font-mono-tech rounded-[5px] bg-[#182019] px-4 py-4.5 text-[26px] text-[#91B99C]">
                {cm.tp}
                <small className="mt-1 block font-sans text-[9px] text-[#c6c1b5]">
                  Correctly rejected
                </small>
              </div>
            </div>

            <p className="m-0 text-[11px] text-[#A7A39A]">
              Reference labels are independent of model predictions. One decision inspection
              per cycle contributes to cycle-level detection metrics.
              <br />
              {cm.unlabeledCount} objects are not included in detection metrics
              {cm.reviewRequiredCount > 0
                ? `; ${cm.reviewRequiredCount} review_required separated.`
                : "."}
            </p>
          </div>
        </section>

        {/* Baseline vs OpenVINO */}
        <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
          <div className="flex items-center justify-between border-b border-[#252421] px-5 py-4">
            <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
              Baseline vs OpenVINO
            </h2>
            <span className="font-mono-tech inline-block rounded-[3px] border border-[#33332f] bg-[#1c1c1a] px-2 py-1 text-[9px] tracking-[0.05em] text-[#b8b4ab]">
              BENCHMARK NOT RECORDED
            </span>
          </div>

          <div className="p-5">
            <div className="font-mono-tech flex justify-between text-[9px] text-[#A7A39A]">
              <span>BASELINE</span>
              <span>OPTIMIZED</span>
            </div>

            <div
              className="mb-4.5 flex h-[176px] flex-col justify-center text-center"
              style={{
                background:
                  "repeating-linear-gradient(0deg, transparent, transparent 43px, #23221e 44px)",
              }}
            >
              <strong className="text-[22px] font-normal text-[#c5c0b5]">
                No comparable runs yet
              </strong>
              <p className="mt-1 mb-0 text-[11px] text-[#A7A39A]">
                Model speed and full-cycle speed will be reported separately.
              </p>
            </div>

            <div className="font-mono-tech flex justify-between text-[9px] text-[#A7A39A]">
              <span>Model · device · precision</span>
              <span>Sample count · quality · timing</span>
            </div>
            <p className="mt-3 mb-0 text-[11px] text-[#A7A39A]">
              No extrapolated speedup. Compare matched inputs and include cloud waiting time
              in cycle duration.
            </p>
          </div>
        </section>
      </div>

      {/* Cycle History Table */}
      <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#252421] px-5 py-4">
          <div className="flex items-center gap-4">
            <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
              Cycle history
            </h2>
            <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] bg-[#211c15] px-2 py-1 text-[8px] tracking-[0.05em] text-[#C7A477]">
              {snapshot.activeSession?.name.toUpperCase() ?? "NO SESSION"}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              aria-label="Filter cycles by cycle or object ID"
              value={searchObject}
              onChange={(e) => setSearchObject(e.target.value)}
              placeholder="Cycle or object ID"
              className="w-[150px] rounded-[4px] border border-[#423d33] bg-[#171714] px-2.5 py-1.5 text-[10px] text-[#F2EEE6]"
            />
            <label htmlFor="outcome-filter" className="text-[11px] text-[#A7A39A]">
              Show
            </label>
            <select
              id="outcome-filter"
              value={outcomeFilter}
              onChange={(e) =>
                setOutcomeFilter(
                  e.target.value as
                    | "all"
                    | "failed"
                    | "retry"
                    | "unverified"
                    | "correct"
                    | "aborted"
                    | "in_progress"
                )
              }
              className="rounded-[4px] border border-[#423d33] bg-[#171714] px-2.5 py-1.5 text-[10px] text-[#F2EEE6]"
            >
              <option value="all">All outcomes</option>
              <option value="failed">Failures</option>
              <option value="retry">Retries</option>
              <option value="unverified">Unverified</option>
              <option value="correct">Confirmed correct</option>
              <option value="aborted">Aborted</option>
              <option value="in_progress">In progress</option>
            </select>
            <span className="font-mono-tech hidden text-[9px] text-[#A7A39A] sm:inline">
              {snapshot.cycles.length} SESSION CYCLES
            </span>
          </div>
        </div>

        <div className="grid gap-3 border-b border-[#252421] px-5 py-3 text-[10px] sm:grid-cols-3 lg:grid-cols-6">
          <label>Reference label<select aria-label="Filter by reference label" value={referenceFilter} onChange={e=>setReferenceFilter(e.target.value as 'all' | 'labeled' | 'unlabeled')} className="mt-1 w-full rounded border border-[#423d33] bg-[#171714] p-2"><option value="all">All labels</option><option value="labeled">Labeled</option><option value="unlabeled">Unlabeled</option></select></label>
          <label>From date (UTC)<input aria-label="History start date UTC" type="date" value={startedAfter} onChange={e=>setStartedAfter(e.target.value)} className="mt-1 w-full rounded border border-[#423d33] bg-[#171714] p-2"/></label>
          <label>Through date (UTC)<input aria-label="History end date UTC" type="date" value={startedBefore} onChange={e=>setStartedBefore(e.target.value)} className="mt-1 w-full rounded border border-[#423d33] bg-[#171714] p-2"/></label>
          <label>Model ID<input aria-label="Filter history by model" value={modelFilter} onChange={e=>setModelFilter(e.target.value)} className="mt-1 w-full rounded border border-[#423d33] bg-[#171714] p-2"/></label>
          <label>Error code<input aria-label="Filter history by error" value={errorFilter} onChange={e=>setErrorFilter(e.target.value)} className="mt-1 w-full rounded border border-[#423d33] bg-[#171714] p-2"/></label>
          <label>Rows per page<select aria-label="History rows per page" value={pageSize} onChange={e=>setPageSize(Number(e.target.value))} className="mt-1 w-full rounded border border-[#423d33] bg-[#171714] p-2"><option value={5}>5</option><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option></select></label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr>
                <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                  Cycle / object
                </th>
                <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                  Task outcome
                </th>
                <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                  Attempts
                </th>
                <th className="hidden border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A] sm:table-cell">
                  Full cycle
                </th>
                <th className="hidden border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A] sm:table-cell">
                  Reference quality
                </th>
                <th className="border-b border-[#252421] px-3 py-2.5 text-right text-[9px] font-normal text-[#A7A39A]" />
              </tr>
            </thead>
            <tbody>
              {visibleCycles.length > 0 ? (
                visibleCycles.map((c, idx) => {
                  const refQuality = (c.referenceLabelId ? refMap.get(c.referenceLabelId) : null) ?? "Not supplied";
                  const attempts = snapshot.attempts.filter((attempt) => attempt.cycleId === c.id).sort((a, b) => a.ordinal - b.ordinal);
                  const recovered = c.outcome === "correct" && attempts.length > 1 && attempts.slice(0, -1).some((attempt) => attempt.outcome === "failed");
                  return (
                    <tr key={c.id} className="hover:bg-[#151513]">
                      <td
                        className={`font-mono-tech px-3 py-3 text-[10px] ${
                          idx < visibleCycles.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {c.id} <span className="text-[#A7A39A]">/ {c.objectId}</span>
                        <time dateTime={c.startedAt} className="mt-1 block text-[9px] text-[#A7A39A]">{formatTimestamp(c.startedAt)}</time>
                      </td>
                      <td
                        className={`px-3 py-3 ${
                          idx < visibleCycles.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {renderOutcomeBadge(c.outcome)}
                      </td>
                      <td
                        className={`font-mono-tech px-3 py-3 text-[10px] ${
                          idx < visibleCycles.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {c.attemptIds.length}
                        {recovered ? " · recovered" : c.attemptIds.length > 1 ? " · retry" : ""}
                      </td>
                      <td
                        className={`font-mono-tech hidden px-3 py-3 text-[10px] sm:table-cell ${
                          idx < visibleCycles.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {c.fullCycleDurationSec === null
                          ? c.outcome === "in_progress" ? "In progress" : "Unavailable"
                          : `${c.fullCycleDurationSec.toFixed(1)} s`}
                      </td>
                      <td
                        className={`hidden px-3 py-3 sm:table-cell ${
                          idx < visibleCycles.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {refQuality}
                      </td>
                      <td
                        className={`px-3 py-3 text-right ${
                          idx < visibleCycles.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => onOpenCycleTrace(c.id)}
                          aria-label={`Open trace for ${c.id}`}
                          className="min-h-[28px] rounded-[5px] border border-[#3e3b34] px-2.5 py-1 text-[10px] text-[#F2EEE6] hover:bg-[#22201b]"
                        >
                          Trace ↗
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-[#A7A39A]">
                    No cycles match the active filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#252421] px-5 py-3 text-[10px] text-[#A7A39A]">
          <span>
            Showing {visibleCycles.length} of {filteredCycles.length} matching records · All{" "}
            {snapshot.cycles.length} included in JSON/CSV export · Times in {DISPLAY_TIME_ZONE}
          </span>
          <div className="flex items-center gap-3">
            <button type="button" aria-label="Previous history page" disabled={pagination.page === 0} onClick={()=>setPage(pagination.page-1)} className="text-[#C7A477] disabled:opacity-40">Previous</button>
            <span>Page {pagination.page+1} of {pagination.pages}</span>
            <button type="button" aria-label="Next history page" disabled={pagination.page >= pagination.pages-1} onClick={()=>setPage(pagination.page+1)} className="text-[#C7A477] disabled:opacity-40">Next</button>
          </div>
        </div>
      </section>
    </div>
  );
};
