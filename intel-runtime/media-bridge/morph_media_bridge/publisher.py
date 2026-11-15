"""Bounded input to exactly one owned software H.264 encoder subprocess."""
from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time

from .config import Config
from .frames import LatestFrame, Stats, advance_deadline, utc_now
from .source import wait_or_stop


def ffmpeg_command(config: Config, *, validation_output: str | None = None) -> list[str]:
    command = [config.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-nostats", "-xerror",
               "-progress", "pipe:2", "-stats_period", "0.2", "-f", "image2pipe", "-framerate", str(config.fps),
               "-c:v", "mjpeg", "-err_detect", "explode", "-probesize", "32", "-analyzeduration", "0",
               "-use_wallclock_as_timestamps", "1", "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
               "-profile:v", "baseline", "-pix_fmt", "yuv420p", "-bf", "0",
               "-b:v", f"{config.bitrate_kbps}k", "-maxrate", f"{config.bitrate_kbps}k",
               "-bufsize", f"{max(32, config.bitrate_kbps // 5)}k",
               "-g", str(config.fps), "-keyint_min", str(config.fps), "-sc_threshold", "0",
               # Re-stamp at the selected frame's decode/filter arrival with fine clock
               # precision. image2pipe's wallclock packet PTS is quantized to 1/fps.
               # A one-tick clamp also handles equal/backward local wall-clock values.
               "-vf", "settb=expr=1/90000,setpts='if(eq(N,0),0,max(PREV_OUTPTS+1,(RTCTIME-RTCSTART)/(1000000*TB)))'",
               "-enc_time_base:v", "1:90000",
               "-fps_mode", "passthrough", "-flush_packets", "1"]
    if validation_output is not None:
        output_format = "matroska" if validation_output.endswith(".mkv") else "h264"
        return command + ["-f", output_format, "-y", validation_output]
    return command + ["-rtsp_transport", "tcp", "-f", "rtsp", config.rtsp_url]


class FFmpegPublisher:
    def __init__(self, config: Config, stats: Stats):
        self.config, self.stats = config, stats
        self.process: asyncio.subprocess.Process | None = None
        self.stderr_task: asyncio.Task | None = None
        self.reported_frames = 0

    async def start(self) -> None:
        if self.process is not None:
            raise RuntimeError("Publisher already owns a process")
        launching = asyncio.create_task(asyncio.create_subprocess_exec(
            *ffmpeg_command(self.config), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            start_new_session=True, limit=8192))
        try:
            self.process = await asyncio.shield(launching)
        except asyncio.CancelledError:
            # A cancellation during process creation must still collect and close the child.
            self.process = await launching
            await self.close()
            raise
        assert self.process.stdin is not None
        # Do not keep a Python transport backlog of several small JPEGs.
        self.process.stdin.transport.set_write_buffer_limits(high=0, low=0)
        self.reported_frames = 0
        self.stderr_task = asyncio.create_task(self._read_progress())
        self.stats.counters["publisherStarts"] += 1
        self.stats.publisher_state = "starting"

    async def _read_progress(self) -> None:
        assert self.process and self.process.stderr
        try:
            while line := await self.process.stderr.readline():
                # No raw stderr/URLs/credentials enter HTTP, files or logs.
                if line.startswith(b"frame="):
                    with contextlib.suppress(ValueError):
                        count = int(line[6:].strip())
                        if count >= self.reported_frames:
                            self.stats.counters["encodedFramesReported"] += count - self.reported_frames
                            self.reported_frames = count
                            if count > 0:
                                self.stats.publisher_state = "streaming"
                elif line.startswith(b"[av") or b"Error" in line or b"error" in line:
                    self.stats.last_error = "encoder-diagnostic"
        except (ValueError, OSError):
            self.stats.last_error = "encoder-progress-invalid"

    async def write(self, jpeg: bytes) -> None:
        if self.process is None or self.process.returncode is not None or self.process.stdin is None:
            raise BrokenPipeError("Owned encoder is unavailable")
        self.process.stdin.write(jpeg)
        await self.process.stdin.drain()
        if self.process.returncode is not None:
            raise BrokenPipeError("Owned encoder exited")

    async def close(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        # Each encoder has a new process group, so only this bridge's children are signaled.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), 1)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await asyncio.wait_for(process.wait(), 1)
        finally:
            # Also remove descendants after an early parent exit.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            if process.stdin:
                process.stdin.close()
            if self.stderr_task:
                self.stderr_task.cancel()
                await asyncio.gather(self.stderr_task, return_exceptions=True)
                self.stderr_task = None


async def publish_latest(config: Config, slot: LatestFrame, stats: Stats, stop: asyncio.Event,
                         publisher_factory=FFmpegPublisher) -> None:
    delay = config.reconnect_min_ms / 1000
    publisher = None
    started_once = False
    next_due = time.monotonic()
    try:
        while not stop.is_set():
            if publisher is None:
                publisher = publisher_factory(config, stats)
                try:
                    await publisher.start()
                    if started_once:
                        stats.counters["publisherRestarts"] += 1
                    started_once = True
                except (OSError, RuntimeError):
                    stats.counters["publisherFailures"] += 1
                    stats.publisher_state = "failed"
                    stats.last_error = "encoder-start-failed"
                    await publisher.close()
                    publisher = None
                    if await wait_or_stop(stop, delay):
                        break
                    delay = min(delay * 2, config.reconnect_max_ms / 1000)
                    continue
            # Throttle before selecting, allowing the source to replace older pending frames.
            if await wait_or_stop(stop, max(0, next_due - time.monotonic())):
                break
            try:
                await asyncio.wait_for(slot.ready.wait(), 0.1)
            except TimeoutError:
                # Detect an encoder exit even when source traffic has stopped.
                process = getattr(publisher, "process", None)
                if process is not None and process.returncode is not None:
                    stats.publisher_state = "failed"
                    stats.last_error = "encoder-exited"
                    stats.counters["publisherFailures"] += 1
                    await publisher.close()
                    publisher = None
                    if await wait_or_stop(stop, delay):
                        break
                    delay = min(delay * 2, config.reconnect_max_ms / 1000)
                continue
            frame = slot.take()
            if frame is None:
                continue
            age_ms = max(0, time.monotonic() - frame.received_mono) * 1000
            if age_ms > config.max_receipt_age_ms:
                stats.counters["staleFrames"] += 1
                continue
            stats.inflight_bytes = len(frame.jpeg)
            try:
                # At most one selected JPEG can be in the pipe write/drain operation.
                write_budget = min(config.write_timeout_ms, config.max_receipt_age_ms - age_ms) / 1000
                await asyncio.wait_for(publisher.write(frame.jpeg), write_budget)
                stats.counters["submittedFrames"] += 1
                stats.counters["submittedBytes"] += len(frame.jpeg)
                stats.last_submitted_age_ms = round(max(0, time.monotonic() - frame.received_mono) * 1000, 1)
                stats.last_submitted_at = utc_now()
                if stats.publisher_state == "streaming":
                    delay = config.reconnect_min_ms / 1000
            except (TimeoutError, OSError, RuntimeError) as error:
                stats.counters["publisherFailures"] += 1
                stats.publisher_state = "failed"
                stats.last_error = "encoder-write-failed"
                # A stalled partial JPEG must never remain for a later viewer/frame.
                if isinstance(error, TimeoutError):
                    stats.counters["writeTimeouts"] += 1
                    stats.last_error = "encoder-write-timeout"
                await publisher.close()
                publisher = None
                if await wait_or_stop(stop, delay):
                    break
                delay = min(delay * 2, config.reconnect_max_ms / 1000)
            finally:
                stats.inflight_bytes = 0
            next_due, skipped = advance_deadline(next_due, 1 / config.fps, time.monotonic())
            stats.counters["publisherCadenceSkipped"] += skipped
    finally:
        if publisher is not None:
            await publisher.close()
        stats.inflight_bytes = 0
        stats.publisher_state = "stopped"
