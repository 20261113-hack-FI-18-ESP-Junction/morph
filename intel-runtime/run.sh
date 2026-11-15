#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${MORPH_PYTHON:-$PACKAGE_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  printf '%s\n' 'Set MORPH_PYTHON to a Python interpreter with station/requirements.txt installed, or create .venv as documented.' >&2
  exit 1
fi
export MORPH_DATA_DIR="${MORPH_DATA_DIR:-$PACKAGE_DIR/.runtime/station}"
export PYTHONPATH="$PACKAGE_DIR/source/common/HachingJunction/station${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -m morph_station "$@"
