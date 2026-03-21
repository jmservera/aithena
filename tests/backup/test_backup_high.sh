#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 2: High-Priority Backup — Integration Test
# =============================================================================
# Creates an isolated temp environment with mock curl/docker, runs
# backup-high.sh, and verifies every guarantee:
#   1. Solr backup archive + SHA-256 checksum exist and verify
#   2. ZooKeeper tar archives + SHA-256 checksums exist and verify
#   3. Solr health check failure prevents backup (exit 1)
#   4. Solr BACKUP API failure prevents backup (exit 1)
#   5. Missing ZK node directory handled gracefully (exit 2)
#   6. Retention purge removes only expired files
#   7. Dry-run mode produces no output files
#   8. Invalid input validation rejects bad values
#
# Usage:
#   ./tests/backup/test_backup_high.sh
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
    # Restore PATH
    export PATH="$ORIG_PATH"
    if [[ -n "${TEST_ROOT:-}" && -d "${TEST_ROOT:-}" ]]; then
        rm -rf "$TEST_ROOT"
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# create_mock_curl — writes a mock curl script that responds to Solr API calls
# Arguments: $1 = mock bin dir, $2 = health_response, $3 = backup_response
# ---------------------------------------------------------------------------
create_mock_curl() {
    local mock_dir="$1"
    local health_response="${2:-healthy}"
    local backup_response="${3:-success}"

    cat > "${mock_dir}/curl" <<MOCK_CURL
#!/usr/bin/env bash
# Mock curl for backup-high.sh testing
args="\$*"

if echo "\$args" | grep -q "CLUSTERSTATUS"; then
    if [[ "$health_response" == "healthy" ]]; then
        echo '{"responseHeader":{"status":0},"cluster":{"collections":{"books":{}},"live_nodes":["solr1:8983_solr","solr2:8983_solr","solr3:8983_solr"]}}'
        exit 0
    else
        exit 1
    fi
fi

if echo "\$args" | grep -q "action=BACKUP"; then
    if [[ "$backup_response" == "success" ]]; then
        echo '{"responseHeader":{"status":0},"success":{}}'
        exit 0
    else
        echo '{"responseHeader":{"status":500},"error":{"msg":"backup failed"}}'
        exit 1
    fi
fi

exit 0
MOCK_CURL
    chmod +x "${mock_dir}/curl"
}

# ---------------------------------------------------------------------------
# create_mock_docker — writes a mock docker script that simulates docker cp
# Arguments: $1 = mock bin dir, $2 = behavior (success|fail)
# ---------------------------------------------------------------------------
create_mock_docker() {
    local mock_dir="$1"
    local behavior="${2:-success}"

    cat > "${mock_dir}/docker" <<MOCK_DOCKER
#!/usr/bin/env bash
# Mock docker for backup-high.sh testing
if [[ "\$1" == "cp" ]]; then
    if [[ "$behavior" == "success" ]]; then
        # Simulate docker cp: parse destination and create a marker file
        local_dest="\${*: -1}"
        # Strip trailing /. or / for dest path
        local_dest="\${local_dest%/.}"
        local_dest="\${local_dest%/}"
        mkdir -p "\$local_dest"
        echo "mock-solr-index-data" > "\$local_dest/snapshot.metadata"
        echo "mock-shard-data" > "\$local_dest/shard1_replica1"
        exit 0
    else
        echo "Error: No such container: solr" >&2
        exit 1
    fi
fi
exit 0
MOCK_DOCKER
    chmod +x "${mock_dir}/docker"
}

# ---------------------------------------------------------------------------
# Setup — isolated temp environment
# ---------------------------------------------------------------------------
setup() {
    local health_resp="${1:-healthy}"
    local backup_resp="${2:-success}"
    local docker_resp="${3:-success}"

    TEST_ROOT="$(mktemp -d /tmp/aithena-backup-high-test-XXXXXX)"

    local solr_backup_dir="${TEST_ROOT}/backups/high"
    local zk_backup_dir="${TEST_ROOT}/backups/zookeeper"
    local zk_volume_base="${TEST_ROOT}/volumes"
    local project_root="${TEST_ROOT}/project"
    local log_dir="${TEST_ROOT}/var/log"
    local mock_bin="${TEST_ROOT}/mock-bin"

    mkdir -p "$solr_backup_dir" "$zk_backup_dir" "$project_root" "$log_dir" "$mock_bin"

    # Create mock ZK volume directories with test data
    for i in 1 2 3; do
        local zk_dir="${zk_volume_base}/zoo-data${i}"
        mkdir -p "${zk_dir}/data" "${zk_dir}/logs" "${zk_dir}/datalog"
        echo "myid=${i}" > "${zk_dir}/data/myid"
        echo "zk-snapshot-data-node${i}" > "${zk_dir}/data/snapshot.0"
        echo "zk-log-data-node${i}" > "${zk_dir}/logs/log.1"
        echo "zk-txn-log-node${i}" > "${zk_dir}/datalog/log.100000001"
    done

    # Create mock curl and docker
    create_mock_curl "$mock_bin" "$health_resp" "$backup_resp"
    create_mock_docker "$mock_bin" "$docker_resp"

    # Prepend mock bin to PATH
    export PATH="${mock_bin}:${ORIG_PATH}"

    # Export environment for the backup script
    export SOLR_URL="http://localhost:8983"
    export SOLR_COLLECTION="books"
    export SOLR_BACKUP_LOCATION="/var/solr/backups"
    export SOLR_CONTAINER="solr"
    export SOLR_BACKUP_DIR="$solr_backup_dir"
    export ZK_BACKUP_DIR="$zk_backup_dir"
    export ZK_VOLUME_BASE="$zk_volume_base"
    export ZK_NODES="3"
    export BACKUP_RETENTION_DAYS="30"
    export SOLR_HEALTH_TIMEOUT="6"
    export SOLR_BACKUP_TIMEOUT="10"
    export PROJECT_ROOT="$project_root"
    export LOG_FILE="${log_dir}/aithena-backup-high.log"
    unset DRY_RUN
}

# ---------------------------------------------------------------------------
# Resolve the path to the backup script under test
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_SCRIPT="${REPO_ROOT}/scripts/backup-high.sh"

if [[ ! -x "$BACKUP_SCRIPT" ]]; then
    echo "ERROR: Backup script not found or not executable: ${BACKUP_SCRIPT}"
    echo "       Run: chmod +x scripts/backup-high.sh"
    exit 1
fi

# =========================================================================
# Test 1: Full backup — all components present
# =========================================================================
echo ""
echo "━━━ Test 1: Full backup (Solr + ZooKeeper) ━━━"
setup "healthy" "success" "success"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Exit code 0 (all components present)"

# Check Solr backup archive exists
solr_tar=$(find "$SOLR_BACKUP_DIR" -maxdepth 1 -name "books-*.tar.gz" -not -name "*.sha256" -print -quit)
solr_sha="${solr_tar}.sha256"

assert_file_exists "${solr_tar:-__missing__}" "Solr backup archive exists"
assert_file_exists "${solr_sha:-__missing__}" "Solr backup checksum sidecar exists"

# Verify Solr checksum
if [[ -f "${solr_sha:-}" ]]; then
    pushd "$(dirname "$solr_sha")" > /dev/null
    if sha256sum --check "$(basename "$solr_sha")" &>/dev/null; then
        pass "Solr backup checksum verification"
    else
        fail "Solr backup checksum verification"
    fi
    popd > /dev/null
fi

# Check ZK backup archives exist for all 3 nodes
for i in 1 2 3; do
    zk_tar=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -name "zoo-data${i}-*.tar.gz" -not -name "*.sha256" -print -quit)
    zk_sha="${zk_tar}.sha256"

    assert_file_exists "${zk_tar:-__missing__}" "ZK node ${i} backup archive exists"
    assert_file_exists "${zk_sha:-__missing__}" "ZK node ${i} checksum sidecar exists"

    # Verify ZK checksum
    if [[ -f "${zk_sha:-}" ]]; then
        pushd "$(dirname "$zk_sha")" > /dev/null
        if sha256sum --check "$(basename "$zk_sha")" &>/dev/null; then
            pass "ZK node ${i} checksum verification"
        else
            fail "ZK node ${i} checksum verification"
        fi
        popd > /dev/null
    fi
done

# Verify ZK archive contents — extract and check data integrity
verify_dir="${TEST_ROOT}/verify"
mkdir -p "$verify_dir"
zk_tar1=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -name "zoo-data1-*.tar.gz" -not -name "*.sha256" -print -quit)
if [[ -f "${zk_tar1:-}" ]]; then
    tar -xzf "$zk_tar1" -C "$verify_dir"
    if [[ -f "${verify_dir}/zoo-data1/data/myid" ]]; then
        myid=$(cat "${verify_dir}/zoo-data1/data/myid")
        if [[ "$myid" == "myid=1" ]]; then
            pass "ZK node 1 archive contents intact (myid=1)"
        else
            fail "ZK node 1 archive contents corrupt — expected myid=1, got ${myid}"
        fi
    else
        fail "ZK node 1 archive missing data/myid"
    fi
fi

# Verify log file was written
assert_file_exists "$LOG_FILE" "Log file was created"
if grep -q "High-Priority Backup START" "$LOG_FILE" 2>/dev/null; then
    pass "Log contains START marker"
else
    fail "Log missing START marker"
fi
if grep -q "High-Priority Backup END" "$LOG_FILE" 2>/dev/null; then
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
setup "unhealthy" "success" "success"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (Solr cluster unhealthy)"

# No backup files should exist
solr_count=$(find "$SOLR_BACKUP_DIR" -maxdepth 1 -name "*.tar.gz" -type f 2>/dev/null | wc -l)
zk_count=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -name "*.tar.gz" -type f 2>/dev/null | wc -l)
if [[ "$solr_count" -eq 0 && "$zk_count" -eq 0 ]]; then
    pass "No backup files created on health check failure"
else
    fail "Backup files created despite health check failure (solr=${solr_count}, zk=${zk_count})"
fi

cleanup

# =========================================================================
# Test 3: Solr BACKUP API failure → hard failure
# =========================================================================
echo ""
echo "━━━ Test 3: Solr BACKUP API failure ━━━"
setup "healthy" "fail" "success"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (Solr BACKUP API failed)"

# No Solr backup should exist (ZK may or may not have run)
solr_count=$(find "$SOLR_BACKUP_DIR" -maxdepth 1 -name "books-*.tar.gz" -type f 2>/dev/null | wc -l)
if [[ "$solr_count" -eq 0 ]]; then
    pass "No Solr backup archive on API failure"
else
    fail "Solr backup created despite API failure (count=${solr_count})"
fi

cleanup

# =========================================================================
# Test 4: Missing ZK node directory → partial failure (exit 2)
# =========================================================================
echo ""
echo "━━━ Test 4: Missing ZK node directory (partial failure) ━━━"
setup "healthy" "success" "success"

# Remove ZK node 3 directory
rm -rf "${ZK_VOLUME_BASE}/zoo-data3"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "2" "$rc" "Exit code 2 (missing ZK node, non-fatal)"

# Nodes 1 and 2 should still be backed up
zk1=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -name "zoo-data1-*.tar.gz" -not -name "*.sha256" -print -quit)
zk2=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -name "zoo-data2-*.tar.gz" -not -name "*.sha256" -print -quit)
zk3=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -name "zoo-data3-*.tar.gz" -not -name "*.sha256" -print -quit)

assert_file_exists "${zk1:-__missing__}" "ZK node 1 still backed up when node 3 missing"
assert_file_exists "${zk2:-__missing__}" "ZK node 2 still backed up when node 3 missing"
assert_file_not_exists "${zk3:-}" "ZK node 3 correctly skipped"

# Solr backup should still succeed
solr_tar=$(find "$SOLR_BACKUP_DIR" -maxdepth 1 -name "books-*.tar.gz" -not -name "*.sha256" -print -quit)
assert_file_exists "${solr_tar:-__missing__}" "Solr backup still created despite missing ZK node"

cleanup

# =========================================================================
# Test 5: Retention purge
# =========================================================================
echo ""
echo "━━━ Test 5: Retention purge removes expired backups ━━━"
setup "healthy" "success" "success"

# Run backup to create current files
bash "$BACKUP_SCRIPT" >/dev/null 2>&1

# Create "old" Solr backup that should be purged (>30 days)
old_solr="${SOLR_BACKUP_DIR}/books-19700101-0000.tar.gz"
old_solr_sha="${SOLR_BACKUP_DIR}/books-19700101-0000.tar.gz.sha256"
touch -d "35 days ago" "$old_solr"
touch -d "35 days ago" "$old_solr_sha"

# Create "old" ZK backup that should be purged
old_zk="${ZK_BACKUP_DIR}/zoo-data1-19700101-0000.tar.gz"
old_zk_sha="${ZK_BACKUP_DIR}/zoo-data1-19700101-0000.tar.gz.sha256"
touch -d "35 days ago" "$old_zk"
touch -d "35 days ago" "$old_zk_sha"

# Create "recent" file that should NOT be purged
recent_solr="${SOLR_BACKUP_DIR}/books-29990101-0000.tar.gz"
touch "$recent_solr"

# Run backup again (includes purge step)
bash "$BACKUP_SCRIPT" >/dev/null 2>&1

assert_file_not_exists "$old_solr" "Old Solr backup purged (>30 days)"
assert_file_not_exists "$old_solr_sha" "Old Solr checksum purged (>30 days)"
assert_file_not_exists "$old_zk" "Old ZK backup purged (>30 days)"
assert_file_not_exists "$old_zk_sha" "Old ZK checksum purged (>30 days)"
assert_file_exists "$recent_solr" "Recent Solr backup preserved"

cleanup

# =========================================================================
# Test 6: Dry-run mode
# =========================================================================
echo ""
echo "━━━ Test 6: Dry-run mode (no files written) ━━━"
setup "healthy" "success" "success"
export DRY_RUN=1

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Dry-run exits cleanly"

solr_count=$(find "$SOLR_BACKUP_DIR" -maxdepth 1 -type f -name '*.tar.gz' 2>/dev/null | wc -l)
zk_count=$(find "$ZK_BACKUP_DIR" -maxdepth 1 -type f -name '*.tar.gz' 2>/dev/null | wc -l)

if [[ "$solr_count" -eq 0 && "$zk_count" -eq 0 ]]; then
    pass "Dry-run produced no backup files"
else
    fail "Dry-run produced unexpected files (solr=${solr_count}, zk=${zk_count})"
fi

unset DRY_RUN
cleanup

# =========================================================================
# Test 7: Input validation — invalid BACKUP_RETENTION_DAYS
# =========================================================================
echo ""
echo "━━━ Test 7: Input validation ━━━"
setup "healthy" "success" "success"

export BACKUP_RETENTION_DAYS="notanumber"
rc=0
bash "$BACKUP_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects non-integer BACKUP_RETENTION_DAYS"
export BACKUP_RETENTION_DAYS="30"

export ZK_NODES="0"
rc=0
bash "$BACKUP_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects ZK_NODES=0"
export ZK_NODES="3"

export SOLR_URL="not-a-url"
rc=0
bash "$BACKUP_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects invalid SOLR_URL"
export SOLR_URL="http://localhost:8983"

export SOLR_HEALTH_TIMEOUT="-5"
rc=0
bash "$BACKUP_SCRIPT" 2>/dev/null || rc=$?
assert_exit_code "1" "$rc" "Rejects negative SOLR_HEALTH_TIMEOUT"
export SOLR_HEALTH_TIMEOUT="6"

cleanup

# =========================================================================
# Test 8: File permissions — umask 077 enforced
# =========================================================================
echo ""
echo "━━━ Test 8: File permissions (umask 077) ━━━"
setup "healthy" "success" "success"

bash "$BACKUP_SCRIPT" >/dev/null 2>&1

# Check that backup files are not group/world-readable
bad_perms=0
while IFS= read -r -d '' f; do
    perms="$(stat -c '%a' "$f" 2>/dev/null || stat -f '%Lp' "$f" 2>/dev/null)"
    group_bit="${perms: -2:1}"
    other_bit="${perms: -1}"
    if [[ "$group_bit" != "0" || "$other_bit" != "0" ]]; then
        ((bad_perms++)) || true
    fi
done < <(find "$SOLR_BACKUP_DIR" "$ZK_BACKUP_DIR" -maxdepth 1 -type f \( -name '*.tar.gz' -o -name '*.sha256' \) -print0 2>/dev/null)

if [[ "$bad_perms" -eq 0 ]]; then
    pass "All backup files are owner-only (umask 077)"
else
    fail "${bad_perms} file(s) have group/world permissions"
fi

cleanup

# =========================================================================
# Test 9: Docker cp failure → hard failure
# =========================================================================
echo ""
echo "━━━ Test 9: Docker cp failure ━━━"
setup "healthy" "success" "fail"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (docker cp failed)"

solr_count=$(find "$SOLR_BACKUP_DIR" -maxdepth 1 -name "books-*.tar.gz" -type f 2>/dev/null | wc -l)
if [[ "$solr_count" -eq 0 ]]; then
    pass "No Solr backup archive on docker cp failure"
else
    fail "Solr backup created despite docker cp failure"
fi

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
