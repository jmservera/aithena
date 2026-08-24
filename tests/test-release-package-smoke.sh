#!/usr/bin/env bash
# =============================================================================
# Release package smoke test
# =============================================================================
# Builds the real artifact with scripts/build-release-package.sh, extracts it,
# and asserts that the extracted package is usable:
#
#   * the archive root is exactly aithena-<version>/ and the smoke test uses the
#     resolved nested root for every later assertion;
#   * the literal documented commands run (./install.sh --check,
#     ./installer/run.sh --help, non-interactive/offline safe modes);
#   * every inventoried path, build context, Dockerfile (implicit and explicit)
#     and Dockerfile COPY source is present;
#   * shipped documentation has no broken local links and no Compose command
#     that skips the root docker-compose.yml;
#   * removing implicit Dockerfiles makes the validator fail with a specific
#     missing-path error, and restoring them makes it pass again.
#
# Docker is optional: only the runtime `docker compose config` checks are
# skipped when it is unavailable.  With --require-docker (used by CI) a missing
# Docker CLI is a hard failure.
# =============================================================================
set -euo pipefail

ROOT="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
REQUIRE_DOCKER=0
PYTHON_BIN="${PYTHON_BIN:-python3}"
PREBUILT_ARCHIVE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require-docker)
      REQUIRE_DOCKER=1
      shift
      ;;
    --archive)
      # Smoke test an already-built archive (used by the release workflow so
      # that the published asset is exactly the artifact that gets validated).
      PREBUILT_ARCHIVE="${2:-}"
      shift 2
      ;;
    --help | -h)
      sed -n '2,22p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

PASS=0
FAIL=0
SKIP=0

pass() {
  PASS=$((PASS + 1))
  printf '  ✅ %s\n' "$*"
}

fail() {
  FAIL=$((FAIL + 1))
  printf '  ❌ %s\n' "$*" >&2
}

skip() {
  SKIP=$((SKIP + 1))
  printf '  ⏭️  %s\n' "$*"
}

check() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "$description"
  else
    fail "$description"
  fi
}

check_fails() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    fail "$description (command unexpectedly succeeded)"
  else
    pass "$description"
  fi
}

WORK_DIR="$(mktemp -d -t aithena-smoke-XXXXXXXX)"
cleanup() {
  if [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" && "$(basename -- "$WORK_DIR")" == aithena-smoke-* ]]; then
    rm -rf -- "$WORK_DIR"
  fi
}
trap cleanup EXIT INT TERM

OUTPUT_DIR="$WORK_DIR/out"
EXTRACT_DIR="$WORK_DIR/extract"
mkdir -p "$OUTPUT_DIR" "$EXTRACT_DIR"

if [[ -n "$PREBUILT_ARCHIVE" ]]; then
  if [[ ! -f "$PREBUILT_ARCHIVE" ]]; then
    echo "FATAL: --archive does not exist: $PREBUILT_ARCHIVE" >&2
    exit 1
  fi
  PREBUILT_ARCHIVE="$(realpath -- "$PREBUILT_ARCHIVE")"
  mapfile -t PREBUILT_ROOTS < <(tar -tzf "$PREBUILT_ARCHIVE" | awk -F/ 'NF>1 {print $1}' | sort -u)
  ARCHIVE_ROOT_NAME="${PREBUILT_ROOTS[0]:-}"
  VERSION="${ARCHIVE_ROOT_NAME#aithena-}"
  if [[ "${#PREBUILT_ROOTS[@]}" -ne 1 || "$VERSION" == "$ARCHIVE_ROOT_NAME" || -z "$VERSION" ]]; then
    echo "FATAL: archive root must be aithena-<version>/ (found: $ARCHIVE_ROOT_NAME)" >&2
    exit 1
  fi
  ARCHIVE="$OUTPUT_DIR/aithena-${VERSION}.tar.gz"
  cp -- "$PREBUILT_ARCHIVE" "$ARCHIVE"
  (cd "$OUTPUT_DIR" && sha256sum "aithena-${VERSION}.tar.gz" > "aithena-${VERSION}.tar.gz.sha256")
else
  VERSION="$(tr -d '[:space:]' <"$ROOT/VERSION")"
  ARCHIVE="$OUTPUT_DIR/aithena-${VERSION}.tar.gz"
fi

DOCKER_AVAILABLE=0
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DOCKER_AVAILABLE=1
fi
if [[ "$REQUIRE_DOCKER" -eq 1 && "$DOCKER_AVAILABLE" -eq 0 ]]; then
  echo "FATAL: --require-docker was given but the Docker Compose CLI is unusable." >&2
  exit 1
fi

if [[ -n "$PREBUILT_ARCHIVE" ]]; then
  echo "━━━ Smoke testing the pre-built archive $PREBUILT_ARCHIVE ━━━"
else
  echo "━━━ Building the release package ━━━"
  build_args=(--output-dir "$OUTPUT_DIR")
  if [[ "$REQUIRE_DOCKER" -eq 1 ]]; then
    build_args+=(--require-docker)
  fi
  bash "$ROOT/scripts/build-release-package.sh" "${build_args[@]}"
fi

echo
echo "━━━ Archive layout ━━━"
check "archive exists: aithena-${VERSION}.tar.gz" test -f "$ARCHIVE"
check "checksum exists" test -f "${ARCHIVE}.sha256"
check "checksum verifies" bash -c "cd '$OUTPUT_DIR' && sha256sum -c 'aithena-${VERSION}.tar.gz.sha256'"

mapfile -t ARCHIVE_ROOTS < <(tar -tzf "$ARCHIVE" | awk -F/ 'NF>1 {print $1}' | sort -u)
if [[ "${#ARCHIVE_ROOTS[@]}" -eq 1 && "${ARCHIVE_ROOTS[0]}" == "aithena-${VERSION}" ]]; then
  pass "archive has a single nested root: aithena-${VERSION}/"
else
  fail "archive root must be exactly aithena-${VERSION}/ (found: ${ARCHIVE_ROOTS[*]})"
fi

tar -xzf "$ARCHIVE" -C "$EXTRACT_DIR"
PACKAGE_ROOT="$EXTRACT_DIR/aithena-${VERSION}"
check "extracted nested root resolves" test -d "$PACKAGE_ROOT"
if [[ ! -d "$PACKAGE_ROOT" ]]; then
  echo "FATAL: extracted package root not found; cannot continue." >&2
  exit 1
fi

echo
echo "━━━ Package contents ━━━"
for relative in \
  docker-compose.yml \
  docker/compose.prod.yml \
  docker/compose.ssl.yml \
  docker/compose.gpu-nvidia.yml \
  docker/compose.gpu-intel.yml \
  docker/compose.single-node.yml \
  docker/compose.solr9.yml \
  docker/compose.solr10.yml \
  docker/compose.e2e.yml \
  docker/compose.ci-ports.yml \
  docker/compose.dev-ports.yml \
  installer/run.sh \
  installer/setup.py \
  src/aithena-common \
  src/nginx/ssl.conf.template \
  release-inventory.json \
  RELEASE-PACKAGE.md \
  install.sh \
  VERSION; do
  check "ships $relative" test -e "$PACKAGE_ROOT/$relative"
done

check "VERSION matches the repository" bash -c "[[ \"\$(tr -d '[:space:]' <'$PACKAGE_ROOT/VERSION')\" == '$VERSION' ]]"

echo
echo "━━━ Permissions ━━━"
check "install.sh is executable" test -x "$PACKAGE_ROOT/install.sh"
check "installer/run.sh is executable" test -x "$PACKAGE_ROOT/installer/run.sh"
check "src/solr/entrypoint.sh is executable" test -x "$PACKAGE_ROOT/src/solr/entrypoint.sh"
check "install.sh parses" bash -n "$PACKAGE_ROOT/install.sh"

echo
echo "━━━ Literal documented commands ━━━"
check "./install.sh --check" bash -c "cd '$PACKAGE_ROOT' && ./install.sh --check"
check "./install.sh --help" bash -c "cd '$PACKAGE_ROOT' && ./install.sh --help"
check "./installer/run.sh --help" bash -c "cd '$PACKAGE_ROOT' && ./installer/run.sh --help </dev/null"
check "non-interactive help stays non-interactive" bash -c "cd '$PACKAGE_ROOT' && ./installer/run.sh --help </dev/null >/dev/null"
check "offline help mode" bash -c "cd '$PACKAGE_ROOT' && AITHENA_INSTALLER_OFFLINE=1 ./installer/run.sh --help </dev/null"

echo
echo "━━━ Inventory validation ━━━"
check "inventory validates against the extracted package" \
  "$PYTHON_BIN" "$ROOT/scripts/release_inventory.py" validate \
  --root "$PACKAGE_ROOT" --inventory "$PACKAGE_ROOT/release-inventory.json"

mapfile -t DOCKERFILES < <("$PYTHON_BIN" "$ROOT/scripts/release_inventory.py" paths \
  --inventory "$PACKAGE_ROOT/release-inventory.json" --key dockerfiles)
mapfile -t IMPLICIT_DOCKERFILES < <("$PYTHON_BIN" "$ROOT/scripts/release_inventory.py" paths \
  --inventory "$PACKAGE_ROOT/release-inventory.json" --key implicit_dockerfiles)
mapfile -t BUILD_CONTEXT_DIRS < <("$PYTHON_BIN" -c '
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    inventory = json.load(handle)
for context in inventory["build_contexts"]:
    print(context["context"])
' "$PACKAGE_ROOT/release-inventory.json" | sort -u)
mapfile -t COPY_SOURCES < <("$PYTHON_BIN" "$ROOT/scripts/release_inventory.py" paths \
  --inventory "$PACKAGE_ROOT/release-inventory.json" --key copy_sources)

if [[ "${#DOCKERFILES[@]}" -ge 6 ]]; then
  pass "inventory lists ${#DOCKERFILES[@]} Dockerfiles"
else
  fail "inventory must list every Dockerfile (found ${#DOCKERFILES[@]})"
fi

if [[ "${#IMPLICIT_DOCKERFILES[@]}" -ge 4 ]]; then
  pass "inventory lists ${#IMPLICIT_DOCKERFILES[@]} implicit Dockerfiles"
else
  fail "inventory must list every implicit Dockerfile (found ${#IMPLICIT_DOCKERFILES[@]})"
fi

for expected in src/embeddings-server/Dockerfile src/solr/Dockerfile; do
  if printf '%s\n' "${IMPLICIT_DOCKERFILES[@]}" | grep -Fxq "$expected"; then
    pass "implicit Dockerfile tracked: $expected"
  else
    fail "implicit Dockerfile missing from inventory: $expected"
  fi
done

for dockerfile in "${DOCKERFILES[@]}"; do
  check "packaged Dockerfile: $dockerfile" test -f "$PACKAGE_ROOT/$dockerfile"
done
for context in "${BUILD_CONTEXT_DIRS[@]}"; do
  [[ "$context" == "." ]] && continue
  check "packaged build context: $context" test -d "$PACKAGE_ROOT/$context"
done
if [[ "${#COPY_SOURCES[@]}" -eq 0 ]]; then
  fail "inventory produced no Dockerfile COPY sources"
else
  copy_missing=0
  for source in "${COPY_SOURCES[@]}"; do
    [[ -e "$PACKAGE_ROOT/$source" ]] || {
      copy_missing=$((copy_missing + 1))
      fail "missing COPY source: $source"
    }
  done
  if [[ "$copy_missing" -eq 0 ]]; then
    pass "all ${#COPY_SOURCES[@]} Dockerfile COPY sources are packaged"
  fi
fi

echo
echo "━━━ Shipped documentation ━━━"
check "no broken local links" "$PYTHON_BIN" "$ROOT/scripts/release_docs.py" links --root "$PACKAGE_ROOT"
check "documented Compose commands start with docker-compose.yml" \
  "$PYTHON_BIN" "$ROOT/scripts/release_docs.py" commands --root "$PACKAGE_ROOT"
for document in README.md docs/quickstart.md docs/user-manual.md docs/admin-manual.md RELEASE-PACKAGE.md; do
  check "ships $document" test -f "$PACKAGE_ROOT/$document"
done
check "RELEASE-PACKAGE.md documents the installer entrypoint" \
  grep -Fq './installer/run.sh' "$PACKAGE_ROOT/RELEASE-PACKAGE.md"

# Every shell command in RELEASE-PACKAGE.md that only validates the package
# must actually work from the extracted archive root.
while IFS= read -r documented_command; do
  check "RELEASE-PACKAGE.md command runs: $documented_command" \
    bash -c "cd '$PACKAGE_ROOT' && $documented_command"
done < <(grep -E '^\./install\.sh --check$|^tar -tzf ' "$PACKAGE_ROOT/RELEASE-PACKAGE.md" || true)

echo
echo "━━━ Implicit Dockerfile removal regression ━━━"
# Criterion 13: deleting real implicit Dockerfiles must make the validator fail
# with a specific missing-path error mentioning each removed file.
REMOVED_A="src/embeddings-server/Dockerfile"
REMOVED_B="${IMPLICIT_DOCKERFILES[0]}"
if [[ "$REMOVED_B" == "$REMOVED_A" ]]; then
  REMOVED_B="${IMPLICIT_DOCKERFILES[1]}"
fi
BACKUP_DIR="$WORK_DIR/backup"
mkdir -p "$BACKUP_DIR"
for removed in "$REMOVED_A" "$REMOVED_B"; do
  cp "$PACKAGE_ROOT/$removed" "$BACKUP_DIR/$(echo "$removed" | tr '/' '_')"
  rm -f "$PACKAGE_ROOT/$removed"
done

VALIDATE_LOG="$WORK_DIR/validate-missing.log"
set +e
"$PYTHON_BIN" "$ROOT/scripts/release_inventory.py" validate \
  --root "$PACKAGE_ROOT" --inventory "$PACKAGE_ROOT/release-inventory.json" \
  >"$VALIDATE_LOG" 2>&1
VALIDATE_STATUS=$?
set -e

if [[ "$VALIDATE_STATUS" -ne 0 ]]; then
  pass "validator exits non-zero (${VALIDATE_STATUS}) when implicit Dockerfiles are missing"
else
  fail "validator passed even though ${REMOVED_A} and ${REMOVED_B} were removed"
fi
for removed in "$REMOVED_A" "$REMOVED_B"; do
  if grep -Fq "$removed" "$VALIDATE_LOG"; then
    pass "validator names the missing path: $removed"
  else
    fail "validator did not report the missing path: $removed"
  fi
done
if grep -Fq "missing 2 required path(s)" "$VALIDATE_LOG"; then
  pass "validator reports the exact number of missing paths"
else
  fail "validator must report exactly 2 missing paths ($(head -1 "$VALIDATE_LOG"))"
fi

check_fails "packaged install.sh rejects the incomplete package" \
  bash -c "cd '$PACKAGE_ROOT' && ./install.sh --check"

for removed in "$REMOVED_A" "$REMOVED_B"; do
  cp "$BACKUP_DIR/$(echo "$removed" | tr '/' '_')" "$PACKAGE_ROOT/$removed"
done
check "validator passes again after restoring the Dockerfiles" \
  "$PYTHON_BIN" "$ROOT/scripts/release_inventory.py" validate \
  --root "$PACKAGE_ROOT" --inventory "$PACKAGE_ROOT/release-inventory.json"
check "packaged install.sh accepts the restored package" \
  bash -c "cd '$PACKAGE_ROOT' && ./install.sh --check"

echo
echo "━━━ Compose configuration ━━━"
if [[ "$DOCKER_AVAILABLE" -eq 1 ]]; then
  COMPOSE_ENV=(
    AUTH_JWT_SECRET=smoke-placeholder
    AUTH_DB_DIR="$WORK_DIR/auth"
    BOOKS_PATH="$WORK_DIR/books"
    BOOK_LIBRARY_PATH="$WORK_DIR/books"
    HF_TOKEN=smoke-placeholder
    SOLR_ADMIN_USER=solr_admin
    SOLR_ADMIN_PASS=smoke-placeholder
    SOLR_READONLY_USER=solr_read
    SOLR_READONLY_PASS=smoke-placeholder
    RABBITMQ_ADMIN_USER=admin
    RABBITMQ_ADMIN_PASS=smoke-placeholder
  )
  mkdir -p "$WORK_DIR/auth" "$WORK_DIR/books"
  while IFS= read -r combination; do
    read -ra files <<<"$combination"
    args=()
    for file in "${files[@]}"; do
      args+=(-f "$file")
    done
    check "docker compose ${files[*]} config" \
      env "${COMPOSE_ENV[@]}" bash -c "cd '$PACKAGE_ROOT' && docker compose ${args[*]} config --quiet"
  done <<'COMBINATIONS'
docker-compose.yml
docker-compose.yml docker/compose.prod.yml
docker-compose.yml docker/compose.prod.yml docker/compose.ssl.yml
docker-compose.yml docker/compose.gpu-nvidia.yml
docker-compose.yml docker/compose.gpu-intel.yml
docker-compose.yml docker/compose.single-node.yml
docker-compose.yml docker/compose.single-node.yml docker/compose.solr9.yml
docker-compose.yml docker/compose.single-node.yml docker/compose.solr10.yml
docker-compose.yml docker/compose.e2e.yml
docker-compose.yml docker/compose.ci-ports.yml
docker-compose.yml docker/compose.dev-ports.yml
COMBINATIONS
else
  skip "docker compose config checks (Docker CLI unavailable)"
fi

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf 'Release package smoke test: %d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
