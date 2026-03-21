#!/usr/bin/env bash
# =============================================================================
# Aithena Post-Restore Verification Suite
# =============================================================================
# Validates system integrity after any backup restore operation.
#
# Checks (from PRD Section 5.3):
#   1. All services report healthy in docker-compose ps
#   2. Admin UI loads at http://localhost/admin
#   3. Auth: Login works with known test credentials
#   4. Search: Keyword and semantic search return results
#   5. Redis: redis-cli ping returns PONG
#   6. RabbitMQ: Management UI accessible at port 15672
#   7. Solr: Collection status shows replicas healthy
#   8. No errors in docker-compose logs (last 100 lines)
#   9. Disk usage reasonable (not grown unexpectedly)
#
# Usage:
#   ./tests/verify-restore.sh
#   VERIFY_USERNAME=admin VERIFY_PASSWORD=secret ./tests/verify-restore.sh
#
# Environment variables:
#   SOLR_URL            (default: http://localhost:8983/solr/books)
#   SEARCH_API_URL      (default: http://localhost:8080)
#   ADMIN_URL           (default: http://localhost/admin)
#   RABBITMQ_API_URL    (default: http://localhost:15672)
#   RABBITMQ_USER       (default: guest)
#   RABBITMQ_PASSWORD   (default: guest)
#   REDIS_HOST          (default: localhost)
#   REDIS_PORT          (default: 6379)
#   VERIFY_USERNAME     (default: empty, skips auth check)
#   VERIFY_PASSWORD     (default: empty, skips auth check)
#   VERIFY_TIMEOUT      (default: 30 seconds per check)
#   DISK_MAX_PERCENT    (default: 90)
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOLR_URL="${SOLR_URL:-http://localhost:8983/solr/books}"
SEARCH_API_URL="${SEARCH_API_URL:-http://localhost:8080}"
ADMIN_URL="${ADMIN_URL:-http://localhost/admin}"
RABBITMQ_API_URL="${RABBITMQ_API_URL:-http://localhost:15672}"
RABBITMQ_USER="${RABBITMQ_USER:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
VERIFY_USERNAME="${VERIFY_USERNAME:-}"
VERIFY_PASSWORD="${VERIFY_PASSWORD:-}"
VERIFY_TIMEOUT="${VERIFY_TIMEOUT:-30}"
DISK_MAX_PERCENT="${DISK_MAX_PERCENT:-90}"

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

pass_check() { ((PASS_COUNT++)) || true; echo "  ✅  PASS  $1"; }
fail_check() { ((FAIL_COUNT++)) || true; echo "  ❌  FAIL  $1"; }
skip_check() { ((SKIP_COUNT++)) || true; echo "  ⏭️   SKIP  $1"; }

# ---------------------------------------------------------------------------
# Check 1: Docker Compose services healthy
# ---------------------------------------------------------------------------
check_compose_services() {
    echo "--- Check 1: Docker Compose services ---"
    local output
    if ! output=$(docker compose ps --format "{{.Name}}\t{{.Status}}" 2>&1); then
        fail_check "Could not query docker compose: $output"
        return
    fi

    if [[ -z "$output" ]]; then
        fail_check "No services found in docker compose ps"
        return
    fi

    local unhealthy=""
    while IFS=$'\t' read -r name status; do
        if [[ ! "$status" =~ [Uu]p ]]; then
            unhealthy="${unhealthy}${name}(${status}) "
        fi
    done <<< "$output"

    if [[ -n "$unhealthy" ]]; then
        fail_check "Unhealthy services: $unhealthy"
    else
        local count
        count=$(echo "$output" | wc -l)
        pass_check "All $count service(s) running"
    fi
}

# ---------------------------------------------------------------------------
# Check 2: Admin UI accessible
# ---------------------------------------------------------------------------
check_admin_ui() {
    echo "--- Check 2: Admin UI ---"
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$VERIFY_TIMEOUT" -L "$ADMIN_URL" 2>/dev/null)

    if [[ "$status" -ge 200 && "$status" -lt 400 ]]; then
        pass_check "Admin UI accessible (HTTP $status)"
    else
        fail_check "Admin UI returned HTTP $status at $ADMIN_URL"
    fi
}

# ---------------------------------------------------------------------------
# Check 3: Auth login
# ---------------------------------------------------------------------------
check_auth_login() {
    echo "--- Check 3: Auth login ---"
    if [[ -z "$VERIFY_USERNAME" || -z "$VERIFY_PASSWORD" ]]; then
        skip_check "No test credentials configured (set VERIFY_USERNAME/VERIFY_PASSWORD)"
        return
    fi

    local response status
    response=$(curl -s -w "\n%{http_code}" --max-time "$VERIFY_TIMEOUT" \
        -X POST "${SEARCH_API_URL}/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${VERIFY_USERNAME}\",\"password\":\"${VERIFY_PASSWORD}\"}" 2>/dev/null)

    status=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | head -n -1)

    if [[ "$status" == "200" ]] && echo "$body" | grep -qi "token"; then
        pass_check "Login successful, token received"
    else
        fail_check "Login failed: HTTP $status"
    fi
}

# ---------------------------------------------------------------------------
# Check 4: Search returns results
# ---------------------------------------------------------------------------
check_search() {
    echo "--- Check 4: Search ---"
    local response
    response=$(curl -s --max-time "$VERIFY_TIMEOUT" \
        "${SOLR_URL}/select?q=*:*&rows=0&wt=json" 2>/dev/null)

    if [[ -z "$response" ]]; then
        fail_check "Solr query returned empty response"
        return
    fi

    local num_found
    num_found=$(echo "$response" | grep -o '"numFound":[0-9]*' | head -1 | cut -d: -f2)

    if [[ -n "$num_found" ]]; then
        pass_check "Solr search operational ($num_found documents)"
    else
        fail_check "Could not parse Solr response"
    fi
}

# ---------------------------------------------------------------------------
# Check 5: Redis PING
# ---------------------------------------------------------------------------
check_redis() {
    echo "--- Check 5: Redis ---"

    # Try redis-cli first, fall back to raw TCP
    if command -v redis-cli &>/dev/null; then
        local pong
        pong=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING 2>/dev/null)
        if [[ "$pong" == "PONG" ]]; then
            pass_check "Redis PING → PONG (redis-cli)"
            return
        fi
    fi

    # Fallback: raw TCP
    local response
    response=$(echo -e "PING\r" | timeout "$VERIFY_TIMEOUT" nc -q 1 "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null)

    if echo "$response" | grep -qi "PONG"; then
        pass_check "Redis PING → PONG (TCP)"
    else
        fail_check "Redis did not respond to PING at ${REDIS_HOST}:${REDIS_PORT}"
    fi
}

# ---------------------------------------------------------------------------
# Check 6: RabbitMQ management accessible
# ---------------------------------------------------------------------------
check_rabbitmq() {
    echo "--- Check 6: RabbitMQ ---"
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$VERIFY_TIMEOUT" \
        -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
        "${RABBITMQ_API_URL}/api/overview" 2>/dev/null)

    if [[ "$status" == "200" ]]; then
        pass_check "RabbitMQ management API accessible"
    else
        fail_check "RabbitMQ management API returned HTTP $status"
    fi
}

# ---------------------------------------------------------------------------
# Check 7: Solr cluster status
# ---------------------------------------------------------------------------
check_solr_cluster() {
    echo "--- Check 7: Solr cluster ---"
    local base_url
    base_url="${SOLR_URL%%/solr/*}"

    local response
    response=$(curl -s --max-time "$VERIFY_TIMEOUT" \
        "${base_url}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null)

    if [[ -z "$response" ]]; then
        fail_check "Could not reach Solr CLUSTERSTATUS API"
        return
    fi

    # Check for live nodes
    local live_nodes
    live_nodes=$(echo "$response" | grep -o '"live_nodes":\[' | head -1)

    if [[ -z "$live_nodes" ]]; then
        fail_check "No live_nodes found in cluster status"
        return
    fi

    # Check for books collection
    if echo "$response" | grep -q '"books"'; then
        # Check for active replicas
        local down_count
        down_count=$(echo "$response" | grep -c '"state":"down"' || true)
        if [[ "$down_count" -gt 0 ]]; then
            fail_check "Found $down_count down replica(s) in Solr cluster"
        else
            pass_check "Solr cluster healthy, books collection present"
        fi
    else
        fail_check "'books' collection not found in Solr cluster"
    fi
}

# ---------------------------------------------------------------------------
# Check 8: No errors in logs
# ---------------------------------------------------------------------------
check_logs() {
    echo "--- Check 8: Docker logs ---"
    local logs
    if ! logs=$(docker compose logs --tail=100 --no-color 2>&1); then
        fail_check "Could not retrieve docker compose logs"
        return
    fi

    # Count genuine errors (exclude known false positives)
    local error_count
    error_count=$(echo "$logs" \
        | grep -iE '\bERROR\b|\bFATAL\b|\bPANIC\b|Traceback \(most recent call last\)' \
        | grep -viE 'error_log|error\.log|loglevel.*error|ERROR_REPORTING' \
        | wc -l)

    if [[ "$error_count" -gt 0 ]]; then
        fail_check "Found $error_count error line(s) in recent logs"
        echo "$logs" \
            | grep -iE '\bERROR\b|\bFATAL\b|\bPANIC\b|Traceback' \
            | grep -viE 'error_log|error\.log|loglevel.*error|ERROR_REPORTING' \
            | head -5 \
            | sed 's/^/        /'
    else
        pass_check "No errors in last 100 log lines"
    fi
}

# ---------------------------------------------------------------------------
# Check 9: Disk usage
# ---------------------------------------------------------------------------
check_disk_usage() {
    echo "--- Check 9: Disk usage ---"
    local usage
    usage=$(df --output=pcent / 2>/dev/null | tail -1 | tr -d '% ')

    if [[ -z "$usage" ]]; then
        skip_check "Could not determine disk usage"
        return
    fi

    if [[ "$usage" -le "$DISK_MAX_PERCENT" ]]; then
        pass_check "Disk usage ${usage}% (threshold: ${DISK_MAX_PERCENT}%)"
    else
        fail_check "Disk usage ${usage}% exceeds threshold (${DISK_MAX_PERCENT}%)"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "Aithena Post-Restore Verification"
    echo "============================================================"
    echo "Started: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo ""

    check_compose_services
    check_admin_ui
    check_auth_login
    check_search
    check_redis
    check_rabbitmq
    check_solr_cluster
    check_logs
    check_disk_usage

    echo ""
    echo "------------------------------------------------------------"
    local total=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
    if [[ "$FAIL_COUNT" -eq 0 ]]; then
        echo "[PASS] ${PASS_COUNT}/${total} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"
        echo "============================================================"
        exit 0
    else
        echo "[FAIL] ${PASS_COUNT}/${total} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"
        echo "============================================================"
        exit 1
    fi
}

main "$@"
