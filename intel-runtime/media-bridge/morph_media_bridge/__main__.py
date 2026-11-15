"""Explicit preflight/run commands. Importing this package opens no device or port."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys

from .config import Config, ConfigError, private_token
from .frames import LatestFrame, Stats, utc_now
from .http_status import StatusServer
from .publisher import publish_latest
from .source import receive_studio, receive_synthetic


def preflight(config: Config) -> dict:
    """Local-only inspection; never contacts Studio, MediaMTX or hardware."""
    private_token(config.status_token_file)
    if config.studio_token_file:
        private_token(config.studio_token_file)
    executable = shutil.which(config.ffmpeg)
    if executable is None:
        raise ConfigError("Configured FFmpeg executable is unavailable")
    try:
        result = subprocess.run([executable, "-hide_banner", "-encoders"], capture_output=True,
                                timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ConfigError("FFmpeg preflight failed") from None
    if result.returncode or not any(line.split()[1:2] == [b"libx264"] for line in result.stdout.splitlines()):
        raise ConfigError("FFmpeg does not advertise required libx264 encoder; no fallback is allowed")
    return {"ok": True, "checkedAt": utc_now(), "inputMode": config.input_mode,
            "sourceMode": config.source_mode, "cameraId": config.camera_id, "streamId": config.stream_id,
            "encoder": config.encoder, "networkContacted": False, "hardwareOpened": False}


class InstanceLock:
    def __init__(self, directory: Path):
        self.directory, self.stream = directory, None

    def __enter__(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ConfigError("runtimeDir must be an owner-only directory")
        fd = os.open(self.directory / "bridge.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        self.stream = os.fdopen(fd, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stream.close()
            raise ConfigError("A bridge already owns this runtimeDir") from None
        self.stream.write(str(os.getpid()))
        self.stream.flush()
        return self

    def __exit__(self, *args):
        if self.stream:
            self.stream.close()


def write_final_status(config: Config, stats: Stats) -> None:
    path = config.runtime_dir / "last-status.json.tmp"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(stats.status(), stream, indent=2, allow_nan=False)
        stream.write("\n")
    path.replace(config.runtime_dir / "last-status.json")


async def run(config: Config, duration: float | None = None) -> dict:
    stats, stop = Stats(config), asyncio.Event()
    slot = LatestFrame(stats)
    server = StatusServer(config, stats)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    source_task = publisher_task = stopper = None
    failed = False
    try:
        await server.start()
        receiver = receive_synthetic if config.input_mode == "synthetic" else receive_studio
        source_task = asyncio.create_task(receiver(config, slot, stats, stop))
        publisher_task = asyncio.create_task(publish_latest(config, slot, stats, stop))
        stopper = asyncio.create_task(stop.wait())
        tasks = {source_task, publisher_task, stopper}
        done, _ = await asyncio.wait(tasks, timeout=duration, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is not stopper and not task.cancelled() and task.exception() is not None:
                failed = True
                stats.last_error = "bridge-task-failed"
    finally:
        stop.set()
        # Cancellation promptly interrupts recv/drain/backoff; their finally blocks own cleanup.
        active = [task for task in (source_task, publisher_task, stopper) if task is not None]
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        await server.close()
        slot.clear()
        stats.stopped = True
        write_final_status(config, stats)
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
    result = stats.status()
    result["exitReason"] = "task-failed" if failed else "stopped"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit Studio JPEG to local H.264 media bridge")
    parser.add_argument("command", choices=("preflight", "run"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--duration", type=float, help="Stop after this many seconds (explicit local QA)")
    args = parser.parse_args(argv)
    try:
        if args.duration is not None and not 0 < args.duration <= 86400:
            raise ConfigError("duration must be greater than zero and at most 86400 seconds")
        config = Config.load(args.config)
        check = preflight(config)
        if args.command == "preflight":
            print(json.dumps(check))
            return 0
        with InstanceLock(config.runtime_dir):
            result = asyncio.run(run(config, args.duration))
        # Deliberately contains no URL, camera fingerprint, token or subprocess command.
        print(json.dumps(result, allow_nan=False))
        return 1 if result["exitReason"] == "task-failed" else 0
    except (ConfigError, OSError) as error:
        # OS errors can contain arbitrary paths. Keep this channel bounded and sanitized.
        print(str(error) if isinstance(error, ConfigError) else "Cannot start configured bridge", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
