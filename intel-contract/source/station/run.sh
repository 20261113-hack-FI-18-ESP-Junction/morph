#!/usr/bin/env bash
set -euo pipefail

STATION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$STATION_DIR")"
STATION_PYTHON="${MORPH_PYTHON:-$PROJECT_DIR/.junction-setup/python/bin/python}"

if [[ ! -x "$STATION_PYTHON" ]]; then
  printf '%s\n' "Python runtime not found. Set MORPH_PYTHON to the isolated environment containing station/requirements.txt." >&2
  exit 1
fi

export PYTHONPATH="$STATION_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$STATION_PYTHON" -m morph_station "$@"
