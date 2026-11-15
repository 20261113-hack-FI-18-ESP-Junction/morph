export type MediaSourceMode = "live" | "simulation";
export type MediaStatus =
  | "unconfigured"
  | "connecting"
  | "live"
  | "frozen"
  | "disconnected"
  | "error";

export interface MediaConfiguration {
  version: 1;
  configured: boolean;
  cameraId: string | null;
  label: string;
  streamId: string | null;
  sourceMode: MediaSourceMode;
  profile: { width: number; height: number; fps: number } | null;
  whepPath: "/api/media/v1/whep" | null;
  iceServers: RTCIceServer[];
  producer: {
    state: string;
    receivedAt: string | null;
    receiptAgeMs: number | null;
    counters: Record<string, number>;
  } | null;
  reason: string | null;
  checkedAt: string;
}

export interface MediaStatistics {
  decodedFps: number | null;
  bitrateBps: number | null;
  lostPackets: number | null;
  receivedPackets: number | null;
  packetLossPercent: number | null;
  jitterBufferMs: number | null;
  roundTripMs: number | null;
  codec: string | null;
}

export interface MediaState {
  status: MediaStatus;
  configuration: MediaConfiguration | null;
  reason: string | null;
  frameAgeMs: number | null;
  displayVisible: boolean;
  statistics: MediaStatistics;
}

export const emptyStatistics = (): MediaStatistics => ({
  decodedFps: null,
  bitrateBps: null,
  lostPackets: null,
  receivedPackets: null,
  packetLossPercent: null,
  jitterBufferMs: null,
  roundTripMs: null,
  codec: null,
});

export const initialMediaState = (): MediaState => ({
  status: "unconfigured",
  configuration: null,
  reason: null,
  frameAgeMs: null,
  displayVisible: true,
  statistics: emptyStatistics(),
});
