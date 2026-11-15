"""Strict, operator-owned configuration. No camera discovery or implicit defaults."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import stat
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit


class ConfigError(ValueError):
    pass


def keys(value: object, allowed: set[str], required: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ConfigError(f"Invalid or missing {name} fields")
    return value


def integer(value: object, low: int, high: int, name: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ConfigError(f"{name} must be an integer from {low} to {high}")
    return value


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ConfigError(f"Invalid {name}")
    return value


def loopback(host: str | None) -> bool:
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def private_token(path: Path) -> str:
    """Read without following the final symlink; never include token bytes in errors."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
                raise ConfigError("Token file must be an owner-only regular file")
            value = stream.read(513).strip()
    except OSError:
        raise ConfigError("Cannot read private token file") from None
    if not 32 <= len(value) <= 256 or not re.fullmatch(rb"[A-Za-z0-9_~-]+", value):
        raise ConfigError("Token must contain 32 to 256 URL-safe characters")
    return value.decode("ascii")


@dataclass(frozen=True)
class Config:
    camera_id: str
    stream_id: str
    source_mode: str
    input_mode: str
    width: int
    height: int
    fps: int
    studio_url: str | None
    studio_token_file: Path | None
    ffmpeg: str
    rtsp_url: str
    encoder: str
    bitrate_kbps: int
    max_jpeg_bytes: int
    max_receipt_age_ms: int
    write_timeout_ms: int
    source_timeout_ms: int
    reconnect_min_ms: int
    reconnect_max_ms: int
    status_host: str
    status_port: int
    status_token_file: Path
    runtime_dir: Path

    @classmethod
    def load(cls, path: Path) -> "Config":
        try:
            if path.stat().st_size > 32768:
                raise ConfigError("Configuration exceeds 32 KiB")
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ConfigError("Cannot read configuration JSON") from None
        return cls.parse(data, path.resolve().parent)

    @classmethod
    def parse(cls, raw: object, base: Path) -> "Config":
        required = {"version", "cameraId", "streamId", "sourceMode", "inputMode", "profile", "publisher", "status", "runtimeDir"}
        data = keys(raw, required | {"studio", "limits"}, required, "configuration")
        if type(data["version"]) is not int or data["version"] != 1:
            raise ConfigError("Configuration version must be 1")
        camera_id, stream_id = (identifier(data[name], name) for name in ("cameraId", "streamId"))
        mode, input_mode = data["sourceMode"], data["inputMode"]
        if mode not in ("live", "simulation") or input_mode not in ("studio", "synthetic"):
            raise ConfigError("Explicit sourceMode and inputMode are required")
        if input_mode == "synthetic" and mode != "simulation":
            raise ConfigError("Synthetic input must be labeled simulation")
        profile = keys(data["profile"], {"width", "height", "fps"}, {"width", "height", "fps"}, "profile")
        width = integer(profile["width"], 32, 1920, "width")
        height = integer(profile["height"], 32, 1080, "height")
        fps = integer(profile["fps"], 1, 60, "fps")
        if width % 2 or height % 2:
            raise ConfigError("H.264 profile dimensions must be even")

        def local_path(value: object, name: str) -> Path:
            if not isinstance(value, str) or not value or "\x00" in value:
                raise ConfigError(f"Invalid {name}")
            candidate = Path(value).expanduser()
            return candidate if candidate.is_absolute() else base / candidate

        studio_url, studio_token = None, None
        if input_mode == "studio":
            studio = keys(data.get("studio"), {"baseUrl", "camera", "tokenFile"}, {"baseUrl", "camera"}, "Studio")
            url = urlsplit(str(studio["baseUrl"]))
            if url.scheme not in ("ws", "wss") or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
                raise ConfigError("Studio baseUrl must be an explicit ws/wss origin without credentials")
            if not loopback(url.hostname):
                raise ConfigError("Initial topology requires Studio on a literal loopback address")
            camera = keys(studio["camera"], {"name", "hardware_name", "driver", "fingerprint", "payload"}, {"name", "hardware_name", "driver", "fingerprint", "payload"}, "Studio camera")
            if any(not isinstance(camera[key], str) or not camera[key] for key in ("name", "hardware_name", "driver")):
                raise ConfigError("Studio camera names and driver must be explicit")
            if not isinstance(camera["fingerprint"], dict) or not camera["fingerprint"]:
                raise ConfigError("Studio camera fingerprint must be explicit")
            payload = keys(camera["payload"], {"width", "height", "fps"}, {"width", "height", "fps"}, "Studio camera payload")
            for key, high in (("width", 1920), ("height", 1080), ("fps", 60)):
                integer(payload[key], 1, high, f"Studio {key}")
            # Preserve the exact existing capture profile; never silently change ownership/profile.
            if payload["width"] != width or payload["height"] != height or payload["fps"] < fps:
                raise ConfigError("Output dimensions must match Studio; output fps cannot exceed capture fps")
            studio_url = studio["baseUrl"].rstrip("/") + "/api/cameras/ws?" + urlencode({"camera": json.dumps(camera, separators=(",", ":"))})
            if "tokenFile" in studio:
                studio_token = local_path(studio["tokenFile"], "Studio tokenFile")
                if url.scheme == "ws" and not loopback(url.hostname):
                    raise ConfigError("Remote authenticated Studio subscriptions require wss")
        elif "studio" in data:
            raise ConfigError("Synthetic input must not include Studio configuration")
        pub = keys(data["publisher"], {"ffmpeg", "rtspUrl", "encoder", "bitrateKbps"}, {"ffmpeg", "rtspUrl", "encoder"}, "publisher")
        if pub["encoder"] != "libx264":
            raise ConfigError("Only tested software libx264 is supported; hardware requires a separate reviewed adapter")
        if not isinstance(pub["ffmpeg"], str) or not pub["ffmpeg"] or "\x00" in pub["ffmpeg"]:
            raise ConfigError("Explicit ffmpeg executable is required")
        rtsp = urlsplit(str(pub["rtspUrl"]))
        if rtsp.scheme != "rtsp" or not loopback(rtsp.hostname) or rtsp.username or rtsp.password or rtsp.query or rtsp.fragment or rtsp.path != "/" + stream_id:
            raise ConfigError("Publisher must target a credential-free literal loopback RTSP URL for streamId")
        try:
            integer(rtsp.port, 1, 65535, "RTSP port")
        except ValueError:
            raise ConfigError("Explicit valid RTSP port is required") from None
        status = keys(data["status"], {"host", "port", "tokenFile"}, {"host", "port", "tokenFile"}, "status")
        if not isinstance(status["host"], str) or not loopback(status["host"]):
            raise ConfigError("Status must bind to a literal loopback address; proxy remote access securely")
        limits = keys(data.get("limits", {}), {"maxJpegBytes", "maxReceiptAgeMs", "writeTimeoutMs", "sourceTimeoutMs", "reconnectMinMs", "reconnectMaxMs"}, set(), "limits")
        settings = [integer(limits.get(name, default), low, high, name) for name, default, low, high in (
            ("maxJpegBytes", 2097152, 4096, 4194304), ("maxReceiptAgeMs", 300, 50, 5000),
            ("writeTimeoutMs", 250, 25, 5000), ("sourceTimeoutMs", 3000, 100, 30000),
            ("reconnectMinMs", 250, 25, 5000), ("reconnectMaxMs", 5000, 100, 30000))]
        if settings[4] > settings[5]:
            raise ConfigError("Reconnect minimum exceeds maximum")
        return cls(camera_id, stream_id, mode, input_mode, width, height, fps, studio_url, studio_token,
                   pub["ffmpeg"], pub["rtspUrl"], pub["encoder"], integer(pub.get("bitrateKbps", 1500), 128, 20000, "bitrateKbps"), *settings, status["host"],
                   integer(status["port"], 1, 65535, "status port"), local_path(status["tokenFile"], "status tokenFile"),
                   local_path(data["runtimeDir"], "runtimeDir"))
