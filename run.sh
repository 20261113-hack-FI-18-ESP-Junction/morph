#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOSE_PYTHON="${MORPH_PYTHON:-$PACKAGE_DIR/.venv/bin/python}"
if [[ ! -x "$JOSE_PYTHON" ]]; then
  printf '%s\n' "Python runtime not found. Create .venv from station/requirements.txt or set MORPH_PYTHON." >&2
  exit 1
fi
export PYTHONPATH="$PACKAGE_DIR/station${PYTHONPATH:+:$PYTHONPATH}"
exec "$JOSE_PYTHON" -m morph_station.lab --data-dir "$PACKAGE_DIR/.data/jose-control" "$@"
