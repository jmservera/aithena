#!/bin/bash
#
# Production Smoke Test Suite for Aithena
# ==========================================
# Post-deployment validation script that checks all services are healthy
# and critical user flows are functional.
#
# Usage:
#   ./production-smoke-test.sh [--host HOST] [--timeout SECONDS]
#
# Environment Variables:
#   AITHENA_HOST        - Host to test (default: localhost)
#   AITHENA_TIMEOUT     - Timeout for HTTP requests in seconds (default: 10)
#   SMOKE_AUTH_TOKEN    - Pre-configured Bearer token for /v1/* endpoints (optional)
#   ADMIN_USERNAME      - Admin username for authenticated endpoints (default: admin)
#   ADMIN_PASSWORD      - Admin password for authenticated endpoints (required for admin tests)
#
#   If neither SMOKE_AUTH_TOKEN nor ADMIN_PASSWORD is set, tests for protected
#   /v1/* endpoints will be skipped with a warning.
#
# Exit Codes:
#   0 - All checks passed
#   1 - One or more checks failed
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

HOST="${AITHENA_HOST:-localhost}"
TIMEOUT="${AITHENA_TIMEOUT:-10}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
SMOKE_AUTH_TOKEN="${SMOKE_AUTH_TOKEN:-}"
AUTH_TOKEN=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --help|-h)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# Color output helpers
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

log_info() {
    echo -e "${YELLOW}ℹ${NC} $*"
}

log_pass() {
    echo -e "${GREEN}✅${NC} $*"
    PASS_COUNT=$((PASS_COUNT + 1))
}

log_fail() {
    echo -e "${RED}❌${NC} $*"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

log_skip() {
    echo -e "${YELLOW}⊘${NC} $*"
    SKIP_COUNT=$((SKIP_COUNT + 1))
}

# ============================================================================
# HTTP check helpers
# ============================================================================

check_http() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local extra_args="${4:-}"

    local -a curl_opts=(-sf -m "$TIMEOUT" -o /dev/null -w "%{http_code}")
    if [[ -n "$AUTH_TOKEN" ]]; then
        curl_opts+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi
    if [[ -n "$extra_args" ]]; then
        curl_opts+=($extra_args)
    fi
    curl_opts+=("$url")

    if curl "${curl_opts[@]}" | grep -q "^${expected_status}$"; then
        log_pass "$name"
        return 0
    else
        log_fail "$name - Expected HTTP $expected_status from $url"
        return 1
    fi
}

check_http_json() {
    local name="$1"
    local url="$2"
    local json_field="$3"
    local extra_args="${4:-}"

    local -a curl_opts=(-sf -m "$TIMEOUT")
    if [[ -n "$AUTH_TOKEN" ]]; then
        curl_opts+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi
    if [[ -n "$extra_args" ]]; then
        curl_opts+=($extra_args)
    fi
    curl_opts+=("$url")

    local response
    response=$(curl "${curl_opts[@]}" 2>/dev/null || true)

    if [[ -z "$response" ]]; then
        log_fail "$name - No response from $url"
        return 1
    fi

    if echo "$response" | grep -q "\"${json_field}\""; then
        log_pass "$name"
        return 0
    else
        log_fail "$name - Response missing field '$json_field'"
        return 1
    fi
}

# ============================================================================
# Auth token helpers
# ============================================================================

# Acquire an auth token for protected /v1/* endpoints.
# Uses SMOKE_AUTH_TOKEN env var if set, otherwise logs in with admin credentials.
acquire_auth_token() {
    if [[ -n "$SMOKE_AUTH_TOKEN" ]]; then
        AUTH_TOKEN="$SMOKE_AUTH_TOKEN"
        log_info "Using pre-configured auth token (SMOKE_AUTH_TOKEN)"
        return 0
    fi

    if [[ -z "$ADMIN_PASSWORD" ]]; then
        log_info "⚠ No auth token available (set SMOKE_AUTH_TOKEN or ADMIN_PASSWORD)"
        log_info "  Tests for protected /v1/* endpoints will be skipped"
        return 1
    fi

    local login_response
    login_response=$(curl -sf -m "$TIMEOUT" -X POST "http://${HOST}/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${ADMIN_USERNAME}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
        2>/dev/null || true)

    if [[ -z "$login_response" ]]; then
        log_info "⚠ Login request failed — protected endpoint tests will be skipped"
        return 1
    fi

    local access_token
    access_token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 || true)

    if [[ -z "$access_token" ]]; then
        log_info "⚠ Login did not return access token — protected endpoint tests will be skipped"
        return 1
    fi

    AUTH_TOKEN="$access_token"
    log_info "Acquired auth token via admin login"
    return 0
}

# Check that AUTH_TOKEN is set; if not, skip the calling test.
require_auth() {
    local test_name="$1"
    if [[ -z "$AUTH_TOKEN" ]]; then
        log_skip "$test_name (no auth token — set SMOKE_AUTH_TOKEN or ADMIN_PASSWORD)"
        return 1
    fi
    return 0
}

# ============================================================================
# Test: Docker Health Checks via /health endpoints
# ============================================================================

test_health_endpoints() {
    log_info "Testing service health endpoints..."

    # Nginx /health — no auth required (public endpoint)
    check_http "Nginx health check" "http://${HOST}/health"

    # Solr-search API /v1/health — exact-match location, no auth required
    check_http "API health endpoint" "http://${HOST}/v1/health"

    # Admin dashboard health (via nginx proxy to streamlit)
    # Streamlit health endpoint is at /admin/streamlit/_stcore/health
    check_http "Admin dashboard health" "http://${HOST}/admin/streamlit/_stcore/health"
}

# ============================================================================
# Test: Version Endpoints
# ============================================================================

test_version_endpoints() {
    log_info "Testing version endpoints..."

    # /v1/version — exact-match location, no auth required
    check_http_json "API version endpoint" "http://${HOST}/v1/version" "version"

    # Check that version field is not empty
    local version
    version=$(curl -sf -m "$TIMEOUT" "http://${HOST}/v1/version" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ -n "$version" && "$version" != "dev" ]]; then
        log_pass "API version is set: $version"
    elif [[ "$version" == "dev" ]]; then
        log_pass "API version is set: $version (development)"
    else
        log_fail "API version is empty or invalid"
    fi
}

# ============================================================================
# Test: Search API Endpoints (protected — behind nginx auth_request)
# ============================================================================

test_search_api() {
    log_info "Testing search API endpoints..."

    if ! require_auth "Search API tests"; then
        return 0
    fi

    # All /v1/* endpoints (except exact-match public ones) require auth
    check_http "Search endpoint" "http://${HOST}/v1/search"
    check_http "Search with query" "http://${HOST}/v1/search?q=test"
    check_http "Facets endpoint" "http://${HOST}/v1/facets"
    check_http "Stats endpoint" "http://${HOST}/v1/stats"
    check_http "Books endpoint" "http://${HOST}/v1/books"
}

# ============================================================================
# Test: UI Loads
# ============================================================================

test_ui_loads() {
    log_info "Testing UI availability..."

    # Main UI should load (nginx serves React app) — no auth required
    check_http "UI homepage loads" "http://${HOST}/"

    # Check for HTML response with expected content
    local response
    response=$(curl -sf -m "$TIMEOUT" "http://${HOST}/" 2>/dev/null || true)
    if echo "$response" | grep -q "<html"; then
        log_pass "UI returns valid HTML"
    else
        log_fail "UI did not return valid HTML"
    fi
}

# ============================================================================
# Test: Admin Dashboard
# ============================================================================

test_admin_dashboard() {
    log_info "Testing admin dashboard..."

    # Admin dashboard loads (proxied by nginx, behind auth_request with redirect)
    # Streamlit apps redirect to trailing slash, so we expect 200 or 301/302
    if check_http "Admin dashboard loads" "http://${HOST}/admin/streamlit/" "200" "-L"; then
        : # Pass already logged
    elif check_http "Admin dashboard redirects" "http://${HOST}/admin/streamlit" "301" ""; then
        log_pass "Admin dashboard redirect working"
    elif check_http "Admin dashboard redirects" "http://${HOST}/admin/streamlit" "302" ""; then
        log_pass "Admin dashboard redirect working"
    else
        log_fail "Admin dashboard not accessible"
    fi
}

# ============================================================================
# Test: Solr Cluster Health (protected — /v1/status behind auth_request)
# ============================================================================

test_solr_cluster() {
    log_info "Testing Solr cluster health..."

    if ! require_auth "Solr cluster health tests"; then
        return 0
    fi

    # Solr is not directly exposed, but we can check via the API status endpoint
    check_http_json "Solr status via API" "http://${HOST}/v1/status" "solr"

    # Check that Solr is reported as healthy
    local solr_status
    local -a status_opts=(-sf -m "$TIMEOUT")
    if [[ -n "$AUTH_TOKEN" ]]; then
        status_opts+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi
    solr_status=$(curl "${status_opts[@]}" "http://${HOST}/v1/status" 2>/dev/null | grep -o '"solr":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ "$solr_status" == "healthy" ]]; then
        log_pass "Solr cluster is healthy"
    elif [[ -n "$solr_status" ]]; then
        log_fail "Solr cluster status: $solr_status (expected: healthy)"
    else
        log_fail "Could not determine Solr cluster status"
    fi
}

# ============================================================================
# Test: Redis Connectivity (protected — /v1/status behind auth_request)
# ============================================================================

test_redis() {
    log_info "Testing Redis connectivity..."

    if ! require_auth "Redis connectivity tests"; then
        return 0
    fi

    # Redis is not directly exposed, check via API status endpoint
    local redis_status
    local -a status_opts=(-sf -m "$TIMEOUT")
    if [[ -n "$AUTH_TOKEN" ]]; then
        status_opts+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi
    redis_status=$(curl "${status_opts[@]}" "http://${HOST}/v1/status" 2>/dev/null | grep -o '"redis":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ "$redis_status" == "connected" ]]; then
        log_pass "Redis is connected"
    elif [[ -n "$redis_status" ]]; then
        log_fail "Redis status: $redis_status (expected: connected)"
    else
        log_fail "Could not determine Redis status"
    fi
}

# ============================================================================
# Test: RabbitMQ Connectivity (protected — /v1/status behind auth_request)
# ============================================================================

test_rabbitmq() {
    log_info "Testing RabbitMQ connectivity..."

    if ! require_auth "RabbitMQ connectivity tests"; then
        return 0
    fi

    # RabbitMQ is not directly exposed, check via API status endpoint
    local rabbitmq_status
    local -a status_opts=(-sf -m "$TIMEOUT")
    if [[ -n "$AUTH_TOKEN" ]]; then
        status_opts+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi
    rabbitmq_status=$(curl "${status_opts[@]}" "http://${HOST}/v1/status" 2>/dev/null | grep -o '"rabbitmq":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ "$rabbitmq_status" == "connected" ]]; then
        log_pass "RabbitMQ is connected"
    elif [[ -n "$rabbitmq_status" ]]; then
        log_fail "RabbitMQ status: $rabbitmq_status (expected: connected)"
    else
        log_fail "Could not determine RabbitMQ status"
    fi
}

# ============================================================================
# Test: Authenticated Admin Endpoints (requires auth token)
# ============================================================================

test_authenticated_endpoints() {
    log_info "Testing authenticated admin endpoints..."

    if ! require_auth "Authenticated admin endpoint tests"; then
        return 0
    fi

    # Test /v1/admin/containers endpoint (admin-only, requires auth)
    check_http_json "Admin containers endpoint" "http://${HOST}/v1/admin/containers" "containers"

    # Test /v1/auth/validate endpoint (verifies the token itself)
    check_http_json "Auth validate endpoint" "http://${HOST}/v1/auth/validate" "username"
}

# ============================================================================
# Test: PDF Viewer (critical user flow)
# ============================================================================

test_pdf_viewer() {
    log_info "Testing PDF viewer..."

    # PDF viewer is a frontend feature - check that the UI assets are served
    # The actual PDF viewing requires documents to be indexed, so we just check
    # that the UI loads (already tested in test_ui_loads)
    log_skip "PDF viewer functional test (requires indexed documents)"
}

# ============================================================================
# Test: Similar Books Feature (protected — /v1/books/* behind auth_request)
# ============================================================================

test_similar_books() {
    log_info "Testing similar books feature..."

    if ! require_auth "Similar books tests"; then
        return 0
    fi

    # Similar books endpoint requires a valid document ID
    # For smoke test, just verify the endpoint exists and returns 404 for invalid ID
    # (not 500 or connection error)
    local -a curl_opts=(-sf -m "$TIMEOUT" -o /dev/null -w "%{http_code}")
    if [[ -n "$AUTH_TOKEN" ]]; then
        curl_opts+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi
    curl_opts+=("http://${HOST}/v1/books/nonexistent-id/similar")

    local status_code
    status_code=$(curl "${curl_opts[@]}" || echo "000")

    if [[ "$status_code" == "404" ]]; then
        log_pass "Similar books endpoint exists (returned 404 for invalid ID)"
    elif [[ "$status_code" == "200" ]]; then
        log_pass "Similar books endpoint is functional"
    else
        log_fail "Similar books endpoint returned unexpected status: $status_code"
    fi
}

# ============================================================================
# Main Test Execution
# ============================================================================

main() {
    echo "=================================================="
    echo "Aithena Production Smoke Test Suite"
    echo "=================================================="
    echo "Host: $HOST"
    echo "Timeout: ${TIMEOUT}s"
    echo ""

    # Acquire auth token for protected /v1/* endpoints (best-effort)
    acquire_auth_token || true
    echo ""

    # Run all test suites
    test_health_endpoints
    test_version_endpoints
    test_search_api
    test_ui_loads
    test_admin_dashboard
    test_solr_cluster
    test_redis
    test_rabbitmq
    test_authenticated_endpoints
    test_pdf_viewer
    test_similar_books

    # Summary
    echo ""
    echo "=================================================="
    echo "Test Summary"
    echo "=================================================="
    echo -e "${GREEN}Passed:${NC} $PASS_COUNT"
    echo -e "${RED}Failed:${NC} $FAIL_COUNT"
    echo -e "${YELLOW}Skipped:${NC} $SKIP_COUNT"
    echo "=================================================="

    if [[ $FAIL_COUNT -eq 0 ]]; then
        echo -e "${GREEN}✅ All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}❌ Some tests failed!${NC}"
        exit 1
    fi
}

# Run main function
main
