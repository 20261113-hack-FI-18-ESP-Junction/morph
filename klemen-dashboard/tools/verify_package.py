"""Verify the portable source package against its reconciliation inventory."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "SOURCE_RECONCILIATION.json"
GENERATED = {"node_modules", "dist", ".npm-cache", ".venv", "__pycache__", ".pytest_cache"}


def main():
    manifest = json.loads((ROOT / MANIFEST).read_text())
    entries = manifest["inventory"]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    errors = []
    if hashlib.sha256(canonical).hexdigest() != manifest["inventorySha256"]:
        errors.append("Inventory checksum differs")
    expected = {entry["path"]: entry for entry in entries}
    if len(expected) != len(entries) or entries != sorted(entries, key=lambda item: item["path"]):
        errors.append("Inventory is duplicated or unsorted")
    found = set()
    for file in ROOT.rglob("*"):
        relative = file.relative_to(ROOT)
        if any(part in GENERATED for part in relative.parts) or relative.as_posix() == MANIFEST:
            continue
        if file.is_symlink():
            errors.append(f"Unexpected symlink: {relative}")
            continue
        if not file.is_file():
            continue
        name = relative.as_posix()
        found.add(name)
        entry = expected.get(name)
        data = file.read_bytes()
        if entry is None or entry["bytes"] != len(data) or entry["sha256"] != hashlib.sha256(data).hexdigest():
            errors.append(f"Unexpected or changed file: {name}")
    errors.extend(f"Missing file: {name}" for name in sorted(set(expected) - found))
    for imported in manifest["imports"]:
        entry = expected.get(imported["path"])
        if entry is None or entry["sha256"] != imported["packagedSha256"]:
            errors.append(f"Imported file inventory differs: {imported['path']}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "files": len(entries), "imports": len(manifest["imports"]),
                      "inventorySha256": manifest["inventorySha256"],
                      "manifestSha256": hashlib.sha256((ROOT / MANIFEST).read_bytes()).hexdigest()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
