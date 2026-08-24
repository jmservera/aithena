#!/usr/bin/env bash
# =============================================================================
# Aithena — installer entrypoint
# =============================================================================
# The single documented way to run the first-run installer, both from a source
# checkout and from an extracted release package:
#
#   ./installer/run.sh --help
#   ./installer/run.sh --library-path ~/books --admin-user admin ...
#   AITHENA_INSTALLER_OFFLINE=1 ./installer/run.sh --help
#
# Interpreter selection:
#   * every candidate interpreter is probed for BOTH availability and the
#     ability to import the installer runtime dependencies;
#   * a candidate that exists but cannot import them is skipped, never fatal;
#   * when no candidate works, the script falls back to `uv run` and exports
#     AITHENA_INSTALLER_UV=1 so installer/setup.py does not launch uv a second
#     time (no double-launch);
#   * offline mode never reaches for the network: `uv run --offline` is used and
#     an interpreter that cannot import the dependencies is reported clearly.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PACKAGE_ROOT="$(cd -P -- "$SCRIPT_DIR/.." && pwd -P)"
SETUP_PY="$SCRIPT_DIR/setup.py"
COMMON_SRC="$PACKAGE_ROOT/src/aithena-common"

OFFLINE="${AITHENA_INSTALLER_OFFLINE:-0}"

usage() {
  cat <<'USAGE'
Usage: ./installer/run.sh [OPTIONS]

Run the Aithena first-run installer with the best available Python interpreter.

Entrypoint options:
  --offline    Never use the network; requires a local interpreter that can
               import aithena-common, or a warm uv cache
  --help, -h   Show this help text (also prints the installer's own options)

Environment:
  AITHENA_PYTHON              Interpreter to try before python3/python
  AITHENA_INSTALLER_OFFLINE   Set to 1 for the same effect as --offline

Every other option is forwarded verbatim to installer/setup.py.
USAGE
}

FORWARD_ARGS=()
SHOW_HELP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --offline)
      OFFLINE=1
      shift
      ;;
    --help | -h)
      SHOW_HELP=1
      FORWARD_ARGS+=("$1")
      shift
      ;;
    *)
      FORWARD_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$SHOW_HELP" -eq 1 ]]; then
  usage
  printf '\n'
fi

if [[ ! -f "$SETUP_PY" ]]; then
  printf 'Aithena installer is incomplete: %s not found.\n' "$SETUP_PY" >&2
  exit 1
fi

# The bundled aithena-common source is importable directly from a source
# checkout and from the extracted release package.
if [[ -d "$COMMON_SRC" ]]; then
  export PYTHONPATH="${COMMON_SRC}${PYTHONPATH:+:${PYTHONPATH}}"
fi

interpreter_can_import() {
  local interpreter="$1"
  "$interpreter" - <<'PROBE' >/dev/null 2>&1
import importlib

for module in ("aithena_common.auth_db", "aithena_common.passwords"):
    importlib.import_module(module)
PROBE
}

candidates=()
if [[ -n "${AITHENA_PYTHON:-}" ]]; then
  candidates+=("$AITHENA_PYTHON")
fi
candidates+=(python3 python python3.13 python3.12)

probed=()
for candidate in "${candidates[@]}"; do
  resolved="$(command -v "$candidate" 2>/dev/null || true)"
  if [[ -z "$resolved" ]]; then
    continue
  fi
  probed+=("$resolved")
  if interpreter_can_import "$resolved"; then
    exec "$resolved" "$SETUP_PY" ${FORWARD_ARGS[@]+"${FORWARD_ARGS[@]}"}
  fi
done

# No interpreter could import the runtime dependencies — fall back to uv.
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
  printf 'Aithena installer could not find a usable Python interpreter.\n' >&2
  if [[ "${#probed[@]}" -gt 0 ]]; then
    printf 'Probed interpreters (none could import aithena-common):\n' >&2
    printf '  - %s\n' "${probed[@]}" >&2
  else
    printf 'No python3/python interpreter is on PATH.\n' >&2
  fi
  printf '\nFix it with either of:\n' >&2
  printf '  1. Install uv (https://docs.astral.sh/uv/) and re-run ./installer/run.sh\n' >&2
  printf '  2. pip install -e %s and re-run ./installer/run.sh\n' "$COMMON_SRC" >&2
  exit 1
fi

# AITHENA_INSTALLER_UV=1 tells installer/setup.py that uv is already in charge,
# so ensure_runtime_dependencies() reports a clear error instead of re-launching
# uv from inside the interpreter.
export AITHENA_INSTALLER_UV=1

uv_args=(run --project "$SCRIPT_DIR")
if [[ "$OFFLINE" == "1" ]]; then
  uv_args+=(--offline)
fi
uv_args+=(python "$SETUP_PY")

exec "$UV_BIN" "${uv_args[@]}" ${FORWARD_ARGS[@]+"${FORWARD_ARGS[@]}"}
