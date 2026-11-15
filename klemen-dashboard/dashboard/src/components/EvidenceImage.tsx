import { useEffect, useState } from "react";

export const DISPLAY_TIME_ZONE = "Europe/Ljubljana";

export function formatTimestamp(value: string | null | undefined, includeDate = true): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "Unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: DISPLAY_TIME_ZONE,
    ...(includeDate ? { day: "2-digit", month: "short", year: "numeric" } as const : {}),
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).format(new Date(value));
}

interface EvidenceImageProps { src?: string | null; alt: string; className?: string }

/** The same-origin evidence proxy supplies image bytes without a browser token. */
export function EvidenceImage({ src, alt, className = "h-full w-full object-contain" }: EvidenceImageProps) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const localEvidence = Boolean(src && /^\/api\/v1\/evidence\/[A-Za-z0-9_.%:-]+$/.test(src));
  if (!localEvidence || failed) return (
    <div role="img" aria-label={`${alt}: unavailable`} className="flex h-full min-h-[60px] w-full items-center justify-center p-3 text-center text-[11px] text-[#A7A39A]">
      {failed ? "Evidence image unavailable" : "No image evidence"}
    </div>
  );
  return <img src={src!} alt={alt} className={className} onError={() => setFailed(true)} />;
}
