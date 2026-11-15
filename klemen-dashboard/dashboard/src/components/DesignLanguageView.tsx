import React from "react";

interface DesignLanguageViewProps {
  onNavigateView: (view: "live" | "system" | "quality") => void;
}

const SWATCHES: [string, string][] = [
  ["Canvas", "#080808"],
  ["Panel", "#101010"],
  ["Hairline", "#252421"],
  ["Ink", "#F2EEE6"],
  ["Secondary", "#A7A39A"],
  ["Bronze", "#C7A477"],
  ["Verified", "#91B99C"],
  ["Fault", "#E36363"],
];

export const DesignLanguageView: React.FC<DesignLanguageViewProps> = ({
  onNavigateView,
}) => {
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            M / MORPH CONTROL ROOM
          </span>
          <h1 className="my-2 text-[30px] font-[450] leading-[1.15] tracking-[-0.055em] text-[#F2EEE6]">
            Morph design language
          </h1>
          <p className="m-0 text-[12px] text-[#A7A39A]">
            A quiet instrument for an adaptive machine.
          </p>
        </div>
        <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] px-2 py-1 text-[9px] tracking-[0.05em] text-[#F2EEE6]">
          DESIGN REFERENCE / 01
        </span>
      </div>

      {/* Hero Lockup */}
      <section className="relative flex h-[210px] items-center justify-between overflow-hidden border-b border-[#252421]">
        <div className="flex items-center gap-5">
          <img
            src="/assets/aistudio/morph-mark_854b67cd.svg"
            alt="Morph M mark"
            className="w-[84px] sm:w-[100px]"
          />
          <div>
            <strong className="block text-[38px] font-medium tracking-[0.12em] text-[#F2EEE6] sm:text-[61px]">
              MORPH
            </strong>
            <p className="m-0 text-[11px] tracking-[0.18em] text-[#C7A477]">
              THE ART OF ADAPTATION
            </p>
          </div>
        </div>
        <img
          src="/assets/aistudio/orbital_7a3f6055.svg"
          alt="Decorative orbital diagram"
          className="pointer-events-none absolute right-6 w-[540px] opacity-70"
        />
      </section>

      {/* 01 / Color */}
      <section className="mt-6">
        <h2 className="mb-4 text-[12px] font-medium text-[#F2EEE6]">
          01 / Color — neutral black, warm light, precise signals
        </h2>
        <div className="grid grid-cols-4 gap-2.5 sm:grid-cols-8">
          {SWATCHES.map(([name, hex]) => (
            <div key={name}>
              <div
                className="h-[62px] rounded-[5px] border border-[#3c3932]"
                style={{ backgroundColor: hex }}
              />
              <p className="mt-2 mb-1 text-[10px] text-[#F2EEE6]">{name}</p>
              <code className="font-mono-tech text-[9px] text-[#A7A39A]">{hex}</code>
            </div>
          ))}
        </div>
      </section>

      {/* 02 / Typography */}
      <section className="mt-6">
        <h2 className="mb-4 text-[12px] font-medium text-[#F2EEE6]">
          02 / Typography — operational clarity with one editorial accent
        </h2>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div className="border-t border-[#252421] py-4.5">
            <label className="font-mono-tech text-[9px] text-[#C7A477]">
              INTER / INTERFACE
            </label>
            <strong className="my-2 block text-[32px] font-normal tracking-[-0.03em] text-[#F2EEE6]">
              Observe. Adapt.
            </strong>
            <p className="m-0 text-[10px] text-[#A7A39A]">
              Clear navigation, controls and descriptions.
              <br />
              Regular 400 · Medium 500 · 14px body
            </p>
          </div>

          <div className="border-t border-[#252421] py-4.5">
            <label className="font-mono-tech text-[9px] text-[#C7A477]">
              SPACE MONO / EVIDENCE
            </label>
            <strong className="font-mono-tech my-2 block text-[26px] font-normal text-[#F2EEE6]">
              C-012 / 0.78
            </strong>
            <p className="m-0 text-[10px] text-[#A7A39A]">
              IDs, time, model inputs and measured values.
              <br />
              Use tabular numerals for changing metrics.
            </p>
          </div>

          <div className="border-t border-[#252421] py-4.5">
            <label className="font-mono-tech text-[9px] text-[#C7A477]">
              CORMORANT / ACCENT
            </label>
            <strong className="font-editorial my-2 block text-[37px] font-normal text-[#F2EEE6]">
              A new perspective.
            </strong>
            <p className="m-0 text-[10px] text-[#A7A39A]">
              One short decorative phrase in the masthead.
              <br />
              Never use this face for telemetry or controls.
            </p>
          </div>
        </div>
      </section>

      {/* 03 / Controls */}
      <section className="mt-6">
        <h2 className="mb-4 text-[12px] font-medium text-[#F2EEE6]">
          03 / Controls — emphasis follows consequences
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => onNavigateView("live")}
            className="min-h-[38px] rounded-[5px] border border-[#C7A477] bg-[#C7A477] px-4 py-2 text-[12px] font-semibold text-[#17130d]"
          >
            Open live inspection
          </button>
          <button
            type="button"
            onClick={() => onNavigateView("quality")}
            className="min-h-[38px] rounded-[5px] border border-[#3e3b34] px-4 py-2 text-[12px] text-[#F2EEE6] hover:bg-[#22201b]"
          >
            View evidence ↗
          </button>
          <span className="font-mono-tech inline-block rounded-[3px] border border-[#344b39] bg-[#152019] px-2 py-1 text-[9px] tracking-[0.05em] text-[#91B99C]">
            VERIFIED
          </span>
          <span className="font-mono-tech inline-block rounded-[3px] border border-[#514633] bg-[#211d16] px-2 py-1 text-[9px] tracking-[0.05em] text-[#D6B775]">
            AWAITING EVIDENCE
          </span>
          <span className="font-mono-tech inline-block rounded-[3px] border border-[#484137] bg-[#211c15] px-2 py-1 text-[9px] tracking-[0.05em] text-[#C7A477]">
            SIMULATION
          </span>
        </div>
      </section>

      {/* Principles */}
      <div className="mt-6 grid grid-cols-1 gap-6 border-t border-[#252421] pt-5 md:grid-cols-3">
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            01 / RESTRAINT
          </span>
          <p className="mt-2 text-[11px] text-[#A7A39A]">
            <b className="font-medium text-[#F2EEE6]">Art belongs in the masthead.</b>
            <br />
            Subtle Copernican geometry. Slow motion. No illustration replaces evidence.
          </p>
        </div>
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            02 / HIERARCHY
          </span>
          <p className="mt-2 text-[11px] text-[#A7A39A]">
            <b className="font-medium text-[#F2EEE6]">The current object is the focus.</b>
            <br />
            Camera first. One evidence panel. Three clear views. Details open on demand.
          </p>
        </div>
        <div>
          <span className="font-mono-tech text-[10px] tracking-[0.1em] text-[#C7A477]">
            03 / INTEGRITY
          </span>
          <p className="mt-2 text-[11px] text-[#A7A39A]">
            <b className="font-medium text-[#F2EEE6]">Unknown stays unknown.</b>
            <br />
            Show counts, sources and mode. A beautiful prototype never proves a physical
            result.
          </p>
        </div>
      </div>
    </div>
  );
};
