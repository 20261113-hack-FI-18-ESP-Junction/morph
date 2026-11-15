#!/usr/bin/env python3
"""Create a portable, scoped context snapshot with hashes; exclude private connection data."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from store import ContextStore, MAX_ASSET_BYTES, now

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--output", type=Path)
args = parser.parse_args()
store = ContextStore(args.root)
output = args.output or store.root / "dist" / "morph-context.zip"
output.parent.mkdir(parents=True, exist_ok=True)
manifest = {"created_at": now(), "mode": "portable snapshot; not automatic synchronization", "excluded": ["credentials", ".junction-setup", "native chat databases", "temporary files", "outside-workspace attachments", "context_mcp/tests (synthetic redaction fixtures)"], "files": [], "skipped": []}
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
    for relative, path in store.paths():
        if relative.startswith("context_mcp/tests/"):
            continue
        try:
            if store.is_text(path):
                text, redacted = store.text(relative)
                data = text.encode()
            else:
                if path.stat().st_size > MAX_ASSET_BYTES:
                    raise ValueError("Asset exceeds 32 MB")
                data, redacted = path.read_bytes(), False
        except ValueError as error:
            manifest["skipped"].append({"path": relative, "reason": str(error)})
            continue
        bundle.writestr("morph-context/" + relative, data)
        manifest["files"].append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "redacted": redacted})
    bundle.writestr("morph-context/BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"output": str(output), "files": len(manifest["files"]), "skipped": manifest["skipped"], "bytes": output.stat().st_size}, indent=2))
