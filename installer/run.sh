#!/usr/bin/env bash
# installer/run.sh — documented, dependency-free entry point for the Aithena installer.
#
# This is the ONE supported way to run the installer, whether you are working
# from a source checkout or an extracted release package:
#
#   ./installer/run.sh
#
# It resolves the installer's `aithena-common` dependency (and its
# `argon2-cffi` dependency) via `uv run`, in an isolated environment, so
# nothing needs to be `pip install`-ed system-wide first. All arguments are
# passed straight through to `installer/setup.py` — see `--help` for details.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: 'uv' was not found on PATH.

installer/run.sh uses uv (https://docs.astral.sh/uv/) to resolve the
installer's aithena-common dependency without requiring a system-wide
pip install. Install uv and re-run this script:

  curl -LsSf https://astral.sh/uv/install.sh | sh

Alternatively, if aithena-common and its dependencies (argon2-cffi) are
already importable by your python3, you can run the installer directly:

  python3 installer/setup.py
EOF
  exit 1
fi

exec uv run "$SCRIPT_DIR/setup.py" "$@"
