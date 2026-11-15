#!/usr/bin/env bash
# Reproduce the verified development environment; never connects to the robot.
set -euo pipefail
setup_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$setup_root"
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  printf '%s\n' 'This script is for Apple Silicon macOS. Use setup/setup-intel.sh on the target.' >&2
  exit 1
fi
command -v uv >/dev/null || { printf '%s\n' 'uv is required.' >&2; exit 1; }
export UV_CACHE_DIR="$setup_root/.junction-setup/uv-cache"
export UV_PYTHON_INSTALL_DIR="$setup_root/.junction-setup/python-runtimes"
if [ ! -x .junction-setup/anomalib/bin/python ]; then
  uv venv --python 3.12 .junction-setup/anomalib
fi
if [ -f setup/requirements-anomalib-macos.lock ]; then
  uv pip sync --python .junction-setup/anomalib/bin/python setup/requirements-anomalib-macos.lock
else
  uv pip install --python .junction-setup/anomalib/bin/python -r setup/requirements-anomalib-macos.in
fi
uv pip check --python .junction-setup/anomalib/bin/python
printf '%s\n' 'Activate with: source setup/activate-anomalib.sh' \
  'Verify with: python setup/smoke-anomalib.py' \
  'This prepares software only; the Intel station and physical cycle require separate verification.'
