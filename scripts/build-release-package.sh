#!/usr/bin/env bash
# scripts/build-release-package.sh — single source of truth for staging and
# archiving the Aithena production release package.
#
# Used by both `.github/workflows/release.yml` (real releases) and
# `tests/test-release-package-smoke.sh` (CI/dev smoke testing), so any fix to
# packaging layout only has to happen in one place.
#
# Usage:
#   build-release-package.sh --version X.Y.Z [--archive PATH] [--checksum]
#                             [--output-dir DIR]
#
# Safety notes:
#   * Staging always happens in a script-owned temporary directory created by
#     `mktemp -d`. That directory is never caller-controlled, so removing it
#     on exit is always safe.
#   * --output-dir is caller-controlled and is NEVER deleted by this script.
#     The directory itself is only created (mkdir -p) if missing; its
#     *contents* are only cleared when this exact directory carries a marker
#     file left by a previous run of this script, and only after the path
#     passes `assert_safe_output_dir` (rejects the filesystem root, $HOME, the
#     repository root, any ancestor of the repository, any directory that is
#     itself a git checkout/worktree, and any path that fails to resolve).
#   * --archive writes/overwrites a single named file, never a directory.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

VERSION=""
ARCHIVE_PATH=""
WRITE_CHECKSUM=0
OUTPUT_DIR=""

STAGE_MARKER=".aithena-release-stage"

usage() {
  cat <<'EOF'
Usage: build-release-package.sh --version X.Y.Z [options]

Options:
  --version VERSION   Version string to stamp into the packaged VERSION file (required).
  --archive PATH       Write a .tar.gz release archive to this exact path.
  --checksum           Write PATH.sha256 next to the archive. Requires --archive.
  --output-dir DIR     Also copy the staged (uncompressed) package tree into DIR.
                        DIR is safety-checked and never recursively deleted outright;
                        see the script header comment for the exact rules.
  -h, --help           Show this help and exit.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:?--version requires a value}"
      shift 2
      ;;
    --archive)
      ARCHIVE_PATH="${2:?--archive requires a value}"
      shift 2
      ;;
    --checksum)
      WRITE_CHECKSUM=1
      shift
      ;;
    --output-dir)
      OUTPUT_DIR="${2:?--output-dir requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$VERSION" ]] || die "--version is required"
if [[ "$WRITE_CHECKSUM" -eq 1 && -z "$ARCHIVE_PATH" ]]; then
  die "--checksum requires --archive"
fi

# ── Safety guard for the caller-controlled --output-dir ─────────────────────
assert_safe_output_dir() {
  local candidate="$1"
  local resolved
  resolved="$(realpath -m -- "$candidate")" || die "Could not resolve --output-dir: $candidate"

  [[ -n "$resolved" && "$resolved" != "." ]] || die "refusing to use an empty/unresolvable --output-dir"
  [[ "$resolved" != "/" ]] || die "refusing to use the filesystem root as --output-dir"
  [[ "$resolved" != "${HOME:-}" ]] || die "refusing to use \$HOME as --output-dir"
  [[ "$resolved" != "$REPO_ROOT" ]] || die "refusing to use the repository root as --output-dir"

  # Reject the resolved path if it is an ancestor of (or equal to) the repo root.
  case "$REPO_ROOT/" in
    "$resolved/"*) die "refusing to use an ancestor of the repository as --output-dir: $resolved" ;;
  esac

  # Reject the resolved path if it is the repo root itself or any path nested
  # inside it (e.g. `--output-dir src/nginx`): even though such a path would
  # pass every other check, staging/clearing content there could clobber real
  # tracked source files. Only paths entirely outside the repository tree are
  # considered safe.
  case "$resolved/" in
    "$REPO_ROOT/"*) die "refusing to use a directory inside the repository as --output-dir: $resolved" ;;
  esac

  # Reject any directory that is itself a git checkout/worktree root.
  if [[ -e "$resolved/.git" ]]; then
    die "refusing to use a git repository/worktree root as --output-dir: $resolved"
  fi

  # Reject any directory registered as a worktree of this repository.
  if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    local wt wt_resolved
    while IFS= read -r wt; do
      [[ -n "$wt" ]] || continue
      wt_resolved="$(realpath -m -- "$wt" 2>/dev/null || true)"
      [[ -n "$wt_resolved" ]] || continue
      if [[ "$resolved" == "$wt_resolved" ]]; then
        die "refusing to use a registered git worktree as --output-dir: $resolved"
      fi
    done < <(git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | awk '/^worktree /{ $1=""; sub(/^ /,""); print }')
  fi

  printf '%s\n' "$resolved"
}

# ── Stage in a script-owned temp directory (always safe to rm -rf) ──────────
STAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/aithena-release-stage.XXXXXX")"
cleanup() {
  rm -rf -- "$STAGE_ROOT"
}
trap cleanup EXIT

PACKAGE_DIR="$STAGE_ROOT/aithena-release"
mkdir -p "$PACKAGE_DIR"

echo "Staging Aithena release package (version $VERSION) in $PACKAGE_DIR"

copy_path() {
  local src="$1" dest="$2"
  [[ -e "$REPO_ROOT/$src" ]] || die "Required packaging source path is missing: $src"
  mkdir -p "$(dirname -- "$PACKAGE_DIR/$dest")"
  cp -a "$REPO_ROOT/$src" "$PACKAGE_DIR/$dest"
}

# ── Top-level files ──────────────────────────────────────────────────────────
copy_path "docker-compose.yml" "docker-compose.yml"
copy_path "README.md" "README.md"
copy_path "LICENSE" "LICENSE"
copy_path ".env.example" ".env.example"

# The VERSION file is written directly from the requested --version so the
# staged package always agrees with the archive it is built into, even when
# callers (like the smoke test) request a version that differs from the
# repository's checked-in VERSION file.
printf '%s\n' "$VERSION" > "$PACKAGE_DIR/VERSION"

# ── Docs referenced by the packaged installer/README ────────────────────────
copy_path "docs/quickstart.md" "docs/quickstart.md"
copy_path "docs/admin-manual.md" "docs/admin-manual.md"
copy_path "docs/user-manual.md" "docs/user-manual.md"
copy_path "docs/config/README.md" "docs/config/README.md"

# ── Installer (bootstrap wrapper + PEP 723 script + aithena-common dep) ─────
copy_path "installer/run.sh" "installer/run.sh"
copy_path "installer/setup.py" "installer/setup.py"
copy_path "installer/__main__.py" "installer/__main__.py"
copy_path "installer/__init__.py" "installer/__init__.py"
copy_path "installer/pyproject.toml" "installer/pyproject.toml"
copy_path "installer/uv.lock" "installer/uv.lock"

copy_path "src/aithena-common/pyproject.toml" "src/aithena-common/pyproject.toml"
copy_path "src/aithena-common/uv.lock" "src/aithena-common/uv.lock"
copy_path "src/aithena-common/aithena_common/__init__.py" "src/aithena-common/aithena_common/__init__.py"
copy_path "src/aithena-common/aithena_common/auth_db.py" "src/aithena-common/aithena_common/auth_db.py"
copy_path "src/aithena-common/aithena_common/passwords.py" "src/aithena-common/aithena_common/passwords.py"

# ── Compose overlays selectable by the installer's generated start.sh ───────
COMPOSE_OVERLAY_FILES=(
  "docker/compose.prod.yml"
  "docker/compose.dev-ports.yml"
  "docker/compose.gpu-nvidia.yml"
  "docker/compose.gpu-intel.yml"
  "docker/compose.ssl.yml"
  "docker/compose.single-node.yml"
)
for overlay in "${COMPOSE_OVERLAY_FILES[@]}"; do
  copy_path "$overlay" "$overlay"
done

# ── Runtime config bind-mounted by the base compose file and its overlays ──
# Keep this list in sync with every `./src/...` bind mount across
# docker-compose.yml and docker/*.yml (see docker/compose.ssl.yml's
# ssl.conf.template mount, the historical omission this list closes).
CONFIG_BIND_PATHS=(
  "src/nginx/docker-entrypoint-solr-auth.sh"
  "src/nginx/default.conf.template"
  "src/nginx/ssl.conf.template"
  "src/nginx/html"
  "src/solr/books"
  "src/solr/add-conf-overlay.sh"
  "src/solr/entrypoint.sh"
  "src/solr/log4j2.xml"
  "src/redis/redis.conf"
  "src/rabbitmq/rabbitmq.conf"
  "src/rabbitmq/init-definitions.sh"
)
for path in "${CONFIG_BIND_PATHS[@]}"; do
  copy_path "$path" "$path"
done

echo "Staged $(find "$PACKAGE_DIR" -type f | wc -l) files."

# ── Optionally copy the staged tree into a caller-specified directory ───────
if [[ -n "$OUTPUT_DIR" ]]; then
  safe_output_dir="$(assert_safe_output_dir "$OUTPUT_DIR")"

  if [[ -f "$safe_output_dir/$STAGE_MARKER" ]]; then
    # Only clear directory *contents* we know we created previously — never
    # the directory itself, and only after the marker proves prior ownership.
    find "$safe_output_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  fi

  mkdir -p "$safe_output_dir"
  cp -a "$PACKAGE_DIR/." "$safe_output_dir/"
  touch "$safe_output_dir/$STAGE_MARKER"
  echo "Copied staged package to $safe_output_dir"
fi

# ── Optionally build the .tar.gz archive (and checksum) ─────────────────────
if [[ -n "$ARCHIVE_PATH" ]]; then
  mkdir -p "$(dirname -- "$ARCHIVE_PATH")"
  tar -czf "$ARCHIVE_PATH" -C "$STAGE_ROOT" aithena-release
  echo "Built archive: $ARCHIVE_PATH"

  if [[ "$WRITE_CHECKSUM" -eq 1 ]]; then
    archive_dir="$(cd -- "$(dirname -- "$ARCHIVE_PATH")" && pwd)"
    archive_name="$(basename -- "$ARCHIVE_PATH")"
    (cd "$archive_dir" && sha256sum "$archive_name" > "$archive_name.sha256")
    echo "Wrote checksum: $ARCHIVE_PATH.sha256"
  fi
fi
