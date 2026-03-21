#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 2: High-Priority Restore — Integration Test
# =============================================================================
# Creates an isolated temp environment with mock curl/docker, runs
# restore-high.sh, and verifies every guarantee:
#   1. Solr restore from archive + checksum verification
#   2. ZooKeeper restore from tar archives + data integrity
#   3. Solr health check failure prevents restore (exit 1)
#   4. Missing Solr backup archive → hard failure (exit 1)
#   5. Missing ZK node archive → partial failure (exit 2)
#   6. Checksum mismatch → hard failure (exit 1)
#   7. Dry-run mode produces no changes
#   8. Input validation rejects bad values
#
# Usage:
#   ./tests/backup/test_restore_high.sh
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

assert_file_exists() {
    if [[ -f "$1" ]]; then pass "$2"; else fail "$2 — file not found: $1"; fi
}

assert_file_not_exists() {
    if [[ ! -f "$1" ]]; then pass "$2"; else fail "$2 — file unexpectedly exists: $1"; fi
}

assert_dir_exists() {
    if [[ -d "$1" ]]; then pass "$2"; else fail "$2 — directory not found: $1"; fi
}

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
# create_mock_curl — mock curl that responds to Solr API calls
# Arguments: $1 = mock bin dir, $2 = health (healthy|unhealthy)
#            $3 = restore_response (success|fail), $4 = cluster_has_collection (yes|no)
# ---------------------------------------------------------------------------
create_mock_curl() {
    local mock_dir="$1"
    local health_response="${2:-healthy}"
    local restore_response="${3:-success}"
    local cluster_has_collection="${4:-yes}"

    cat > "${mock_dir}/curl" <<MOCK_CURL
#!/usr/bin/env bash
# Mock curl for restore-high.sh testing
args="\$*"

if echo "\$args" | grep -q "CLUSTERSTATUS"; then
    if [[ "$health_response" == "healthy" ]]; then
        if [[ "$cluster_has_collection" == "yes" ]]; then
            echo '{"responseHeader":{"status":0},"cluster":{"collections":{"books":{}},"live_nodes":["solr1:8983_solr","solr2:8983_solr","solr3:8983_solr"]}}'
        else
            echo '{"responseHeader":{"status":0},"cluster":{"collections":{},"live_nodes":["solr1:8983_solr"]}}'
        fi
        exit 0
    else
        exit 1
    fi
fi

if echo "\$args" | grep -q "action=DELETE"; then
    echo '{"responseHeader":{"status":0}}'
    exit 0
fi

if echo "\$args" | grep -q "action=RESTORE"; then
    if [[ "$restore_response" == "success" ]]; then
        echo '{"responseHeader":{"status":0},"success":{}}'
        exit 0
    else
        echo '{"responseHeader":{"status":500},"error":{"msg":"restore failed"}}'
        exit 1
    fi
fi

exit 0
MOCK_CURL
    chmod +x "${mock_dir}/curl"
}

# ---------------------------------------------------------------------------
# create_mock_docker — mock docker for container operations
# Arguments: $1 = mock bin dir, $2 = behavior (success|fail)
# ---------------------------------------------------------------------------
create_mock_docker() {
    local mock_dir="$1"
    local behavior="${2:-success}"

    cat > "${mock_dir}/docker" <<MOCK_DOCKER
#!/usr/bin/env bash
# Mock docker for restore-high.sh testing
if [[ "\$1" == "cp" ]]; then
    if [[ "$behavior" == "success" ]]; then
        exit 0
    else
        echo "Error: No such container: solr" >&2
        exit 1
    fi
fi
if [[ "\$1" == "exec" ]]; then
    exit 0
fi
exit 0
MOCK_DOCKER
    chmod +x "${mock_dir}/docker"
}

# ---------------------------------------------------------------------------
# create_solr_backup — create a fake Solr backup archive with checksum
# ---------------------------------------------------------------------------
create_solr_backup() {
    local backup_dir="$1"
    local timestamp="${2:-$(date -u +%Y%m%d-%H%M)}"
    local collection="${3:-books}"
    local corrupt_checksum="${4:-no}"

    local work_dir
    work_dir="$(mktemp -d /tmp/solr-backup-gen-XXXXXX)"

    local backup_name="${collection}-${timestamp}"
    mkdir -p "${work_dir}/${backup_name}"
    echo "mock-solr-index-data" > "${work_dir}/${backup_name}/snapshot.metadata"
    echo "mock-shard-data" > "${work_dir}/${backup_name}/shard1_replica1"

    local archive="${backup_dir}/${backup_name}.tar.gz"
    tar -czf "$archive" -C "$work_dir" "$backup_name"

    if [[ "$corrupt_checksum" == "yes" ]]; then
        echo "0000000000000000000000000000000000000000000000000000000000000000  $(basename "$archive")" > "${archive}.sha256"
    else
        sha256sum "$archive" > "${archive}.sha256"
    fi

    rm -rf "$work_dir"
    echo "$archive"
}

# ---------------------------------------------------------------------------
# create_zk_backups — create fake ZK backup archives with checksums
# ---------------------------------------------------------------------------
create_zk_backups() {
    local backup_dir="$1"
    local timestamp="${2:-$(date -u +%Y%m%d-%H%M)}"
    local node_count="${3:-3}"
    local skip_node="${4:-0}"

    local work_dir
    work_dir="$(mktemp -d /tmp/zk-backup-gen-XXXXXX)"

    for i in $(seq 1 "$node_count"); do
        if [[ "$i" -eq "$skip_node" ]]; then
            continue
        fi

        mkdir -p "${work_dir}/zoo-data${i}/data" "${work_dir}/zoo-data${i}/logs"
        echo "myid=${i}" > "${work_dir}/zoo-data${i}/data/myid"
        echo "zk-snapshot-data-node${i}" > "${work_dir}/zoo-data${i}/data/snapshot.0"
        echo "zk-log-data-node${i}" > "${work_dir}/zoo-data${i}/logs/log.1"

        local archive="${backup_dir}/zoo-data${i}-${timestamp}.tar.gz"
        tar -czf "$archive" -C "$work_dir" "zoo-data${i}"
        sha256sum "$archive" > "${archive}.sha256"
    done

    rm -rf "$work_dir"
}

# ---------------------------------------------------------------------------
# Setup — isolated temp environment
# ---------------------------------------------------------------------------
setup() {
    local health_resp="${1:-healthy}"
    local restore_resp="${2:-success}"
    local docker_resp="${3:-success}"
    local cluster_coll="${4:-yes}"

    TEST_ROOT="$(mktemp -d /tmp/aithena-restore-high-test-XXXXXX)"

    local solr_restore_from="${TEST_ROOT}/backups/high"
    local zk_restore_from="${TEST_ROOT}/backups/zookeeper"
    local zk_volume_base="${TEST_ROOT}/volumes"
    local project_root="${TEST_ROOT}/project"
    local log_dir="${TEST_ROOT}/var/log"
    local mock_bin="${TEST_ROOT}/mock-bin"

    mkdir -p "$solr_restore_from" "$zk_restore_from" "$zk_volume_base" \
             "$project_root" "$log_dir" "$mock_bin"

    # Create mock curl and docker
    create_mock_curl "$mock_bin" "$health_resp" "$restore_resp" "$cluster_coll"
    create_mock_docker "$mock_bin" "$docker_resp"

    # Prepend mock bin to PATH (also mock sleep to speed up tests)
    cat > "${mock_bin}/sleep" <<'MOCK_SLEEP'
#!/usr/bin/env bash
exit 0
MOCK_SLEEP
    chmod +x "${mock_bin}/sleep"

    export PATH="${mock_bin}:${ORIG_PATH}"

    # Export environment for the restore script
    export RESTORE_FROM="$solr_restore_from"
    export ZK_RESTORE_FROM="$zk_restore_from"
    export SOLR_URL="http://localhost:8983"
    export SOLR_COLLECTION="books"
    export SOLR_BACKUP_LOCATION="/var/solr/backups"
    export SOLR_CONTAINER="solr"
    export SOLR_HEALTH_TIMEOUT="6"
    export SOLR_RESTORE_TIMEOUT="10"
    export ZK_VOLUME_BASE="$zk_volume_base"
    export ZK_NODES="3"
    export PROJECT_ROOT="$project_root"
    export LOG_FILE="${log_dir}/aithena-restore-high.log"
    unset DRY_RUN
    export COMPONENT="all"
}

# ---------------------------------------------------------------------------
# Resolve the path to the restore script under test
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESTORE_SCRIPT="${REPO_ROOT}/scripts/restore-high.sh"

if [[ ! -x "$RESTORE_SCRIPT" ]]; then
    echo "ERROR: Restore script not found or not executable: ${RESTORE_SCRIPT}"
    echo "       Run: chmod +x scripts/restore-high.sh"
    exit 1
fi

# =========================================================================
# Test 1: Full restore — Solr + ZooKeeper
# =========================================================================
echo ""
echo "━━━ Test 1: Full restore (Solr + ZooKeeper) ━━━"
setup "healthy" "success" "success" "yes"

# Create backup files to restore from
create_solr_backup "$RESTORE_FROM" "20250101-0200" "books" >/dev/null
create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Exit code 0 (full restore)"

# Verify ZK data was restored
for i in 1 2 3; do
    assert_dir_exists "${ZK_VOLUME_BASE}/zoo-data${i}" "ZK node ${i} volume restored"
    if [[ -f "${ZK_VOLUME_BASE}/zoo-data${i}/data/myid" ]]; then
        local_myid=$(cat "${ZK_VOLUME_BASE}/zoo-data${i}/data/myid")
        if [[ "$local_myid" == "myid=${i}" ]]; then
            pass "ZK node ${i} data intact (myid=${i})"
        else
            fail "ZK node ${i} data corrupt — expected myid=${i}, got ${local_myid}"
        fi
    else
        fail "ZK node ${i} missing data/myid"
    fi
done

# Verify log file
assert_file_exists "$LOG_FILE" "Log file was created"
if grep -q "High-Priority Restore START" "$LOG_FILE" 2>/dev/null; then
    pass "Log contains START marker"
else
    fail "Log missing START marker"
fi
if grep -q "High-Priority Restore END" "$LOG_FILE" 2>/dev/null; then
    pass "Log contains END marker"
else
    fail "Log missing END marker"
fi

cleanup

# =========================================================================
# Test 2: Solr health check failure → hard failure
# =========================================================================
echo ""
echo "━━━ Test 2: Solr health check failure ━━━"
setup "unhealthy" "success" "success" "yes"

create_solr_backup "$RESTORE_FROM" "20250101-0200" >/dev/null
create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (Solr cluster unhealthy)"

cleanup

# =========================================================================
# Test 3: Missing Solr backup archive → hard failure
# =========================================================================
echo ""
echo "━━━ Test 3: Missing Solr backup archive ━━━"
setup "healthy" "success" "success" "yes"

# Only create ZK backups, no Solr backup
create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (no Solr backup found)"

cleanup

# =========================================================================
# Test 4: Missing ZK node archive → partial failure (exit 2)
# =========================================================================
echo ""
echo "━━━ Test 4: Missing ZK node archive (partial failure) ━━━"
setup "healthy" "success" "success" "yes"

create_solr_backup "$RESTORE_FROM" "20250101-0200" >/dev/null
# Create only nodes 1 and 2, skip node 3
create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "2" "$rc" "Exit code 2 (missing ZK node 3, non-fatal)"

# Nodes 1 and 2 should still be restored
assert_dir_exists "${ZK_VOLUME_BASE}/zoo-data1" "ZK node 1 restored despite node 3 missing"
assert_dir_exists "${ZK_VOLUME_BASE}/zoo-data2" "ZK node 2 restored despite node 3 missing"

cleanup

# =========================================================================
# Test 5: Checksum mismatch → hard failure
# =========================================================================
echo ""
echo "━━━ Test 5: Checksum mismatch ━━━"
setup "healthy" "success" "success" "yes"

create_solr_backup "$RESTORE_FROM" "20250101-0200" "books" "yes"  # corrupt checksum
create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (checksum mismatch)"

cleanup

# =========================================================================
# Test 6: Dry-run mode (no changes)
# =========================================================================
echo ""
echo "━━━ Test 6: Dry-run mode (no changes) ━━━"
setup "healthy" "success" "success" "yes"
export DRY_RUN=1

create_solr_backup "$RESTORE_FROM" "20250101-0200" >/dev/null
create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Dry-run exits cleanly"

# ZK volumes should NOT have been created
zk_volume_count=$(find "$ZK_VOLUME_BASE" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
if [[ "$zk_volume_count" -eq 0 ]]; then
    pass "Dry-run produced no ZK volume changes"
else
    fail "Dry-run created ${zk_volume_count} unexpected ZK volume(s)"
fi

unset DRY_RUN
cleanup

# =========================================================================
# Test 7: Solr-only restore (component=solr)
# =========================================================================
echo ""
echo "━━━ Test 7: Solr-only restore (component=solr) ━━━"
setup "healthy" "success" "success" "yes"
export COMPONENT="solr"

create_solr_backup "$RESTORE_FROM" "20250101-0200" >/dev/null

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Solr-only restore succeeds"

# ZK volumes should NOT have been created (only Solr was requested)
zk_volume_count=$(find "$ZK_VOLUME_BASE" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
if [[ "$zk_volume_count" -eq 0 ]]; then
    pass "Solr-only restore did not touch ZK volumes"
else
    fail "Solr-only restore created ${zk_volume_count} unexpected ZK volume(s)"
fi

export COMPONENT="all"
cleanup

# =========================================================================
# Test 8: ZK-only restore (component=zk)
# =========================================================================
echo ""
echo "━━━ Test 8: ZK-only restore (component=zk) ━━━"
setup "healthy" "success" "success" "yes"
export COMPONENT="zk"

create_zk_backups "$ZK_RESTORE_FROM" "20250101-0200" 3

rc=0
bash "$RESTORE_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "ZK-only restore succeeds"

# Verify ZK data was restored
for i in 1 2 3; do
    assert_dir_exists "${ZK_VOLUME_BASE}/zoo-data${i}" "ZK node ${i} restored in ZK-only mode"
done

export COMPONENT="all"
cleanup

# =========================================================================
# Test 9: Input validation
# =========================================================================
echo ""
echo "━━━ Test 9: Input validation ━━━"
setup "healthy" "success" "success" "yes"

export ZK_NODES="0"
rc=0
bash "$RESTORE_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects ZK_NODES=0"
export ZK_NODES="3"

export SOLR_URL="not-a-url"
rc=0
bash "$RESTORE_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects invalid SOLR_URL"
export SOLR_URL="http://localhost:8983"

export SOLR_HEALTH_TIMEOUT="-5"
rc=0
bash "$RESTORE_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects negative SOLR_HEALTH_TIMEOUT"
export SOLR_HEALTH_TIMEOUT="6"

cleanup

# =========================================================================
# Test 10: Backup directory not found → exit 1
# =========================================================================
echo ""
echo "━━━ Test 10: Backup directory not found ━━━"
setup "healthy" "success" "success" "yes"
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
