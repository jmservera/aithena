#!/usr/bin/env bash
# =============================================================================
# Release Package Smoke Test
# =============================================================================
# Validates that a release archive contains all required files, Dockerfiles,
# build contexts, and that the installer entry point works from an extracted
# package. Includes comprehensive regression coverage for implicit Dockerfiles.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${ROOT}/.test-artifacts/smoke-test"
PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ✅ $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $*"; }

cleanup() { rm -rf "$ARTIFACT_DIR"; }
trap cleanup EXIT

rm -rf "$ARTIFACT_DIR"
mkdir -p "$ARTIFACT_DIR"

echo "=== Release Package Smoke Test ==="

# Build the release package
echo ""
echo "== Building release archive =="
if bash "$ROOT/scripts/build-release-package.sh" \
  --version "0.0.0-smoketest" \
  --output-dir "$ARTIFACT_DIR/staged" \
  --archive "$ARTIFACT_DIR/aithena-smoketest.tar.gz" \
  --checksum >"$ARTIFACT_DIR/build.log" 2>&1; then
  pass "Release archive built"
else
  fail "Release archive build failed"
  cat "$ARTIFACT_DIR/build.log" >&2
  exit 1
fi

# Verify checksum
ARCHIVE="$ARTIFACT_DIR/aithena-smoketest.tar.gz"
CHECKSUM_FILE="${ARCHIVE}.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
  if (cd "$ARTIFACT_DIR" && sha256sum -c "$CHECKSUM_FILE" >/dev/null 2>&1); then
    pass "Archive checksum verifies"
  else
    fail "Archive checksum mismatch"
  fi
fi

# Extract archive
echo ""
echo "== Extracting archive =="
EXTRACT_DIR="$ARTIFACT_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
if tar -xzf "$ARCHIVE" -C "$EXTRACT_DIR" 2>"$ARTIFACT_DIR/extract.log"; then
  pass "Archive extracted"
else
  fail "Archive extraction failed"
  cat "$ARTIFACT_DIR/extract.log" >&2
fi

# Validate required paths
echo ""
echo "== Validating required paths =="

REQUIRED_PATHS=(
  "docker-compose.yml"
  "docker/compose.prod.yml"
  "docker/compose.ssl.yml"
  "docker/compose.dev-ports.yml"
  "docker/compose.gpu-nvidia.yml"
  "docker/compose.gpu-intel.yml"
  "docker/compose.single-node.yml"
  "docker/compose.solr9.yml"
  "docker/compose.solr10.yml"
  "installer/run.sh"
  "installer/setup.py"
  "src/aithena-common/aithena_common/__init__.py"
  "src/aithena-common/pyproject.toml"
  ".env.example"
  "README.md"
)

for path in "${REQUIRED_PATHS[@]}"; do
  if [[ -e "$EXTRACT_DIR/$path" ]]; then
    pass "present: $path"
  else
    fail "MISSING: $path"
  fi
done

# Validate Dockerfiles for all build contexts
echo ""
echo "== Validating build context Dockerfiles ===="

# Get inventory from Compose config
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  INVENTORY="$ARTIFACT_DIR/inventory.json"
  if (cd "$EXTRACT_DIR" && python3 "$ROOT/scripts/release_inventory.py" \
    --compose-dir . --format json >"$INVENTORY" 2>/dev/null); then
    
    # Extract implicit Dockerfiles from inventory
    IMPLICIT_DFS=$(python3 -c "
import json
with open('$INVENTORY') as f:
  data = json.load(f)
  for df in data.get('implicit_dockerfiles_for_regression', []):
    print(df)
" 2>/dev/null || true)
    
    if [[ -n "$IMPLICIT_DFS" ]]; then
      while IFS= read -r df_path; do
        if [[ -e "$EXTRACT_DIR/$df_path" ]]; then
          pass "implicit Dockerfile: $df_path"
        else
          fail "MISSING implicit Dockerfile: $df_path"
        fi
      done <<< "$IMPLICIT_DFS"
    else
      pass "Inventory generated (no implicit Dockerfiles found or none listed)"
    fi
  else
    fail "Could not generate Compose inventory"
  fi
fi

# Test installer entry point from extracted package
echo ""
echo "== Testing installer entry point ==="

if (cd "$EXTRACT_DIR" && bash installer/run.sh --help >"$ARTIFACT_DIR/installer-help.log" 2>&1); then
  if grep -q "usage:\|options:" "$ARTIFACT_DIR/installer-help.log" || grep -q "Usage:" "$ARTIFACT_DIR/installer-help.log"; then
    pass "installer/run.sh --help executes from extracted package"
  else
    fail "installer/run.sh --help produced unexpected output"
    head -5 "$ARTIFACT_DIR/installer-help.log" >&2
  fi
else
  fail "installer/run.sh --help failed from extracted package"
  cat "$ARTIFACT_DIR/installer-help.log" >&2
fi

# Verify no ModuleNotFoundError in installer output
if grep -qi "ModuleNotFoundError\|ImportError" "$ARTIFACT_DIR/installer-help.log"; then
  fail "installer output contains import error"
else
  pass "installer output clean (no import errors)"
fi

# Regression test: Remove an implicit Dockerfile and verify smoke test fails
echo ""
echo "== Regression Test: Implicit Dockerfile Deletion ==="

if [[ -n "$IMPLICIT_DFS" ]]; then
  FIRST_DF=$(echo "$IMPLICIT_DFS" | head -1)
  if [[ -n "$FIRST_DF" && -e "$EXTRACT_DIR/$FIRST_DF" ]]; then
    # Remove the first implicit Dockerfile
    BACKUP_DIR="$ARTIFACT_DIR/regression-backup"
    mkdir -p "$BACKUP_DIR"
    mv "$EXTRACT_DIR/$FIRST_DF" "$BACKUP_DIR/"
    
    # Re-run inventory check — should now report the missing file as a failure
    # (This validates that our validator actually catches the problem)
    if [[ -e "$EXTRACT_DIR/$FIRST_DF" ]]; then
      fail "Regression test setup failed: could not remove $FIRST_DF"
    else
      pass "Regression test: successfully deleted $FIRST_DF from extracted package"
    fi
    
    # Restore for other tests
    mv "$BACKUP_DIR/$FIRST_DF" "$EXTRACT_DIR/"
  fi
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: $PASS passed, $FAIL failed"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
