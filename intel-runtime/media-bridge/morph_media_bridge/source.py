"""One source connection for the bridge lifetime, independent of viewer count."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import time

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidHandshake, InvalidURI

from .config import Config, private_token
from .frames import LatestFrame, Stats, advance_deadline, synthetic_jpeg, valid_jpeg


async def wait_or_stop(stop: asyncio.Event, seconds: float) -> bool:
    if stop.is_set():
        return True
    if seconds <= 0:
        return False
    try:
        await asyncio.wait_for(stop.wait(), seconds)
        return True
    except TimeoutError:
        return False


async def receive_studio(config: Config, slot: LatestFrame, stats: Stats, stop: asyncio.Event,
                         connector: Callable = connect) -> None:
    headers = None
    if config.studio_token_file:
        headers = {"Authorization": "Bearer " + private_token(config.studio_token_file)}
    delay = config.reconnect_min_ms / 1000
    attempted = False
    while not stop.is_set():
        if attempted:
            stats.counters["sourceReconnects"] += 1
        attempted = True
        stats.source_state = "connecting"
        accepted = 0
        try:
            # max_queue bounds WS message framing; our application slot remains one JPEG.
            async with connector(config.studio_url, additional_headers=headers, proxy=None,
                                 compression=None, max_size=config.max_jpeg_bytes, max_queue=1,
                                 open_timeout=3, close_timeout=1, ping_interval=10, ping_timeout=5) as ws:
                stats.counters["sourceConnections"] += 1
                stats.source_state = "connected"
                while not stop.is_set():
                    try:
                        message = await asyncio.wait_for(ws.recv(), config.source_timeout_ms / 1000)
                    except TimeoutError:
                        stats.counters["sourceTimeouts"] += 1
                        raise
                    if valid_jpeg(message, config, stats):
                        slot.offer(message)
                        accepted += 1
                        # A sustained connection resets backoff; one-frame flapping doesn't.
                        if accepted >= config.fps:
                            delay = config.reconnect_min_ms / 1000
        except asyncio.CancelledError:
            raise
        except (OSError, TimeoutError, ConnectionClosed, InvalidHandshake, InvalidURI, RuntimeError) as error:
            stats.counters["sourceFailures"] += 1
            # Oversize messages closed by websockets never reach valid_jpeg.
            if isinstance(error, ConnectionClosedError) and error.sent and error.sent.code == 1009:
                stats.counters["oversizedFrames"] += 1
            stats.last_error = "source-timeout" if isinstance(error, TimeoutError) else "source-unavailable"
        finally:
            stats.source_state = "disconnected"
            slot.clear()
        if await wait_or_stop(stop, delay):
            return
        delay = min(delay * 2, config.reconnect_max_ms / 1000)


async def receive_synthetic(config: Config, slot: LatestFrame, stats: Stats, stop: asyncio.Event) -> None:
    stats.source_state = "connected"
    stats.counters["sourceConnections"] += 1
    sequence = 0
    next_due = time.monotonic()
    try:
        while not stop.is_set():
            if await wait_or_stop(stop, max(0, next_due - time.monotonic())):
                break
            sequence += 1
            # This source is intentionally generated; never opens Studio or a device.
            jpeg = synthetic_jpeg(config.width, config.height, sequence)
            if valid_jpeg(jpeg, config, stats):
                slot.offer(jpeg)
            next_due, skipped = advance_deadline(next_due, 1 / config.fps, time.monotonic())
            stats.counters["sourceCadenceSkipped"] += skipped
    finally:
        stats.source_state = "disconnected"
        slot.clear()
