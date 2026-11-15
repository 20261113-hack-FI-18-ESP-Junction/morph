#!/usr/bin/env python3
"""Create private, synthetic-only local configuration; does not start services."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]


def write_private(path: Path, content: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def prepare(directory: Path, ffmpeg: str = "ffmpeg") -> dict:
    directory = directory.resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    status_token, viewer_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    config = json.loads((ROOT / "examples/synthetic.json").read_text())
    config["publisher"]["ffmpeg"] = ffmpeg
    config["status"]["tokenFile"] = str(directory / "status.token")
    config["runtimeDir"] = str(directory / "bridge")
    write_private(directory / "status.token", status_token + "\n")
    write_private(directory / "viewer-password.token", viewer_password + "\n")
    write_private(directory / "bridge.json", json.dumps(config, indent=2) + "\n")
    media = (ROOT / "examples/mediamtx-local.yml").read_text().replace("REPLACE_WITH_PRIVATE_GENERATED_PASSWORD", viewer_password)
    write_private(directory / "mediamtx.yml", media)
    return {"created": True, "sourceMode": "simulation", "directory": str(directory),
            "bridgeConfig": str(directory / "bridge.json"), "mediaConfig": str(directory / "mediamtx.yml"),
            "viewerUsername": "morph-viewer", "viewerPasswordFile": str(directory / "viewer-password.token"),
            "statusTokenFile": str(directory / "status.token"), "servicesStarted": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="New private directory; existing directory is rejected")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    print(json.dumps(prepare(args.directory, args.ffmpeg)))


if __name__ == "__main__":
    main()
