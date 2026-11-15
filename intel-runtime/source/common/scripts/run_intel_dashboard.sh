#!/usr/bin/env bash
# Start the isolated Intel records service or connected dashboard in the foreground.
set -euo pipefail

MORPH_BUNDLE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
MORPH_PROJECT_DIR="$MORPH_BUNDLE_DIR/HachingJunction"
export MORPH_PYTHON="${MORPH_PYTHON:-$MORPH_BUNDLE_DIR/../../morph-intel-transfer/morph-context/.junction-setup/python/bin/python}"
export MORPH_DATA_DIR="$MORPH_PROJECT_DIR/station/.data"
export MORPH_TOKEN_FILE="$MORPH_DATA_DIR/api-token"
export PYTHONDONTWRITEBYTECODE=1
unset MORPH_API_TOKEN MORPH_DB_PATH MORPH_EVIDENCE_DIR

case "${1:-help}" in
  api)
    cd -- "$MORPH_PROJECT_DIR"
    exec bash station/run.sh serve --host 127.0.0.1 --port "${MORPH_API_PORT:-8000}"
    ;;
  ui)
    export MORPH_STATION_ORIGIN="http://127.0.0.1:${MORPH_API_PORT:-8000}"
    export PORT="${MORPH_UI_PORT:-3001}"
    export NODE_ENV=production
    cd -- "$MORPH_BUNDLE_DIR/morph-station"
    exec node --import tsx server.ts
    ;;
  init)
    cd -- "$MORPH_PROJECT_DIR"
    exec bash station/run.sh init
    ;;
  seed-simulation)
    cd -- "$MORPH_PROJECT_DIR"
    exec bash station/run.sh seed-demo --prefix intel-bringup
    ;;
  help|--help|-h)
    printf '%s\n' 'Usage: bash scripts/run_intel_dashboard.sh {api|ui|init|seed-simulation}'
    printf '%s\n' 'Run api and ui in separate terminals; Ctrl+C stops only that foreground service.'
    printf '%s\n' 'Defaults: API 127.0.0.1:8000; UI 127.0.0.1:3001. Studio is not started or stopped.'
    ;;
  *)
    printf '%s\n' 'Unknown operation. Use --help.' >&2
    exit 2
    ;;
esac
