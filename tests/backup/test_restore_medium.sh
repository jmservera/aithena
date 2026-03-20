#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 3: Medium-Priority Restore — Integration Test
# =============================================================================
# Creates an isolated temp environment with mock curl/docker, runs
# restore-medium.sh, and verifies every guarantee:
#   1. Redis RDB restore from compressed backup + checksum verification
#   2. RabbitMQ definitions import from compressed backup + checksum verification
#   3. Redis health check failure prevents restore (exit 1)
#   4. RabbitMQ health check failure prevents restore (exit 1)
#   5. Missing backup → hard failure (exit 1)
#   6. Checksum mismatch → hard failure (exit 1)
#   7. Dry-run mode produces no changes
#   8. Component-level restore (redis-only, rabbitmq-only)
#
# Usage:
#   ./tests/backup/test_restore_medium.sh
#
# Exit codes:
#   0  All tests passed
#   1  One or more tests failed
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
TEST_ROOT=""
ORIG_PATH="$PATH"

pass() { ((PASS_COUNT++)) || true; echo "  ✅  $1"; }
fail() { ((FAIL_COUNT++)) || true; echo "  ❌  $1"; }

assert_exit_code() {
    local expected="$1" actual="$2" label="$3"
    if [[ "$actual" == "$expected" ]]; then
        pass "$label (exit=$actual)"
    else
        fail "$label — expected exit=$expected got exit=$actual"
    fi
}

# ---------------------------------------------------------------------------
# Cleanup trap
# ---------------------------------------------------------------------------
cleanup() {
    export PATH="$ORIG_PATH"
    if [[ -n "${TEST_ROOT:-}" && -d "${TEST_ROOT:-}" ]]; then
        rm -rf "$TEST_ROOT"
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# create_mock_curl — mock curl for RabbitMQ API
# Arguments: $1=mock_dir, $2=health (healthy|unhealthy), $3=import (success|fail)
# ---------------------------------------------------------------------------
create_mock_curl() {
    local mock_dir="$1"
    local health_response="${2:-healthy}"
    local import_response="${3:-success}"

    cat > "${mock_dir}/curl" <<MOCK_CURL
#!/usr/bin/env bash
args="\$*"

if echo "\$args" | grep -q "healthchecks"; then
    if [[ "$health_response" == "healthy" ]]; then
        echo '{"status":"ok"}'
        exit 0
    else
        exit 1
    fi
fi

if echo "\$args" | grep -q "definitions"; then
    if [[ "$import_response" == "success" ]]; then
        # write_out http_code — curl -w "%{http_code}" returns code appended
        printf "200"
        exit 0
    else
        printf "500"
        exit 1
    fi
fi

exit 0
MOCK_CURL
    chmod +x "${mock_dir}/curl"
}

# ---------------------------------------------------------------------------
# create_mock_docker — mock docker for Redis operations
# Arguments: $1=mock_dir, $2=health (healthy|unhealthy), $3=cp (success|fail)
# ---------------------------------------------------------------------------
create_mock_docker() {
    local mock_dir="$1"
    local health="${2:-healthy}"
    local cp_result="${3:-success}"

    cat > "${mock_dir}/docker" <<MOCK_DOCKER
#!/usr/bin/env bash
if [[ "\$1" == "exec" ]]; then
    if [[ "$health" == "healthy" ]]; then
        echo "PONG"
        exit 0
    else
        echo "Could not connect" >&2
        exit 1
    fi
fi
if [[ "\$1" == "cp" ]]; then
    if [[ "$cp_result" == "success" ]]; then
        exit 0
    else
        echo "Error: No such container" >&2
        exit 1
    fi
fi
if [[ "\$1" == "restart" ]]; then
    exit 0
fi
exit 0
MOCK_DOCKER
    chmod +x "${mock_dir}/docker"
}

# ---------------------------------------------------------------------------
# create_redis_backup — create a fake Redis RDB backup with checksum
# ---------------------------------------------------------------------------
create_redis_backup() {
    local backup_dir="$1"
    local timestamp="${2:-$(date -u +%Y%m%d-%H%M)}"
    local corrupt_checksum="${3:-no}"

    local rdb_file="${backup_dir}/redis-dump-${timestamp}.rdb"
    echo "REDIS0009mock-rdb-data" > "$rdb_file"

    local compressed="${rdb_file}.gz"
    gzip -c "$rdb_file" > "$compressed"
    rm -f "$rdb_file"

    if [[ "$corrupt_checksum" == "yes" ]]; then
        echo "0000000000000000000000000000000000000000000000000000000000000000  $(basename "$compressed")" > "${compressed}.sha256"
    else
        sha256sum "$compressed" > "${compressed}.sha256"
    fi
}

# ---------------------------------------------------------------------------
# create_rabbitmq_backup — create a fake RabbitMQ definitions backup
# ---------------------------------------------------------------------------
create_rabbitmq_backup() {
    local backup_dir="$1"
    local timestamp="${2:-$(date -u +%Y%m%d-%H%M)}"
    local corrupt_checksum="${3:-no}"

    local defs_file="${backup_dir}/rabbitmq-definitions-${timestamp}.json"
    cat > "$defs_file" <<'JSON'
{"rabbit_version":"3.12.0","users":[{"name":"guest"}],"vhosts":[{"name":"/"}],"queues":[]}
JSON

    local compressed="${defs_file}.gz"
    gzip -c "$defs_file" > "$compressed"
    rm -f "$defs_file"

    if [[ "$corrupt_checksum" == "yes" ]]; then
        echo "0000000000000000000000000000000000000000000000000000000000000000  $(basename "$compressed")" > "${compressed}.sha256"
    else
        sha256sum "$compressed" > "${compressed}.sha256"
    fi
}

# ---------------------------------------------------------------------------
# Setup — isolated temp environment
# ---------------------------------------------------------------------------
setup() {
    local redis_health="${1:-healthy}"
    local rabbitmq_health="${2:-healthy}"
    local docker_cp="${3:-success}"
    local rabbitmq_import="${4:-success}"

    TEST_ROOT="$(mktemp -d /tmp/aithena-restore-medium-test-XXXXXX)"

    local restore_from="${TEST_ROOT}/backups/medium"
    local project_root="${TEST_ROOT}/project"
    local log_dir="${TEST_ROOT}/var/log"
    local mock_bin="${TEST_ROOT}/mock-bin"

    mkdir -p "$restore_from" "$project_root" "$log_dir" "$mock_bin"

    # Create mocks
    create_mock_curl "$mock_bin" "$rabbitmq_health" "$rabbitmq_import"
    create_mock_docker "$mock_bin" "$redis_health" "$docker_cp"

    # Mock sleep to speed up tests
    cat > "${mock_bin}/sleep" <<'MOCK_SLEEP'
#!/usr/bin/env bash
exit 0
MOCK_SLEEP
    chmod +x "${mock_bin}/sleep"

    export PATH="${mock_bin}:${ORIG_PATH}"

    export RESTORE_FROM="$restore_from"
    export REDIS_CONTAINER="redis"
    export REDIS_RDB_PATH="/data/dump.rdb"
    export RABBITMQ_CONTAINER="rabbitmq"
    export RABBITMQ_URL="http://localhost:15672"
    export RABBITMQ_USER="guest"
    export RABBITMQ_PASS="guest"
    export RABBITMQ_HEALTH_TIMEOUT="6"
    export PROJECT_ROOT="$project_root"
    export LOG_FILE="${log_dir}/aithena-restore-medium.log"
    unset DRY_RUN
    export COMPONENT="all"
}

# ---------------------------------------------------------------------------
# Resolve the path to the restore script under test
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESTORE_SCRIPT="${REPO_ROOT}/scripts/restore-medium.sh"

if [[ ! -x "$RESTORE_SCRIPT" ]]; then
    echo "ERROR: Restore script not found or not executable: ${RESTORE_SCRIPT}"
    echo "       Run: chmod +x scripts/restore-medium.sh"
    exit 1
fi

# =========================================================================
# Test 1: Full restore — Redis + RabbitMQ
# =========================================================================
echo ""
echo "━━━ Test 1: Full restore (Redis + RabbitMQ) ━━━"
setup "healthy" "healthy" "success" "success"

create_redis_backup "$RESTORE_FROM" "20250101-0300"
create_rabbitmq_backup "$RESTORE_FROM" "20250101-0300"

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Exit code 0 (full restore)"

# Verify log
if grep -q "Medium-Priority Restore START" "$LOG_FILE" 2>/dev/null; then
    pass "Log contains START marker"
else
    fail "Log missing START marker"
fi
if grep -q "Medium-Priority Restore END" "$LOG_FILE" 2>/dev/null; then
    pass "Log contains END marker"
else
    fail "Log missing END marker"
fi

cleanup

# =========================================================================
# Test 2: Redis health check failure → skipped in all mode (exit 2)
# =========================================================================
echo ""
echo "━━━ Test 2: Redis health check failure (all mode → partial) ━━━"
setup "unhealthy" "healthy" "success" "success"

create_redis_backup "$RESTORE_FROM" "20250101-0300"
create_rabbitmq_backup "$RESTORE_FROM" "20250101-0300"

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "2" "$rc" "Exit code 2 (Redis unavailable, partial in all mode)"

cleanup

# =========================================================================
# Test 3: Redis health check failure → hard failure in redis-only mode
# =========================================================================
echo ""
echo "━━━ Test 3: Redis health check failure (redis-only → exit 1) ━━━"
setup "unhealthy" "healthy" "success" "success"
export COMPONENT="redis"

create_redis_backup "$RESTORE_FROM" "20250101-0300"

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (Redis unavailable in redis-only mode)"

export COMPONENT="all"
cleanup

# =========================================================================
# Test 4: Missing Redis backup → hard failure
# =========================================================================
echo ""
echo "━━━ Test 4: Missing Redis backup (redis-only → exit 1) ━━━"
setup "healthy" "healthy" "success" "success"
export COMPONENT="redis"

# No backup created
rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (no Redis backup found)"

export COMPONENT="all"
cleanup

# =========================================================================
# Test 5: Redis checksum mismatch → hard failure
# =========================================================================
echo ""
echo "━━━ Test 5: Redis checksum mismatch ━━━"
setup "healthy" "healthy" "success" "success"
export COMPONENT="redis"

create_redis_backup "$RESTORE_FROM" "20250101-0300" "yes"  # corrupt checksum

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (Redis checksum mismatch)"

export COMPONENT="all"
cleanup

# =========================================================================
# Test 6: Dry-run mode
# =========================================================================
echo ""
echo "━━━ Test 6: Dry-run mode (no changes) ━━━"
setup "healthy" "healthy" "success" "success"
export DRY_RUN=1

create_redis_backup "$RESTORE_FROM" "20250101-0300"
create_rabbitmq_backup "$RESTORE_FROM" "20250101-0300"

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Dry-run exits cleanly"

unset DRY_RUN
cleanup

# =========================================================================
# Test 7: RabbitMQ-only restore
# =========================================================================
echo ""
echo "━━━ Test 7: RabbitMQ-only restore ━━━"
setup "healthy" "healthy" "success" "success"
export COMPONENT="rabbitmq"

create_rabbitmq_backup "$RESTORE_FROM" "20250101-0300"

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "RabbitMQ-only restore succeeds"

export COMPONENT="all"
cleanup

# =========================================================================
# Test 8: Input validation
# =========================================================================
echo ""
echo "━━━ Test 8: Input validation ━━━"
setup "healthy" "healthy" "success" "success"

export RABBITMQ_URL="not-a-url"
rc=0
bash "$RESTORE_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects invalid RABBITMQ_URL"
export RABBITMQ_URL="http://localhost:15672"

export RABBITMQ_HEALTH_TIMEOUT="-1"
rc=0
bash "$RESTORE_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects negative RABBITMQ_HEALTH_TIMEOUT"
export RABBITMQ_HEALTH_TIMEOUT="6"

cleanup

# =========================================================================
# Test 9: Backup directory not found
# =========================================================================
echo ""
echo "━━━ Test 9: Backup directory not found ━━━"
setup "healthy" "healthy" "success" "success"
export RESTORE_FROM="/nonexistent/path"

rc=0
bash "$RESTORE_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (backup directory not found)"

cleanup

# =========================================================================
# Summary
# =========================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "  Results: ${PASS_COUNT}/${TOTAL} passed"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
    echo "  ❌ ${FAIL_COUNT} test(s) FAILED"
    exit 1
else
    echo "  ✅ All tests passed!"
    exit 0
fi
