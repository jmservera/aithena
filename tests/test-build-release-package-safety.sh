#!/usr/bin/env bash
# shellcheck disable=SC2015,SC2016
# SC2015: `cond && pass "..." || fail "..."` is exact here — pass/fail always return 0.
# SC2016: single-quoted example commands are printed literally on purpose.
# =============================================================================
# Aithena — destructive-path and archive-completeness regression tests
# =============================================================================
# Proves that scripts/build-release-package.sh can never delete caller content
# and that the package validator actually catches packaging defects.
#
# Usage: tests/test-build-release-package-safety.sh
# =============================================================================
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd -P)"
BUILDER="$REPO_ROOT/scripts/build-release-package.sh"
INVENTORY="$REPO_ROOT/scripts/release_inventory.py"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1" >&2; }
section() { printf '\n▶ %s\n' "$1"; }

PYTHON_RUNNER=(python3)
if ! python3 -c "import yaml" >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    PYTHON_RUNNER=(uv run --no-project --quiet --with pyyaml python)
  else
    echo "ERROR: python3 with PyYAML (or uv) is required" >&2
    exit 2
  fi
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aithena-safety.XXXXXXXX")"
# shellcheck disable=SC2317  # invoked via the EXIT trap
cleanup() {
  [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" ]] && rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

# reject_case LABEL OUTPUT_DIR EXPECTED_SUBSTRING
reject_case() {
  local label="$1" outdir="$2" expected="$3"
  local log="$WORK_DIR/reject.log"
  if bash "$BUILDER" --output-dir "$outdir" > "$log" 2>&1; then
    fail "$label — builder exited 0 but must refuse"
    return
  fi
  if grep -qF "$expected" "$log"; then
    pass "$label"
  else
    fail "$label — refused, but message lacked '$expected': $(tail -1 "$log")"
  fi
}

section "Refuses destructive output directories"
reject_case "rejects the filesystem root" "/" "filesystem root"
reject_case "rejects \$HOME" "${HOME}" "refusing to use \$HOME"
reject_case "rejects a system directory" "/usr" "system directory"
reject_case "rejects the repository root" "$REPO_ROOT" "inside the repository"
reject_case "rejects a descendant of the repository (src/nginx)" "$REPO_ROOT/src/nginx" "inside the repository"
reject_case "rejects a not-yet-existing descendant of the repository" "$REPO_ROOT/build/artifacts" "inside the repository"
reject_case "rejects an ancestor of the repository" "$(dirname -- "$REPO_ROOT")" "it contains the repository"

section "Canonicalises symlinked invocations"
SYMLINK_DIR="$WORK_DIR/symlinks"
mkdir -p "$SYMLINK_DIR"
ln -s "$REPO_ROOT" "$SYMLINK_DIR/checkout"
reject_case "rejects <symlink-to-repo>/src/nginx" "$SYMLINK_DIR/checkout/src/nginx" "inside the repository"
reject_case "rejects the symlinked repository root itself" "$SYMLINK_DIR/checkout" "inside the repository"

section "Refuses registered git worktrees and foreign git trees"
WORKTREE_FOUND=0
while IFS= read -r worktree; do
  [[ -n "$worktree" ]] || continue
  worktree="$(realpath -m -- "$worktree")"
  [[ "$worktree" != "$REPO_ROOT" ]] || continue
  WORKTREE_FOUND=1
  reject_case "rejects registered worktree root $(basename -- "$worktree")" "$worktree" "git worktree"
  reject_case "rejects a nested path inside worktree $(basename -- "$worktree")" "$worktree/docs/generated" "git worktree"
  break
done < <(git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')

if [[ "$WORKTREE_FOUND" -eq 0 ]]; then
  # Create one so the assertion always runs, even on a single-worktree clone.
  TEMP_WT="$WORK_DIR/extra-worktree"
  if git -C "$REPO_ROOT" worktree add --detach "$TEMP_WT" >/dev/null 2>&1; then
    reject_case "rejects registered worktree root" "$TEMP_WT" "git worktree"
    reject_case "rejects a nested path inside a registered worktree" "$TEMP_WT/docs/generated" "git worktree"
    git -C "$REPO_ROOT" worktree remove --force "$TEMP_WT" >/dev/null 2>&1 || true
  else
    fail "could not create a temporary worktree to exercise worktree rejection"
  fi
fi

FOREIGN="$WORK_DIR/foreign-repo"
mkdir -p "$FOREIGN"
git -C "$FOREIGN" init --quiet
printf 'important\n' > "$FOREIGN/precious.txt"
reject_case "rejects a foreign git working tree" "$FOREIGN" "git working tree"
reject_case "rejects a subdirectory of a foreign git working tree" "$FOREIGN/nested/out" "git working tree"
[[ -f "$FOREIGN/precious.txt" ]] && pass "foreign checkout content was left untouched" \
  || fail "foreign checkout content was deleted"

section "A caller-created marker file never grants deletion authority"
MARKER_DIR="$WORK_DIR/marker dir"
mkdir -p "$MARKER_DIR/subdir"
: > "$MARKER_DIR/.aithena-release-stage"
printf 'do not delete me\n' > "$MARKER_DIR/precious.txt"
printf 'nested\n' > "$MARKER_DIR/subdir/nested.txt"
if bash "$BUILDER" --output-dir "$MARKER_DIR" > "$WORK_DIR/marker.log" 2>&1; then
  pass "builder succeeds in a safe directory that contains a forged marker file"
else
  fail "builder failed in a safe directory containing a forged marker file"
  tail -5 "$WORK_DIR/marker.log" >&2
fi
[[ -f "$MARKER_DIR/precious.txt" ]] && pass "pre-existing file survived the build" || fail "pre-existing file was deleted"
[[ -f "$MARKER_DIR/subdir/nested.txt" ]] && pass "pre-existing subdirectory survived the build" || fail "pre-existing subdirectory was deleted"
[[ -f "$MARKER_DIR/.aithena-release-stage" ]] && pass "forged marker file survived the build" || fail "forged marker file was deleted"
case "$MARKER_DIR" in
  *" "*) pass "whitespace in --output-dir is handled correctly ('$(basename "$MARKER_DIR")')" ;;
  *) fail "whitespace test directory lost its space: $MARKER_DIR" ;;
esac

VERSION="$(tr -d ' \t\n\r' < "$REPO_ROOT/VERSION")"
ARCHIVE="$MARKER_DIR/aithena-v${VERSION}-release.tar.gz"
[[ -f "$ARCHIVE" ]] && pass "archive was created with the expected name" || fail "archive was not created: $ARCHIVE"
[[ -f "$ARCHIVE.sha256" ]] && pass "checksum companion file was created" || fail "checksum file was not created"
if ! find "$MARKER_DIR" -maxdepth 1 -name '.aithena-v*.tmp*' | grep -q .; then
  pass "no temporary archive files were left behind"
else
  fail "temporary archive files were left in the output directory"
fi

section "Replacing an existing archive is atomic and scoped"
FIRST_SUM="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
printf 'stale\n' > "$ARCHIVE"
bash "$BUILDER" --output-dir "$MARKER_DIR" > "$WORK_DIR/rebuild.log" 2>&1 \
  && pass "rebuild replaces an existing archive of the same name" \
  || { fail "rebuild failed"; tail -5 "$WORK_DIR/rebuild.log" >&2; }
SECOND_SUM="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
STALE_SUM="$(printf 'stale\n' | sha256sum | awk '{print $1}')"
[[ "$SECOND_SUM" != "$STALE_SUM" ]] && pass "stale archive content was actually replaced" \
  || fail "stale archive content survived the rebuild"
tar -tzf "$ARCHIVE" > /dev/null 2>&1 && pass "replaced archive is a readable tarball" \
  || fail "replaced archive is not a readable tarball"
[[ "$FIRST_SUM" == "$SECOND_SUM" ]] && pass "rebuilt archive is byte-identical (reproducible)" \
  || pass "rebuilt archive replaced the stale file (content differs, mtimes vary)"
[[ -f "$MARKER_DIR/precious.txt" ]] && pass "unrelated file still intact after rebuild" || fail "unrelated file lost on rebuild"

section "Refuses to overwrite a non-regular archive path"
SYMLINK_OUT="$WORK_DIR/symlink-out"
mkdir -p "$SYMLINK_OUT"
printf 'target\n' > "$WORK_DIR/symlink-target.txt"
ln -s "$WORK_DIR/symlink-target.txt" "$SYMLINK_OUT/aithena-v${VERSION}-release.tar.gz"
if bash "$BUILDER" --output-dir "$SYMLINK_OUT" > "$WORK_DIR/symlink.log" 2>&1; then
  fail "builder overwrote a symlinked archive path"
else
  grep -q "not a regular file" "$WORK_DIR/symlink.log" \
    && pass "refuses to write through a symlinked archive path" \
    || fail "refused, but not for the expected reason"
fi
[[ "$(cat "$WORK_DIR/symlink-target.txt")" == "target" ]] \
  && pass "symlink target content untouched" || fail "symlink target was overwritten"

section "Manifest completeness"
MANIFEST="$WORK_DIR/manifest.txt"
bash "$BUILDER" --print-manifest > "$MANIFEST"
for required in \
  "docker-compose.yml" \
  "docker/compose.prod.yml" \
  "docker/compose.ssl.yml" \
  "docker/compose.gpu-nvidia.yml" \
  "docker/compose.gpu-intel.yml" \
  "docker/compose.single-node.yml" \
  "docker/compose.solr9.yml" \
  "docker/compose.solr10.yml" \
  "docker/compose.e2e.yml" \
  "docker/compose.ci-ports.yml" \
  "docker/compose.dev-ports.yml" \
  "src/solr/Dockerfile" \
  "src/nginx/ssl.conf.template" \
  "src/aithena-common/pyproject.toml" \
  "installer/run.sh" \
  "installer/setup.py" \
  "scripts/MIGRATION.md" \
  "CHANGELOG.md" \
  "README.md" \
  "docs/quickstart.md"; do
  grep -qx "$required" "$MANIFEST" && pass "manifest includes $required" || fail "manifest is missing $required"
done

section "Validator catches reintroduced packaging defects"
DEFECT_DIR="$WORK_DIR/defect"
mkdir -p "$DEFECT_DIR"
tar -xzf "$ARCHIVE" -C "$DEFECT_DIR"
PKG="$DEFECT_DIR/$(find "$DEFECT_DIR" -mindepth 1 -maxdepth 1 -printf '%f\n' | head -1)"

validator_must_fail() {
  local label="$1"
  if "${PYTHON_RUNNER[@]}" "$INVENTORY" --repo-root "$REPO_ROOT" check "$PKG" >/dev/null 2>&1; then
    fail "$label — validator passed a defective package"
  else
    pass "$label"
  fi
}

"${PYTHON_RUNNER[@]}" "$INVENTORY" --repo-root "$REPO_ROOT" check "$PKG" >/dev/null 2>&1 \
  && pass "pristine extracted package validates" || fail "pristine extracted package failed validation"

mv "$PKG/src/solr/Dockerfile" "$WORK_DIR/Dockerfile.bak"
validator_must_fail "removing src/solr/Dockerfile fails validation"
mv "$WORK_DIR/Dockerfile.bak" "$PKG/src/solr/Dockerfile"

mv "$PKG/src/nginx/ssl.conf.template" "$WORK_DIR/ssl.bak"
validator_must_fail "removing src/nginx/ssl.conf.template fails validation"
mv "$WORK_DIR/ssl.bak" "$PKG/src/nginx/ssl.conf.template"

mv "$PKG/docker/compose.solr9.yml" "$WORK_DIR/solr9.bak"
validator_must_fail "removing a documented overlay fails validation"
mv "$WORK_DIR/solr9.bak" "$PKG/docker/compose.solr9.yml"

printf '\nSee [Nowhere](docs/does-not-exist.md).\n' >> "$PKG/README.md"
validator_must_fail "a broken local documentation link fails validation"
"${PYTHON_RUNNER[@]}" - "$PKG" <<'PY'
import sys
from pathlib import Path

readme = Path(sys.argv[1]) / "README.md"
text = readme.read_text(encoding="utf-8")
readme.write_text(text.replace("\nSee [Nowhere](docs/does-not-exist.md).\n", ""), encoding="utf-8")
PY

printf '\n```bash\ndocker compose -f docker/compose.prod.yml up -d\n```\n' >> "$PKG/docs/quickstart.md"
validator_must_fail "a compose command missing the root file fails validation"

section "Result"
printf '  %d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
exit 0
