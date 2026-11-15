#!/usr/bin/env bash
set -euo pipefail
context_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
context_python="$context_root/.junction-setup/context-mcp/bin/python"
if [[ ! -x "$context_python" ]]; then
  printf '%s\n' 'Run python3 context_mcp/bootstrap.py first.' >&2
  exit 1
fi
exec "$context_python" "$context_root/context_mcp/server.py" --root "$context_root" "$@"
