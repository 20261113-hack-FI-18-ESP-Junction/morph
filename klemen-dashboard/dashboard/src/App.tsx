import React, { useEffect, useState, useSyncExternalStore } from "react";
import { CycleDetailDrawer } from "./components/CycleDetailDrawer.tsx";
import { DesignLanguageView } from "./components/DesignLanguageView.tsx";
import { LiveInspectionView } from "./components/LiveInspectionView.tsx";
import { QualityHistoryView } from "./components/QualityHistoryView.tsx";
import { ReplayPanel } from "./components/ReplayPanel.tsx";
import { RobotSystemView } from "./components/RobotSystemView.tsx";
import { stationClient } from "./services/stationClient.ts";
import { EvidenceAnalystPanel } from "./analysis/EvidenceAnalystPanel.tsx";
import type { ViewMode } from "./types/morph.ts";
import { formatTimestamp, DISPLAY_TIME_ZONE } from "./components/EvidenceImage.tsx";

type NavDestination = "live" | "system" | "quality" | "design";

export default function App() {
  const [navView, setNavView] = useState<NavDestination>("live");
  const snapshot = useSyncExternalStore(stationClient.subscribe, stationClient.getState);
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [refreshPending, setRefreshPending] = useState(false);
  const [catalogPending, setCatalogPending] = useState(false);
  const showToast = (message: string) => setToastMessage(message);
  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => setToastMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);
  useEffect(() => { void stationClient.start(); return () => stationClient.stop(); }, []);
  useEffect(() => { setSelectedCycleId(null); }, [snapshot.activeSession?.id, snapshot.viewMode]);
  useEffect(() => { void stationClient.setHistoryVisible(navView === "quality"); }, [navView]);
  const openCycle = (cycleId: string) => {
    setSelectedCycleId(cycleId);
    if (snapshot.viewMode !== "replay") void stationClient.selectCycle(cycleId);
  };
  const closeCycle = () => {
    setSelectedCycleId(null);
    if (snapshot.viewMode !== "replay") void stationClient.selectCycle();
  };
  const handleModeSwitch = async (mode: ViewMode, sessionId?: string) => {
    if (mode === "replay") { try { await stationClient.startReplay(); setNavView("quality"); } catch { showToast("Load a current persisted session before replaying."); } return; }
    setSelectedCycleId(null);
    await stationClient.selectMode(mode, sessionId);
  };
  const unsupported = async () => { showToast("This operation is unavailable until its station integration is verified."); };
  const refreshRecords = async () => {
    if (refreshPending) return;
    setRefreshPending(true);
    try { await stationClient.refresh(); }
    catch { showToast("Records could not be refreshed. Check the station connection and retry."); }
    finally { setRefreshPending(false); }
  };
  const loadOlderSessions = async () => {
    if (catalogPending) return;
    setCatalogPending(true);
    try { await stationClient.loadOlderSessions(); }
    catch { showToast("Older sessions could not be loaded. Check the station connection and retry."); }
    finally { setCatalogPending(false); }
  };
  const downloadFile = (filename: string, content: string, mimeType: string) => {
    const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 500);
  };
  const handleExportCsv = async () => {
    if (!snapshot.activeSession) return;
    try {
      const csv = await stationClient.exportCsv(snapshot.activeSession.id);
      downloadFile(`morph-${snapshot.activeSession.id.replace(/[^a-zA-Z0-9_-]/g, "-")}-latest-records.csv`, csv, "text/csv");
      showToast("Exported the latest server records as CSV; these may be newer than the displayed snapshot.");
    } catch { showToast("Export unavailable. Check the station connection and retry."); }
  };
  const handleExportJson = async () => {
    if (!snapshot.activeSession) return;
    try {
      const json = await stationClient.exportJson(snapshot.activeSession.id);
      downloadFile(`morph-${snapshot.activeSession.id.replace(/[^a-zA-Z0-9_-]/g, "-")}-snapshot.json`, json, "application/json");
      showToast(snapshot.recordScope === "session" || snapshot.viewMode === "replay"
        ? "Exported the displayed saved session snapshot as JSON."
        : "Exported the latest persisted session trace as JSON.");
    } catch { showToast("Export unavailable. Check the station connection and retry."); }
  };
  const isDisconnected = snapshot.dataConnection !== "connected";
  const isReplay = snapshot.viewMode === "replay";
  const sourceLabel = isReplay ? `READ-ONLY REPLAY · ${snapshot.sourceMode?.toUpperCase()}` : snapshot.viewMode === "simulation" ? "PERSISTED SIMULATION" : "LIVE RECORDS";
  const selectedCycle = selectedCycleId ? snapshot.cycles.find(c => c.id === selectedCycleId) ?? null : null;

  return (
    <div className="flex min-h-screen flex-col bg-[#080808] text-[#F2EEE6] sm:flex-row">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      {/* Sidebar (212px on Desktop, compact icon/number rail at 600-900px, top bar on <600px) */}
      <aside className="flex shrink-0 flex-row flex-wrap items-center justify-between gap-y-4 border-b border-[#252421] bg-[#0b0b0a] px-4.5 py-4 sm:w-[70px] sm:flex-col sm:items-stretch sm:justify-start sm:border-r sm:border-b-0 sm:px-2.5 sm:py-6 lg:w-[212px] lg:px-5 lg:pt-[30px] lg:pb-5">
        <a
          href="#live"
          onClick={(e) => {
            e.preventDefault();
            setNavView("live");
          }}
          className="flex items-center gap-2.5 text-[20px] font-semibold leading-[1.2] tracking-[0.17em] text-[#F2EEE6] sm:justify-center lg:justify-start lg:text-[25px]"
        >
          <img
            src="/assets/aistudio/morph-mark_854b67cd.svg"
            alt="Morph articulated-M logo"
            className="w-[30px] sm:w-[38px]"
          />
          <span className="sm:hidden lg:block">
            MORPH
            <small className="mt-1.5 hidden text-[7px] font-normal tracking-[0.19em] text-[#A7A39A] lg:block">
              PHYSICAL INTELLIGENCE
            </small>
          </span>
        </a>

        <div className="font-mono-tech mt-14 mb-5 hidden px-2.5 text-[10px] tracking-[0.09em] text-[#8c887e] lg:block">
          WORKSPACE / 01
        </div>

        <nav
          aria-label="Primary"
          className="flex w-full flex-row justify-between gap-1 sm:mt-10 sm:w-auto sm:flex-col sm:gap-2 lg:mt-0"
        >
          <button
            type="button"
            aria-label="Live inspection" onClick={() => setNavView("live")}
            aria-current={navView === "live" ? "page" : undefined}
            className={`flex items-center gap-3 whitespace-nowrap rounded-[5px] border px-2.5 py-2 text-left text-[12px] transition-colors sm:justify-center sm:py-3 lg:justify-start ${
              navView === "live"
                ? "border-[#3f382d] bg-[#1a1916] text-[#F2EEE6]"
                : "border-transparent text-[#A7A39A] hover:text-[#F2EEE6]"
            }`}
          >
            <span className="font-mono-tech text-[11px] text-[#C7A477] lg:text-[10px]">
              01
            </span>
            <span className="sm:hidden lg:inline">Live inspection</span>
            <span
              className={`ml-auto hidden h-1 w-1 rounded-full bg-[#C7A477] lg:inline-block ${
                navView === "live" ? "visible" : "invisible"
              }`}
            />
          </button>

          <button
            type="button"
            aria-label="Robot and system" onClick={() => setNavView("system")}
            aria-current={navView === "system" ? "page" : undefined}
            className={`flex items-center gap-3 whitespace-nowrap rounded-[5px] border px-2.5 py-2 text-left text-[12px] transition-colors sm:justify-center sm:py-3 lg:justify-start ${
              navView === "system"
                ? "border-[#3f382d] bg-[#1a1916] text-[#F2EEE6]"
                : "border-transparent text-[#A7A39A] hover:text-[#F2EEE6]"
            }`}
          >
            <span className="font-mono-tech text-[11px] text-[#C7A477] lg:text-[10px]">
              02
            </span>
            <span className="sm:hidden lg:inline">System</span>
            <span
              className={`ml-auto hidden h-1 w-1 rounded-full bg-[#C7A477] lg:inline-block ${
                navView === "system" ? "visible" : "invisible"
              }`}
            />
          </button>

          <button
            type="button"
            aria-label="Quality and history" onClick={() => setNavView("quality")}
            aria-current={navView === "quality" ? "page" : undefined}
            className={`flex items-center gap-3 whitespace-nowrap rounded-[5px] border px-2.5 py-2 text-left text-[12px] transition-colors sm:justify-center sm:py-3 lg:justify-start ${
              navView === "quality"
                ? "border-[#3f382d] bg-[#1a1916] text-[#F2EEE6]"
                : "border-transparent text-[#A7A39A] hover:text-[#F2EEE6]"
            }`}
          >
            <span className="font-mono-tech text-[11px] text-[#C7A477] lg:text-[10px]">
              03
            </span>
            <span className="sm:hidden lg:inline">History</span>
            <span
              className={`ml-auto hidden h-1 w-1 rounded-full bg-[#C7A477] lg:inline-block ${
                navView === "quality" ? "visible" : "invisible"
              }`}
            />
          </button>
        </nav>

        {/* Editorial Sidebar Note (Desktop only) */}
        <div className="mt-20 hidden px-2.5 lg:block">
          <span className="font-mono-tech text-[8px] tracking-[0.1em] text-[#C7A477]">
            THE ART OF ADAPTATION
          </span>
          <div
            aria-hidden="true"
            className="relative mt-5 h-[75px] w-[75px] rounded-full border border-[#554833] opacity-50"
          >
            <div className="absolute inset-[12px_-10px] -rotate-40 rounded-full border border-[#776043]" />
            <div className="absolute inset-[-10px_22px] rotate-25 rounded-full border border-[#776043]" />
          </div>
          <p className="mt-4 text-[22px] font-light leading-[1.55] tracking-[-0.04em] text-[#b4b0a6]">
            Observe.
            <br />
            Understand.
            <br />
            <em className="font-editorial text-[35px] leading-none text-[#C7A477]">
              Adapt.
            </em>
          </p>
        </div>

        {/* Sidebar Bottom */}
        <div className="mt-auto hidden pt-20 lg:block">
          <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] bg-[#211c15] px-2 py-1 text-[9px] tracking-[0.05em] text-[#C7A477]">
            {sourceLabel}
          </span>
          <p className="mt-2 text-[10px] leading-[1.9] text-[#858177]">
            Station evidence workspace
            <br />
            Intel records · Mac analytics
          </p>
          <div className="mt-1 flex flex-col items-start gap-1.5">
            <button
              type="button"
              onClick={() => setNavView("design")}
              className="p-0 text-[11px] text-[#C7A477] hover:underline"
            >
              Design language ↗
            </button>
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 84px Ornamental Masthead at Absolute Top */}
        <div
          aria-label="Decorative Renaissance artwork"
          className="relative h-[64px] overflow-hidden border-b border-[#252421] px-5 py-3.5 sm:h-[70px] sm:px-8 sm:py-[13px]"
        >
          <div>
            <span className="font-mono-tech text-[8px] tracking-[0.1em] text-[#C7A477] sm:text-[10px]">
              MORPH / JUNCTION 2026
            </span>
            <p className="my-1 text-[13px] tracking-[-0.02em] text-[#F2EEE6] sm:text-[18px]">
              A new perspective on{" "}
              <em className="font-editorial text-[17px] text-[#c8bbaa] sm:text-[23px]">
                physical intelligence.
              </em>
            </p>
          </div>

          <div
            aria-hidden="true"
            className="pointer-events-none absolute top-0 right-0 hidden h-full w-[340px] overflow-hidden sm:block lg:right-[125px] lg:w-[560px]"
          >
            <img
              src="/assets/aistudio/orbital_7a3f6055.svg"
              alt=""
              className="orbital-motion absolute -top-[39px] -left-[65px] h-[165px] w-[520px] opacity-65"
            />
            <img
              src="/assets/aistudio/copernicus-scriven_f284bf85.jpg"
              alt="Decorative historical engraving of Nicolaus Copernicus"
              className="copernicus-engraving absolute -top-[29px] right-1 h-[148px] w-[130px] object-cover object-[50%_29%]"
            />
          </div>
        </div>

        {/* 76px Sticky Operational Control Bar */}
        <header className="sticky top-0 z-20 flex min-h-[76px] flex-wrap items-center justify-between gap-3 border-b border-[#252421] bg-[#080808] px-5 py-3 sm:px-8 sm:py-0">
          <div className="flex flex-wrap items-center gap-3 text-[12px] text-[#A7A39A]">
            <span
              className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                isDisconnected
                  ? "bg-[#A7A39A]"
                  : snapshot.stopRecord
                  ? "bg-[#E36363]"
                  : "bg-[#D6B775]"
              }`}
            />
            <span>{isReplay ? "Replay" : "Records API"} <b className="ml-1.5 font-medium text-[#F2EEE6]">{isReplay ? "Frozen snapshot" : snapshot.dataConnection}</b></span>
            <span className="font-mono-tech text-[10px] text-[#A7A39A]">{sourceLabel} · {isReplay ? "SAVED SESSION TOTALS" : snapshot.recordScope === "session" ? "SAVED SESSION SNAPSHOT" : snapshot.dataStale ? "STALE / NOT CURRENT" : snapshot.selectedSessionId ? "SELECTED SESSION RECORDS" : "FOLLOWING LATEST SESSION"}</span>
            <label className="flex items-center gap-2 text-[11px]">
              Session
              <select aria-label="Selected station session" value={snapshot.selectedSessionId ?? ""}
                disabled={snapshot.sessions.length === 0 || isReplay}
                onChange={event => void handleModeSwitch(snapshot.viewMode, event.target.value || undefined)}
                className="max-w-[230px] rounded border border-[#3e3b34] bg-[#101010] px-2 py-1.5 text-[#F2EEE6] disabled:opacity-50">
                <option value="">{snapshot.sessions.length === 0 ? "Follow latest · no sessions for this source" : "Follow latest session"}</option>
                {snapshot.sessions.map(session => <option key={session.id} value={session.id}>{session.name}</option>)}
              </select>
            </label>
            {snapshot.sessionCatalogHasMore && <button
              type="button"
              className="text-action disabled:cursor-not-allowed disabled:opacity-45"
              disabled={catalogPending || isReplay}
              aria-busy={catalogPending}
              onClick={() => void loadOlderSessions()}
            >{catalogPending ? "Loading sessions…" : "Load older sessions"}</button>}

            {/* Persistent Mode Switcher: Live | Simulation | Replay */}
            <span className="hidden h-[18px] border-r border-[#33312b] md:inline-block" />
            <div
              role="group"
              aria-label="View mode selector"
              className="flex items-center gap-1 rounded-[4px] border border-[#252421] bg-[#101010] p-0.5 text-[10px]"
            >
              <button
                type="button"
                aria-pressed={snapshot.viewMode === "live"}
                onClick={() => handleModeSwitch("live")}
                className={`rounded-[3px] px-2 py-1 ${
                  snapshot.viewMode === "live"
                    ? "bg-[#292822] font-medium text-[#F2EEE6]"
                    : "text-[#A7A39A] hover:text-[#F2EEE6]"
                }`}
              >
                Live
              </button>
              <button
                type="button"
                aria-pressed={snapshot.viewMode === "simulation"}
                onClick={() => handleModeSwitch("simulation")}
                className={`rounded-[3px] px-2 py-1 ${
                  snapshot.viewMode === "simulation"
                    ? "bg-[#211c15] font-medium text-[#C7A477]"
                    : "text-[#A7A39A] hover:text-[#F2EEE6]"
                }`}
              >
                Simulation
              </button>
              <button
                type="button"
                disabled={!snapshot.activeSession || isDisconnected || snapshot.dataStale || isReplay} aria-pressed={isReplay} title="Browse recorded events without executing tasks" onClick={() => handleModeSwitch("replay")}
                className={`rounded-[3px] px-2 py-1 ${
                  snapshot.viewMode === "replay"
                    ? "bg-[#292822] font-medium text-[#F2EEE6]"
                    : "text-[#A7A39A] hover:text-[#F2EEE6]"
                }`}
              >
                Replay
              </button>
            </div>
          </div>

          <div className="flex w-full flex-wrap items-center justify-between gap-3 sm:w-auto sm:justify-end">
            <span className="text-[10px] text-[#a59b89]">Robot monitor only <span aria-hidden="true">·</span> Control host: Jose’s Mac</span>
            <button
              type="button"
              disabled={refreshPending || isReplay}
              aria-busy={refreshPending}
              onClick={() => void refreshRecords()}
              className="quiet-button disabled:cursor-not-allowed disabled:opacity-45"
              title={isReplay ? "Replay preserves its frozen records" : "Refresh the station records shown in this view"}
            >
              <span aria-hidden="true">↻</span> {refreshPending ? "Refreshing…" : "Refresh records"}
            </button>
          </div>
        </header>

        {!isReplay && (snapshot.dataStale || isDisconnected) && (
          <div role="status" aria-live="polite" className="flex flex-wrap items-center justify-between gap-3 border-b border-[#514633] bg-[#211d16] px-5 py-3 text-[11px] text-[#D6B775] sm:px-8">
            <span>{snapshot.activeFaultBanner ?? "Waiting for station records. No live data has been received."}</span>
            <button type="button" onClick={() => void stationClient.reconnect()} className="rounded border border-[#6c5840] px-3 py-1.5 text-[#F2EEE6]">Reconnect records</button>
          </div>
        )}
        {/* Main Content Viewport (32px desktop padding) */}
        <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-[1660px] flex-1 px-4.5 py-6 sm:px-7 sm:pt-7 sm:pb-8 xl:px-9">
          {isReplay && <ReplayPanel snapshot={snapshot} onSeek={index=>stationClient.seekReplay(index)} onOpenCycle={openCycle}/>}
          {navView === "live" && (
            <LiveInspectionView
              snapshot={snapshot}
              selectedPreset="demo_01_full"
              onSelectPreset={() => void unsupported()}
              onOpenSimulation={() => handleModeSwitch("simulation")}
              onShowDisconnected={() => handleModeSwitch("live")}
              onOpenCycleTrace={openCycle}
              onNavigateQuality={() => setNavView("quality")}
              onStartCycle={unsupported}
              onAdvanceCycle={unsupported}
              onStartNewSession={unsupported}
              onEndActiveSession={unsupported}
              onSubmitVoiceGoal={unsupported}
              onEnrichVoiceTimestamps={unsupported}
              onCommitQueuedGoal={unsupported}
            />
          )}

          {navView === "system" && <RobotSystemView snapshot={snapshot} />}

          {navView === "quality" && (
            <>
            {!isReplay && snapshot.canonicalSource && snapshot.recordScope !== "session" && <div className="view-heading"><div><span className="eyebrow">03 / QUALITY &amp; RELIABILITY</span><h1>Quality &amp; history<span className="heading-period">.</span></h1><p>Evidence that stays with the object.</p></div></div>}
            {!isReplay && <div className="history-scope-banner" role="status">
              <div>
                <strong className="font-medium">{snapshot.historyStatus === "loading" ? "Loading saved session history…" : snapshot.recordScope === "session" ? "Saved session snapshot" : "Session history unavailable"}</strong>
                <p>{snapshot.historyError ?? (snapshot.recordScope === "session" ? `${formatTimestamp(snapshot.historyLoadedAt)} · ${DISPLAY_TIME_ZONE}${snapshot.historyUpdateAvailable ? " · New records are available" : " · Filters and totals refer to this saved snapshot"}` : "Complete history is loaded when you open this view. Recent live records remain separate.")}</p>
              </div>
              <button type="button" className="quiet-button" disabled={refreshPending || snapshot.historyStatus === "loading" || !snapshot.activeSession} onClick={() => void refreshRecords()}>{snapshot.historyStatus === "loading" ? "Loading…" : "Refresh history"}</button>
            </div>}
            {(isReplay || snapshot.recordScope === "session" || !snapshot.canonicalSource) && <>
            <QualityHistoryView
              snapshot={snapshot}
              onOpenCycleTrace={openCycle}
              onExportCsv={handleExportCsv}
              onExportJson={handleExportJson}
            />
            <EvidenceAnalystPanel snapshot={snapshot} onOpenSource={(source) => {
              if (source.sessionId === snapshot.activeSession?.id && source.cycleId && snapshot.cycles.some(cycle => cycle.id === source.cycleId)) {
                openCycle(source.cycleId);
              } else {
                showToast("The cited revision is preserved in the evidence snapshot. Select its source session to open the current cycle trace.");
              }
            }} />
            </>}
            </>
          )}

          {navView === "design" && (
            <DesignLanguageView
              onNavigateView={(view) => setNavView(view)}
            />
          )}
        </main>

        {/* Footer */}
        <footer className="font-mono-tech flex flex-col justify-between gap-2 border-t border-[#252421] px-5 py-3.5 text-[8px] text-[#868278] sm:flex-row sm:items-center sm:px-8">
          <span>
            MONITOR ONLY · INTEL RECORDS · AUDITABLE OUTCOMES
          </span>
          <div className="flex flex-wrap items-center gap-4">
            <span>Displayed times: Europe/Ljubljana (UTC+01:00)</span>
          </div>
        </footer>
      </div>

      {/* Cycle Trace & Evidence Drawer */}
      <CycleDetailDrawer
        cycle={selectedCycle}
        viewMode={snapshot.viewMode}
        sessionName={snapshot.activeSession?.name ?? "No session"}
        attempts={
          selectedCycle
            ? snapshot.attempts.filter((a) => a.cycleId === selectedCycle.id)
            : []
        }
        inspections={
          selectedCycle
            ? snapshot.inspections.filter((i) => i.cycleId === selectedCycle.id)
            : []
        }
        frames={
          selectedCycle
            ? snapshot.frames.filter((f) => f.cycleId === selectedCycle.id)
            : []
        }
        nemotronObservations={
          selectedCycle
            ? snapshot.nemotronObservations.filter(
                (n) => n.cycleId === selectedCycle.id
              )
            : []
        }
        decisions={
          selectedCycle
            ? snapshot.decisions.filter((d) => d.cycleId === selectedCycle.id)
            : []
        }
        skillExecutions={
          selectedCycle
            ? snapshot.skillExecutions.filter((e) => e.cycleId === selectedCycle.id)
            : []
        }
        referenceLabel={
          selectedCycle
            ? snapshot.referenceLabels.find((r) => r.id === selectedCycle.referenceLabelId) ??
              null
            : null
        }
        confirmation={
          selectedCycle
            ? snapshot.confirmations.find(
                (cf) => cf.id === selectedCycle.confirmationId
              ) ?? null
            : null
        }
        confirmations={selectedCycle ? snapshot.confirmations.filter(record => record.cycleId === selectedCycle.id) : []}
        corrections={
          selectedCycle
            ? snapshot.corrections.filter(
                (cor) =>
                  cor.entityId === selectedCycle.id ||
                  cor.entityId === selectedCycle.referenceLabelId ||
                  selectedCycle.attemptIds.includes(cor.entityId)
              )
            : []
        }
        onClose={closeCycle}
        reviewAvailable={!isReplay && !isDisconnected && !snapshot.dataStale}
        onSubmitReview={(cycleId, request) => stationClient.reviewCycle(cycleId, request)}
        onRefresh={() => stationClient.refreshReview(selectedCycle!.id)}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 w-max max-w-[calc(100vw-2rem)] -translate-x-1/2 rounded-[5px] border border-[#6c5840] bg-[#2b271f] px-5 py-3 text-[12px] text-[#F2EEE6] shadow-lg"
        >
          {toastMessage}
        </div>
      )}
    </div>
  );
}
