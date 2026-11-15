import React from "react";
import { Activity, Cpu, Database, Radio, ShieldCheck } from "lucide-react";
import { formatTimestamp, DISPLAY_TIME_ZONE } from "./EvidenceImage.tsx";
import { DataPair, StatusPill, readableLabel } from "./DashboardPrimitives.tsx";
import type { StationSnapshot, TelemetryValue } from "../types/morph.ts";

interface RobotSystemViewProps {
  snapshot: StationSnapshot;
}
const measurement = (value: TelemetryValue) =>
  value.value === null
    ? "Unavailable"
    : `${value.value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${value.unit}`;

export const RobotSystemView: React.FC<RobotSystemViewProps> = ({
  snapshot,
}) => {
  const isReplay = snapshot.viewMode === "replay";
  const connected =
    snapshot.dataConnection === "connected" && !snapshot.dataStale;
  const joints = snapshot.joints.filter((joint) => !joint.isPlaceholderName);
  const hardware = [
    { label: "CPU load", record: snapshot.hardwareSummary.cpuLoad },
    { label: "Memory", record: snapshot.hardwareSummary.memory },
    { label: "Control rate", record: snapshot.hardwareSummary.controlRate },
  ];
  return (
    <div>
      <div className="view-heading">
        <div>
          <span className="eyebrow">02 / SYSTEM OBSERVABILITY</span>
          <h1>
            Robot &amp; system<span className="heading-period">.</span>
          </h1>
          <p>Connection health, recorded identities and measured telemetry.</p>
        </div>
        <StatusPill
          tone={isReplay ? "bronze" : connected ? "good" : "warn"}
          dot
        >
          {isReplay
            ? "Saved replay"
            : connected
              ? "Records connected"
              : "Records not current"}
        </StatusPill>
      </div>

      <div className="system-grid">
        <div className="system-stack">
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div className="panel-title">
                <Database size={16} />
                <h2>Records connection</h2>
              </div>
              <StatusPill>
                {isReplay
                  ? "Frozen snapshot"
                  : readableLabel(snapshot.dataConnection, "Unavailable")}
              </StatusPill>
            </div>
            <dl className="connection-facts">
              <DataPair label="Data source">
                {snapshot.sourceMode === "simulation"
                  ? "Persisted simulation"
                  : "Intel station records"}
              </DataPair>
              <DataPair label="Session">
                {snapshot.activeSession?.name ?? "No session received"}
              </DataPair>
              <DataPair label="Last received">
                {formatTimestamp(snapshot.receivedAt)} · {DISPLAY_TIME_ZONE}
              </DataPair>
              <DataPair label="Event connection">
                {isReplay
                  ? "Paused during replay"
                  : readableLabel(snapshot.eventConnection, "Unavailable")}
              </DataPair>
              <DataPair label="Record sequence" mono>
                {snapshot.receivedAt
                  ? snapshot.lastEventSequence
                  : "Unavailable"}
              </DataPair>
              <DataPair label="Record scope">
                {isReplay
                  ? "Saved replay"
                  : snapshot.recordScope === "session"
                    ? "Saved complete session"
                    : "Current object and recent cycles"}
              </DataPair>
            </dl>
            <p className="system-note">
              Connection health describes the records feed. Robot connection and
              physical outcome confirmation are tracked separately.
            </p>
          </section>

          <section className="dashboard-panel">
            <div className="panel-heading">
              <div className="panel-title">
                <Radio size={16} />
                <h2>Component availability</h2>
              </div>
              <StatusPill>Capability status</StatusPill>
            </div>
            <div className="component-list">
              {snapshot.components.map((component) => (
                <div className="component-row" key={component.id}>
                  <div>
                    <strong>{component.name}</strong>
                    <p>{component.roleDescription}</p>
                    <small>{component.configuredIdentity}</small>
                    {component.latestError && (
                      <p className="text-bad">{component.latestError}</p>
                    )}
                  </div>
                  <StatusPill
                    tone={
                      component.capabilityStatus === "verified"
                        ? "good"
                        : component.connectionState === "error"
                          ? "bad"
                          : "neutral"
                    }
                  >
                    {readableLabel(component.capabilityStatus)}
                  </StatusPill>
                </div>
              ))}
            </div>
            <p className="system-note">
              Stored model runs document individual requests. They do not
              establish current provider access or a working physical
              integration.
            </p>
          </section>
        </div>

        <div className="system-stack">
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div className="panel-title">
                <ShieldCheck size={16} />
                <h2>Recorded station identity</h2>
              </div>
            </div>
            <dl className="connection-facts">
              <DataPair label="Robot ID" mono>
                {snapshot.activeSession?.robotId ?? "Not recorded"}
              </DataPair>
              <DataPair label="Configuration" mono>
                {snapshot.activeSession?.configId ?? "Not recorded"}
              </DataPair>
              <DataPair label="Session started">
                {formatTimestamp(snapshot.activeSession?.startedAt)}
              </DataPair>
              <DataPair label="Session ended">
                {snapshot.activeSession
                  ? snapshot.activeSession.endedAt
                    ? formatTimestamp(snapshot.activeSession.endedAt)
                    : "Open session"
                  : "Not recorded"}
              </DataPair>
              <DataPair label="Physical connection">
                {snapshot.stationConnected
                  ? "Reported connected"
                  : "Unavailable"}
              </DataPair>
              <DataPair label="Robot control">
                {snapshot.canControl ? "Available" : "Unavailable in this view"}
              </DataPair>
              <DataPair label="Active goal">
                {snapshot.goalState.activeGoal
                  ? snapshot.goalState.activeGoalLabel
                  : "Unavailable"}
              </DataPair>
            </dl>
          </section>

          <section className="dashboard-panel">
            <div className="panel-heading">
              <div className="panel-title">
                <Activity size={16} />
                <h2>Arm telemetry</h2>
              </div>
              <StatusPill>
                {joints.some((joint) => joint.measured.value !== null)
                  ? "Measured values"
                  : "Unavailable"}
              </StatusPill>
            </div>
            {joints.length ? (
              <div className="telemetry-table-wrap">
                <table className="telemetry-table">
                  <thead>
                    <tr>
                      <th scope="col">Joint</th>
                      <th scope="col">Measured</th>
                      <th scope="col">Requested</th>
                      <th scope="col">Deviation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {joints.map((joint) => (
                      <tr key={joint.jointName}>
                        <td>{joint.jointName}</td>
                        <td>
                          {measurement(joint.measured)}
                          {joint.measured.state === "stale" && " · stale"}
                        </td>
                        <td>{measurement(joint.commanded)}</td>
                        <td>{measurement(joint.deviation)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="telemetry-empty">
                <h3>No measured joint data.</h3>
                <p>
                  Joint names, positions and requested values will appear when a
                  controller supplies measurements with units and timestamps.
                </p>
              </div>
            )}
          </section>

          <section className="dashboard-panel">
            <div className="panel-heading">
              <div className="panel-title">
                <Cpu size={16} />
                <h2>Compute &amp; timing telemetry</h2>
              </div>
            </div>
            <div className="hardware-values">
              {hardware.map((item) => (
                <div key={item.label}>
                  <span className="field-label">{item.label}</span>
                  <strong>
                    {item.record.value === null
                      ? "—"
                      : measurement(item.record)}
                  </strong>
                  <small>
                    {item.record.value === null
                      ? "Unavailable"
                      : `${readableLabel(item.record.state)} · ${formatTimestamp(item.record.measuredAt, false)}`}
                  </small>
                </div>
              ))}
            </div>
            <p className="system-note">
              Motor temperature, current, force and GPU/NPU utilization are
              unavailable until a supported source supplies measurements.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};
