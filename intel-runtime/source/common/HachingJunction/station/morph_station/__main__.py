"""Intentional local initialization, demo seeding, serving and API requests."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from .api import create_app, data_directory, load_token, token_file
from .store import StationStore, StoreError


def initialize() -> Path:
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if "MORPH_API_TOKEN" not in os.environ:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(secrets.token_urlsafe(48) + "\n")
    load_token()
    db = Path(os.environ.get("MORPH_DB_PATH", directory / "station.sqlite3"))
    StationStore(db, evidence_dir=Path(os.environ.get("MORPH_EVIDENCE_DIR", db.parent / "evidence")))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Morph M06 local records API; no hardware or provider dispatch.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init", help="Initialize the local database and a private token file; print no token.")
    serve = subcommands.add_parser("serve", help="Serve existing data without seeding or movement.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    seed = subcommands.add_parser("seed-demo", help="Explicitly add deterministic, labeled simulation records.")
    seed.add_argument("--prefix", default="demo")
    call = subcommands.add_parser("request", help="Call an API route using the token file without printing the token.")
    call.add_argument("path", help="An /api/v1/... path; quote query strings in the shell.")
    call.add_argument("--method", choices=["GET", "POST"], default="GET")
    call.add_argument("--body", type=Path, help="JSON request body file.")
    call.add_argument("--output", type=Path, help="Save the response bytes to this path.")
    call.add_argument("--url", default="http://127.0.0.1:8000", help="Explicit station base URL.")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            path = initialize()
            print(f"Local records initialized. Token source: {'MORPH_API_TOKEN' if 'MORPH_API_TOKEN' in os.environ else path}")
            print("No simulation was seeded; no hardware or provider connection was started.")
        elif args.command == "serve":
            import uvicorn

            uvicorn.run(create_app(), host=args.host, port=args.port)
        elif args.command == "seed-demo":
            from .simulation import seed_demo

            load_token()
            directory = data_directory()
            db = Path(os.environ.get("MORPH_DB_PATH", directory / "station.sqlite3"))
            store = StationStore(db, evidence_dir=Path(os.environ.get("MORPH_EVIDENCE_DIR", db.parent / "evidence")))
            print(json.dumps(seed_demo(store, prefix=args.prefix), ensure_ascii=False, indent=2))
        else:
            from .client import request

            body = args.body.read_bytes() if args.body else None
            result = request(args.path, method=args.method, body=body, base_url=args.url)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(result)
                print(f"Response saved to {args.output}")
            else:
                sys.stdout.buffer.write(result)
                if result and not result.endswith(b"\n"):
                    sys.stdout.buffer.write(b"\n")
        return 0
    except (ValueError, OSError, StoreError) as exc:
        message = exc.detail if isinstance(exc, StoreError) else str(exc)
        print(f"Morph: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
