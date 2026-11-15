#!/usr/bin/env bash
# Ubuntu Intel Core Ultra setup. Source requirements checked 2026-11-14.
# This installs software; it does not start Studio, connect a robot, or move it.
set -euo pipefail
umask 077

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
setup_dir="$project_dir/.junction-setup"
install_system=false
preflight_only=false
for argument in "$@"; do
  case "$argument" in
    --install-system-packages) install_system=true ;;
    --preflight) preflight_only=true ;;
    -h|--help)
      printf '%s\n' \
        'Usage: bash setup/setup-intel.sh [--preflight] [--install-system-packages]' \
        'Run on the actual Ubuntu x86_64 Intel Core Ultra station.' \
        '--preflight: inventory only, no package installation.' \
        '--install-system-packages: install the native libraries with apt/sudo.' \
        'GPU/NPU drivers, accounts, group memberships, and robot calibration are untouched.'
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$argument" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { printf '%s\n' 'Python 3 is required for the host preflight.' >&2; exit 1; }
python3 "$project_dir/setup/check-intel.py" --require-host
if "$preflight_only"; then exit 0; fi

if "$install_system"; then
  # These are user-space/native build dependencies, not accelerator drivers.
  sudo apt-get update
  sudo apt-get install -y ffmpeg libgl1 libglib2.0-0t64 libusb-1.0-0 \
    libusb-1.0-0-dev libturbojpeg0 libclang-dev pkg-config build-essential \
    g++ git python3-venv
fi

python3 - <<'PY'
import ctypes.util
import re
import shutil
import subprocess
import sys
missing = [name for name in ('ffmpeg', 'git') if not shutil.which(name)]
missing += [name for name in ('GL', 'glib-2.0', 'usb-1.0', 'turbojpeg', 'avcodec')
            if not ctypes.util.find_library(name)]
if missing:
    print('Missing native prerequisites: ' + ', '.join(missing), file=sys.stderr)
    print('Re-run with --install-system-packages to install the documented native libraries.', file=sys.stderr)
    sys.exit(1)
ffmpeg = subprocess.run(['ffmpeg', '-version'], check=True, text=True, capture_output=True)
major = re.search(r'ffmpeg version (?:n)?(\d+)\.', ffmpeg.stdout)
if not major or not 4 <= int(major.group(1)) <= 8:
    print('Studio TorchCodec 0.11.1 requires FFmpeg shared libraries from version 4 through 8.', file=sys.stderr)
    print('Ask the station mentor for the supported FFmpeg package; do not replace drivers.', file=sys.stderr)
    sys.exit(1)
PY

mkdir -p "$setup_dir/uv-cache" "$setup_dir/managed-python" "$setup_dir/checks" \
  "$setup_dir/cache" "$setup_dir/matplotlib" "$setup_dir/huggingface"
export UV_CACHE_DIR="$setup_dir/uv-cache"
export UV_PYTHON_INSTALL_DIR="$setup_dir/managed-python"
export XDG_CACHE_HOME="$setup_dir/cache"
export MPLCONFIGDIR="$setup_dir/matplotlib"
export HF_HOME="$setup_dir/huggingface"

# Keep the package manager local and versioned; Ubuntu's Python is not modified.
if [[ ! -x "$setup_dir/bootstrap/bin/python" ]]; then
  python3 -m venv "$setup_dir/bootstrap" || {
    printf '%s\n' 'Install python3-venv (or re-run with --install-system-packages), then retry.' >&2
    exit 1
  }
fi
"$setup_dir/bootstrap/bin/python" -m pip install --disable-pip-version-check 'uv==0.11.24'
uv_bin="$setup_dir/bootstrap/bin/uv"
export PATH="$setup_dir/bootstrap/bin:$PATH"

ensure_venv() {
  local destination=$1
  if [[ -x "$destination/bin/python" ]]; then
    "$destination/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "This setup requires Python 3.12; preserve the existing environment and select another path."'
  elif [[ -e "$destination" ]]; then
    printf 'Existing non-venv path requires inspection: %s\n' "$destination" >&2
    exit 1
  else
    "$uv_bin" venv --python 3.12 "$destination"
  fi
}

ensure_venv "$setup_dir/anomalib"
ensure_venv "$setup_dir/physicalai"

# All transitive versions are fixed in platform-specific lock files. The two
# environments intentionally have different torch/jsonargparse/OpenVINO versions.
"$uv_bin" pip sync --python "$setup_dir/anomalib/bin/python" --torch-backend cpu \
  "$project_dir/setup/requirements-anomalib-intel.lock"
"$uv_bin" pip check --python "$setup_dir/anomalib/bin/python"
"$uv_bin" pip sync --python "$setup_dir/physicalai/bin/python" --torch-backend xpu \
  "$project_dir/setup/physicalai-intel.lock"
"$uv_bin" pip check --python "$setup_dir/physicalai/bin/python"

"$setup_dir/anomalib/bin/python" -c 'from anomalib.engine import Engine; from anomalib.models import Patchcore; print("Anomalib Engine/Patchcore imports passed")'
"$setup_dir/physicalai/bin/physicalai-studio" --help

runtime_failures=0
"$setup_dir/anomalib/bin/python" "$project_dir/setup/check-intel.py" \
  --runtime --require-host --require-devices CPU GPU NPU \
  --output "$setup_dir/checks/anomalib-intel.json" || runtime_failures=1
"$setup_dir/physicalai/bin/python" "$project_dir/setup/check-intel.py" \
  --runtime --require-host --require-devices CPU GPU NPU \
  --output "$setup_dir/checks/physicalai-intel.json" || runtime_failures=1

if [[ "$runtime_failures" -ne 0 ]]; then
  printf '%s\n' \
    'Packages are installed, but at least one accelerator check did not pass.' \
    'Read .junction-setup/checks/*-intel.json and ask the station mentor to check drivers/device access.' \
    'No physical cycle has been verified.' >&2
  exit 1
fi
printf '%s\n' \
  'Software installation and synthetic CPU/GPU/NPU checks passed in both environments.' \
  'Start the UI intentionally with: bash setup/run-studio.sh' \
  'Next: confirm the assigned station, camera streams, SO-101 calibration, training access, and an observed physical cycle.'
