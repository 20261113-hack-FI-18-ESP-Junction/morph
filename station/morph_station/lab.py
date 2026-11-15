"""Run the explicitly isolated Mac integration lab on loopback."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets

import uvicorn

from .control_api import create_control_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / ".data/mac-lab")
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    token_path = args.data_dir / "lab-token"
    if not token_path.exists():
        descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(secrets.token_urlsafe(36))
    if token_path.is_symlink() or token_path.stat().st_mode & 0o077:
        raise SystemExit("Lab token must be a regular owner-only file.")
    app = create_control_app(args.data_dir / "lab.sqlite3", token_path.read_text().strip(), enable_browser_lab=True)
    print(f"Morph simulation lab: http://127.0.0.1:{args.port}/lab")
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
