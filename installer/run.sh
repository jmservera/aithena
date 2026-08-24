#!/usr/bin/env bash
# =============================================================================
# Aithena — first-run installer entry point
# =============================================================================
# This is THE documented way to run the installer, both from a source checkout
# and from an extracted release package:
#
#   ./installer/run.sh              # interactive setup
#   ./installer/run.sh --help       # option reference
#   ./installer/run.sh --library-path /data/books --admin-user admin ... \
#     --environment prod --gpu none --no-ssl --topology single-node
#
# The installer imports `aithena_common`, which is not installed system-wide.
# This wrapper bootstraps that dependency without mutating the user's global
# Python environment, in this order:
#
#   1. Already importable (a preinstalled/offline environment) → run directly.
#   2. `uv` available → `uv run --project installer` (resolves the local
#      `src/aithena-common` path dependency from installer/uv.lock).
#   3. `AITHENA_INSTALLER_VENV` or a project-local `.venv` → use its python.
#   4. Otherwise → actionable error explaining how to bootstrap.
#
# Offline/air-gapped installs keep working: set AITHENA_INSTALLER_OFFLINE=1 to
# force `uv --offline` (no index access, cache/lock only), or pre-create a
# virtualenv with aithena-common installed and export AITHENA_INSTALLER_VENV.
#
# See also: docs/quickstart.md, docs/admin-manual.md,
#           docs/deployment/offline-deployment.md
# =============================================================================
set -euo pipefail

# Resolve the real script location so symlinked invocations still find the
# package root (installer/.. == package root, in source and in the archive).
resolve_self() {
  local target="${BASH_SOURCE[0]}"
  if command -v readlink >/dev/null 2>&1; then
    local resolved
    if resolved="$(readlink -f -- "$target" 2>/dev/null)" && [[ -n "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi
  printf '%s\n' "$target"
}

SELF="$(resolve_self)"
INSTALLER_DIR="$(cd -- "$(dirname -- "$SELF")" && pwd)"
ROOT="$(cd -- "$INSTALLER_DIR/.." && pwd)"

WANTS_HELP=0
for arg in "$@"; do
  if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
    WANTS_HELP=1
    break
  fi
done

usage() {
  cat <<'EOF'
Usage: ./installer/run.sh [OPTIONS]

Run the Aithena first-run installer. It writes .env, creates the auth storage
directory and SQLite auth database, generates the JWT secret and service
credentials, and writes ./start.sh with the correct docker compose file chain.

Common options (full list is printed once dependencies are available):
  --library-path PATH     Host path to the PDF library directory
  --admin-user NAME       Bootstrap admin username
  --admin-password PASS   Bootstrap admin password
  --origin URL            Public origin, e.g. http://localhost
  --auth-db-path PATH     Persistent SQLite auth database path
  --env-file PATH         .env file to write (default: <package>/.env)
  --environment {dev,prod}
  --gpu {nvidia,intel,none}
  --ssl / --no-ssl        Enable/disable the Let's Encrypt SSL overlay
  --domain NAME           Domain used for the SSL certificate
  --topology {single-node,distributed}
  --reset                 Recreate auth storage and rotate generated secrets
  -h, --help              Show this message

Environment:
  AITHENA_INSTALLER_VENV      Path to a virtualenv that already has
                              aithena-common installed (offline installs).
  AITHENA_INSTALLER_OFFLINE=1 Force `uv run --offline` (air-gapped hosts).

Non-interactive use: pass every value on the command line and redirect stdin
from /dev/null; the installer only prompts when stdin and stdout are TTYs.
EOF
}

python_can_import() {
  local python_bin="$1"
  [[ -x "$python_bin" || -n "$(command -v "$python_bin" 2>/dev/null)" ]] || return 1
  PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

sys.exit(0 if importlib.util.find_spec("aithena_common") else 1)
PY
}

run_with_python() {
  local python_bin="$1"
  shift
  cd "$ROOT"
  PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" AITHENA_INSTALLER_UV=1 \
    exec "$python_bin" -m installer.setup "$@"
}

# 1. Dependencies already available (offline images, preinstalled venvs, CI).
for candidate in "${AITHENA_INSTALLER_PYTHON:-}" python3 python; do
  [[ -n "$candidate" ]] || continue
  command -v "$candidate" >/dev/null 2>&1 || continue
  if python_can_import "$candidate"; then
    run_with_python "$candidate" "$@"
  fi
  break
done

# 2. A project-local virtualenv (created by a previous run or by an operator).
for venv in "${AITHENA_INSTALLER_VENV:-}" "$ROOT/.venv" "$INSTALLER_DIR/.venv"; do
  [[ -n "$venv" && -x "$venv/bin/python" ]] || continue
  if python_can_import "$venv/bin/python"; then
    run_with_python "$venv/bin/python" "$@"
  fi
done

# 3. uv resolves aithena-common from installer/uv.lock + src/aithena-common.
if command -v uv >/dev/null 2>&1; then
  uv_args=(run --project "$INSTALLER_DIR")
  if [[ "${AITHENA_INSTALLER_OFFLINE:-0}" == "1" ]]; then
    uv_args+=(--offline)
  fi
  cd "$ROOT"
  set +e
  AITHENA_INSTALLER_UV=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
    uv "${uv_args[@]}" python -m installer.setup "$@"
  status=$?
  set -e
  if [[ $status -eq 0 ]]; then
    exit 0
  fi
  if [[ $WANTS_HELP -eq 1 ]]; then
    usage
    exit 0
  fi
  exit "$status"
fi

# 4. Nothing worked. --help must still be useful without any dependency.
if [[ $WANTS_HELP -eq 1 ]]; then
  usage
  exit 0
fi

cat >&2 <<EOF
ERROR: cannot run the Aithena installer — the 'aithena-common' dependency is
       not available and no supported bootstrap method was found.

Fix one of the following and re-run './installer/run.sh':

  * Install uv (recommended):
      curl -LsSf https://astral.sh/uv/install.sh | sh
      # then: ./installer/run.sh

  * Or create a virtualenv yourself (works offline with a local wheel cache):
      python3 -m venv .venv
      .venv/bin/pip install ./src/aithena-common
      ./installer/run.sh

  * Or point the installer at an existing environment:
      AITHENA_INSTALLER_VENV=/path/to/venv ./installer/run.sh

Package root: $ROOT
EOF
exit 1
