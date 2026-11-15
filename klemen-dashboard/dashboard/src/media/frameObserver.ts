export interface FrameObservationOptions {
  onFrame: () => void;
  onVisibility: (visible: boolean) => void;
  document?: Pick<
    Document,
    "visibilityState" | "addEventListener" | "removeEventListener"
  >;
  setInterval?: typeof globalThis.setInterval;
  clearInterval?: typeof globalThis.clearInterval;
}

/** Observes presentation, never a connected socket or the video clock alone. */
export function observeDisplayedFrames(
  video: HTMLVideoElement,
  options: FrameObservationOptions,
): () => void {
  const page = options.document ?? document;
  const every = options.setInterval ?? globalThis.setInterval;
  const cancel = options.clearInterval ?? globalThis.clearInterval;
  let stopped = false;
  let frameHandle: number | null = null;
  let interval: ReturnType<typeof globalThis.setInterval> | null = null;
  let previousPresented: number | null = null;
  const visible = () => page.visibilityState !== "hidden";
  const visibilityChanged = () => {
    previousPresented = null;
    options.onVisibility(visible());
  };
  page.addEventListener("visibilitychange", visibilityChanged);
  visibilityChanged();

  if (typeof video.requestVideoFrameCallback === "function") {
    const next = () => {
      if (stopped) return;
      frameHandle = video.requestVideoFrameCallback(() => {
        if (stopped) return;
        if (visible()) options.onFrame();
        next();
      });
    };
    next();
  } else if (typeof video.getVideoPlaybackQuality === "function") {
    // totalVideoFrames includes displayed and dropped frames; subtract drops.
    interval = every(() => {
      if (stopped || !visible() || video.paused || video.readyState < 2) return;
      const quality = video.getVideoPlaybackQuality();
      const presented = quality.totalVideoFrames - quality.droppedVideoFrames;
      if (!Number.isFinite(presented) || presented < 0) return;
      if (previousPresented !== null && presented > previousPresented)
        options.onFrame();
      previousPresented = presented;
    }, 250);
  }

  return () => {
    stopped = true;
    page.removeEventListener("visibilitychange", visibilityChanged);
    if (frameHandle !== null) video.cancelVideoFrameCallback?.(frameHandle);
    if (interval !== null) cancel(interval);
  };
}
