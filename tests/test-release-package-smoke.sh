#!/usr/bin/env bash
# shellcheck disable=SC2015,SC2016
# SC2015: `cond && pass "..." || fail "..."` is exact here — pass/fail always return 0.
# SC2016: single-quoted example commands are printed literally on purpose.
# =============================================================================
# Aithena — release package smoke test
# =============================================================================
# Builds (or accepts) the exact release artifact, extracts it into a clean
# temporary directory, and validates that an operator can install from it:
#
#   * every packaged path, Compose build context, Dockerfile and bind mount
#     exists (deterministic — no Docker required);
#   * every local documentation link resolves and every documented command is
#     literally correct;
#   * the documented entry point `./installer/run.sh` works in help mode and in
#     non-interactive mode, and generates .env / auth DB / start.sh with the
#     right contents and file modes;
#   * `docker compose config` succeeds for the supported base/prod/SSL/GPU/
#     single-node overlay combinations (only this last step is skipped when
#     Docker is unavailable; `--require-docker` turns that skip into a failure,
#     which is how CI and the release workflow run it).
#
# Usage:
#   tests/test-release-package-smoke.sh [--archive PATH] [--require-docker]
# =============================================================================
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd -P)"
INVENTORY="$REPO_ROOT/scripts/release_inventory.py"

ARCHIVE=""
REQUIRE_DOCKER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) ARCHIVE="$(readlink -f -- "$2")"; shift 2 ;;
    --require-docker) REQUIRE_DOCKER=1; shift ;;
    -h|--help) sed -n '2,25p' "$SCRIPT_PATH"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

PASS=0
FAIL=0
SKIP=0

pass() { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1" >&2; }
skip() { SKIP=$((SKIP + 1)); printf '  ⏭️  SKIP %s\n' "$1"; }
section() { printf '\n▶ %s\n' "$1"; }

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "$label"
  else
    fail "$label"
  fi
}

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aithena-smoke.XXXXXXXX")"
# shellcheck disable=SC2317  # invoked via the EXIT trap
cleanup() {
  [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" ]] && rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

PYTHON_RUNNER=(python3)
if ! python3 -c "import yaml" >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    PYTHON_RUNNER=(uv run --no-project --quiet --with pyyaml python)
  else
    echo "ERROR: python3 with PyYAML (or uv) is required" >&2
    exit 2
  fi
fi

VERSION="$(tr -d ' \t\n\r' < "$REPO_ROOT/VERSION")"
if [[ -n "$ARCHIVE" ]]; then
  # Validate whatever version the caller built (release workflow passes a tag
  # version that may differ from the checked-in VERSION file).
  archive_base="$(basename -- "$ARCHIVE")"
  archive_version="${archive_base#aithena-v}"
  archive_version="${archive_version%-release.tar.gz}"
  [[ -n "$archive_version" ]] && VERSION="$archive_version"
fi

section "Build or locate the release artifact"
if [[ -z "$ARCHIVE" ]]; then
  OUT_DIR="$WORK_DIR/artifact"
  mkdir -p "$OUT_DIR"
  if bash "$REPO_ROOT/scripts/build-release-package.sh" --output-dir "$OUT_DIR" > "$WORK_DIR/build.log" 2>&1; then
    pass "scripts/build-release-package.sh produced the release archive"
  else
    fail "scripts/build-release-package.sh failed"
    cat "$WORK_DIR/build.log" >&2
    exit 1
  fi
  ARCHIVE="$OUT_DIR/aithena-v${VERSION}-release.tar.gz"
fi

if [[ -f "$ARCHIVE" ]]; then
  pass "release archive exists: $(basename "$ARCHIVE")"
else
  fail "release archive not found: $ARCHIVE"
  exit 1
fi

if [[ -f "$ARCHIVE.sha256" ]]; then
  if ( cd -- "$(dirname -- "$ARCHIVE")" && sha256sum -c "$(basename -- "$ARCHIVE").sha256" >/dev/null 2>&1 ); then
    pass "sha256 checksum matches the archive"
  else
    fail "sha256 checksum does not match the archive"
  fi
else
  fail "sha256 checksum file is missing next to the archive"
fi

section "Extract into a clean directory"
EXTRACT_DIR="$WORK_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
if tar -xzf "$ARCHIVE" -C "$EXTRACT_DIR"; then
  pass "archive extracts cleanly"
else
  fail "archive failed to extract"
  exit 1
fi

mapfile -t TOP_LEVEL < <(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -printf '%f\n')
if [[ ${#TOP_LEVEL[@]} -eq 1 && -d "$EXTRACT_DIR/${TOP_LEVEL[0]}" ]]; then
  pass "archive contains exactly one top-level directory (${TOP_LEVEL[0]})"
else
  fail "archive must contain exactly one top-level directory, found: ${TOP_LEVEL[*]}"
  exit 1
fi
PKG="$EXTRACT_DIR/${TOP_LEVEL[0]}"

section "Package contents, Compose dependencies, and documentation"
if "${PYTHON_RUNNER[@]}" "$INVENTORY" --repo-root "$REPO_ROOT" check "$PKG" > "$WORK_DIR/check.log" 2>&1; then
  while IFS= read -r line; do
    [[ "$line" == *PASS* ]] && pass "${line#*PASS }"
  done < "$WORK_DIR/check.log"
else
  cat "$WORK_DIR/check.log" >&2
  fail "package validation command failed (see output above)"
  while IFS= read -r line; do
    [[ "$line" == *FAIL* ]] && fail "${line#*FAIL }"
  done < "$WORK_DIR/check.log"
fi

check "packaged VERSION matches the archive name" \
  bash -c "[[ \"\$(tr -d ' \t\n\r' < '$PKG/VERSION')\" == '$VERSION' ]]"
check "root docker-compose.yml is packaged" test -f "$PKG/docker-compose.yml"
check "src/aithena-common is packaged for the installer" test -f "$PKG/src/aithena-common/pyproject.toml"
check "src/nginx/ssl.conf.template is packaged for the SSL overlay" test -f "$PKG/src/nginx/ssl.conf.template"
check "src/solr/Dockerfile is packaged for the Solr build context" test -f "$PKG/src/solr/Dockerfile"
check ".env.example is packaged" test -f "$PKG/.env.example"

section "Documented entry point: ./installer/run.sh"
( cd "$PKG" && ./installer/run.sh --help > "$WORK_DIR/help.log" 2>&1 ) \
  && pass "./installer/run.sh --help succeeds inside the extracted package" \
  || { fail "./installer/run.sh --help failed inside the extracted package"; cat "$WORK_DIR/help.log" >&2; }
check "help output documents --library-path" grep -q -- "--library-path" "$WORK_DIR/help.log"

( cd "$REPO_ROOT" && ./installer/run.sh --help >/dev/null 2>&1 ) \
  && pass "./installer/run.sh --help succeeds from the source checkout" \
  || fail "./installer/run.sh --help failed from the source checkout"

section "Non-interactive install from the extracted package"
LIBRARY="$WORK_DIR/library"
AUTH_DB="$WORK_DIR/auth/users.db"
mkdir -p "$LIBRARY"
if ( cd "$PKG" && ./installer/run.sh \
      --library-path "$LIBRARY" \
      --admin-user admin \
      --admin-password 'Sm0ke-Test-Passw0rd!' \
      --origin http://localhost \
      --auth-db-path "$AUTH_DB" \
      --environment prod \
      --gpu none \
      --no-ssl \
      --topology single-node < /dev/null > "$WORK_DIR/install.log" 2>&1 ); then
  pass "./installer/run.sh completes non-interactively inside the package"
else
  fail "./installer/run.sh failed non-interactively inside the package"
  cat "$WORK_DIR/install.log" >&2
fi

if [[ -f "$PKG/.env" ]]; then
  pass ".env was generated"
  mode="$(stat -c '%a' "$PKG/.env")"
  [[ "$mode" == "600" ]] && pass ".env has mode 600" || fail ".env has mode $mode, expected 600"
  check ".env contains a generated JWT secret" bash -c "grep -q '^AUTH_JWT_SECRET=..' '$PKG/.env'"
  check ".env points at the requested library path" grep -q "BOOKS_PATH=$LIBRARY" "$PKG/.env"
else
  fail ".env was not generated"
fi

if [[ -f "$AUTH_DB" ]]; then
  pass "auth database was created"
  mode="$(stat -c '%a' "$AUTH_DB")"
  [[ "$mode" == "600" ]] && pass "auth database has mode 600" || fail "auth database has mode $mode, expected 600"
else
  fail "auth database was not created"
fi

if [[ -f "$PKG/start.sh" ]]; then
  pass "start.sh was generated"
  [[ -x "$PKG/start.sh" ]] && pass "start.sh is executable" || fail "start.sh is not executable"
  check "start.sh starts the chain with the root compose file" \
    grep -q -- "docker compose -f docker-compose.yml -f docker/compose.prod.yml" "$PKG/start.sh"
  check "start.sh selects the single-node overlay" \
    grep -q -- "-f docker/compose.single-node.yml" "$PKG/start.sh"
  # Every compose file the generated launcher references must exist.
  missing_start_files=0
  while read -r composefile; do
    [[ -f "$PKG/$composefile" ]] || { fail "start.sh references missing file: $composefile"; missing_start_files=1; }
  done < <(grep -o -- '-f [^ ]*\.yml' "$PKG/start.sh" | awk '{print $2}' | sort -u)
  [[ "$missing_start_files" -eq 0 ]] && pass "every compose file referenced by start.sh exists in the package"
else
  fail "start.sh was not generated"
fi

section "GPU + SSL variant of the generated launcher"
if ( cd "$PKG" && ./installer/run.sh \
      --library-path "$LIBRARY" \
      --admin-user admin \
      --admin-password 'Sm0ke-Test-Passw0rd!' \
      --origin https://books.example.com \
      --auth-db-path "$AUTH_DB" \
      --environment prod \
      --gpu nvidia \
      --ssl --domain books.example.com \
      --topology distributed < /dev/null > "$WORK_DIR/install-ssl.log" 2>&1 ); then
  pass "./installer/run.sh completes for the GPU + SSL configuration"
  check "start.sh chains base → prod → gpu → ssl in order" \
    grep -q -- "docker compose -f docker-compose.yml -f docker/compose.prod.yml -f docker/compose.gpu-nvidia.yml -f docker/compose.ssl.yml" "$PKG/start.sh"
else
  fail "./installer/run.sh failed for the GPU + SSL configuration"
  cat "$WORK_DIR/install-ssl.log" >&2
fi

section "Compose configuration for supported overlay combinations"
COMBINATIONS=(
  "docker-compose.yml"
  "docker-compose.yml docker/compose.prod.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.ssl.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.gpu-nvidia.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.gpu-intel.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.single-node.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.gpu-nvidia.yml docker/compose.ssl.yml docker/compose.single-node.yml"
  "docker-compose.yml docker/compose.single-node.yml docker/compose.solr9.yml"
  "docker-compose.yml docker/compose.single-node.yml docker/compose.solr10.yml"
  "docker-compose.yml docker/compose.dev-ports.yml"
  "docker-compose.yml docker/compose.ci-ports.yml"
  "docker-compose.yml docker/compose.e2e.yml"
)

DOCKER_OK=0
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DOCKER_OK=1
fi

if [[ "$DOCKER_OK" -eq 1 ]]; then
  for combo in "${COMBINATIONS[@]}"; do
    args=()
    # shellcheck disable=SC2086  # deliberate word splitting of the combination
    for file in $combo; do args+=(-f "$file"); done
    combo_env=()
    if [[ "$combo" == *compose.ssl.yml* ]]; then
      # The SSL overlay deliberately requires an operator-provided domain.
      combo_env=(NGINX_HOST=aithena.example.com)
    fi
    if ( cd "$PKG" && env "${combo_env[@]}" docker compose "${args[@]}" config >/dev/null 2>"$WORK_DIR/compose.err" ); then
      pass "docker compose config: $combo"
    else
      fail "docker compose config failed: $combo — $(tail -3 "$WORK_DIR/compose.err" | tr '\n' ' ')"
    fi
  done
elif [[ "$REQUIRE_DOCKER" -eq 1 ]]; then
  fail "Docker Compose is required (--require-docker) but is unavailable — refusing to skip runtime Compose validation"
else
  for combo in "${COMBINATIONS[@]}"; do
    # shellcheck disable=SC2086  # deliberate word splitting of the combination
    if "${PYTHON_RUNNER[@]}" - "$PKG" $combo <<'PY'
import sys
from pathlib import Path

import yaml


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor("!", lambda loader, suffix, node: None)

pkg = Path(sys.argv[1])
for name in sys.argv[2:]:
    with (pkg / name).open(encoding="utf-8") as handle:
        if not isinstance(yaml.load(handle, Loader=Loader), dict):
            raise SystemExit(f"{name}: not a mapping")
PY
    then
      skip "docker compose config: $combo (Docker unavailable — YAML parse only)"
    else
      fail "packaged Compose file is not parseable: $combo"
    fi
  done
  printf '\n  ⚠️  Docker is unavailable in this environment: runtime `docker compose config`\n'
  printf '      validation was skipped for %d combination(s). CI and the release\n' "${#COMBINATIONS[@]}"
  printf '      workflow run this test with --require-docker, where the skip is a failure.\n'
fi

section "Result"
printf '  %d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
[[ "$FAIL" -eq 0 ]] || exit 1
exit 0
