import React, { useEffect, useRef, useState } from "react";
import { Radio, RefreshCw, Video, WifiOff } from "lucide-react";
import { LiveMediaClient } from "../media/client.ts";
import { observeDisplayedFrames } from "../media/frameObserver.ts";
import {
  initialMediaState,
  type MediaSourceMode,
  type MediaStatus,
} from "../media/types.ts";
import { StatusPill, type StatusTone } from "./DashboardPrimitives.tsx";
import "./LiveVideoPanel.css";

const statusLabels: Record<MediaStatus, string> = {
  unconfigured: "Not configured",
  connecting: "Connecting",
  live: "Frames arriving",
  frozen: "Frozen",
  disconnected: "Disconnected",
  error: "Connection error",
};
const statusTone = (status: MediaStatus): StatusTone =>
  status === "live"
    ? "good"
    : status === "frozen" || status === "connecting"
      ? "warn"
      : status === "error"
        ? "bad"
        : "neutral";
const measured = (value: number | null, unit: string, decimals = 1) =>
  value === null
    ? "Unavailable"
    : `${value.toLocaleString(undefined, { maximumFractionDigits: decimals })} ${unit}`;

export function LiveVideoPanel({
  sourceMode,
  selectedSessionName = null,
}: {
  sourceMode: MediaSourceMode;
  selectedSessionName?: string | null;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const observerRef = useRef<(() => void) | null>(null);
  const clientRef = useRef<LiveMediaClient | null>(null);
  const [state, setState] = useState(initialMediaState);
  const [playbackError, setPlaybackError] = useState(false);

  useEffect(() => {
    let mounted = true;
    if (!clientRef.current) {
      clientRef.current = new LiveMediaClient({
        onStream: (stream) => {
          observerRef.current?.();
          observerRef.current = null;
          const video = videoRef.current;
          if (!video) return;
          video.srcObject = stream;
          if (!stream) {
            video.pause();
            return;
          }
          observerRef.current = observeDisplayedFrames(video, {
            onFrame: () => clientRef.current?.noteDisplayedFrame(),
            onVisibility: (visible) =>
              clientRef.current?.setDisplayVisible(visible),
          });
          void video.play().catch(() => {
            if (video.srcObject === stream) setPlaybackError(true);
          });
        },
      });
    }
    const client = clientRef.current;
    const unsubscribe = client.subscribe(() => {
      if (mounted) setState(client.getState());
    });
    setPlaybackError(false);
    void client.connect(sourceMode);
    return () => {
      mounted = false;
      unsubscribe();
      observerRef.current?.();
      observerRef.current = null;
      void client.dispose();
    };
  }, [sourceMode]);

  const configuration = state.configuration;
  const statistics = state.statistics;
  const empty =
    state.status === "unconfigured" ||
    state.status === "error" ||
    state.status === "connecting";
  const frameAge =
    state.frameAgeMs === null
      ? "No displayed frame observed"
      : `Last displayed frame ${measured(state.frameAgeMs / 1000, "s", 1)} ago`;
  const reconnect = () => {
    setPlaybackError(false);
    void clientRef.current?.connect(sourceMode);
  };

  return (
    <section
      className="dashboard-panel live-video-panel"
      aria-label="Current camera preview"
    >
      <div className="panel-heading">
        <div className="panel-title">
          <Video size={16} />
          <h2>Camera preview</h2>
        </div>
        <div className="live-video-badges">
          <StatusPill tone={sourceMode === "simulation" ? "bronze" : "neutral"}>
            {sourceMode === "simulation"
              ? "Simulation video"
              : "Live camera source"}
          </StatusPill>
          <span role="status">
            <StatusPill tone={statusTone(state.status)} dot>
              {statusLabels[state.status]}
            </StatusPill>
          </span>
        </div>
      </div>

      <div className="live-video-layout">
        <div
          className={`live-video-viewport${state.status === "live" ? " is-streaming" : ""}`}
        >
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            aria-label={`${sourceMode === "simulation" ? "Simulation" : "Live camera"} video preview`}
          />
          {state.status !== "live" && (
            <div className={`live-video-overlay${empty ? " is-empty" : ""}`}>
              {state.status === "disconnected" ? (
                <WifiOff size={24} />
              ) : (
                <Video size={24} />
              )}
              <strong>{statusLabels[state.status]}</strong>
              <p>
                {state.reason ?? "Checking the independent preview connection."}
              </p>
            </div>
          )}
          <div className="live-video-source-label">
            <Radio size={11} />
            {sourceMode === "simulation"
              ? "SIMULATION VIDEO SOURCE"
              : "CURRENT CAMERA VIEW"}
          </div>
        </div>

        <div className="live-video-information">
          <div className="live-video-identity">
            <span className="eyebrow">INDEPENDENT MEDIA CONNECTION</span>
            <h3>{configuration?.label || "Station preview"}</h3>
            <p>
              {selectedSessionName
                ? `Current preview continues independently of selected session “${selectedSessionName}”. This is not saved footage from that session. `
                : "Current video is separate from the exact analyzed snapshot below. "}
              Preview frames do not confirm a physical outcome.
            </p>
          </div>

          <dl className="live-video-metrics">
            <div>
              <dt>Decoded video</dt>
              <dd>{measured(statistics.decodedFps, "FPS")}</dd>
            </div>
            <div>
              <dt>Received video bitrate</dt>
              <dd>
                {measured(
                  statistics.bitrateBps === null
                    ? null
                    : statistics.bitrateBps / 1000,
                  "kbit/s",
                  0,
                )}
              </dd>
            </div>
            <div>
              <dt>Packet loss · last interval</dt>
              <dd>{measured(statistics.packetLossPercent, "%")}</dd>
              {statistics.lostPackets !== null &&
                statistics.receivedPackets !== null && (
                  <small>
                    {statistics.lostPackets} lost /{" "}
                    {statistics.lostPackets + statistics.receivedPackets}{" "}
                    packets
                  </small>
                )}
            </div>
            <div>
              <dt>Mean jitter-buffer residence</dt>
              <dd>{measured(statistics.jitterBufferMs, "ms")}</dd>
            </div>
            <div>
              <dt>Network round-trip time</dt>
              <dd>{measured(statistics.roundTripMs, "ms")}</dd>
            </div>
            <div>
              <dt>Negotiated codec</dt>
              <dd>{statistics.codec ?? "Unavailable"}</dd>
            </div>
          </dl>

          <div className="live-video-freshness">
            <span>
              {state.displayVisible
                ? frameAge
                : "Display freshness paused while this tab is hidden"}
            </span>
            <p>
              Metrics sample the browser receiver about once per second.
              Round-trip time and buffer residence are not camera-to-display
              latency.
            </p>
          </div>

          {configuration?.profile && (
            <p className="live-video-profile">
              Configured publisher profile · {configuration.profile.width} ×{" "}
              {configuration.profile.height} · {configuration.profile.fps} FPS
            </p>
          )}

          <div className="live-video-actions">
            <button
              type="button"
              className="quiet-button"
              onClick={reconnect}
              disabled={state.status === "connecting"}
              aria-busy={state.status === "connecting"}
            >
              <RefreshCw
                size={13}
                className={
                  state.status === "connecting"
                    ? "live-video-updating"
                    : undefined
                }
              />
              {state.status === "connecting"
                ? "Connecting video…"
                : state.status === "unconfigured"
                  ? "Check preview"
                  : "Reconnect video"}
            </button>
            {playbackError && (
              <button
                type="button"
                className="quiet-button"
                onClick={() => {
                  void videoRef.current
                    ?.play()
                    .then(() => setPlaybackError(false))
                    .catch(() => setPlaybackError(true));
                }}
              >
                Resume playback
              </button>
            )}
          </div>
          {playbackError && (
            <p role="alert" className="live-video-playback-error">
              The browser paused playback. Resume to observe new frames.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
