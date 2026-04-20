#!/usr/bin/env bash
# =============================================================================
# Aithena — Post-Install Health Check & Verification
# =============================================================================
# Verifies that all Aithena services are running correctly after installation.
# Can be run from the offline package or from the installation directory.
#
# Usage:
#   ./verify.sh                     # standard health check
#   ./verify.sh --install-dir DIR   # check a custom install location
#   ./verify.sh --wait SECONDS      # wait for services before checking (default: 0)
#   ./verify.sh --help              # show this help
#
# Exit codes:
#   0  All services healthy
#   1  One or more services failed
#
# See also: docs/deployment/offline-deployment.md
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/aithena"
WAIT_SECONDS=0

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
pass()  { printf "  ${GREEN}✓ PASS${NC}  %s\n" "$*"; }
fail()  { printf "  ${RED}✗ FAIL${NC}  %s\n" "$*"; }
warn_v() { printf "  ${YELLOW}⚠ WARN${NC}  %s\n" "$*"; }
info()  { printf "${BLUE}[INFO]${NC}  %s\n" "$*"; }

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Verify Aithena deployment health.

Options:
  --install-dir DIR   Installation directory (default: /opt/aithena)
  --wait SECONDS      Wait for services before checking (default: 0)
  --help              Show this help message

Exit codes:
  0  All services healthy
  1  One or more checks failed
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir)  INSTALL_DIR="$2"; shift 2 ;;
    --wait)         WAIT_SECONDS="$2"; shift 2 ;;
    --help|-h)      usage; exit 0 ;;
    *)              echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Resolve compose directory
# ---------------------------------------------------------------------------
# Try install dir first, then script dir (for running from package)
if [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
  COMPOSE_DIR="$INSTALL_DIR"
elif [[ -f "${SCRIPT_DIR}/docker-compose.yml" ]]; then
  COMPOSE_DIR="$SCRIPT_DIR"
elif [[ -f "${SCRIPT_DIR}/compose/docker-compose.yml" ]]; then
  COMPOSE_DIR="${SCRIPT_DIR}/compose"
else
  echo "ERROR: Cannot find docker-compose.yml in ${INSTALL_DIR} or ${SCRIPT_DIR}" >&2
  exit 1
fi

COMPOSE_CMD="docker compose -f ${COMPOSE_DIR}/docker-compose.yml"
if [[ -f "${COMPOSE_DIR}/docker/compose.prod.yml" ]]; then
  COMPOSE_CMD="${COMPOSE_CMD} -f ${COMPOSE_DIR}/docker/compose.prod.yml"
fi

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
VERSION="unknown"
for vf in "${INSTALL_DIR}/VERSION" "${SCRIPT_DIR}/VERSION"; do
  if [[ -f "$vf" ]]; then
    VERSION="$(tr -d '[:space:]' < "$vf")"
    break
  fi
done

echo ""
echo "========================================="
echo "  Aithena v${VERSION} — Health Check"
echo "========================================="
echo ""

# ---------------------------------------------------------------------------
# Optional wait
# ---------------------------------------------------------------------------
if [[ "$WAIT_SECONDS" -gt 0 ]]; then
  info "Waiting ${WAIT_SECONDS}s for services to stabilize..."
  sleep "$WAIT_SECONDS"
fi

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNED=0

record_pass() { CHECKS_PASSED=$((CHECKS_PASSED + 1)); }
record_fail() { CHECKS_FAILED=$((CHECKS_FAILED + 1)); }
record_warn() { CHECKS_WARNED=$((CHECKS_WARNED + 1)); }

# =========================================================================
# Check 1: Docker daemon
# =========================================================================
info "Checking Docker daemon..."
if docker info &>/dev/null; then
  pass "Docker daemon is running"
  record_pass
else
  fail "Docker daemon is not running"
  record_fail
  echo ""
  echo "Cannot proceed without Docker. Start Docker and try again."
  exit 1
fi

# =========================================================================
# Check 2: Container status via docker compose ps
# =========================================================================
info "Checking container status..."

# Get service status
cd "$COMPOSE_DIR"

EXPECTED_SERVICES=(
  "redis"
  "rabbitmq"
  "embeddings-server"
  "document-lister"
  "document-indexer"
  "solr-search"
  "redis-commander"
  "aithena-ui"
  "nginx"
  "zoo1"
  "zoo2"
  "zoo3"
  "solr"
  "solr2"
  "solr3"
)

# Check each service
for svc in "${EXPECTED_SERVICES[@]}"; do
  STATUS="$(${COMPOSE_CMD} ps --format '{{.Status}}' "$svc" 2>/dev/null || echo "not found")"

  if [[ "$STATUS" == *"healthy"* ]]; then
    pass "${svc}: ${STATUS}"
    record_pass
  elif [[ "$STATUS" == *"Up"* ]]; then
    warn_v "${svc}: ${STATUS} (running but health check unknown)"
    record_warn
  elif [[ "$STATUS" == "not found" || -z "$STATUS" ]]; then
    fail "${svc}: not running"
    record_fail
  else
    fail "${svc}: ${STATUS}"
    record_fail
  fi
done

# solr-init is a one-shot container — check it completed
INIT_STATUS="$(${COMPOSE_CMD} ps --format '{{.Status}}' "solr-init" 2>/dev/null || echo "not found")"
if [[ "$INIT_STATUS" == *"Exited (0)"* ]]; then
  pass "solr-init: completed successfully"
  record_pass
elif [[ "$INIT_STATUS" == "not found" || -z "$INIT_STATUS" ]]; then
  warn_v "solr-init: not found (may have been removed after completion)"
  record_warn
else
  fail "solr-init: ${INIT_STATUS}"
  record_fail
fi

echo ""

# =========================================================================
# Check 3: HTTP health endpoints
# =========================================================================
info "Checking HTTP health endpoints..."

# Helper: check an HTTP endpoint
check_endpoint() {
  local name="$1"
  local url="$2"
  local timeout="${3:-10}"

  if curl -sf --connect-timeout "$timeout" --max-time "$timeout" -o /dev/null "$url" 2>/dev/null; then
    pass "${name}: ${url}"
    record_pass
  else
    fail "${name}: ${url} (unreachable or error)"
    record_fail
  fi
}

# nginx gateway (only service with host port binding)
check_endpoint "nginx (gateway)" "http://127.0.0.1:80/health"

# API endpoints through nginx
check_endpoint "solr-search (via nginx)" "http://127.0.0.1:80/v1/health"
check_endpoint "version endpoint" "http://127.0.0.1:80/v1/version"

# Frontend
check_endpoint "aithena-ui (via nginx)" "http://127.0.0.1:80/"

echo ""

# =========================================================================
# Check 4: Docker network connectivity (internal services)
# =========================================================================
info "Checking internal service connectivity..."

# Use docker exec via nginx to probe internal services
# (nginx is connected to all services)
NGINX_CONTAINER="$(${COMPOSE_CMD} ps -q nginx 2>/dev/null | head -1 || true)"

if [[ -n "$NGINX_CONTAINER" ]]; then
  # Check embeddings-server health (internal endpoint)
  if docker exec "$NGINX_CONTAINER" wget -qO /dev/null "http://embeddings-server:8080/health" 2>/dev/null; then
    pass "embeddings-server: internal health OK"
    record_pass
  else
    fail "embeddings-server: internal health check failed"
    record_fail
  fi

  # Check solr-search health (internal endpoint)
  if docker exec "$NGINX_CONTAINER" wget -qO /dev/null "http://solr-search:8080/health" 2>/dev/null; then
    pass "solr-search: internal health OK"
    record_pass
  else
    fail "solr-search: internal health check failed"
    record_fail
  fi

  # Check Solr admin
  if docker exec "$NGINX_CONTAINER" wget -qO /dev/null "http://solr:8983/solr/admin/info/system" 2>/dev/null; then
    pass "solr: admin API responsive"
    record_pass
  else
    fail "solr: admin API unreachable"
    record_fail
  fi
else
  warn_v "Cannot check internal connectivity: nginx container not found"
  record_warn
fi

echo ""

# =========================================================================
# Summary
# =========================================================================
TOTAL=$((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNED))

echo "========================================="
echo "  Health Check Summary"
echo "========================================="
printf "  ${GREEN}Passed:${NC}  %d\n" "$CHECKS_PASSED"
if [[ "$CHECKS_WARNED" -gt 0 ]]; then
  printf "  ${YELLOW}Warnings:${NC} %d\n" "$CHECKS_WARNED"
fi
if [[ "$CHECKS_FAILED" -gt 0 ]]; then
  printf "  ${RED}Failed:${NC}  %d\n" "$CHECKS_FAILED"
fi
echo "  Total:   ${TOTAL}"
echo ""

if [[ "$CHECKS_FAILED" -eq 0 ]]; then
  printf "  ${GREEN}✓ All checks passed!${NC}\n"
  echo ""
  echo "  Aithena is running at: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost')/"
  echo ""
  exit 0
else
  printf "  ${RED}✗ ${CHECKS_FAILED} check(s) failed.${NC}\n"
  echo ""
  echo "  Troubleshooting:"
  echo "    1. Check logs:     docker compose logs <service>"
  echo "    2. Check status:   docker compose ps"
  echo "    3. Restart:        docker compose restart <service>"
  echo "    4. Full restart:   docker compose down && docker compose up -d"
  echo ""
  exit 1
fi
