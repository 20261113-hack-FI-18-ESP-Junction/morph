import React from "react";
import { formatTimestamp, DISPLAY_TIME_ZONE } from "./EvidenceImage.tsx";
import type { StationSnapshot } from "../types/morph.ts";

interface RobotSystemViewProps {
  snapshot: StationSnapshot;
}

export const RobotSystemView: React.FC<RobotSystemViewProps> = ({ snapshot }) => {
  return (
    <div>
      {/* Page Heading */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            02 / MORPH CONTROL ROOM
          </span>
          <h1 className="my-2 text-[30px] font-[450] leading-[1.15] tracking-[-0.055em] text-[#F2EEE6]">
            Robot &amp; system
          </h1>
          <p className="m-0 text-[12px] text-[#A7A39A]">
            Keep connection state separate from physical confirmation.
          </p>
        </div>
        <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] bg-[#211c15] px-2 py-1 text-[9px] tracking-[0.05em] text-[#C7A477]">
          {snapshot.viewMode === "live"
            ? "LIVE RECORDS"
            : snapshot.viewMode === "replay"
            ? "REPLAY"
            : "PERSISTED SIMULATION"}
        </span>
      </div>

      <div role="status" className="mb-5 rounded-[5px] border border-[#403c32] bg-[#15140f] px-4 py-3 text-[11px] text-[#A7A39A]">
        Records API: {snapshot.dataConnection} · {snapshot.dataStale ? "Saved values may be stale" : "Records current"}.
        <span className="mt-1 block">Last refresh: {formatTimestamp(snapshot.receivedAt)} · {DISPLAY_TIME_ZONE}. Physical connection: unavailable.</span>
      </div>

      {/* Main Two-Column System Grid */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.12fr_1fr]">
        {/* Left: Integration Status */}
        <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
          <div className="flex items-center justify-between border-b border-[#252421] px-5 py-4">
            <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
              Integration status
            </h2>
            <span className="font-mono-tech inline-block rounded-[3px] border border-[#33332f] bg-[#1c1c1a] px-2 py-1 text-[9px] tracking-[0.05em] text-[#b8b4ab]">
              ACCESS UNVERIFIED
            </span>
          </div>

          <div className="p-5">
            <p className="mb-4 rounded-[4px] border border-[#332c22] bg-[#151410] px-3.5 py-2.5 text-[11px] text-[#A7A39A]">
              These are the selected components. Live account access and physical execution
              have not been verified.
            </p>

            <div>
              {snapshot.components.map((comp, idx) => (
                <div
                  key={comp.id}
                  className={`flex items-center justify-between gap-5 py-4 ${
                    idx < snapshot.components.length - 1
                      ? "border-b border-[#252421]"
                      : "pb-0"
                  } ${idx === 0 ? "pt-0" : ""}`}
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <b className="text-[12px] font-medium text-[#F2EEE6]">{comp.name}</b>
                      <span className="font-mono-tech text-[9px] text-[#8c887e]">
                        [{comp.capabilityStatus.toUpperCase()} ·{" "}
                        {comp.deploymentLocation === "local_station"
                          ? "LOCAL STATION"
                          : "CLOUD API"}
                        ]
                      </span>
                    </div>
                    <p className="mt-1 mb-0 text-[10px] text-[#A7A39A]">
                      {comp.roleDescription}
                    </p>
                    <p className="font-mono-tech mt-0.5 mb-0 text-[9px] text-[#78746a]">
                      Identity: {comp.configuredIdentity}
                    </p>
                    {comp.latestError && (
                      <p className="mt-1 mb-0 text-[10px] text-[#D6B775]">
                        Note: {comp.latestError}
                      </p>
                    )}
                  </div>
                  <span className="font-mono-tech shrink-0 rounded-[3px] border border-[#33332f] bg-[#1c1c1a] px-2 py-1 text-[8px] tracking-[0.05em] text-[#b8b4ab]">
                    {comp.statusBadgeText}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Right: Arm Telemetry & Hardware Summary */}
        <div>
          <section className="overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
            <div className="flex items-center justify-between border-b border-[#252421] px-5 py-4">
              <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
                Arm telemetry
              </h2>
              <span className="font-mono-tech text-[9px] text-[#A7A39A]">
                NO LIVE CONNECTION
              </span>
            </div>

            <div className="p-5">
              <p className="mb-4 rounded-[4px] border border-[#332c22] bg-[#151410] px-3.5 py-2.5 text-[11px] text-[#A7A39A]">
                Joint values appear only after the controller supplies names, units and
                measured values.
              </p>

              <table className="w-full border-collapse text-[11px]">
                <thead>
                  <tr>
                    <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                      Joint
                    </th>
                    <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                      Measured
                    </th>
                    <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                      Requested
                    </th>
                    <th className="border-b border-[#252421] px-3 py-2.5 text-left text-[9px] font-normal text-[#A7A39A]">
                      Deviation
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.joints.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-[#A7A39A]">Unavailable — no measured joint telemetry supplied.</td></tr>}
                  {snapshot.joints.map((j, idx) => (
                    <tr key={j.jointName}>
                      <td
                        className={`px-3 py-3 text-[#F2EEE6] ${
                          idx < snapshot.joints.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {j.jointName}
                        {j.isPlaceholderName ? "*" : ""}
                      </td>
                      <td
                        className={`px-3 py-3 text-[#A7A39A] ${
                          idx < snapshot.joints.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {j.measured.value === null
                          ? "Unavailable"
                          : `${j.measured.value} ${j.measured.unit}`}
                      </td>
                      <td
                        className={`px-3 py-3 text-[#A7A39A] ${
                          idx < snapshot.joints.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {j.commanded.value === null
                          ? "Unavailable"
                          : `${j.commanded.value} ${j.commanded.unit}`}
                      </td>
                      <td
                        className={`px-3 py-3 text-[#A7A39A] ${
                          idx < snapshot.joints.length - 1
                            ? "border-b border-[#252421]"
                            : ""
                        }`}
                      >
                        {j.deviation.value === null ? "—" : `${j.deviation.value}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <p className="mt-3 mb-0 text-[11px] text-[#A7A39A]">
                {snapshot.joints.some((joint) => joint.isPlaceholderName) ? "*Display placeholders; no measured controller schema available." : "Names and values are shown only when supplied by the controller."}
              </p>
            </div>
          </section>

          {/* Hardware Summary */}
          <div className="mt-5 grid grid-cols-3 gap-5">
            <div className="border-t border-[#252421] pt-4">
              <label className="text-[10px] text-[#A7A39A]">CPU load</label>
              <strong className="font-mono-tech my-1 block text-[22px] font-normal text-[#F2EEE6]">
                —
              </strong>
              <p className="m-0 text-[10px] text-[#A7A39A]">Unavailable</p>
            </div>
            <div className="border-t border-[#252421] pt-4">
              <label className="text-[10px] text-[#A7A39A]">Memory</label>
              <strong className="font-mono-tech my-1 block text-[22px] font-normal text-[#F2EEE6]">
                —
              </strong>
              <p className="m-0 text-[10px] text-[#A7A39A]">Unavailable</p>
            </div>
            <div className="border-t border-[#252421] pt-4">
              <label className="text-[10px] text-[#A7A39A]">Control rate</label>
              <strong className="font-mono-tech my-1 block text-[22px] font-normal text-[#F2EEE6]">
                —
              </strong>
              <p className="m-0 text-[10px] text-[#A7A39A]">Unavailable</p>
            </div>
          </div>

          <div className="mt-5 rounded-[5px] border border-[#403c32] bg-[#15140f] px-4 py-3.5 text-[11px] text-[#A7A39A]">
            Motor temperature, current, force and GPU/NPU utilization remain unavailable
            until measured by a supported source.
          </div>
        </div>
      </div>

      {/* Execution Boundary Panel */}
      <section className="mt-5 overflow-hidden rounded-[8px] border border-[#252421] bg-[#101010]">
        <div className="flex items-center justify-between border-b border-[#252421] px-5 py-4">
          <h2 className="m-0 text-[13px] font-medium tracking-[-0.015em] text-[#F2EEE6]">
            Planned execution boundary
          </h2>
          <span className="font-mono-tech text-[9px] text-[#A7A39A]">
            DISPATCH UNAVAILABLE · RECORD EVENT SEQUENCE {snapshot.lastEventSequence}
          </span>
        </div>

        <div className="p-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="border-b border-[#252421] pb-3 md:border-r md:border-b-0 md:pr-4 md:pb-0">
              <label className="font-mono-tech text-[9px] text-[#C7A477]">
                01 / VALIDATE
              </label>
              <p className="my-1.5 text-[11px] text-[#d4d0c7]">
                Goal + state version · frame freshness
              </p>
              <small className="block text-[10px] text-[#A7A39A]">
                Deadline · permitted task · preconditions
              </small>
            </div>

            <div className="border-b border-[#252421] pb-3 md:border-r md:border-b-0 md:pr-4 md:pb-0">
              <label className="font-mono-tech text-[9px] text-[#C7A477]">
                02 / DISPATCH
              </label>
              <p className="my-1.5 text-[11px] text-[#d4d0c7]">
                One unique execution ID
              </p>
              <small className="block text-[10px] text-[#A7A39A]">
                Supported learned skill on the Intel station
              </small>
            </div>

            <div>
              <label className="font-mono-tech text-[9px] text-[#C7A477]">
                03 / VERIFY
              </label>
              <p className="my-1.5 text-[11px] text-[#d4d0c7]">
                Sent → acknowledged → finished → verified
              </p>
              <small className="block text-[10px] text-[#A7A39A]">
                Confirmation source required for physical success
              </small>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
