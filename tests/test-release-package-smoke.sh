#!/usr/bin/env bash
# =============================================================================
# Release package smoke test
# =============================================================================
# Builds the production release package with scripts/build-release-package.sh
# (the same script used by .github/workflows/release.yml), archives it,
# extracts the archive into a clean directory, and verifies that the
# artifact an operator actually downloads:
#
#   1. Contains docker-compose.yml, docker/compose.prod.yml, installer/, and
#      src/aithena-common/ at the paths documented in README.md / docs/*.md.
#   2. Can run the documented first-run installer entry point
#      (installer/run.sh --help) without a ModuleNotFoundError, proving
#      aithena_common resolves correctly from the packaged layout.
#   3. Produces a packaged Compose config that is syntactically valid and,
#      when Docker Compose v2 is available, resolves cleanly via
#      `docker compose config` (no services started).
#
# This does not start any containers or mutate host state. It is safe to run
# repeatedly and in CI.
#
# Usage:
#   bash tests/test-release-package-smoke.sh                  # build + verify
#   bash tests/test-release-package-smoke.sh --archive PATH   # verify an
#                                                              # already-built
#                                                              # archive (e.g.
#                                                              # the one just
#                                                              # produced by
#                                                              # .github/workflows/release.yml)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ARTIFACT_DIR="$ROOT/.test-artifacts/release-package-smoke"
STAGE_DIR="$ARTIFACT_DIR/staged"
ARCHIVE_PATH="$ARTIFACT_DIR/aithena-smoketest-release.tar.gz"
EXTRACT_DIR="$ARTIFACT_DIR/extracted"
PREBUILT_ARCHIVE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) PREBUILT_ARCHIVE="${2:-}"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [--archive PATH]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ✅ $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $*"; }

cleanup() {
  rm -rf "$ARTIFACT_DIR"
}
trap cleanup EXIT

rm -rf "$ARTIFACT_DIR"
mkdir -p "$ARTIFACT_DIR"

if [[ -n "$PREBUILT_ARCHIVE" ]]; then
  echo "== Using pre-built release archive: ${PREBUILT_ARCHIVE} =="
  if [[ ! -f "$PREBUILT_ARCHIVE" ]]; then
    echo "❌ Archive not found: ${PREBUILT_ARCHIVE}"
    exit 1
  fi
  ARCHIVE_PATH="$PREBUILT_ARCHIVE"
  pass "release archive found: $(basename "$ARCHIVE_PATH")"
else
  echo "== Building release package =="
  if ! bash "$ROOT/scripts/build-release-package.sh" \
    --version "0.0.0-smoketest" \
    --output-dir "$STAGE_DIR" \
    --archive "$ARCHIVE_PATH" \
    --checksum >"$ARTIFACT_DIR/build.log" 2>&1; then
    echo "❌ scripts/build-release-package.sh failed:"
    cat "$ARTIFACT_DIR/build.log"
    exit 1
  fi
  pass "release archive built: $(basename "$ARCHIVE_PATH")"
fi

CHECKSUM_FILE="${ARCHIVE_PATH}.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
  EXPECTED_SHA="$(awk '{print $1}' "$CHECKSUM_FILE")"
  ACTUAL_SHA="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
  if [[ "$EXPECTED_SHA" == "$ACTUAL_SHA" ]]; then
    pass "sha256 checksum verifies"
  else
    fail "sha256 checksum does not match archive contents"
  fi
else
  fail "sha256 checksum file missing: $CHECKSUM_FILE"
fi

echo ""
echo "== Extracting archive into a clean directory =="
mkdir -p "$EXTRACT_DIR"
tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_DIR"
pass "archive extracted to $EXTRACT_DIR"

echo ""
echo "== Verifying required paths (matching README.md / docs/*.md) =="
REQUIRED_PATHS=(
  "docker-compose.yml"
  "docker/compose.prod.yml"
  "docker/compose.dev-ports.yml"
  "docker/compose.gpu-nvidia.yml"
  "docker/compose.gpu-intel.yml"
  "docker/compose.ssl.yml"
  "docker/compose.single-node.yml"
  "installer/run.sh"
  "installer/setup.py"
  "installer/__main__.py"
  "installer/pyproject.toml"
  "src/aithena-common/pyproject.toml"
  "src/aithena-common/aithena_common/__init__.py"
  "src/aithena-common/aithena_common/auth_db.py"
  "src/aithena-common/aithena_common/passwords.py"
  "VERSION"
  ".env.example"
  "docs/quickstart.md"
  "docs/admin-manual.md"
)

for rel_path in "${REQUIRED_PATHS[@]}"; do
  if [[ -e "$EXTRACT_DIR/$rel_path" ]]; then
    pass "present: $rel_path"
  else
    fail "MISSING: $rel_path"
  fi
done

echo ""
echo "== Running the documented installer entry point (safe --help mode) =="
INSTALLER_OUTPUT="$ARTIFACT_DIR/installer-help.log"
if (cd "$EXTRACT_DIR" && bash installer/run.sh --help) >"$INSTALLER_OUTPUT" 2>&1; then
  if grep -q "usage: setup.py" "$INSTALLER_OUTPUT"; then
    pass "installer/run.sh --help ran successfully from the extracted package"
  else
    fail "installer/run.sh --help ran but produced unexpected output"
    cat "$INSTALLER_OUTPUT"
  fi
else
  fail "installer/run.sh --help failed from the extracted package"
  cat "$INSTALLER_OUTPUT"
fi

if grep -qi "ModuleNotFoundError" "$INSTALLER_OUTPUT"; then
  fail "installer/run.sh output contains a ModuleNotFoundError (aithena_common not resolved)"
fi

echo ""
echo "== Cross-checking source-checkout invocation consistency =="
SOURCE_OUTPUT="$ARTIFACT_DIR/source-help.log"
if bash "$ROOT/installer/run.sh" --help >"$SOURCE_OUTPUT" 2>&1 && grep -q "usage: setup.py" "$SOURCE_OUTPUT"; then
  pass "installer/run.sh --help also works from the source checkout"
else
  fail "installer/run.sh --help failed from the source checkout"
  cat "$SOURCE_OUTPUT"
fi

echo ""
echo "== Validating packaged Compose config (no services started) =="
# Combinations the packaged installer's generated start.sh can produce.
COMPOSE_COMBINATIONS=(
  "docker-compose.yml"
  "docker-compose.yml docker/compose.prod.yml"
  "docker-compose.yml docker/compose.dev-ports.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.gpu-nvidia.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.gpu-intel.yml"
  "docker-compose.yml docker/compose.prod.yml docker/compose.ssl.yml"
  "docker-compose.yml docker/compose.single-node.yml"
)

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_ALL_OK=1
  for combo in "${COMPOSE_COMBINATIONS[@]}"; do
    COMPOSE_ARGS=()
    for f in $combo; do
      COMPOSE_ARGS+=(-f "$EXTRACT_DIR/$f")
    done
    COMPOSE_ENV_OUTPUT="$ARTIFACT_DIR/compose-config-$(echo "$combo" | tr ' /.' '___').log"
    if ! AUTH_JWT_SECRET=smoketest-secret \
      AUTH_DB_DIR="$ARTIFACT_DIR/auth" \
      SOLR_ADMIN_USER=smoketest-admin \
      SOLR_ADMIN_PASS=smoketest-admin-pass \
      SOLR_READONLY_USER=smoketest-read \
      SOLR_READONLY_PASS=smoketest-read-pass \
      BOOKS_PATH="$ARTIFACT_DIR/booklibrary" \
      docker compose "${COMPOSE_ARGS[@]}" config >"$COMPOSE_ENV_OUTPUT" 2>&1; then
      fail "docker compose config failed for: ${combo}"
      cat "$COMPOSE_ENV_OUTPUT"
      COMPOSE_ALL_OK=0
    fi
  done
  if [[ "$COMPOSE_ALL_OK" -eq 1 ]]; then
    pass "docker compose config resolved every packaged Compose combination (no services started)"
  fi
else
  echo "  ⚠️ SKIPPED: Docker / Docker Compose v2 not available in this environment —"
  echo "     full 'docker compose config' validation was NOT exercised."
  echo "     Falling back to a deterministic YAML syntax check instead."
  YAML_OK=1
  # Compose files use Compose-spec-only merge tags (!override, !reset) that
  # plain PyYAML does not know about; register permissive constructors so
  # this fallback check validates structure without a false failure on tags
  # that are only meaningful to `docker compose config`.
  YAML_CHECK_SCRIPT='
import sys
import yaml

class ComposeSafeLoader(yaml.SafeLoader):
    pass

def _passthrough(loader, node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)

for tag in ("!override", "!reset"):
    ComposeSafeLoader.add_constructor(tag, _passthrough)

with open(sys.argv[1]) as fh:
    yaml.load(fh, Loader=ComposeSafeLoader)
'
  for f in "${REQUIRED_PATHS[@]}"; do
    case "$f" in
      docker-compose.yml|docker/compose.*.yml)
        if ! python3 -c "$YAML_CHECK_SCRIPT" "$EXTRACT_DIR/$f" 2>"$ARTIFACT_DIR/yaml-error.log"; then
          fail "invalid YAML: $f"
          cat "$ARTIFACT_DIR/yaml-error.log"
          YAML_OK=0
        fi
        ;;
    esac
  done
  if [[ "$YAML_OK" -eq 1 ]]; then
    pass "packaged Compose files are syntactically valid YAML (docker compose config NOT exercised)"
  else
    fail "packaged Compose files failed YAML syntax validation"
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: ${PASS} passed, ${FAIL} failed"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
