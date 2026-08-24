#!/usr/bin/env bash
# =============================================================================
# Aithena — release package builder
# =============================================================================
# Builds the distributable release archive:
#
#   scripts/build-release-package.sh --output-dir /path/outside/the/repo
#
# Produces:
#   <output-dir>/aithena-v<VERSION>-release.tar.gz
#   <output-dir>/aithena-v<VERSION>-release.tar.gz.sha256   (unless --no-checksum)
#
# The archive content is *derived*, not hand-maintained: scripts/
# scripts/release_inventory.py reads the shipped Compose files (build contexts,
# Dockerfiles, bind mounts, env_file/config/secret paths) and the shipped
# documentation link graph to compute the manifest. The staged tree is then
# validated before it is packed, so a missing Dockerfile or a broken local doc
# link fails the build instead of the operator's first `docker compose up`.
#
# Safety model (see tests/test-build-release-package-safety.sh):
#   * staging always happens in a script-owned `mktemp -d` directory, which is
#     the only thing this script ever deletes;
#   * `--output-dir` is canonicalised (symlinks resolved) and rejected when it
#     is `/`, a system directory, `$HOME`, the repository root, any ancestor or
#     descendant of the repository, any registered git worktree (or ancestor /
#     descendant of one), or any other git working tree;
#   * pre-existing caller content in the output directory is never touched —
#     the script only creates/replaces the one specifically named archive file
#     (and its checksum), atomically via a temporary file + `mv`;
#   * no marker file, of any name, ever grants deletion authority.
# =============================================================================
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
INVENTORY="$SCRIPT_DIR/release_inventory.py"

VERSION=""
OUTPUT_DIR=""
WRITE_CHECKSUM=1
PRINT_MANIFEST=0

STAGE_DIR=""

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() { printf '==> %s\n' "$*"; }

# shellcheck disable=SC2317  # invoked via the EXIT trap
cleanup() {
  # The staging directory is created by this script with `mktemp -d`; it is the
  # only path this script is ever allowed to remove.
  if [[ -n "$STAGE_DIR" && -d "$STAGE_DIR" && "$STAGE_DIR" == "${TMPDIR:-/tmp}"/aithena-release-stage.* ]]; then
    rm -rf -- "$STAGE_DIR"
  fi
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage: scripts/build-release-package.sh [OPTIONS]

Options:
  --version VERSION   Version string for the archive name and packaged VERSION
                      file (default: contents of ./VERSION)
  --output-dir DIR    Directory that receives the archive. Must be outside the
                      repository and outside every registered git worktree.
  --no-checksum       Do not write the .sha256 companion file
  --print-manifest    Print the derived file manifest and exit
  -h, --help          Show this message

Examples:
  scripts/build-release-package.sh --print-manifest
  scripts/build-release-package.sh --output-dir "$(mktemp -d)"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) [[ $# -ge 2 ]] || die "--version requires a value"; VERSION="$2"; shift 2 ;;
    --output-dir) [[ $# -ge 2 ]] || die "--output-dir requires a value"; OUTPUT_DIR="$2"; shift 2 ;;
    --no-checksum) WRITE_CHECKSUM=0; shift ;;
    --print-manifest) PRINT_MANIFEST=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

# ---------------------------------------------------------------------------
# Python helper (PyYAML required; uv is used as a fallback provider)
# ---------------------------------------------------------------------------
PYTHON_RUNNER=()
select_python_runner() {
  if python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON_RUNNER=(python3)
  elif command -v uv >/dev/null 2>&1; then
    PYTHON_RUNNER=(uv run --no-project --quiet --with pyyaml python)
  else
    die "python3 with PyYAML (or uv) is required to derive the release manifest"
  fi
}

inventory() {
  "${PYTHON_RUNNER[@]}" "$INVENTORY" --repo-root "$REPO_ROOT" "$@"
}

# ---------------------------------------------------------------------------
# Output directory safety
# ---------------------------------------------------------------------------
canon() {
  # Canonicalise without requiring the path to exist yet.
  realpath -m -- "$1"
}

is_within() {
  # is_within CHILD PARENT — true when CHILD == PARENT or CHILD is below PARENT
  local child="$1" parent="$2"
  [[ "$child" == "$parent" || "$child" == "$parent"/* ]]
}

assert_safe_output_dir() {
  local requested="$1"
  local dir home_dir
  dir="$(canon "$requested")"
  home_dir="$(canon "${HOME:-/nonexistent-home}")"

  [[ "$dir" == /* ]] || die "output directory must resolve to an absolute path: $requested"
  [[ "$dir" != "/" ]] || die "refusing to use the filesystem root as --output-dir"

  local system_dir
  for system_dir in /bin /boot /dev /etc /home /lib /lib64 /media /mnt /opt /proc /root /run /sbin /srv /sys /usr /var /tmp; do
    [[ "$dir" != "$system_dir" ]] || die "refusing to use the system directory '$system_dir' as --output-dir"
  done

  [[ "$dir" != "$home_dir" ]] || die "refusing to use \$HOME ($home_dir) as --output-dir"

  if is_within "$dir" "$REPO_ROOT"; then
    die "refusing to use '$dir' as --output-dir: it is the repository root or inside the repository ($REPO_ROOT); pick a directory outside the checkout"
  fi
  if is_within "$REPO_ROOT" "$dir"; then
    die "refusing to use '$dir' as --output-dir: it contains the repository ($REPO_ROOT)"
  fi

  local worktree
  while IFS= read -r worktree; do
    [[ -n "$worktree" ]] || continue
    worktree="$(canon "$worktree")"
    if is_within "$dir" "$worktree"; then
      die "refusing to use '$dir' as --output-dir: it is inside the registered git worktree '$worktree' and its contents are tracked source"
    fi
    if is_within "$worktree" "$dir"; then
      die "refusing to use '$dir' as --output-dir: it contains the registered git worktree '$worktree'"
    fi
  done < <(git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')

  # Any other git working tree (a foreign checkout) is off limits too.
  local probe="$dir" toplevel
  while [[ "$probe" != "/" && ! -e "$probe" ]]; do
    probe="$(dirname -- "$probe")"
  done
  if [[ -d "$probe" ]] && toplevel="$(git -C "$probe" rev-parse --show-toplevel 2>/dev/null)"; then
    toplevel="$(canon "$toplevel")"
    die "refusing to use '$dir' as --output-dir: it belongs to the git working tree '$toplevel'"
  fi

  printf '%s\n' "$dir"
}

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
select_python_runner

if [[ -z "$VERSION" ]]; then
  [[ -f "$REPO_ROOT/VERSION" ]] || die "VERSION file not found and --version not given"
  VERSION="$(tr -d ' \t\n\r' < "$REPO_ROOT/VERSION")"
fi
[[ -n "$VERSION" ]] || die "version must not be empty"

if [[ "$PRINT_MANIFEST" -eq 1 ]]; then
  inventory manifest
  exit 0
fi

[[ -n "$OUTPUT_DIR" ]] || die "--output-dir is required (must be outside the repository); see --help"

SAFE_OUTPUT_DIR="$(assert_safe_output_dir "$OUTPUT_DIR")"
mkdir -p -- "$SAFE_OUTPUT_DIR"

ARCHIVE_NAME="aithena-v${VERSION}-release.tar.gz"
ARCHIVE_PATH="$SAFE_OUTPUT_DIR/$ARCHIVE_NAME"
PACKAGE_DIR_NAME="aithena-v${VERSION}"

if [[ -e "$ARCHIVE_PATH" && ! -f "$ARCHIVE_PATH" ]] || [[ -L "$ARCHIVE_PATH" ]]; then
  die "refusing to replace '$ARCHIVE_PATH': it exists and is not a regular file"
fi

STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aithena-release-stage.XXXXXXXX")"
PACKAGE_ROOT="$STAGE_DIR/$PACKAGE_DIR_NAME"
mkdir -p -- "$PACKAGE_ROOT"

info "Deriving release manifest from Compose configuration and shipped docs"
MANIFEST_FILE="$STAGE_DIR/manifest.txt"
inventory manifest > "$MANIFEST_FILE"
MANIFEST_COUNT="$(wc -l < "$MANIFEST_FILE" | tr -d ' ')"
[[ "$MANIFEST_COUNT" -gt 0 ]] || die "derived manifest is empty"
info "Manifest contains $MANIFEST_COUNT files"

info "Staging package in $PACKAGE_ROOT"
while IFS= read -r rel; do
  [[ -n "$rel" ]] || continue
  src="$REPO_ROOT/$rel"
  [[ -e "$src" ]] || die "manifest entry does not exist: $rel"
  mkdir -p -- "$PACKAGE_ROOT/$(dirname -- "$rel")"
  cp -p -- "$src" "$PACKAGE_ROOT/$rel"
done < "$MANIFEST_FILE"

# The packaged VERSION file always matches the archive name.
printf '%s\n' "$VERSION" > "$PACKAGE_ROOT/VERSION"

info "Rewriting documentation links that point outside the package"
inventory rewrite-links "$PACKAGE_ROOT" || die "documentation link rewriting failed"

info "Validating the staged package"
"${PYTHON_RUNNER[@]}" "$INVENTORY" --repo-root "$REPO_ROOT" check "$PACKAGE_ROOT" \
  || die "staged package failed validation (see failures above)"

info "Creating $ARCHIVE_PATH"
TMP_ARCHIVE="$SAFE_OUTPUT_DIR/.${ARCHIVE_NAME}.$$.tmp"
tar --format=gnu --sort=name --owner=0 --group=0 --numeric-owner \
  -czf "$TMP_ARCHIVE" -C "$STAGE_DIR" "$PACKAGE_DIR_NAME"
mv -f -- "$TMP_ARCHIVE" "$ARCHIVE_PATH"

if [[ "$WRITE_CHECKSUM" -eq 1 ]]; then
  TMP_SUM="$SAFE_OUTPUT_DIR/.${ARCHIVE_NAME}.sha256.$$.tmp"
  ( cd -- "$SAFE_OUTPUT_DIR" && sha256sum "$ARCHIVE_NAME" ) > "$TMP_SUM"
  mv -f -- "$TMP_SUM" "$ARCHIVE_PATH.sha256"
  info "Wrote $ARCHIVE_PATH.sha256"
fi

info "Release package ready: $ARCHIVE_PATH"
printf '%s\n' "$ARCHIVE_PATH"
