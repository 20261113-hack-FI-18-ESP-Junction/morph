#!/usr/bin/env python3
"""Verify all sealed package files and original/derived source provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".venv", ".runtime", "__pycache__", ".pytest_cache", ".junction-setup"}


def included(path: Path) -> bool:
    return not any(part in IGNORED_PARTS for part in path.relative_to(ROOT).parts)


def safe_path(value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in value or str(relative) != value:
        raise ValueError(f"Invalid manifest path: {value}")
    target = ROOT.joinpath(*relative.parts)
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != ROOT and ROOT in parent.parents):
        raise ValueError(f"Symlink rejected: {value}")
    return target


def content(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> int:
    manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text())
    listed = {}
    errors = []
    for row in manifest["files"]:
        name = row["path"]
        if name in listed:
            errors.append(f"Duplicate manifest path: {name}")
        listed[name] = row
        path = safe_path(name)
        if not path.is_file() or content(path) != {key: row[key] for key in ("bytes", "sha256")}:
            errors.append(f"Changed or missing file: {name}")
    observed = set()
    for path in ROOT.rglob("*"):
        if not included(path):
            continue
        if path.is_symlink():
            errors.append(f"Symlink in package: {path.relative_to(ROOT)}")
        if path.is_file() and path != ROOT / "SOURCE_MANIFEST.json":
            observed.add(path.relative_to(ROOT).as_posix())
    errors += [f"Unlisted package file: {name}" for name in sorted(observed - set(listed))]
    origins = json.loads((ROOT / "SOURCE_ORIGINS.json").read_text())
    for row in origins["files"]:
        sealed = listed.get(row["path"], {})
        if any(sealed.get(key) != row[key] for key in ("bytes", "sha256", "origin")):
            errors.append(f"Provenance mismatch: {row['path']}")
    print(json.dumps({"passed": not errors, "sealedFiles": len(listed), "provenanceFiles": len(origins["files"]), "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
