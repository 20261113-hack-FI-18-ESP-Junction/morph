#!/usr/bin/env python3
"""Run the existing client HTTP smoke with Linux-local tsx and a separate report."""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    source = root / "HachingJunction/station/web-client/tests/smoke_http.py"
    runner = root / "morph-station/node_modules/.bin/tsx"
    if not source.is_file() or not runner.is_file() or not os.access(runner, os.X_OK):
        parser.error("The source smoke runner and installed frontend-local tsx are required. Follow LINUX_RUNBOOK.md.")
    spec = importlib.util.spec_from_file_location("morph_portable_client_smoke", source)
    if spec is None or spec.loader is None:
        parser.error("Cannot load the source smoke runner.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.NODE = runner
    module.REPORT = (args.output or root / "verification/intel-client-http.json").resolve()
    module.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
