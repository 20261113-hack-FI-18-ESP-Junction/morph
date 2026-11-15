#!/usr/bin/env python3
"""Check the running local dashboard, keeping the original Mac report intact."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be in the range 1–65535.")
    root = args.root.resolve()
    source = root / "HachingJunction/station/web-client/tests/smoke_dashboard.py"
    if not source.is_file():
        parser.error("The bundled source dashboard smoke runner is missing.")
    spec = importlib.util.spec_from_file_location("morph_portable_dashboard_smoke", source)
    if spec is None or spec.loader is None:
        parser.error("Cannot load the source dashboard smoke runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ORIGIN = f"http://127.0.0.1:{args.port}"
    module.REPORT = (args.output or root / "verification/intel-dashboard-http.json").resolve()
    module.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
