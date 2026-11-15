"""Check task evidence for accidental credential copies without printing secret values."""
from datetime import datetime, timezone
import json
from pathlib import Path
import stat

evidence = Path(__file__).resolve().parent
root = evidence.parents[1]
workspace = root / "HachingJunction"
provider_file = workspace / "station/.env.providers"
secret_values = []
for line in provider_file.read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    value = value.strip().strip("\"'")
    if key.strip() in {"GEMINI_API_KEY", "GOOGLE_API_KEY", "VERDA_INFERENCE_KEY", "ELEVENLABS_API_KEY"} and len(value) >= 16:
        secret_values.append(value.encode())
token_file = evidence / "runs/hosted-03/data/api-token"
if token_file.exists():
    secret_values.append(token_file.read_bytes().strip())

roots = [evidence, workspace / "context/outbox", workspace / "context/sync-receipts",
         workspace / "context/verification/gemma-intel-20261114", workspace / "station/morph_station",
         workspace / "station/tests", root / "morph-station/src/analysis"]
checked = 0
matches = []
for directory in roots:
    for path in directory.rglob("*"):
        if not path.is_file() or path.is_symlink() or path == token_file or "__pycache__" in path.parts:
            continue
        content = path.read_bytes()
        checked += 1
        if any(value in content for value in secret_values):
            matches.append(str(path.relative_to(root)))

result = {"observedAt": datetime.now(timezone.utc).isoformat(), "checkedFiles": checked,
          "credentialMatchesInPublicFiles": matches,
          "providerFileMode": oct(stat.S_IMODE(provider_file.stat().st_mode)),
          "expectedPrivateApiTokenExcluded": token_file.exists(),
          "scope": "Current provider key values and owned API token checked privately against task artifacts and source; no values emitted."}
(evidence / "public-evidence-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
raise SystemExit(bool(matches) or result["providerFileMode"] != "0o600")
