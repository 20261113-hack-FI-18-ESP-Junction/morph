import type { ReactNode } from "react";

export type StatusTone = "neutral" | "good" | "warn" | "bad" | "bronze";
export function StatusPill({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: StatusTone;
  dot?: boolean;
}) {
  return (
    <span className={`status-pill status-pill--${tone}`}>
      {dot && <span className="status-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
export function DataPair({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="data-pair">
      <dt>{label}</dt>
      <dd className={mono ? "font-mono-tech" : undefined}>{children}</dd>
    </div>
  );
}
export function EmptyEvidence({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="empty-evidence">
      <svg
        width="34"
        height="34"
        viewBox="0 0 34 34"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M12 4H4v8m18-8h8v8M4 22v8h8m18-8v8h-8"
          stroke="currentColor"
          strokeWidth="1.2"
        />
        <circle cx="17" cy="17" r="6" stroke="currentColor" strokeWidth="1.2" />
        <path
          d="M17 8v3m0 12v3M8 17h3m12 0h3"
          stroke="currentColor"
          strokeWidth="1.2"
        />
      </svg>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}
export function destinationLabel(value: string | null | undefined) {
  return value === "good_bin"
    ? "Good bin"
    : value === "defective_bin"
      ? "Defective bin"
      : value === "other"
        ? "Other location"
        : "Not recorded";
}
export function readableLabel(
  value: string | null | undefined,
  fallback = "Not recorded",
) {
  return value
    ? value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase())
    : fallback;
}
