#!/usr/bin/env python3
"""Explicit synthetic RTSP soak on separate loopback ports; owns and cleans its children."""
from __future__ import annotations

import argparse
import asyncio
from collections import deque
import contextlib
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from morph_media_bridge.config import Config
from morph_media_bridge.frames import LatestFrame, Stats, synthetic_jpeg, valid_jpeg
from morph_media_bridge.publisher import FFmpegPublisher, publish_latest
from morph_media_bridge.source import receive_synthetic
from tools.prepare_synthetic import prepare


def ports_free() -> None:
    for port, kind in ((18554, socket.SOCK_STREAM), (18889, socket.SOCK_STREAM), (18189, socket.SOCK_DGRAM)):
        with socket.socket(socket.AF_INET, kind) as probe:
            probe.bind(("127.0.0.1", port))


async def stop_process(process) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), 2)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


async def verify(args, directory: Path) -> dict:
    ports_free()
    private = directory / "private"
    prepare(private, args.ffmpeg)
    config_path = private / "bridge.json"
    data = json.loads(config_path.read_text())
    data["profile"]["fps"] = 30
    data["publisher"]["rtspUrl"] = "rtsp://127.0.0.1:18554/inspection"
    data["status"]["port"] = 18790
    config = Config.parse(data, private)
    media = private / "mediamtx.yml"
    media.write_text(media.read_text().replace(":8554", ":18554").replace(":8889", ":18889").replace(":8189", ":18189"))
    log_path = private / "media.log"
    media_log = log_path.open("wb")
    process = await asyncio.create_subprocess_exec(args.mediamtx, str(media), cwd=private,
        stdout=media_log, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
    stats, stop = Stats(config), asyncio.Event()
    gap_window = [float("inf"), float("inf")]
    gap_drops = [0]
    class PausedSlot(LatestFrame):
        def offer(self, jpeg, now=None):
            if gap_window[0] <= time.monotonic() < gap_window[1]:
                gap_drops[0] += 1
                return
            super().offer(jpeg, now)
    slot = PausedSlot(stats)
    diagnostics = deque(maxlen=30)
    source_task = publisher_task = None
    samples, owned_encoder_pids = [], []
    class ObservedPublisher(FFmpegPublisher):
        async def start(self):
            await super().start()
            owned_encoder_pids.append(self.process.pid)

        async def write(self, jpeg):
            if args.jitter and self.stats.counters["submittedFrames"] % 2 == 0:
                # Deliberate bounded scheduling jitter; the following scheduled tick
                # can be nearer than a full 1/fps interval without any queue growth.
                await asyncio.sleep(0.025)
            await super().write(jpeg)

        async def _read_progress(self):
            # Fixture-only observation; production never exposes raw encoder stderr.
            assert self.process and self.process.stderr
            while line := await self.process.stderr.readline():
                if line.startswith(b"frame="):
                    with contextlib.suppress(ValueError):
                        count = int(line[6:].strip())
                        if count >= self.reported_frames:
                            self.stats.counters["encodedFramesReported"] += count - self.reported_frames
                            self.reported_frames = count
                            if count:
                                self.stats.publisher_state = "streaming"
                elif line.startswith(b"[") or b"error" in line.lower():
                    # These commands contain only the fixed local RTSP path, no credential.
                    diagnostics.append(line.decode("utf-8", errors="replace").strip()[:700])
                    self.stats.last_error = "encoder-diagnostic"
    started = time.monotonic()
    cleanup = {}
    try:
        for _ in range(50):
            if process.returncode is not None:
                raise RuntimeError("Isolated MediaMTX exited before listening")
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", 18554)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError("Isolated MediaMTX did not listen")
        source_task = asyncio.create_task(receive_synthetic(config, slot, stats, stop))
        publisher_task = asyncio.create_task(publish_latest(config, slot, stats, stop, ObservedPublisher))
        started = time.monotonic()
        if args.gap_seconds:
            gap_window[:] = [started + args.duration / 2, started + args.duration / 2 + args.gap_seconds]
        while time.monotonic() - started < args.duration:
            await asyncio.sleep(min(1, args.duration - (time.monotonic() - started)))
            sample = stats.status()
            sample["elapsedSeconds"] = round(time.monotonic() - started, 3)
            samples.append(sample)
            if len(samples) % 15 == 0:
                print(json.dumps({"elapsedSeconds": sample["elapsedSeconds"], "counters": sample["counters"]}), flush=True)
    finally:
        stop.set()
        tasks = [task for task in (source_task, publisher_task) if task]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await stop_process(process)
        media_log.close()
        cleanup["mediaProcessExited"] = process.returncode is not None
        cleanup["encoderProcessesExited"] = True
        for pid in owned_encoder_pids:
            try:
                os.kill(pid, 0)
                cleanup["encoderProcessesExited"] = False
            except ProcessLookupError:
                pass
        try:
            ports_free()
            cleanup["portsReleased"] = True
        except OSError:
            cleanup["portsReleased"] = False
    final = stats.status()
    return {"checkedAt": datetime.now(timezone.utc).isoformat(), "sourceMode": "simulation",
            "durationSeconds": round(time.monotonic() - started, 3), "profile": final["profile"],
            "alternatingWriteJitterMs": 25 if args.jitter else 0,
            "deliberateSourceGapSeconds": args.gap_seconds, "generatedFramesSuppressedForGap": gap_drops[0],
            "final": final, "samples": samples, "encoderDiagnostics": list(diagnostics),
            "passed": final["counters"]["publisherFailures"] == 0 and final["counters"]["publisherStarts"] == 1
            and final["counters"]["encodedFramesReported"] > args.duration * 25 and all(cleanup.values()),
            "cleanup": cleanup, "realCameraOpened": False,
            "networkScope": "new separate loopback RTSP18554/WHEP18889/mediaUDP18189 only",
            "mediaBinarySha256": hashlib.sha256(Path(args.mediamtx).read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mediamtx", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--duration", type=float, default=120)
    parser.add_argument("--jitter", action="store_true", help="Exercise timestamp rounding with alternating25ms write delay")
    parser.add_argument("--gap-seconds", type=float, default=0, help="Suppress source frames at the middle of the synthetic run")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.duration <= 600:
        parser.error("duration must be 1..600 seconds")
    if not 0 <= args.gap_seconds < args.duration / 4:
        parser.error("gap-seconds must be nonnegative and less than one quarter of duration")
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="morph-media-soak-") as temporary:
        result = asyncio.run(verify(args, Path(temporary)))
    result["cleanup"]["privateRuntimeRemoved"] = not Path(temporary).exists()
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "result": str(args.output / "result.json"), "encoderDiagnostics": result["encoderDiagnostics"]}), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
