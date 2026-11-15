# Source this file from Bash or Zsh: source setup/activate-anomalib.sh
if [ -n "${BASH_VERSION:-}" ]; then
  _anomalib_source=${BASH_SOURCE[0]}
elif [ -n "${ZSH_VERSION:-}" ]; then
  _anomalib_source=${(%):-%x}
else
  printf '%s\n' 'Use Bash or Zsh to activate this environment.' >&2
  return 1
fi
_anomalib_root=$(cd -P -- "$(dirname -- "$_anomalib_source")/.." && pwd) || return 1
if [ ! -f "$_anomalib_root/.junction-setup/anomalib/bin/activate" ]; then
  printf '%s\n' 'Anomalib is not installed. Run the setup script for this machine first.' >&2
  unset _anomalib_root _anomalib_source
  return 1
fi
source "$_anomalib_root/.junction-setup/anomalib/bin/activate" || return 1
export UV_CACHE_DIR="$_anomalib_root/.junction-setup/uv-cache"
export HF_HOME="$_anomalib_root/.junction-setup/huggingface"
export TORCH_HOME="$_anomalib_root/.junction-setup/torch"
export MPLCONFIGDIR="$_anomalib_root/.junction-setup/matplotlib"
export XDG_CACHE_HOME="$_anomalib_root/.junction-setup/cache"
export PYTHONUNBUFFERED=1
unset _anomalib_root _anomalib_source
