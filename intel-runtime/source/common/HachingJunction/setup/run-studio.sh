#!/usr/bin/env bash
# Start the isolated native Studio installation on this workstation.
set -euo pipefail

SETUP_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
STUDIO_ENV="$SETUP_ROOT/.junction-setup/physicalai"
if [[ ! -x "$STUDIO_ENV/bin/physicalai-studio" ]]; then
  printf '%s\n' 'Physical AI Studio is not installed in .junction-setup/physicalai.' >&2
  exit 1
fi

# Keep user data and caches in the workspace and keep the UI on loopback.
export STORAGE_DIR="$SETUP_ROOT/.junction-setup/physicalai-storage"
export SETTINGS_FILE="$STORAGE_DIR/settings.json"
export HF_HOME="$SETUP_ROOT/.junction-setup/huggingface"
export XDG_CACHE_HOME="$SETUP_ROOT/.junction-setup/cache"
export MPLCONFIGDIR="$SETUP_ROOT/.junction-setup/cache/matplotlib"
export HF_HUB_DISABLE_TELEMETRY=1
export PATH="$STUDIO_ENV/bin:$PATH"
# Studio 0.3.0 pins TorchCodec 0.11.1, which supports FFmpeg 4 through 8.
if [[ "$(uname -s)" == Darwin && -d /opt/homebrew/opt/ffmpeg@8/lib ]]; then
  export PATH="/opt/homebrew/opt/ffmpeg@8/bin:$PATH"
  export DYLD_LIBRARY_PATH="/opt/homebrew/opt/ffmpeg@8/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi
mkdir -p "$STORAGE_DIR" "$HF_HOME" "$XDG_CACHE_HOME" "$MPLCONFIGDIR"
cd "$STORAGE_DIR"
exec "$STUDIO_ENV/bin/physicalai-studio" serve --host 127.0.0.1 --port "${STUDIO_PORT:-7860}"
