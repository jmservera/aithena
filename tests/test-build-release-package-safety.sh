#!/usr/bin/env bash
# tests/test-build-release-package-safety.sh — regression coverage for the
# destructive-path guard in scripts/build-release-package.sh.
#
# scripts/build-release-package.sh must NEVER `rm -rf` a caller-controlled
# --output-dir without first proving it is safe. This test asserts every
# known-unsafe path is rejected (with the package still staged, but nothing
# unsafe touched) and that a genuinely safe, script-owned directory is
# accepted.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_SCRIPT="$ROOT/scripts/build-release-package.sh"

# All scratch directories used by this test live under a script-owned mktemp
# directory — never a caller-controlled path — so unconditional cleanup here
# is always safe.
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aithena-release-safety-test.XXXXXX")"
trap 'rm -rf -- "$WORK_DIR"' EXIT

PASS_COUNT=0
FAIL_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "PASS: $*"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo "FAIL: $*" >&2
}

# assert_rejected LABEL OUTPUT_DIR
# Runs the build script against OUTPUT_DIR and asserts it exits non-zero
# with an actionable error, and — critically — that OUTPUT_DIR itself (and
# any marker file the script might otherwise have written into it) is left
# untouched.
assert_rejected() {
  local label="$1" output_dir="$2"
  local marker="$output_dir/.pre-existing-marker"
  local had_marker=0
  if [[ -f "$marker" ]]; then
    had_marker=1
  fi

  local log="$WORK_DIR/reject-$label.log"
  if bash "$BUILD_SCRIPT" --version 0.0.0-safety-test --output-dir "$output_dir" >"$log" 2>&1; then
    fail "$label: build script should have refused --output-dir=$output_dir but exited 0"
    cat "$log" >&2
    return
  fi

  if ! grep -qi "refusing" "$log"; then
    fail "$label: build script rejected --output-dir=$output_dir but without an actionable 'refusing' message"
    cat "$log" >&2
    return
  fi

  if [[ "$had_marker" -eq 1 && ! -f "$marker" ]]; then
    fail "$label: pre-existing marker in $output_dir was removed — destructive rm -rf occurred!"
    return
  fi

  pass "$label: --output-dir=$output_dir was safely rejected"
}

echo "== Rejecting known-unsafe --output-dir values =="

assert_rejected "repository-root" "$ROOT"
assert_rejected "filesystem-root" "/"
assert_rejected "home-directory" "$HOME"

# A directory that is itself a git checkout/worktree (has its own .git entry),
# distinct from the actual repository, must also be rejected — even though it
# is not $ROOT and not $HOME.
FAKE_REPO="$WORK_DIR/fake-repo"
mkdir -p "$FAKE_REPO"
touch "$FAKE_REPO/.git"
echo "sentinel-do-not-delete" > "$FAKE_REPO/.pre-existing-marker"
assert_rejected "foreign-git-checkout" "$FAKE_REPO"
if [[ -f "$FAKE_REPO/.pre-existing-marker" ]]; then
  pass "foreign-git-checkout: sentinel file survived the rejected build attempt"
else
  fail "foreign-git-checkout: sentinel file was destroyed — destructive rm -rf occurred!"
fi

# A directory that is an ancestor of the real repository root must be rejected
# too (deleting it would delete the repository along with everything else).
ANCESTOR="$(dirname -- "$ROOT")"
assert_rejected "repository-ancestor" "$ANCESTOR"

# A directory nested *inside* the repository must be rejected too, even
# though it is neither the repo root, an ancestor, $HOME, nor a foreign git
# checkout — accepting it would let --output-dir clobber real tracked source
# files (e.g. `--output-dir src/nginx`).
DESCENDANT="$ROOT/src/nginx"
assert_rejected "repository-descendant" "$DESCENDANT"
if [[ -f "$DESCENDANT/ssl.conf.template" ]]; then
  pass "repository-descendant: real tracked source file survived the rejected build attempt"
else
  fail "repository-descendant: real tracked source file was destroyed — destructive rm -rf occurred!"
fi

# Registered git worktrees of this repository must be rejected, even when
# they are not the repository this script is invoked from.
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  OTHER_WORKTREE="$(git -C "$ROOT" worktree list --porcelain 2>/dev/null | awk '/^worktree /{ $1=""; sub(/^ /,""); print; exit }')"
  if [[ -n "$OTHER_WORKTREE" ]]; then
    RESOLVED_OTHER="$(realpath -m -- "$OTHER_WORKTREE")"
    RESOLVED_ROOT="$(realpath -m -- "$ROOT")"
    if [[ "$RESOLVED_OTHER" != "$RESOLVED_ROOT" ]]; then
      assert_rejected "registered-worktree" "$OTHER_WORKTREE"
    fi
  fi
fi

echo "== Accepting a genuinely safe --output-dir =="
SAFE_DIR="$WORK_DIR/safe-output"
if bash "$BUILD_SCRIPT" --version 0.0.0-safety-test --output-dir "$SAFE_DIR" \
    >"$WORK_DIR/accept.log" 2>&1; then
  if [[ -f "$SAFE_DIR/docker-compose.yml" && -f "$SAFE_DIR/VERSION" ]]; then
    pass "a script-owned scratch directory is accepted and populated"
  else
    fail "safe --output-dir run succeeded but expected files are missing"
    cat "$WORK_DIR/accept.log" >&2
  fi
else
  fail "a genuinely safe --output-dir was unexpectedly rejected"
  cat "$WORK_DIR/accept.log" >&2
fi

echo "== Re-running against the same safe directory only clears our own marker-owned contents =="
echo "stray-user-file-should-not-persist" > "$SAFE_DIR/.leftover-from-first-run"
if bash "$BUILD_SCRIPT" --version 0.0.0-safety-test-2 --output-dir "$SAFE_DIR" \
    >"$WORK_DIR/accept2.log" 2>&1; then
  if [[ "$(cat "$SAFE_DIR/VERSION")" == "0.0.0-safety-test-2" ]]; then
    pass "re-running against the same marker-owned directory refreshes its contents"
  else
    fail "re-running against the same marker-owned directory did not refresh VERSION"
  fi
else
  fail "re-running the build against the previously-created safe directory failed"
  cat "$WORK_DIR/accept2.log" >&2
fi

echo ""
echo "== Summary =="
echo "Passed: $PASS_COUNT, Failed: $FAIL_COUNT"
[[ "$FAIL_COUNT" -eq 0 ]]
