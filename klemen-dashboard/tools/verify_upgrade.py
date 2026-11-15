"""Verify the separately recorded upgrade inventory without rewriting provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> int:
    package = Path(__file__).resolve().parents[1]
    root = package.parent
    manifest = json.loads((package / "verification/dashboard-upgrade-20261115/source-hashes.json").read_text())
    failures = []
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        if root not in path.parents or not path.is_file():
            failures.append(f"Missing or invalid path: {item['path']}")
            continue
        data = path.read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            failures.append(f"Changed source: {item['path']}")
    for failure in failures:
        print(failure)
    print(f"Checked {len(manifest['files'])} upgrade files; {len(failures)} differences.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
