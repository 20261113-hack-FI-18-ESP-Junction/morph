import React from "react";
import type { SoftwareStopRecord } from "../types/morph.ts";

interface SoftwareStopDialogProps {
  open: boolean;
  stopRecord: SoftwareStopRecord | null;
  activeCycleId: string | null;
  canSimulateAck: boolean;
  onSimulateAck: () => void;
  onExportIncident: () => void;
  onClose: () => void;
}

export const SoftwareStopDialog: React.FC<SoftwareStopDialogProps> = ({
  open,
  stopRecord,
  activeCycleId,
  canSimulateAck,
  onSimulateAck,
  onExportIncident,
  onClose,
}) => {
  if (!open || !stopRecord) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/82 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="stop-dialog-title"
    >
      <div className="w-full max-w-[520px] rounded-[12px] border border-[#453a2d] bg-[#121210] p-7 text-[#F2EEE6] shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <span
            className="grid h-11 w-11 place-items-center rounded-[9px] bg-[#321718] text-[20px] text-[#E36363]"
            aria-hidden="true"
          >
            ■
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close stop status"
            className="px-2 py-1 text-[26px] leading-none text-[#A7A39A] hover:text-[#F2EEE6]"
          >
            ×
          </button>
        </div>

        <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#E36363] uppercase">
          SOFTWARE STOP · {stopRecord.mode === "simulation" ? "SIMULATED" : "LIVE CONTROLLER"}
        </span>
        <h2
          id="stop-dialog-title"
          className="my-2.5 text-[32px] font-normal tracking-[-0.04em] text-[#F2EEE6]"
        >
          Stop requested.
        </h2>
        <p className="text-[12px] text-[#A7A39A]">
          The request has been recorded. Physical halt is not yet verified.
        </p>

        <div className="my-6 border-t border-[#252421] text-[11px]">
          <div className="flex items-center justify-between gap-3 border-b border-[#252421] py-3">
            <span className="text-[#A7A39A]">Request ID</span>
            <b className="font-mono-tech font-normal text-[#F2EEE6]">{stopRecord.requestId}</b>
          </div>
          <div className="flex items-center justify-between gap-3 border-b border-[#252421] py-3">
            <span className="text-[#A7A39A]">Request sent</span>
            <b className="font-normal text-[#91B99C]">{stopRecord.requestSentText}</b>
          </div>
          <div className="flex items-center justify-between gap-3 border-b border-[#252421] py-3">
            <span className="text-[#A7A39A]">Controller acknowledgment</span>
            <b
              className={`font-normal ${
                stopRecord.controllerAcknowledged ? "text-[#91B99C]" : "text-[#F2EEE6]"
              }`}
            >
              {stopRecord.controllerStateText}
            </b>
          </div>
          <div className="flex items-center justify-between gap-3 border-b border-[#252421] py-3">
            <span className="text-[#A7A39A]">Physical motion stopped</span>
            <b
              className={`font-normal ${
                stopRecord.physicalHaltVerified ? "text-[#91B99C]" : "text-[#D6B775]"
              }`}
            >
              {stopRecord.physicalHaltText}
            </b>
          </div>
        </div>

        <div className="rounded-[4px] border border-[#603332] bg-[#231614] px-3.5 py-2.5 text-[11px] text-[#F2EEE6]">
          For an immediate physical emergency, use the station’s physical stop procedure. This
          software request does not disconnect actuator power or engage hardware brakes.
        </div>

        <p className="mt-3 text-[11px] text-[#A7A39A]">
          {activeCycleId ? `Cycle ${activeCycleId}` : "Active cycle"} remains in progress or
          unverified until an outcome is recorded. Closing this dialog never resumes the run.
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onExportIncident}
              className="min-h-[38px] rounded-[5px] border border-[#3e3b34] px-4 py-2 text-[12px] text-[#F2EEE6] hover:bg-[#22201b]"
            >
              Export incident JSON
            </button>
            {canSimulateAck && !stopRecord.controllerAcknowledged && (
              <button
                type="button"
                onClick={onSimulateAck}
                className="min-h-[38px] rounded-[5px] border border-[#484137] bg-[#1a1916] px-3 py-2 text-[11px] text-[#C7A477] hover:bg-[#22201b]"
              >
                Simulate controller ack
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="min-h-[38px] rounded-[5px] border border-[#C7A477] bg-[#C7A477] px-4 py-2 text-[12px] font-semibold text-[#17130d] hover:opacity-90"
          >
            Close status
          </button>
        </div>
      </div>
    </div>
  );
};
