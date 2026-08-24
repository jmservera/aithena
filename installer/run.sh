#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SETUP_PY="${AITHENA_INSTALLER_SETUP_PY:-$SCRIPT_DIR/setup.py}"
PYTHON_CANDIDATES_TEXT="${AITHENA_INSTALLER_PYTHON_CANDIDATES:-python3 python}"

has_installer_dependencies() {
  local interpreter="$1"
  "$interpreter" -c "import aithena_common, argon2" >/dev/null 2>&1
}

read -r -a PYTHON_CANDIDATES <<< "$PYTHON_CANDIDATES_TEXT"
for interpreter in "${PYTHON_CANDIDATES[@]}"; do
  [[ -n "$interpreter" ]] || continue
  if ! command -v "$interpreter" >/dev/null 2>&1; then
    continue
  fi
  if has_installer_dependencies "$interpreter"; then
    exec "$interpreter" "$SETUP_PY" "$@"
  fi
done

if command -v uv >/dev/null 2>&1; then
  exec uv run --project "$SCRIPT_DIR" python "$SETUP_PY" "$@"
fi

cat >&2 <<'EOF'
ERROR: Could not find a Python interpreter with the Aithena installer dependencies.

Install uv and rerun:
  https://docs.astral.sh/uv/getting-started/installation/
  ./installer/run.sh

Alternatively install the local Python dependencies, then rerun with python3:
  cd installer
  python3 -m pip install -e ../src/aithena-common argon2-cffi
EOF
exit 1
