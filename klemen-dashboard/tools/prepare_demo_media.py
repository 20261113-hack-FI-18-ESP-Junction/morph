#!/usr/bin/env python3
"""Create a private gateway file from the explicit synthetic bridge generator output."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat


def private_read(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 16384:
            raise ValueError("Expected a small owner-only configuration or token file")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def prepare(runtime: Path) -> Path:
    runtime = runtime.resolve(strict=True)
    info = runtime.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Expected the private synthetic runtime directory")
    source = json.loads(private_read(runtime / "bridge.json"))
    profile = source.get("profile", {})
    status = source.get("status", {})
    if source.get("version") != 1 or source.get("sourceMode") != "simulation" or source.get("inputMode") != "synthetic" or \
        source.get("streamId") != "inspection" or source.get("cameraId") != "synthetic-inspection" or \
        source.get("publisher", {}).get("rtspUrl") != "rtsp://127.0.0.1:8554/inspection" or \
        status.get("host") != "127.0.0.1" or status.get("port") != 8790 or \
        Path(status.get("tokenFile", "")).resolve() != runtime / "status.token":
        raise ValueError("Only the generated loopback simulation topology is accepted")
    if set(profile) != {"width", "height", "fps"} or any(type(profile[k]) is not int for k in profile) or \
        not 16 <= profile["width"] <= 4096 or not 16 <= profile["height"] <= 2160 or not 1 <= profile["fps"] <= 120:
        raise ValueError("Invalid synthetic profile")
    password = private_read(runtime / "viewer-password.token").strip()
    token = private_read(runtime / "status.token").strip()
    if any(not 16 <= len(secret) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in secret) for secret in (password, token)):
        raise ValueError("Invalid generated credential")
    gateway = {"version": 1, "whepUrl": "http://127.0.0.1:8889/inspection/whep",
               "cameraId": source["cameraId"], "streamId": "inspection", "label": "Synthetic inspection preview",
               "sourceMode": "simulation", "profile": profile, "username": "morph-viewer", "password": password,
               "statusUrl": "http://127.0.0.1:8790/api/media/v1/status", "statusToken": token, "iceServers": []}
    target = runtime / "dashboard-media.json"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(gateway, stream, indent=2)
        stream.write("\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = prepare(args.runtime)
    except (ValueError, OSError, KeyError, TypeError):
        print("Could not create the private simulation gateway file. Check the generated directory; existing output is never replaced.")
        return 1
    print(json.dumps({"created": str(target), "sourceMode": "simulation", "servicesStarted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
