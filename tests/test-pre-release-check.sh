#!/bin/sh
# Unit tests for e2e/pre-release-check.sh
# Run: sh tests/test-pre-release-check.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ANALYZER="$REPO_ROOT/e2e/pre-release-check.sh"
ALLOWLIST="$REPO_ROOT/e2e/pre-release-allowlist.txt"
PASS=0
FAIL=0

tmpdir="$REPO_ROOT/.test-artifacts/pre-release-check.$$"
mkdir -p "$tmpdir"
trap 'rm -rf "$tmpdir"' EXIT

assert_exit() {
  _label="$1"
  _expected="$2"
  _actual="$3"
  if [ "$_expected" = "$_actual" ]; then
    PASS=$((PASS + 1))
    echo "  ✅ $_label"
  else
    FAIL=$((FAIL + 1))
    echo "  ❌ $_label (expected exit=$_expected, got $_actual)"
  fi
}

assert_json_count() {
  _label="$1"
  _json_file="$2"
  _expected="$3"
  _actual="$(python3 -c "import json; print(len(json.load(open('$_json_file'))))")"
  if [ "$_expected" = "$_actual" ]; then
    PASS=$((PASS + 1))
    echo "  ✅ $_label"
  else
    FAIL=$((FAIL + 1))
    echo "  ❌ $_label (expected $_expected findings, got $_actual)"
  fi
}

assert_json_field() {
  _label="$1"
  _json_file="$2"
  _index="$3"
  _field="$4"
  _expected="$5"
  _actual="$(python3 -c "import json; print(json.load(open('$_json_file'))[$_index]['$_field'])")"
  if [ "$_expected" = "$_actual" ]; then
    PASS=$((PASS + 1))
    echo "  ✅ $_label"
  else
    FAIL=$((FAIL + 1))
    echo "  ❌ $_label (expected $_field='$_expected', got '$_actual')"
  fi
}

assert_no_category() {
  _label="$1"
  _json_file="$2"
  _category="$3"
  _count="$(python3 -c "import json; print(len([f for f in json.load(open('$_json_file')) if f['category'] == '$_category']))")"
  if [ "$_count" = "0" ]; then
    PASS=$((PASS + 1))
    echo "  ✅ $_label"
  else
    FAIL=$((FAIL + 1))
    echo "  ❌ $_label (found $_count findings with category '$_category')"
  fi
}

# -------------------------------------------------------
echo "Test 1: Clean logs produce zero findings (exit 0)"
cat > "$tmpdir/clean.txt" <<'EOF'
app1  | 2024-01-01 Server started successfully
app2  | 2024-01-01 Listening on port 8080
EOF
sh "$ANALYZER" "$tmpdir/clean.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0" 0 "$rc"
assert_json_count "0 findings" "$tmpdir/out.json" 0

# -------------------------------------------------------
echo "Test 2: FATAL error produces error finding (exit 1)"
cat > "$tmpdir/fatal.txt" <<'EOF'
db1  | 2024-01-01 FATAL: could not connect to database
EOF
sh "$ANALYZER" "$tmpdir/fatal.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 1" 1 "$rc"
assert_json_count "1 finding" "$tmpdir/out.json" 1
assert_json_field "category=crash" "$tmpdir/out.json" 0 "category" "crash"
assert_json_field "severity=error" "$tmpdir/out.json" 0 "severity" "error"

# -------------------------------------------------------
echo "Test 3: Warnings-only produces exit 2"
cat > "$tmpdir/warn.txt" <<'EOF'
app1  | 2024-01-01 this feature is deprecated and will be removed
EOF
sh "$ANALYZER" "$tmpdir/warn.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 2" 2 "$rc"
assert_json_field "category=deprecation" "$tmpdir/out.json" 0 "category" "deprecation"
assert_json_field "severity=warning" "$tmpdir/out.json" 0 "severity" "warning"

# -------------------------------------------------------
echo "Test 4: Allowlist ignores ZK quorum findings"
cat > "$tmpdir/zk.txt" <<'EOF'
zoo1  | 2024-01-01 insecure quorum communication detected
zoo2  | 2024-01-01 non-tls quorum peer established
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/zk.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0" 0 "$rc"
assert_json_count "0 findings (all ignored)" "$tmpdir/out.json" 0

# -------------------------------------------------------
echo "Test 5: Allowlist ignores CrashOnOutOfMemoryError"
cat > "$tmpdir/jvm.txt" <<'EOF'
solr1  | 2024-01-01 -XX:+CrashOnOutOfMemoryError set for JVM
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/jvm.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0" 0 "$rc"
assert_json_count "0 findings (ignored)" "$tmpdir/out.json" 0

# -------------------------------------------------------
echo "Test 6: Allowlist downgrades permission denied to warning"
cat > "$tmpdir/perm.txt" <<'EOF'
app1  | 2024-01-01 PermissionError: permission denied on read-only volume
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/perm.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 2 (warning)" 2 "$rc"
assert_json_field "severity=warning" "$tmpdir/out.json" 0 "severity" "warning"

# -------------------------------------------------------
echo "Test 7: Generic deprecations remain warnings"
cat > "$tmpdir/dep.txt" <<'EOF'
solr1  | 2024-01-01 Deprecated handler class used in config
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/dep.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 2 (warning)" 2 "$rc"
assert_json_field "severity=warning" "$tmpdir/out.json" 0 "severity" "warning"

# -------------------------------------------------------
echo "Test 8: RabbitMQ management metrics deprecation stays info-only"
cat > "$tmpdir/rabbitmq-deprecation.txt" <<'EOF'
rabbitmq-1 | 2026-06-03 [warning] Deprecated features: `management_metrics_collection`.
rabbitmq-1 | 2026-06-03 [warning] Its use will not be permitted by default in a future minor RabbitMQ version and the feature will be removed from a future major RabbitMQ version; actual versions to be determined.
rabbitmq-1 | 2026-06-03 [warning]     "deprecated_features.permit.management_metrics_collection = true"
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/rabbitmq-deprecation.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (info only)" 0 "$rc"
assert_json_count "3 info findings" "$tmpdir/out.json" 3
assert_json_field "severity[0]=info" "$tmpdir/out.json" 0 "severity" "info"
assert_json_field "severity[1]=info" "$tmpdir/out.json" 1 "severity" "info"
assert_json_field "severity[2]=info" "$tmpdir/out.json" 2 "severity" "info"

# -------------------------------------------------------
echo "Test 9: --max-errors threshold allows some errors"
cat > "$tmpdir/multi.txt" <<'EOF'
app1  | 2024-01-01 FATAL: db connect failed
app2  | 2024-01-01 out of memory error
EOF
sh "$ANALYZER" --max-errors 5 "$tmpdir/multi.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (errors <= threshold)" 0 "$rc"

sh "$ANALYZER" --max-errors 1 "$tmpdir/multi.txt" > "$tmpdir/out2.json" 2>/dev/null; rc=$?
assert_exit "exit code 1 (errors > threshold)" 1 "$rc"

# -------------------------------------------------------
echo "Test 10: --max-errors 0 is default (any error fails)"
sh "$ANALYZER" "$tmpdir/multi.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 1 (default threshold)" 1 "$rc"

# -------------------------------------------------------
echo "Test 11: Missing allowlist file is tolerated"
sh "$ANALYZER" --allowlist "/nonexistent/file.txt" "$tmpdir/clean.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (missing allowlist)" 0 "$rc"

# -------------------------------------------------------
echo "Test 12: Allowlist with real errors still catches them"
cat > "$tmpdir/mixed.txt" <<'EOF'
zoo1  | 2024-01-01 insecure quorum communication
app1  | 2024-01-01 FATAL: unrecoverable error
solr1 | 2024-01-01 -XX:+CrashOnOutOfMemoryError
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/mixed.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 1 (real error)" 1 "$rc"
assert_json_count "1 real finding (others filtered)" "$tmpdir/out.json" 1
assert_json_field "category=crash" "$tmpdir/out.json" 0 "category" "crash"

# -------------------------------------------------------
echo "Test 13: Expected Solr startup readiness retries are ignored after startup window"
: > "$tmpdir/solr-startup.txt"
i=1
while [ "$i" -le 65 ]; do
  echo "app1  | 2024-01-01 startup line $i" >> "$tmpdir/solr-startup.txt"
  i=$((i + 1))
done
cat >> "$tmpdir/solr-startup.txt" <<'EOF'
document-indexer-1  | {"timestamp":"2026-06-03T22:45:43Z","level":"INFO","message":"Waiting for Solr collection books (1/60): HTTPConnectionPool(host='solr', port=8983): Failed to establish a new connection: [Errno 111] Connection refused"}
EOF
sh "$ANALYZER" "$tmpdir/solr-startup.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (expected startup retry)" 0 "$rc"
assert_no_category "no connection findings" "$tmpdir/out.json" "connection"

# -------------------------------------------------------
echo "Test 14: Reconnect in filenames and URLs is not a connection warning"
: > "$tmpdir/reconnect-filename.txt"
i=1
while [ "$i" -le 65 ]; do
  echo "app1  | 2024-01-01 startup line $i" >> "$tmpdir/reconnect-filename.txt"
  i=$((i + 1))
done
cat >> "$tmpdir/reconnect-filename.txt" <<'EOF'
document-lister-1  | {"timestamp":"2026-06-03T22:46:23Z","level":"INFO","message":"Document already processed: /data/documents/uploads/reconnect.pdf"}
nginx-1            | 172.18.0.1 - - [03/Jun/2026:22:47:01 +0000] "GET /v1/search/?q=reconnect&page=1&limit=10 HTTP/1.1" 200 123
EOF
sh "$ANALYZER" "$tmpdir/reconnect-filename.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (reconnect content only)" 0 "$rc"
assert_no_category "no connection findings" "$tmpdir/out.json" "connection"

# -------------------------------------------------------
echo "Test 15: Runtime connection failures are still warnings"
: > "$tmpdir/runtime-connection.txt"
i=1
while [ "$i" -le 65 ]; do
  echo "app1  | 2024-01-01 startup line $i" >> "$tmpdir/runtime-connection.txt"
  i=$((i + 1))
done
cat >> "$tmpdir/runtime-connection.txt" <<'EOF'
document-lister-1  | 2024-01-01 RabbitMQ connection timed out while publishing
EOF
sh "$ANALYZER" "$tmpdir/runtime-connection.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 2 (runtime connection warning)" 2 "$rc"
assert_json_count "1 connection finding" "$tmpdir/out.json" 1
assert_json_field "category=connection" "$tmpdir/out.json" 0 "category" "connection"

# -------------------------------------------------------
echo "Test 16: Allowlist ignores accepted ZooKeeper/Solr config posture"
cat > "$tmpdir/zk-config.txt" <<'EOF'
zoo1  | 2026-06-03 clientPort is not set
zoo1  | 2026-06-03 secureClientPort is not set
zoo1  | 2026-06-03 observerMasterPort is not set
zoo1  | 2026-06-03 maxCnxns is not configured
solr1 | 2026-06-03 Using default ZkCredentialsInjector. ZkCredentialsInjector is not secure, it creates an empty list of credentials which leads to 'OPEN_ACL_UNSAFE' ACLs to Zookeeper nodes
solr1 | 2026-06-03 Using default ZkCredentialsProvider
solr1 | 2026-06-03 Using default ZkACLProvider
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/zk-config.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (accepted ZK/Solr config)" 0 "$rc"
assert_json_count "0 findings (accepted config posture)" "$tmpdir/out.json" 0

# -------------------------------------------------------
echo "Test 17: Author paths with failed file opens are not auth failures"
cat > "$tmpdir/author-file-open.txt" <<'EOF'
document-indexer-1   | {"timestamp": "2026-06-06T05:25:03.503125+00:00", "level": "WARNING", "service": "document-indexer", "name": "document_indexer.thumbnail", "message": "Thumbnail generation failed for /data/documents/TestAuthor/TestAuthor - Corrupt Index (2024).pdf: Failed to open file '/data/documents/TestAuthor/TestAuthor - Corrupt Index (2024).pdf'.", "logger": "document_indexer.thumbnail"}
EOF
sh "$ANALYZER" "$tmpdir/author-file-open.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (benign thumbnail warning)" 0 "$rc"
assert_no_category "no security findings" "$tmpdir/out.json" "security"

# -------------------------------------------------------
echo "Test 18: Explicit auth failures are still security errors"
cat > "$tmpdir/auth-failed.txt" <<'EOF'
api-1 | 2026-06-06 auth failed for service account
EOF
sh "$ANALYZER" "$tmpdir/auth-failed.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 1 (security error)" 1 "$rc"
assert_json_field "category=security" "$tmpdir/out.json" 0 "category" "security"
assert_json_field "severity=error" "$tmpdir/out.json" 0 "severity" "error"

# -------------------------------------------------------
echo "Test 19: Explicit authentication failures are still security errors"
cat > "$tmpdir/authentication-failure.txt" <<'EOF'
api-1 | 2026-06-06 authentication failure for service account
EOF
sh "$ANALYZER" "$tmpdir/authentication-failure.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 1 (security error)" 1 "$rc"
assert_json_field "category=security" "$tmpdir/out.json" 0 "category" "security"
assert_json_field "severity=error" "$tmpdir/out.json" 0 "severity" "error"

# -------------------------------------------------------
echo "Test 20: Solr JVM Unsafe deprecations stay info-only"
cat > "$tmpdir/solr-unsafe-deprecation.txt" <<'EOF'
solr-init-1 | WARNING: A terminally deprecated method in sun.misc.Unsafe has been called
solr-init-1 | WARNING: sun.misc.Unsafe::arrayBaseOffset will be removed in a future release
solr-1      | WARNING: A terminally deprecated method in sun.misc.Unsafe has been called
solr-1      | WARNING: sun.misc.Unsafe::arrayBaseOffset will be removed in a future release
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/solr-unsafe-deprecation.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 0 (info-only Solr JVM warnings)" 0 "$rc"
assert_json_count "4 info findings" "$tmpdir/out.json" 4
assert_json_field "severity[0]=info" "$tmpdir/out.json" 0 "severity" "info"
assert_json_field "severity[1]=info" "$tmpdir/out.json" 1 "severity" "info"

# -------------------------------------------------------
echo "Test 21: Deprecated Solr log dir property remains actionable"
cat > "$tmpdir/solr-log-dir-deprecation.txt" <<'EOF'
solr-1 | 2026-06-06 WARN o.a.s.c.u.EnvUtils You are passing in deprecated system property solr.log.dir and should upgrade to using solr.logs.dir instead.
EOF
sh "$ANALYZER" --allowlist "$ALLOWLIST" "$tmpdir/solr-log-dir-deprecation.txt" > "$tmpdir/out.json" 2>/dev/null; rc=$?
assert_exit "exit code 2 (deprecated Solr log dir remains warning)" 2 "$rc"
assert_json_field "severity=warning" "$tmpdir/out.json" 0 "severity" "warning"

# -------------------------------------------------------
echo ""
echo "========================================"
echo "Results: $PASS passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ] || exit 1
