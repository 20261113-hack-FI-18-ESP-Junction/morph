#!/usr/bin/env bash
set -euo pipefail

bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
provider_python="$bundle_dir/../../morph-intel-transfer/morph-context/.junction-setup/python/bin/python"
if [[ ! -x "$provider_python" ]]; then
  printf '%s\n' 'The verified Intel Python environment is missing. Restore its documented location before running this helper.' >&2
  exit 2
fi
exec "$provider_python" "$bundle_dir/HachingJunction/setup/provider-check/check.py" "$@"
