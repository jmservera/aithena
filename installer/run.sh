#!/usr/bin/env bash
# =============================================================================
# Aithena — First-Run Installer Bootstrap
# =============================================================================
# The single documented entry point for the first-run installer. It works
# identically from a source checkout and from an extracted release package,
# and it does not assume aithena_common (or its argon2-cffi dependency) is
# already importable by the system python3 — it uses uv to resolve those
# dependencies in an isolated, ephemeral environment instead.
#
# Usage:
#   ./installer/run.sh                 # interactive first-run setup
#   ./installer/run.sh --help          # show installer/setup.py options
#   ./installer/run.sh --reset ...     # forwarded to installer/setup.py
#
# See also: docs/quickstart.md, docs/admin-manual.md
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SETUP_PY="$SCRIPT_DIR/setup.py"

if [[ ! -f "$SETUP_PY" ]]; then
  echo "ERROR: $SETUP_PY not found. Run this script from a valid Aithena checkout or release package." >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  # installer/setup.py carries PEP 723 inline script metadata declaring
  # aithena-common (resolved from ../src/aithena-common relative to this
  # file) as a dependency, so `uv run` works regardless of the caller's
  # current working directory, with no manual pip/venv setup required.
  exec uv run "$SETUP_PY" "$@"
fi

# Fallback: uv is not installed, but the operator may have already made
# aithena_common (and argon2-cffi) importable manually — honor that instead
# of failing outright.
if python3 -c "import aithena_common, argon2" >/dev/null 2>&1; then
  exec python3 "$SETUP_PY" "$@"
fi

cat >&2 <<EOF
ERROR: Cannot run the Aithena installer.

'uv' was not found on PATH, and the 'aithena_common' package (with its
'argon2-cffi' dependency) is not importable by python3. Running
'python3 installer/setup.py' directly in this state fails with:
  ModuleNotFoundError: No module named 'aithena_common'

Fix by either:
  1. Installing uv (recommended, no root required), then re-running this script:
       curl -LsSf https://astral.sh/uv/install.sh | sh
       ./installer/run.sh

  2. Installing the dependencies manually, then running setup.py directly:
       pip install --user argon2-cffi
       pip install --user -e "${REPO_ROOT}/src/aithena-common"
       python3 installer/setup.py
EOF
exit 1
