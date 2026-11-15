"""Bounded JPEG validation and a single replaceable, undecoded frame slot."""
from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import time
import warnings

from PIL import Image, ImageDraw, UnidentifiedImageError

from .config import Config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Frame:
    jpeg: bytes
    sequence: int
    received_mono: float
    received_at: str


class Stats:
    def __init__(self, config: Config):
        self.config = config
        self.counters = Counter({key: 0 for key in (
            "receivedMessages", "acceptedFrames", "receivedBytes", "replacedFrames", "invalidFrames",
            "oversizedFrames", "staleFrames", "submittedFrames", "submittedBytes", "publisherStarts",
            "publisherRestarts", "publisherFailures", "writeTimeouts", "sourceConnections", "sourceReconnects",
            "sourceFailures", "sourceTimeouts", "discardedOnDisconnect", "encodedFramesReported",
            "sourceCadenceSkipped", "publisherCadenceSkipped",
        )})
        self.source_state = "connecting"
        self.publisher_state = "starting"
        self.received_at: str | None = None
        self.received_mono: float | None = None
        self.last_submitted_age_ms: float | None = None
        self.last_submitted_at: str | None = None
        self.stopped = False
        self.pending_bytes = 0
        self.inflight_bytes = 0
        self.last_error: str | None = None

    def status(self, now: float | None = None) -> dict:
        now = time.monotonic() if now is None else now
        age = None if self.received_mono is None else round(max(0, now - self.received_mono) * 1000, 1)
        if self.stopped:
            state = "stopped"
        elif self.publisher_state == "failed":
            state = "failed"
        elif age is not None and age > self.config.max_receipt_age_ms:
            state = "stale" if self.source_state == "connected" else "disconnected"
        elif self.source_state != "connected":
            state = "connecting" if self.received_at is None else "disconnected"
        else:
            state = self.publisher_state
        return {
            "version": 1, "cameraId": self.config.camera_id, "streamId": self.config.stream_id,
            "sourceMode": self.config.source_mode,
            "profile": {"width": self.config.width, "height": self.config.height, "fps": self.config.fps},
            "state": state, "receivedAt": self.received_at, "receiptAgeMs": age,
            "counters": dict(self.counters),
            "encoder": self.config.encoder, "sourceState": self.source_state,
            "configuredBitrateKbps": self.config.bitrate_kbps,
            "publisherState": self.publisher_state, "captureTimestampAvailable": False,
            "lastSubmittedAt": self.last_submitted_at, "lastSubmittedReceiptAgeMs": self.last_submitted_age_ms,
            "pendingFrames": int(self.pending_bytes > 0), "pendingBytes": self.pending_bytes,
            "inflightFrames": int(self.inflight_bytes > 0), "inflightBytes": self.inflight_bytes,
            "lastErrorCode": self.last_error,
        }


def advance_deadline(previous: float, period: float, now: float) -> tuple[float, int]:
    """Keep the scheduled cadence; missed slots are skipped instead of caught up."""
    next_due = previous + period
    skipped = 0
    if next_due <= now:
        skipped = int((now - next_due) / period) + 1
        next_due += skipped * period
    return next_due, skipped


class LatestFrame:
    """One event-loop-owned pending frame. Replacing never queues older JPEGs."""
    def __init__(self, stats: Stats):
        self.stats = stats
        self.frame: Frame | None = None
        self.ready = asyncio.Event()
        self.sequence = 0

    def offer(self, jpeg: bytes, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self.sequence += 1
        received_at = utc_now()
        if self.frame is not None:
            self.stats.counters["replacedFrames"] += 1
        self.frame = Frame(jpeg, self.sequence, now, received_at)
        self.stats.received_at, self.stats.received_mono = received_at, now
        self.stats.pending_bytes = len(jpeg)
        self.stats.counters["acceptedFrames"] += 1
        self.ready.set()

    def take(self) -> Frame | None:
        frame, self.frame = self.frame, None
        self.stats.pending_bytes = 0
        self.ready.clear()
        return frame

    def clear(self) -> None:
        if self.take() is not None:
            self.stats.counters["discardedOnDisconnect"] += 1


def valid_jpeg(data: object, config: Config, stats: Stats) -> bool:
    """Check envelope/header/dimensions without decoding pixels in the receiver.

    Pillow JPEG verify checks the container, not every entropy-coded pixel. FFmpeg
    owns the one selected frame's decode and reports decode/encode failures.
    """
    stats.counters["receivedMessages"] += 1
    if not isinstance(data, bytes):
        stats.counters["invalidFrames"] += 1
        return False
    stats.counters["receivedBytes"] += len(data)
    if len(data) > config.max_jpeg_bytes:
        stats.counters["oversizedFrames"] += 1
        return False
    if len(data) < 4 or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        stats.counters["invalidFrames"] += 1
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "JPEG" or image.size != (config.width, config.height):
                    raise ValueError("Unexpected JPEG profile")
                image.verify()
    except (ValueError, OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        stats.counters["invalidFrames"] += 1
        return False
    return True


def synthetic_jpeg(width: int, height: int, sequence: int) -> bytes:
    """Changing simulation image; displayed counter is not a capture timestamp."""
    image = Image.new("RGB", (width, height), ((sequence * 11) % 192, (sequence * 7) % 160, 64))
    draw = ImageDraw.Draw(image)
    bar = sequence % max(1, width - 24)
    draw.rectangle((bar, height // 2, min(width - 1, bar + 23), height - 1), fill="white")
    draw.rectangle((0, 0, width - 1, min(height - 1, 44)), fill="black")
    draw.text((8, 7), "SIMULATION - NO CAMERA", fill="white")
    draw.text((8, 24), f"Generated frame {sequence}", fill="white")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=80)
    return output.getvalue()
