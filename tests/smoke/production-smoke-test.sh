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
#   ADMIN_USERNAME      - Admin username for authenticated endpoints (default: admin)
#   ADMIN_PASSWORD      - Admin password for authenticated endpoints (required for admin tests)
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
# HTTP check helper
# ============================================================================

check_http() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local extra_args="${4:-}"
    
    if curl -sf -m "$TIMEOUT" -o /dev/null -w "%{http_code}" $extra_args "$url" | grep -q "^${expected_status}$"; then
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
    
    local response
    response=$(curl -sf -m "$TIMEOUT" $extra_args "$url" 2>/dev/null || true)
    
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
# Test: Docker Health Checks via /health endpoints
# ============================================================================

test_health_endpoints() {
    log_info "Testing service health endpoints..."
    
    # Nginx proxies to solr-search /health
    check_http "Nginx health check" "http://${HOST}/health"
    
    # Solr-search API health (via nginx proxy)
    check_http "API health endpoint" "http://${HOST}/api/health"
    
    # Admin dashboard health (via nginx proxy to streamlit)
    # Streamlit health endpoint is at /admin/streamlit/_stcore/health
    check_http "Admin dashboard health" "http://${HOST}/admin/streamlit/_stcore/health"
}

# ============================================================================
# Test: Version Endpoints
# ============================================================================

test_version_endpoints() {
    log_info "Testing version endpoints..."
    
    # API version endpoint
    check_http_json "API version endpoint" "http://${HOST}/api/version" "version"
    
    # Check that version field is not empty
    local version
    version=$(curl -sf -m "$TIMEOUT" "http://${HOST}/api/version" 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ -n "$version" && "$version" != "dev" ]]; then
        log_pass "API version is set: $version"
    elif [[ "$version" == "dev" ]]; then
        log_pass "API version is set: $version (development)"
    else
        log_fail "API version is empty or invalid"
    fi
}

# ============================================================================
# Test: Search API Endpoints
# ============================================================================

test_search_api() {
    log_info "Testing search API endpoints..."
    
    # Search endpoint (should return 200 even with no query - returns all docs)
    check_http "Search endpoint" "http://${HOST}/api/search"
    
    # Search with query parameter
    check_http "Search with query" "http://${HOST}/api/search?q=test"
    
    # Facets endpoint
    check_http "Facets endpoint" "http://${HOST}/api/facets"
    
    # Stats endpoint
    check_http "Stats endpoint" "http://${HOST}/api/stats"
    
    # Books endpoint
    check_http "Books endpoint" "http://${HOST}/api/books"
}

# ============================================================================
# Test: UI Loads
# ============================================================================

test_ui_loads() {
    log_info "Testing UI availability..."
    
    # Main UI should load (nginx serves React app)
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
    
    # Admin dashboard loads (proxied by nginx)
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
# Test: Solr Cluster Health
# ============================================================================

test_solr_cluster() {
    log_info "Testing Solr cluster health..."
    
    # Solr is not directly exposed, but we can check via the API status endpoint
    check_http_json "Solr status via API" "http://${HOST}/api/v1/status" "solr"
    
    # Check that Solr is reported as healthy
    local solr_status
    solr_status=$(curl -sf -m "$TIMEOUT" "http://${HOST}/api/v1/status" 2>/dev/null | grep -o '"solr":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ "$solr_status" == "healthy" ]]; then
        log_pass "Solr cluster is healthy"
    elif [[ -n "$solr_status" ]]; then
        log_fail "Solr cluster status: $solr_status (expected: healthy)"
    else
        log_fail "Could not determine Solr cluster status"
    fi
}

# ============================================================================
# Test: Redis Connectivity
# ============================================================================

test_redis() {
    log_info "Testing Redis connectivity..."
    
    # Redis is not directly exposed, check via API status endpoint
    local redis_status
    redis_status=$(curl -sf -m "$TIMEOUT" "http://${HOST}/api/v1/status" 2>/dev/null | grep -o '"redis":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ "$redis_status" == "connected" ]]; then
        log_pass "Redis is connected"
    elif [[ -n "$redis_status" ]]; then
        log_fail "Redis status: $redis_status (expected: connected)"
    else
        log_fail "Could not determine Redis status"
    fi
}

# ============================================================================
# Test: RabbitMQ Connectivity
# ============================================================================

test_rabbitmq() {
    log_info "Testing RabbitMQ connectivity..."
    
    # RabbitMQ is not directly exposed, check via API status endpoint
    local rabbitmq_status
    rabbitmq_status=$(curl -sf -m "$TIMEOUT" "http://${HOST}/api/v1/status" 2>/dev/null | grep -o '"rabbitmq":"[^"]*"' | cut -d'"' -f4 || true)
    if [[ "$rabbitmq_status" == "connected" ]]; then
        log_pass "RabbitMQ is connected"
    elif [[ -n "$rabbitmq_status" ]]; then
        log_fail "RabbitMQ status: $rabbitmq_status (expected: connected)"
    else
        log_fail "Could not determine RabbitMQ status"
    fi
}

# ============================================================================
# Test: Authenticated Endpoints (requires admin credentials)
# ============================================================================

test_authenticated_endpoints() {
    log_info "Testing authenticated endpoints..."
    
    if [[ -z "$ADMIN_PASSWORD" ]]; then
        log_skip "Authenticated endpoint tests (ADMIN_PASSWORD not set)"
        return 0
    fi
    
    # Login and get token
    local login_response
    login_response=$(curl -sf -m "$TIMEOUT" -X POST "http://${HOST}/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${ADMIN_USERNAME}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
        2>/dev/null || true)
    
    if [[ -z "$login_response" ]]; then
        log_fail "Login request failed"
        return 1
    fi
    
    local access_token
    access_token=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 || true)
    
    if [[ -z "$access_token" ]]; then
        log_fail "Login did not return access token"
        return 1
    fi
    
    log_pass "Admin login successful"
    
    # Test /v1/admin/containers endpoint with auth
    check_http_json "Admin containers endpoint" "http://${HOST}/api/v1/admin/containers" "containers" "-H 'Authorization: Bearer ${access_token}'"
    
    # Test /v1/auth/validate endpoint
    check_http_json "Auth validate endpoint" "http://${HOST}/api/v1/auth/validate" "username" "-H 'Authorization: Bearer ${access_token}'"
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
# Test: Similar Books Feature
# ============================================================================

test_similar_books() {
    log_info "Testing similar books feature..."
    
    # Similar books endpoint requires a valid document ID
    # For smoke test, just verify the endpoint exists and returns 404 for invalid ID
    # (not 500 or connection error)
    local status_code
    status_code=$(curl -sf -m "$TIMEOUT" -o /dev/null -w "%{http_code}" "http://${HOST}/api/books/nonexistent-id/similar" || echo "000")
    
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
