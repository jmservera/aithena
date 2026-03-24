#!/usr/bin/env bash
# verify.sh — Deterministic quality gate for all aithena services.
# Run before committing. Exit code 0 = all checks pass.
#
# Usage:
#   .squad/scripts/verify.sh              # auto-detect changed services
#   .squad/scripts/verify.sh --all        # check everything
#   .squad/scripts/verify.sh --service X  # check specific service(s)
#   .squad/scripts/verify.sh --lint-only  # skip tests, only lint/format

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

FAILURES=()
SKIPPED=()
LINT_ONLY=false
CHECK_ALL=false
SPECIFIC_SERVICES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) CHECK_ALL=true; shift ;;
    --lint-only) LINT_ONLY=true; shift ;;
    --service) SPECIFIC_SERVICES+=("$2"); shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

PYTHON_SERVICES=(document-indexer document-lister embeddings-server solr-search admin)
NODE_SERVICES=(aithena-ui)

# Determine which services have changes (staged or unstaged vs origin/dev)
changed_services() {
  local changed_files
  # Check staged files first, fall back to diff against origin/dev
  changed_files=$(git diff --cached --name-only 2>/dev/null || true)
  if [ -z "$changed_files" ]; then
    changed_files=$(git diff --name-only origin/dev 2>/dev/null || true)
  fi
  if [ -z "$changed_files" ]; then
    changed_files=$(git diff --name-only HEAD 2>/dev/null || true)
  fi

  local services=()
  for svc in "${PYTHON_SERVICES[@]}" "${NODE_SERVICES[@]}"; do
    if echo "$changed_files" | grep -q "^src/$svc/"; then
      services+=("$svc")
    fi
  done

  # Also check if root config files changed (ruff.toml, etc.)
  if echo "$changed_files" | grep -qE '^(ruff\.toml|\.eslintrc)'; then
    # If root lint config changed, check everything
    for svc in "${PYTHON_SERVICES[@]}" "${NODE_SERVICES[@]}"; do
      if [[ ! " ${services[*]} " =~ " $svc " ]]; then
        services+=("$svc")
      fi
    done
  fi

  echo "${services[@]}"
}

# Determine target services
if [ ${#SPECIFIC_SERVICES[@]} -gt 0 ]; then
  TARGETS=("${SPECIFIC_SERVICES[@]}")
elif [ "$CHECK_ALL" = true ]; then
  TARGETS=("${PYTHON_SERVICES[@]}" "${NODE_SERVICES[@]}")
else
  read -ra TARGETS <<< "$(changed_services)"
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
  echo -e "${GREEN}✅ No changed services detected. Nothing to verify.${NC}"
  echo "   Use --all to check everything, or --service <name> for a specific service."
  exit 0
fi

echo "🔍 Verifying: ${TARGETS[*]}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_check() {
  local label="$1"
  shift
  echo -e "\n${YELLOW}▶ $label${NC}"
  if "$@"; then
    echo -e "${GREEN}  ✅ $label passed${NC}"
  else
    echo -e "${RED}  ❌ $label FAILED${NC}"
    FAILURES+=("$label")
  fi
}

# Python service checks
check_python_service() {
  local svc="$1"
  local svc_dir="src/$svc"

  if [ ! -d "$svc_dir" ]; then
    SKIPPED+=("$svc (directory not found)")
    return
  fi

  # Lint with ruff (uses root ruff.toml)
  run_check "$svc: ruff check" ruff check "$svc_dir"
  run_check "$svc: ruff format --check" ruff format --check "$svc_dir"

  if [ "$LINT_ONLY" = true ]; then
    return
  fi

  # Tests (only if venv/lockfile exists)
  if [ -f "$svc_dir/uv.lock" ] || [ -f "$svc_dir/pyproject.toml" ]; then
    pushd "$svc_dir" > /dev/null
    if [ -d "tests" ] || find . -name "test_*.py" -maxdepth 2 | grep -q .; then
      run_check "$svc: pytest" uv run pytest --tb=short -q
    else
      SKIPPED+=("$svc: pytest (no tests found)")
    fi
    popd > /dev/null
  else
    SKIPPED+=("$svc: pytest (no pyproject.toml)")
  fi
}

# Node service checks
check_node_service() {
  local svc="$1"
  local svc_dir="src/$svc"

  if [ ! -d "$svc_dir" ]; then
    SKIPPED+=("$svc (directory not found)")
    return
  fi

  pushd "$svc_dir" > /dev/null

  # Ensure deps are installed
  if [ ! -d "node_modules" ] && [ -f "package-lock.json" ]; then
    echo -e "${YELLOW}  ⏳ Installing npm dependencies...${NC}"
    npm ci --silent
  fi

  # Lint
  if grep -q '"lint"' package.json 2>/dev/null; then
    run_check "$svc: eslint" npm run lint
  fi

  # Format
  if grep -q '"format:check"' package.json 2>/dev/null; then
    run_check "$svc: prettier" npm run format:check
  fi

  # TypeScript compilation
  if grep -q '"build"' package.json 2>/dev/null; then
    run_check "$svc: tsc build" npm run build
  fi

  if [ "$LINT_ONLY" = true ]; then
    popd > /dev/null
    return
  fi

  # Tests
  if grep -q '"test"' package.json 2>/dev/null || [ -f "vitest.config.ts" ] || [ -f "vitest.config.js" ]; then
    run_check "$svc: vitest" npx vitest run
  else
    SKIPPED+=("$svc: tests (no test script)")
  fi

  popd > /dev/null
}

# Run checks for each target
for svc in "${TARGETS[@]}"; do
  echo ""
  echo "━━━ $svc ━━━"
  if [[ " ${PYTHON_SERVICES[*]} " =~ " $svc " ]]; then
    check_python_service "$svc"
  elif [[ " ${NODE_SERVICES[*]} " =~ " $svc " ]]; then
    check_node_service "$svc"
  else
    echo -e "${RED}  Unknown service: $svc${NC}"
    FAILURES+=("Unknown service: $svc")
  fi
done

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo -e "${YELLOW}⏭️  Skipped:${NC}"
  for s in "${SKIPPED[@]}"; do
    echo "   - $s"
  done
fi

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo -e "\n${RED}❌ FAILED (${#FAILURES[@]} checks):${NC}"
  for f in "${FAILURES[@]}"; do
    echo "   - $f"
  done
  echo ""
  echo -e "${RED}Fix these before committing.${NC}"
  exit 1
else
  echo -e "\n${GREEN}✅ All checks passed.${NC}"
  exit 0
fi
