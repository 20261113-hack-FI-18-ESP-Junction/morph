import { emptyStatistics, type MediaStatistics } from "./types.ts";

type ReportRow = Record<string, unknown>;
export interface InboundSample {
  id: string;
  timestamp: number;
  bytes: number | null;
  frames: number | null;
  received: number | null;
  lost: number | null;
  jitterDelay: number | null;
  jitterCount: number | null;
}

const numeric = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;
const delta = (
  current: number | null,
  previous: number | null,
): number | null =>
  current !== null && previous !== null && current >= previous
    ? current - previous
    : null;

/** Rates use consecutive samples of the same inbound video stream. */
export function readMediaStatistics(
  report: RTCStatsReport,
  previous: InboundSample | null,
): {
  statistics: MediaStatistics;
  sample: InboundSample | null;
} {
  const rows: ReportRow[] = [];
  report.forEach((row) => rows.push(row as unknown as ReportRow));
  const inbound = rows.find(
    (row) =>
      row.type === "inbound-rtp" &&
      (row.kind === "video" || row.mediaType === "video"),
  );
  const statistics = emptyStatistics();
  if (
    !inbound ||
    typeof inbound.id !== "string" ||
    numeric(inbound.timestamp) === null
  )
    return { statistics, sample: null };
  const sample: InboundSample = {
    id: inbound.id,
    timestamp: inbound.timestamp as number,
    bytes: numeric(inbound.bytesReceived),
    frames: numeric(inbound.framesDecoded),
    received: numeric(inbound.packetsReceived),
    lost: numeric(inbound.packetsLost),
    jitterDelay: numeric(inbound.jitterBufferDelay),
    jitterCount: numeric(inbound.jitterBufferEmittedCount),
  };
  statistics.decodedFps = numeric(inbound.framesPerSecond);
  const codec = rows.find(
    (row) => row.id === inbound.codecId && row.type === "codec",
  );
  statistics.codec =
    typeof codec?.mimeType === "string" ? codec.mimeType : null;
  const transport = rows.find(
    (row) => row.type === "transport" && row.id === inbound.transportId,
  );
  const pair = rows.find(
    (row) =>
      row.type === "candidate-pair" &&
      row.id === transport?.selectedCandidatePairId,
  );
  const rtt = numeric(pair?.currentRoundTripTime);
  statistics.roundTripMs = rtt === null ? null : rtt * 1000;
  if (
    !previous ||
    previous.id !== sample.id ||
    sample.timestamp <= previous.timestamp
  )
    return { statistics, sample };
  const seconds = (sample.timestamp - previous.timestamp) / 1000;
  const bytes = delta(sample.bytes, previous.bytes);
  const frames = delta(sample.frames, previous.frames);
  statistics.bitrateBps = bytes === null ? null : (bytes * 8) / seconds;
  statistics.decodedFps ??= frames === null ? null : frames / seconds;
  statistics.receivedPackets = delta(sample.received, previous.received);
  statistics.lostPackets = delta(sample.lost, previous.lost);
  if (statistics.receivedPackets !== null && statistics.lostPackets !== null) {
    const total = statistics.receivedPackets + statistics.lostPackets;
    statistics.packetLossPercent =
      total > 0 ? (statistics.lostPackets / total) * 100 : null;
  }
  const jitterDelay = delta(sample.jitterDelay, previous.jitterDelay);
  const jitterCount = delta(sample.jitterCount, previous.jitterCount);
  statistics.jitterBufferMs =
    jitterDelay !== null && jitterCount !== null && jitterCount > 0
      ? (jitterDelay / jitterCount) * 1000
      : null;
  return { statistics, sample };
}
