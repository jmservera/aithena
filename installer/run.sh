#!/usr/bin/env bash
# =============================================================================
# Aithena — first-run installer entry point
# =============================================================================
# THE documented way to run the installer from source checkout or extracted
# release package:
#
#   ./installer/run.sh              # interactive setup
#   ./installer/run.sh --help       # option reference
#   ./installer/run.sh --library-path /data/books --admin-user admin ... \
#     --environment prod --gpu none --no-ssl --topology single-node
#
# Imports aithena_common (not installed system-wide). Bootstraps via:
#   1. Import check: already importable (preinstalled/offline) → run directly
#   2. AITHENA_INSTALLER_VENV: pre-created virtualenv with aithena-common
#   3. uv available: uv run --project installer (resolves ../src/aithena-common)
#   4. Otherwise: actionable error with bootstrap instructions
#
# Offline air-gapped: AITHENA_INSTALLER_OFFLINE=1 forces uv --offline
# =============================================================================
set -euo pipefail

# Resolve real script location (handles symlinks)
SELF="${BASH_SOURCE[0]}"
while [[ -L "$SELF" ]] && [[ -n "$(readlink -- "$SELF")" ]]; do
  SELF="$(readlink -- "$SELF")"
done
INSTALLER_DIR="$(cd -- "$(dirname -- "$SELF")" && pwd)"
# shellcheck disable=SC2034
ROOT="$(cd -- "$INSTALLER_DIR/.." && pwd)"  # Used in helper functions
SETUP_PY="$INSTALLER_DIR/setup.py"

if [[ ! -f "$SETUP_PY" ]]; then
  echo "ERROR: $SETUP_PY not found" >&2
  exit 1
fi

# Early help flag check (before dependencies)
for arg in "$@"; do
  if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
    cat <<'EOF'
Usage: ./installer/run.sh [OPTIONS]

Run the Aithena first-run installer.

Common options:
  --library-path PATH     Host path to the PDF library
  --admin-user NAME       Bootstrap admin username
  --admin-password PASS   Bootstrap admin password
  --origin URL            Public origin (e.g., http://localhost)
  --environment {dev,prod}
  --gpu {nvidia,intel,none}
  --ssl / --no-ssl        Enable/disable Let's Encrypt SSL overlay
  --domain NAME           Domain for SSL certificate
  --topology {single-node,distributed}
  --reset                 Recreate auth storage and rotate secrets
  -h, --help              Show full help

Environment:
  AITHENA_INSTALLER_VENV      Path to virtualenv with aithena-common
  AITHENA_INSTALLER_OFFLINE=1 Force uv --offline (air-gapped hosts)

Full help (requires dependencies): ./installer/run.sh --help
EOF
    exit 0
  fi
done

# Try multiple interpreter candidates, testing BOTH availability AND import
# Continue probing if found interpreter cannot import aithena_common
try_python_executable() {
  local python_bin="$1"
  
  # Check if executable is available
  if ! command -v "$python_bin" >/dev/null 2>&1; then
    return 1
  fi
  
  # Check if it can import required modules
  if "$python_bin" -c "import aithena_common, argon2" >/dev/null 2>&1; then
    # Success: execute setup.py with this Python
    export AITHENA_INSTALLER_UV=1
    exec "$python_bin" "$SETUP_PY" "$@"
  fi
  
  # This Python found but cannot import → return failure, allow continuing to next candidate
  return 1
}

# Try all Python candidates in order
for python_candidate in python3 python python3.12 python3.11; do
  if try_python_executable "$python_candidate"; then
    # This line only reached if try_python_executable exec'd
    exit 0
  fi
done

# Check if AITHENA_INSTALLER_VENV was provided as pre-created virtualenv
if [[ -n "${AITHENA_INSTALLER_VENV:-}" ]]; then
  venv_python="$AITHENA_INSTALLER_VENV/bin/python"
  if [[ -x "$venv_python" ]]; then
    export AITHENA_INSTALLER_UV=1
    exec "$venv_python" "$SETUP_PY" "$@"
  fi
fi

# Check for uv (recommended bootstrap)
if command -v uv >/dev/null 2>&1; then
  export AITHENA_INSTALLER_UV=1
  uv_args=("run")
  
  # Air-gapped: --offline blocks index access
  if [[ "${AITHENA_INSTALLER_OFFLINE:-0}" == "1" ]]; then
    uv_args+=("--offline")
  fi
  
  uv_args+=("--project" "$INSTALLER_DIR" "$SETUP_PY")
  exec uv "${uv_args[@]}" "$@"
fi

# No working Python + no uv: provide actionable error
cat >&2 <<'EOF'
ERROR: Cannot run the Aithena installer.

No Python interpreter with aithena_common available, and uv is not installed.

Fix by either:

1. Install uv (recommended — no root required):
   curl -LsSf https://astral.sh/uv/install.sh | sh
   Then re-run:
   ./installer/run.sh

2. Use a pre-created virtualenv with aithena-common:
   python3 -m venv ./installer-venv
   ./installer-venv/bin/pip install argon2-cffi
   ./installer-venv/bin/pip install -e src/aithena-common/
   AITHENA_INSTALLER_VENV=./installer-venv ./installer/run.sh

3. Install dependencies directly (requires pip):
   pip install --user argon2-cffi
   pip install --user -e src/aithena-common/
   ./installer/run.sh
EOF
exit 1
