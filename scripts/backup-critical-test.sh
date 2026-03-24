#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 1: Critical Backup — Integration Test
# =============================================================================
# Creates an isolated temp environment with fake data, runs backup-critical.sh,
# and verifies every guarantee:
#   1. Encrypted files exist with correct naming convention
#   2. SHA-256 checksums are valid
#   3. Decrypted output matches the original data
#   4. Optional missing files are handled gracefully (exit 2, not 1)
#   5. Retention purge removes only expired files
#   6. Dry-run mode produces no output files
#
# Usage:
#   ./scripts/backup-critical-test.sh
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
    if [[ -n "${TEST_ROOT:-}" && -d "${TEST_ROOT:-}" ]]; then
        rm -rf "$TEST_ROOT"
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Setup — isolated temp environment
# ---------------------------------------------------------------------------
setup() {
    TEST_ROOT="$(mktemp -d /tmp/aithena-backup-test-XXXXXX)"

    local auth_dir="${TEST_ROOT}/auth"
    local backup_dir="${TEST_ROOT}/backups/critical"
    local key_dir="${TEST_ROOT}/etc/aithena"
    local project_root="${TEST_ROOT}/project"
    local log_dir="${TEST_ROOT}/var/log"

    mkdir -p "$auth_dir" "$backup_dir" "$key_dir" "$project_root" "$log_dir"

    # --- Generate encryption key ---
    openssl rand -base64 32 > "${key_dir}/backup.key"
    chmod 600 "${key_dir}/backup.key"

    # --- Create test SQLite databases ---
    sqlite3 "${auth_dir}/users.db" <<'SQL'
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);
INSERT INTO users VALUES (1, 'Alice', 'alice@example.com');
INSERT INTO users VALUES (2, 'Bob', 'bob@example.com');
SQL

    sqlite3 "${auth_dir}/collections.db" <<'SQL'
CREATE TABLE collections (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT);
INSERT INTO collections VALUES (1, 1, 'My Reading List');
INSERT INTO collections VALUES (2, 2, 'Favorites');
SQL

    # --- Create test .env file ---
    cat > "${project_root}/.env" <<'ENV'
AUTH_JWT_SECRET=supersecretjwtkey123
RABBITMQ_USER=rabbit
RABBITMQ_PASS=rabbitpass789
ENV

    # Export environment for the backup script
    export AUTH_DB_DIR="$auth_dir"
    export BACKUP_DIR="$backup_dir"
    export BACKUP_KEY="${key_dir}/backup.key"
    export BACKUP_RETENTION_DAYS=7
    export PROJECT_ROOT="$project_root"
    export LOG_FILE="${log_dir}/aithena-backup-critical.log"
}

# ---------------------------------------------------------------------------
# Resolve the path to the backup script under test
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup-critical.sh"

if [[ ! -x "$BACKUP_SCRIPT" ]]; then
    echo "ERROR: Backup script not found or not executable: ${BACKUP_SCRIPT}"
    echo "       Run: chmod +x scripts/backup-critical.sh"
    exit 1
fi

# =========================================================================
# Test 1: Full backup — all files present
# =========================================================================
echo ""
echo "━━━ Test 1: Full backup (all files present) ━━━"
setup

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Exit code 0 (all files present)"

# Check encrypted files exist
auth_gpg=$(find "$BACKUP_DIR" -maxdepth 1 -name "auth-*.db.gpg" -print -quit)
coll_gpg=$(find "$BACKUP_DIR" -maxdepth 1 -name "collections-*.db.gpg" -print -quit)
env_gpg=$(find "$BACKUP_DIR" -maxdepth 1 -name "env-*.gpg" ! -name "*.sha256" -print -quit)

assert_file_exists "${auth_gpg:-__missing__}" "Auth DB encrypted backup exists"
assert_file_exists "${coll_gpg:-__missing__}" "Collections DB encrypted backup exists"
assert_file_exists "${env_gpg:-__missing__}" ".env encrypted backup exists"

# Check SHA-256 checksum sidecars
auth_sha="${auth_gpg}.sha256"
coll_sha="${coll_gpg}.sha256"
env_sha="${env_gpg}.sha256"

assert_file_exists "${auth_sha:-__missing__}" "Auth DB checksum sidecar exists"
assert_file_exists "${coll_sha:-__missing__}" "Collections DB checksum sidecar exists"
assert_file_exists "${env_sha:-__missing__}" ".env checksum sidecar exists"

# Verify checksums
if [[ -f "$auth_sha" ]]; then
    pushd "$(dirname "$auth_sha")" > /dev/null
    if sha256sum --check "$(basename "$auth_sha")" &>/dev/null; then
        pass "Auth DB checksum verification"
    else
        fail "Auth DB checksum verification"
    fi
    popd > /dev/null
fi

if [[ -f "$coll_sha" ]]; then
    pushd "$(dirname "$coll_sha")" > /dev/null
    if sha256sum --check "$(basename "$coll_sha")" &>/dev/null; then
        pass "Collections DB checksum verification"
    else
        fail "Collections DB checksum verification"
    fi
    popd > /dev/null
fi

if [[ -f "$env_sha" ]]; then
    pushd "$(dirname "$env_sha")" > /dev/null
    if sha256sum --check "$(basename "$env_sha")" &>/dev/null; then
        pass ".env checksum verification"
    else
        fail ".env checksum verification"
    fi
    popd > /dev/null
fi

# Decrypt and verify original data is intact
decrypt_dir="${TEST_ROOT}/decrypt"
mkdir -p "$decrypt_dir"

# Verify auth DB round-trip
gpg --decrypt --batch --yes --pinentry-mode loopback --no-tty --passphrase-file "$BACKUP_KEY" \
    --output "${decrypt_dir}/auth.db" "$auth_gpg" 2>/dev/null
auth_names="$(sqlite3 "${decrypt_dir}/auth.db" "SELECT name FROM users ORDER BY id;")"
if [[ "$auth_names" == $'Alice\nBob' ]]; then
    pass "Auth DB decryption round-trip — data intact"
else
    fail "Auth DB decryption round-trip — expected 'Alice\\nBob', got '${auth_names}'"
fi

# Verify collections DB round-trip
gpg --decrypt --batch --yes --pinentry-mode loopback --no-tty --passphrase-file "$BACKUP_KEY" \
    --output "${decrypt_dir}/collections.db" "$coll_gpg" 2>/dev/null
coll_titles="$(sqlite3 "${decrypt_dir}/collections.db" "SELECT title FROM collections ORDER BY id;")"
if [[ "$coll_titles" == $'My Reading List\nFavorites' ]]; then
    pass "Collections DB decryption round-trip — data intact"
else
    fail "Collections DB decryption round-trip — expected data mismatch"
fi

# Verify .env round-trip
gpg --decrypt --batch --yes --pinentry-mode loopback --no-tty --passphrase-file "$BACKUP_KEY" \
    --output "${decrypt_dir}/env" "$env_gpg" 2>/dev/null
if grep -q "AUTH_JWT_SECRET=supersecretjwtkey123" "${decrypt_dir}/env"; then
    pass ".env decryption round-trip — secrets intact"
else
    fail ".env decryption round-trip — secrets missing or corrupted"
fi

cleanup

# =========================================================================
# Test 2: Missing optional file (collections.db absent)
# =========================================================================
echo ""
echo "━━━ Test 2: Missing optional file (collections.db absent) ━━━"
setup
rm -f "${AUTH_DB_DIR}/collections.db"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "2" "$rc" "Exit code 2 (optional file missing, non-fatal)"

auth_gpg=$(find "$BACKUP_DIR" -maxdepth 1 -name "auth-*.db.gpg" -print -quit)
coll_gpg=$(find "$BACKUP_DIR" -maxdepth 1 -name "collections-*.db.gpg" -print -quit)

assert_file_exists "${auth_gpg:-__missing__}" "Auth DB still backed up when collections.db absent"
assert_file_not_exists "${coll_gpg:-}" "Collections backup correctly skipped"

cleanup

# =========================================================================
# Test 3: Missing required file (users.db absent) → hard failure
# =========================================================================
echo ""
echo "━━━ Test 3: Missing required file (users.db absent) ━━━"
setup
rm -f "${AUTH_DB_DIR}/users.db"

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "1" "$rc" "Exit code 1 (required file missing, fatal)"

cleanup

# =========================================================================
# Test 4: Retention purge
# =========================================================================
echo ""
echo "━━━ Test 4: Retention purge removes expired backups ━━━"
setup

# Run a backup first to get current files
bash "$BACKUP_SCRIPT" >/dev/null 2>&1

# Create an "old" backup that should be purged (touch with 10-day-old timestamp)
old_file="${BACKUP_DIR}/auth-19700101-0000.db.gpg"
old_sha="${BACKUP_DIR}/auth-19700101-0000.db.gpg.sha256"
touch -d "10 days ago" "$old_file"
touch -d "10 days ago" "$old_sha"

# Also create a "recent" file that should NOT be purged
recent_file="${BACKUP_DIR}/auth-29990101-0000.db.gpg"
touch "$recent_file"

# Run backup again (includes purge step)
bash "$BACKUP_SCRIPT" >/dev/null 2>&1

assert_file_not_exists "$old_file" "Old backup file purged (>7 days)"
assert_file_not_exists "$old_sha"  "Old checksum file purged (>7 days)"
assert_file_exists "$recent_file"  "Recent backup file preserved"

cleanup

# =========================================================================
# Test 5: Dry-run mode
# =========================================================================
echo ""
echo "━━━ Test 5: Dry-run mode (no files written) ━━━"
setup
export DRY_RUN=1

rc=0
bash "$BACKUP_SCRIPT" || rc=$?
assert_exit_code "0" "$rc" "Dry-run exits cleanly"

file_count=$(find "$BACKUP_DIR" -maxdepth 1 -type f -not -name '.backup-critical.lock' | wc -l)
if [[ "$file_count" -eq 0 ]]; then
    pass "Dry-run produced no output files"
else
    fail "Dry-run produced ${file_count} unexpected file(s)"
fi

unset DRY_RUN
cleanup

# =========================================================================
# Test 6: Idempotency — running twice doesn't corrupt or duplicate
# =========================================================================
echo ""
echo "━━━ Test 6: Idempotency (second run is clean) ━━━"
setup

bash "$BACKUP_SCRIPT" >/dev/null 2>&1
count_before=$(find "$BACKUP_DIR" -maxdepth 1 -name '*.gpg' -type f | wc -l)

# Run again immediately; within the same minute files overwrite, later runs create new files
bash "$BACKUP_SCRIPT" >/dev/null 2>&1
count_after=$(find "$BACKUP_DIR" -maxdepth 1 -name '*.gpg' -type f | wc -l)

# Within the same minute, files will overwrite (gpg --yes); across minutes, new files appear
# Either way, it should not crash
if [[ "$count_after" -ge "$count_before" ]]; then
    pass "Second run succeeded without errors"
else
    fail "Second run produced fewer files than first (${count_after} < ${count_before})"
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
