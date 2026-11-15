#!/usr/bin/env bash
# Reproduce the Studio workstation environment without connecting to hardware.
set -euo pipefail
studio_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$studio_root"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'This script is for Apple Silicon macOS. Use setup/setup-intel.sh on the target.' >&2
  exit 1
fi
command -v uv >/dev/null || { printf '%s\n' 'uv is required.' >&2; exit 1; }
export UV_CACHE_DIR="$studio_root/.junction-setup/uv-cache"
export UV_PYTHON_INSTALL_DIR="$studio_root/.junction-setup/python-runtimes"
export XDG_CACHE_HOME="$studio_root/.junction-setup/cache"
export HF_HOME="$studio_root/.junction-setup/huggingface"
export MPLCONFIGDIR="$studio_root/.junction-setup/cache/matplotlib"
export HF_HUB_DISABLE_TELEMETRY=1
if [[ -d /opt/homebrew/opt/ffmpeg@8/lib ]]; then
  export PATH="/opt/homebrew/opt/ffmpeg@8/bin:$PATH"
  export DYLD_LIBRARY_PATH="/opt/homebrew/opt/ffmpeg@8/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi

if [[ ! -x .junction-setup/physicalai/bin/python ]]; then
  uv venv --python 3.12 .junction-setup/physicalai
fi
uv pip sync --python .junction-setup/physicalai/bin/python setup/physicalai-macos.lock
uv pip check --python .junction-setup/physicalai/bin/python

# TorchCodec requires FFmpeg shared libraries as well as a command-line binary.
# A static imageio-ffmpeg executable alone does not satisfy that dependency.
.junction-setup/physicalai/bin/python -c '
from importlib.metadata import version
import torch
import torchcodec
import cv2
import openvino

for package in ("physicalai-studio", "physicalai", "physicalai-train", "torch", "torchcodec", "openvino"):
    print(f"{package}: {version(package)}")
print(f"OpenCV: {cv2.__version__}")
print(f"OpenVINO devices: {openvino.Core().available_devices}")
print("Software imports passed. This is not a robot or trained-policy test.")
'
printf '%s\n' 'Start the Studio UI with: bash setup/run-studio.sh' \
  'Studio will listen on 127.0.0.1:7860 and keep its data in this workspace.'
