#!/usr/bin/env bash
# =============================================================================
# Release package builder — destructive safety regressions
# =============================================================================
# Criterion 7 of issue #1854: the builder must never delete caller data.
#
# Every case below asserts one of:
#   * an unsafe --output-dir is rejected with exit code 3 before anything is
#     written (filesystem root, $HOME, this repository/worktree and all their
#     ancestors and descendants, every registered git worktree, foreign git
#     trees, directories holding arbitrary caller content, symlink and
#     whitespace aliases of any of the above);
#   * a marker file never authorises deletion;
#   * pre-existing caller files survive both rejected and successful runs.
# =============================================================================
set -euo pipefail

ROOT="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
BUILDER="$ROOT/scripts/build-release-package.sh"
REJECT_CODE=3

PASS=0
FAIL=0

pass() {
  PASS=$((PASS + 1))
  printf '  ✅ %s\n' "$*"
}

fail() {
  FAIL=$((FAIL + 1))
  printf '  ❌ %s\n' "$*" >&2
}

# assert_rejected DESCRIPTION OUTPUT_DIR
assert_rejected() {
  local description="$1" target="$2" status=0 output
  output="$(bash "$BUILDER" --output-dir "$target" 2>&1)" || status=$?
  if [[ "$status" -ne "$REJECT_CODE" ]]; then
    fail "$description (expected exit $REJECT_CODE, got $status)"
    printf '     %s\n' "$(printf '%s' "$output" | tail -2)" >&2
    return
  fi
  if ! printf '%s' "$output" | grep -q 'Unsafe --output-dir'; then
    fail "$description (exit $status but no unsafe-output-dir diagnostic)"
    return
  fi
  pass "$description"
}

assert_survives() {
  local description="$1" file="$2" expected="$3"
  if [[ ! -f "$file" ]]; then
    fail "$description (file was deleted: $file)"
    return
  fi
  if [[ "$(cat "$file")" != "$expected" ]]; then
    fail "$description (file was modified: $file)"
    return
  fi
  pass "$description"
}

WORK_DIR="$(mktemp -d -t aithena-safety-XXXXXXXX)"
cleanup() {
  if [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" && "$(basename -- "$WORK_DIR")" == aithena-safety-* ]]; then
    chmod -R u+w -- "$WORK_DIR" 2>/dev/null || true
    rm -rf -- "$WORK_DIR"
  fi
}
trap cleanup EXIT INT TERM

VERSION="$(tr -d '[:space:]' <"$ROOT/VERSION")"

echo "━━━ Precious files that must survive every run ━━━"
REPO_PRECIOUS="$ROOT/.release-safety-precious/precious.txt"
mkdir -p "$(dirname -- "$REPO_PRECIOUS")"
printf 'do-not-delete-repo\n' >"$REPO_PRECIOUS"
remove_repo_precious() { rm -rf -- "$ROOT/.release-safety-precious"; }
trap 'remove_repo_precious; cleanup' EXIT INT TERM

echo
echo "━━━ Filesystem root, home and repository ━━━"
assert_rejected "rejects the filesystem root" /
assert_rejected "rejects \$HOME" "$HOME"
assert_rejected "rejects \$HOME with a trailing slash" "$HOME/"
assert_rejected "rejects the repository root" "$ROOT"
assert_rejected "rejects a repository ancestor" "$(dirname -- "$ROOT")"
assert_rejected "rejects a repository descendant" "$ROOT/docs"
assert_rejected "rejects a nested repository descendant" "$ROOT/.release-safety-precious"
assert_rejected "rejects an unnormalised path back into the repository" "$ROOT/docs/../scripts"

echo
echo "━━━ Registered git worktrees ━━━"
WORKTREE_COUNT=0
while IFS= read -r line; do
  [[ "$line" == worktree\ * ]] || continue
  worktree="$(realpath -m -- "${line#worktree }")"
  WORKTREE_COUNT=$((WORKTREE_COUNT + 1))
  assert_rejected "rejects registered worktree $worktree" "$worktree"
  assert_rejected "rejects worktree ancestor $(dirname -- "$worktree")" "$(dirname -- "$worktree")"
  assert_rejected "rejects worktree descendant $worktree/scripts" "$worktree/scripts"
done < <(git -C "$ROOT" worktree list --porcelain)
if [[ "$WORKTREE_COUNT" -gt 0 ]]; then
  pass "checked $WORKTREE_COUNT registered worktree(s)"
else
  fail "expected at least one registered git worktree"
fi

echo
echo "━━━ Foreign git and source trees ━━━"
FOREIGN="$WORK_DIR/foreign-repo"
mkdir -p "$FOREIGN/nested"
git -C "$FOREIGN" init --quiet
printf 'do-not-delete-foreign\n' >"$FOREIGN/nested/precious.txt"
assert_rejected "rejects a foreign git working tree" "$FOREIGN"
assert_rejected "rejects a directory inside a foreign git working tree" "$FOREIGN/nested"
assert_survives "foreign repository content survives" "$FOREIGN/nested/precious.txt" "do-not-delete-foreign"

echo
echo "━━━ Arbitrary caller content ━━━"
CALLER="$WORK_DIR/caller"
mkdir -p "$CALLER/notes"
printf 'do-not-delete-caller\n' >"$CALLER/notes/precious.txt"
printf 'do-not-delete-top\n' >"$CALLER/report.md"
assert_rejected "rejects a directory holding arbitrary caller content" "$CALLER"
assert_survives "caller file survives" "$CALLER/report.md" "do-not-delete-top"
assert_survives "nested caller file survives" "$CALLER/notes/precious.txt" "do-not-delete-caller"

MARKER_DIR="$WORK_DIR/marker"
mkdir -p "$MARKER_DIR"
printf 'safe to delete? no.\n' >"$MARKER_DIR/.aithena-release-output"
printf 'do-not-delete-marker\n' >"$MARKER_DIR/precious.txt"
assert_rejected "a marker file never authorises deletion" "$MARKER_DIR"
assert_survives "marker directory content survives" "$MARKER_DIR/precious.txt" "do-not-delete-marker"

NESTED_VERSION_DIR="$WORK_DIR/nested-version"
mkdir -p "$NESTED_VERSION_DIR/aithena-${VERSION}"
printf 'do-not-delete-nested-version\n' >"$NESTED_VERSION_DIR/aithena-${VERSION}/precious.txt"
assert_rejected "rejects an output dir holding a pre-existing aithena-<version>/ dir" "$NESTED_VERSION_DIR"
assert_survives "pre-existing nested version dir survives" \
  "$NESTED_VERSION_DIR/aithena-${VERSION}/precious.txt" "do-not-delete-nested-version"

NOT_A_DIR="$WORK_DIR/regular-file"
printf 'do-not-delete-file\n' >"$NOT_A_DIR"
assert_rejected "rejects a path that is not a directory" "$NOT_A_DIR"
assert_survives "regular file survives" "$NOT_A_DIR" "do-not-delete-file"

echo
echo "━━━ Symlink and whitespace aliases ━━━"
ALIAS="$WORK_DIR/repo-alias"
ln -s "$ROOT" "$ALIAS"
assert_rejected "rejects a symlink alias of the repository" "$ALIAS"

SPACED_DIR="$WORK_DIR/dir with spaces"
mkdir -p "$SPACED_DIR"
SPACED_ALIAS="$SPACED_DIR/repo alias"
ln -s "$ROOT" "$SPACED_ALIAS"
assert_rejected "rejects a whitespace symlink alias of the repository" "$SPACED_ALIAS"

HOME_ALIAS="$WORK_DIR/home-alias"
ln -s "$HOME" "$HOME_ALIAS"
assert_rejected "rejects a symlink alias of \$HOME" "$HOME_ALIAS"

CALLER_ALIAS="$WORK_DIR/caller-alias"
ln -s "$CALLER" "$CALLER_ALIAS"
assert_rejected "rejects a symlink alias of a caller content directory" "$CALLER_ALIAS"

echo
echo "━━━ Symlinked invocation of the builder itself ━━━"
BUILDER_ALIAS="$WORK_DIR/build alias.sh"
ln -s "$BUILDER" "$BUILDER_ALIAS"
alias_status=0
alias_output="$(bash "$BUILDER_ALIAS" --output-dir "$ROOT" 2>&1)" || alias_status=$?
if [[ "$alias_status" -eq "$REJECT_CODE" ]] && printf '%s' "$alias_output" | grep -Fq "$ROOT"; then
  pass "symlinked invocation still canonicalises the repository and rejects it"
else
  fail "symlinked invocation must resolve the repository root (exit $alias_status)"
fi

echo
echo "━━━ Successful build preserves unrelated files ━━━"
SAFE_OUT="$WORK_DIR/artifacts"
mkdir -p "$SAFE_OUT"
printf 'old-artifact\n' >"$SAFE_OUT/aithena-0.0.1.tar.gz"
printf 'old-checksum\n' >"$SAFE_OUT/aithena-0.0.1.tar.gz.sha256"
printf '*\n' >"$SAFE_OUT/.gitignore"
build_status=0
bash "$BUILDER" --output-dir "$SAFE_OUT" >"$WORK_DIR/build.log" 2>&1 || build_status=$?
if [[ "$build_status" -eq 0 ]]; then
  pass "builds successfully into a clean artifacts directory"
else
  fail "build into a safe output directory failed (exit $build_status)"
  tail -5 "$WORK_DIR/build.log" >&2
fi
assert_survives "unrelated previous artifact survives" "$SAFE_OUT/aithena-0.0.1.tar.gz" "old-artifact"
assert_survives "unrelated previous checksum survives" "$SAFE_OUT/aithena-0.0.1.tar.gz.sha256" "old-checksum"
assert_survives ".gitignore survives" "$SAFE_OUT/.gitignore" "*"
if [[ -f "$SAFE_OUT/aithena-${VERSION}.tar.gz" ]]; then
  pass "wrote exactly the named archive aithena-${VERSION}.tar.gz"
else
  fail "expected archive aithena-${VERSION}.tar.gz"
fi
if find "$SAFE_OUT" -mindepth 1 -maxdepth 1 -name '.aithena-*' -print -quit | grep -q .; then
  fail "builder left a temporary file in the output directory"
else
  pass "builder left no temporary files in the output directory"
fi

echo
echo "━━━ Rebuild replaces only the named archive ━━━"
printf 'do-not-delete-rebuild\n' >"$SAFE_OUT/aithena-0.0.2.tar.gz"
FIRST_SUM="$(sha256sum "$SAFE_OUT/aithena-${VERSION}.tar.gz" | cut -d' ' -f1)"
rebuild_status=0
bash "$BUILDER" --output-dir "$SAFE_OUT" >>"$WORK_DIR/build.log" 2>&1 || rebuild_status=$?
if [[ "$rebuild_status" -eq 0 ]]; then
  pass "rebuild into the same directory succeeds"
else
  fail "rebuild failed (exit $rebuild_status)"
fi
assert_survives "sibling archive survives the rebuild" "$SAFE_OUT/aithena-0.0.2.tar.gz" "do-not-delete-rebuild"
assert_survives "old artifact survives the rebuild" "$SAFE_OUT/aithena-0.0.1.tar.gz" "old-artifact"
if [[ -n "$FIRST_SUM" && -f "$SAFE_OUT/aithena-${VERSION}.tar.gz" ]]; then
  pass "named archive is still present after the rebuild"
else
  fail "named archive disappeared during the rebuild"
fi

echo
echo "━━━ Repository content is untouched ━━━"
assert_survives "precious file inside the repository survives" "$REPO_PRECIOUS" "do-not-delete-repo"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf 'Release package safety test: %d passed, %d failed\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
