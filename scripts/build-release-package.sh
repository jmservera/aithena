#!/usr/bin/env bash
# =============================================================================
# Aithena — source release package builder
# =============================================================================
# Builds ``aithena-<version>.tar.gz`` (archive root: ``aithena-<version>/``)
# from the file inventory derived by ``scripts/release_inventory.py``.
#
# Destructive-safety contract:
#   * staging happens in a script-owned ``mktemp -d`` directory, removed by a
#     trap that only ever touches that directory;
#   * the output directory is never deleted, emptied or recreated;
#   * only the single archive file (plus its ``.sha256``) is written, through a
#     temporary file in the same directory followed by an atomic ``mv``;
#   * unsafe output directories (filesystem root, $HOME, this repository and any
#     registered git worktree — including every ancestor and descendant — other
#     git/source trees, and directories holding unrelated caller content) are
#     rejected before anything is written.  Marker files never authorise
#     deletion; nothing is deleted outside the staging directory.
#
# Usage:
#   scripts/build-release-package.sh --output-dir DIR [OPTIONS]
# =============================================================================
set -euo pipefail

umask 022

SCRIPT_PATH="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -P -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)"
REPO_ROOT="$(cd -P -- "$SCRIPT_DIR/.." && pwd -P)"
INVENTORY_SCRIPT="$SCRIPT_DIR/release_inventory.py"

OUTPUT_DIR=""
VERSION=""
REQUIRE_DOCKER=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn() { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
step() { printf "${BLUE}[STEP]${NC}  %s\n" "$*"; }

usage() {
  cat <<'USAGE'
Usage: scripts/build-release-package.sh --output-dir DIR [OPTIONS]

Build the Aithena source release archive (aithena-<version>.tar.gz).

Options:
  --output-dir DIR     Directory that receives the archive (required).
                       Must be outside this repository and every git worktree.
  --version VERSION    Override the version (default: contents of VERSION)
  --require-docker     Fail unless the Docker Compose CLI can be used to derive
                       the authoritative inventory
  --help, -h           Show this help text

The archive root is aithena-<version>/ and always contains:
  * docker-compose.yml and every shipped docker/compose.*.yml overlay
  * installer/ (including the documented ./installer/run.sh entrypoint)
  * src/aithena-common, every Compose build context, Dockerfile and COPY source
  * every bind-mounted config path (nginx SSL template included)
  * the shipped documentation set and release-inventory.json
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --require-docker)
      REQUIRE_DOCKER=1
      shift
      ;;
    --help | -h)
      usage
      exit 0
      ;;
    *)
      error "Unknown option: $1"
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
  error "--output-dir is required (it must live outside this repository)."
  usage >&2
  exit 2
fi

for cmd in tar gzip sha256sum realpath "$PYTHON_BIN"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    error "Required command not found: $cmd"
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Destructive-safety guards
# ---------------------------------------------------------------------------

# is_within CHILD PARENT — true when CHILD is PARENT or lives inside PARENT.
is_within() {
  local child="${1%/}/"
  local parent="${2%/}/"
  [[ "$child" == "$parent"* ]]
}

reject() {
  error "Unsafe --output-dir: $1"
  error "Refusing to write release artifacts there."
  exit 3
}

registered_worktrees() {
  local line
  git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | while IFS= read -r line; do
    if [[ "$line" == worktree\ * ]]; then
      realpath -m -- "${line#worktree }"
    fi
  done
}

assert_safe_output_dir() {
  local target="$1"
  local home_dir
  home_dir="$(realpath -m -- "${HOME:-/nonexistent}")"

  [[ "$target" == "/" ]] && reject "the filesystem root"
  [[ "$target" == "$home_dir" ]] && reject "the home directory ($home_dir)"

  if is_within "$target" "$REPO_ROOT" || is_within "$REPO_ROOT" "$target"; then
    reject "$target is this repository, an ancestor or a descendant of $REPO_ROOT"
  fi

  local worktree
  while IFS= read -r worktree; do
    [[ -z "$worktree" ]] && continue
    if is_within "$target" "$worktree" || is_within "$worktree" "$target"; then
      reject "$target overlaps the registered git worktree $worktree"
    fi
  done < <(registered_worktrees)

  # Foreign git / source trees: walk the existing ancestry looking for a .git
  # entry.  A marker file inside the target never authorises anything.
  local probe="$target"
  while [[ -n "$probe" && "$probe" != "/" ]]; do
    if [[ -e "$probe/.git" ]]; then
      reject "$probe belongs to another git working tree"
    fi
    probe="$(dirname -- "$probe")"
  done

  if [[ -e "$target" && ! -d "$target" ]]; then
    reject "$target exists and is not a directory"
  fi

  if [[ -d "$target" ]]; then
    local entry base
    while IFS= read -r -d '' entry; do
      base="$(basename -- "$entry")"
      case "$base" in
        aithena-*.tar.gz | aithena-*.tar.gz.sha256 | .gitignore) ;;
        # Leftovers from an interrupted run of this script.
        .aithena-*.tar.gz.*) ;;
        *)
          reject "$target holds unrelated caller content (for example '$base')"
          ;;
      esac
    done < <(find "$target" -mindepth 1 -maxdepth 1 -print0)
  fi
}

OUTPUT_DIR_CANONICAL="$(realpath -m -- "$OUTPUT_DIR")"
assert_safe_output_dir "$OUTPUT_DIR_CANONICAL"

# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------

STAGING_DIR="$(mktemp -d -t aithena-release-XXXXXXXX)"
TEMP_ARCHIVE=""
TEMP_CHECKSUM=""
cleanup() {
  # Only ever removes files this script created: the mktemp staging directory
  # and its own dot-prefixed temporary archive/checksum in the output directory.
  if [[ -n "$TEMP_ARCHIVE" && -f "$TEMP_ARCHIVE" ]]; then
    rm -f -- "$TEMP_ARCHIVE"
  fi
  if [[ -n "$TEMP_CHECKSUM" && -f "$TEMP_CHECKSUM" ]]; then
    rm -f -- "$TEMP_CHECKSUM"
  fi
  if [[ -n "${STAGING_DIR:-}" && -d "$STAGING_DIR" && "$(basename -- "$STAGING_DIR")" == aithena-release-* ]]; then
    rm -rf -- "$STAGING_DIR"
  fi
}
trap cleanup EXIT INT TERM

if [[ -z "$VERSION" ]]; then
  VERSION="$(tr -d '[:space:]' <"$REPO_ROOT/VERSION")"
fi
if [[ -z "$VERSION" ]]; then
  error "Unable to determine the release version."
  exit 1
fi

PACKAGE_NAME="aithena-${VERSION}"
PACKAGE_ROOT="$STAGING_DIR/$PACKAGE_NAME"
INVENTORY_JSON="$STAGING_DIR/release-inventory.json"

step "Deriving release inventory from Docker Compose"
inventory_args=(generate --repo-root "$REPO_ROOT" --output "$INVENTORY_JSON")
if [[ "$REQUIRE_DOCKER" -eq 1 ]]; then
  inventory_args+=(--require-docker)
fi
"$PYTHON_BIN" "$INVENTORY_SCRIPT" "${inventory_args[@]}"

mapfile -t REQUIRED_PATHS < <("$PYTHON_BIN" "$INVENTORY_SCRIPT" paths --inventory "$INVENTORY_JSON" --key required_paths)
mapfile -t DOCKERFILE_PATHS < <("$PYTHON_BIN" "$INVENTORY_SCRIPT" paths --inventory "$INVENTORY_JSON" --key dockerfiles)
mapfile -t IMPLICIT_DOCKERFILES < <("$PYTHON_BIN" "$INVENTORY_SCRIPT" paths --inventory "$INVENTORY_JSON" --key implicit_dockerfiles)
mapfile -t COMPOSE_FILES < <("$PYTHON_BIN" "$INVENTORY_SCRIPT" paths --inventory "$INVENTORY_JSON" --key compose_files)
mapfile -t UNSHIPPED_COMPOSE_FILES < <("$PYTHON_BIN" "$INVENTORY_SCRIPT" paths --inventory "$INVENTORY_JSON" --key unshipped_compose_files)

if [[ "${#REQUIRED_PATHS[@]}" -eq 0 ]]; then
  error "Inventory produced no required paths."
  exit 1
fi
if [[ "${#DOCKERFILE_PATHS[@]}" -eq 0 ]]; then
  error "Inventory produced no Dockerfiles."
  exit 1
fi
if [[ "${#IMPLICIT_DOCKERFILES[@]}" -eq 0 ]]; then
  error "Inventory produced no implicit (context-relative) Dockerfiles."
  exit 1
fi

info "Version: $VERSION"
info "Required paths: ${#REQUIRED_PATHS[@]}"
info "Dockerfiles: ${#DOCKERFILE_PATHS[@]} (implicit: ${#IMPLICIT_DOCKERFILES[@]})"

REPO_IS_GIT=0
if command -v git > /dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  REPO_IS_GIT=1
fi

step "Staging $PACKAGE_NAME"
mkdir -p "$PACKAGE_ROOT"
# Paths are staged shortest-first so that a directory entry is always copied
# before anything nested inside it; nested entries are then skipped instead of
# being copied *into* the already-staged directory (which would duplicate the
# subtree as, for example, src/nginx/html/html).
staged_paths=()
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  source_path="$REPO_ROOT/$relative"
  if [[ ! -e "$source_path" ]]; then
    error "Inventory references a missing repository path: $relative"
    exit 1
  fi

  already_staged=0
  for staged in "${staged_paths[@]+"${staged_paths[@]}"}"; do
    if is_within "$relative" "$staged"; then
      already_staged=1
      break
    fi
  done
  if [[ "$already_staged" -eq 1 ]]; then
    continue
  fi

  target_path="$PACKAGE_ROOT/$relative"
  mkdir -p -- "$(dirname -- "$target_path")"
  if [[ -d "$source_path" && "$REPO_IS_GIT" -eq 1 ]]; then
    # Copy tracked and new-but-not-ignored files so local build artefacts
    # (build/, *.egg-info/, .venv/) never leak into the archive.
    mkdir -p -- "$target_path"
    while IFS= read -r -d '' tracked; do
      mkdir -p -- "$PACKAGE_ROOT/$(dirname -- "$tracked")"
      cp -p -- "$REPO_ROOT/$tracked" "$PACKAGE_ROOT/$tracked"
    done < <(git -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard -- "$relative")
  else
    cp -R -- "$source_path" "$target_path"
  fi
  if [[ -d "$source_path" ]]; then
    staged_paths+=("$relative")
  fi
done < <(printf '%s\n' "${REQUIRED_PATHS[@]}" | awk '{print gsub(/\//, "/"), $0}' | sort -k1,1n -k2 | cut -d' ' -f2-)

cp -- "$INVENTORY_JSON" "$PACKAGE_ROOT/release-inventory.json"

# ---------------------------------------------------------------------------
# Generated package entrypoint
# ---------------------------------------------------------------------------

emit_bash_array() {
  local name="$1"
  shift
  printf '%s=(\n' "$name"
  local value
  for value in "$@"; do
    printf '  %q\n' "$value"
  done
  printf ')\n'
}

step "Generating install.sh"
INSTALL_SCRIPT="$PACKAGE_ROOT/install.sh"
{
  cat <<'INSTALL_HEADER'
#!/usr/bin/env bash
# Aithena release package entrypoint (generated by scripts/build-release-package.sh).
set -euo pipefail

PACKAGE_ROOT="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CHECK_ONLY=0

usage() {
  cat <<'USAGE'
Usage: ./install.sh [--check] [INSTALLER ARGS...]

Validate this release package and run the Aithena installer.

Options:
  --check      Validate package contents only; never runs the installer
  --help, -h   Show this help text

Any other argument is forwarded verbatim to ./installer/run.sh.
USAGE
}

INSTALLER_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --help | -h)
      usage
      exit 0
      ;;
    *)
      INSTALLER_ARGS+=("$1")
      shift
      ;;
  esac
done

INSTALL_HEADER

  emit_bash_array COMPOSE_FILES "${COMPOSE_FILES[@]}"
  emit_bash_array DOCKERFILE_PATHS "${DOCKERFILE_PATHS[@]}"
  emit_bash_array OMITTED_IMAGES "${UNSHIPPED_COMPOSE_FILES[@]}"

  cat <<'INSTALL_BODY'

missing=()
for relative in "${COMPOSE_FILES[@]}" "${DOCKERFILE_PATHS[@]}"; do
  [[ -e "$PACKAGE_ROOT/$relative" ]] || missing+=("$relative")
done
for relative in installer/run.sh docker-compose.yml release-inventory.json VERSION; do
  [[ -e "$PACKAGE_ROOT/$relative" ]] || missing+=("$relative")
done

if [[ "${#missing[@]}" -gt 0 ]]; then
  printf 'Release package is incomplete; missing %d path(s):\n' "${#missing[@]}" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

if [[ "${#OMITTED_IMAGES[@]}" -gt 0 ]]; then
  printf 'Note: %d component(s) are intentionally not shipped:\n' "${#OMITTED_IMAGES[@]}"
  printf '  - %s\n' "${OMITTED_IMAGES[@]}"
fi

# Full inventory validation using the validator shipped inside the archive.
VALIDATOR="$PACKAGE_ROOT/scripts/release_inventory.py"
if [[ -f "$VALIDATOR" ]] && command -v python3 > /dev/null 2>&1; then
  if ! python3 "$VALIDATOR" validate --root "$PACKAGE_ROOT" \
    --inventory "$PACKAGE_ROOT/release-inventory.json"; then
    printf 'Release package failed inventory validation.\n' >&2
    exit 1
  fi
else
  printf 'Note: python3 not available — skipped the full inventory validation.\n'
fi

printf 'Release package validated: %d compose file(s), %d Dockerfile(s).\n' \
  "${#COMPOSE_FILES[@]}" "${#DOCKERFILE_PATHS[@]}"

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  exit 0
fi

exec "$PACKAGE_ROOT/installer/run.sh" "${INSTALLER_ARGS[@]+"${INSTALLER_ARGS[@]}"}"
INSTALL_BODY
} >"$INSTALL_SCRIPT"
chmod 0755 "$INSTALL_SCRIPT"
bash -n "$INSTALL_SCRIPT"

step "Generating RELEASE-PACKAGE.md"
{
  cat <<EOF_DOC
# Aithena ${VERSION} — release package

This archive extracts to \`${PACKAGE_NAME}/\`. Every command below is run from
that directory.

## Install

\`\`\`bash
./install.sh --check          # validate the package without touching the host
./installer/run.sh --help     # installer options
./installer/run.sh            # interactive first-run setup
\`\`\`

## Start the stack

\`\`\`bash
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml -f docker/compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker/compose.prod.yml -f docker/compose.ssl.yml up -d
\`\`\`

The root \`docker-compose.yml\` always comes first; \`docker/compose.prod.yml\`
and every feature overlay are applied after it.

## Shipped Compose overlays

EOF_DOC
  for compose_file in "${COMPOSE_FILES[@]}"; do
    printf -- '- %s\n' "\`$compose_file\`"
  done
  printf '\n## Compose files intentionally not shipped\n\n'
  if [[ "${#UNSHIPPED_COMPOSE_FILES[@]}" -eq 0 ]]; then
    printf 'None — every Compose file in the repository ships with this archive.\n'
  else
    for compose_file in "${UNSHIPPED_COMPOSE_FILES[@]}"; do
      printf -- '- %s\n' "\`$compose_file\`"
    done
  fi
  cat <<'EOF_DOC_TAIL'

## Build contexts and Dockerfiles

`release-inventory.json` lists every build context, Dockerfile (implicit and
explicit), Dockerfile `COPY` source and bind-mounted configuration path that
this archive must contain. Re-validate an extracted archive with:

```bash
./install.sh --check
```

`install.sh --check` re-runs the inventory validation shipped with the archive
(`scripts/release_inventory.py`) against the extracted tree, so a truncated or
tampered download fails loudly instead of half-working.

## Documentation

Shipped documents live under `docs/`. Links that point at repository files which
are not part of the archive are rewritten to canonical
`https://github.com/jmservera/aithena/blob/main/...` URLs.
EOF_DOC_TAIL
} >"$PACKAGE_ROOT/RELEASE-PACKAGE.md"

printf '%s\n' "$VERSION" >"$PACKAGE_ROOT/VERSION"

step "Canonicalising documentation links"
"$PYTHON_BIN" "$SCRIPT_DIR/release_docs.py" rewrite --root "$PACKAGE_ROOT"

step "Validating shipped documentation"
"$PYTHON_BIN" "$SCRIPT_DIR/release_docs.py" all --root "$PACKAGE_ROOT"

step "Validating staged package"
"$PYTHON_BIN" "$INVENTORY_SCRIPT" validate --root "$PACKAGE_ROOT" --inventory "$INVENTORY_JSON"

for dockerfile in "${DOCKERFILE_PATHS[@]}"; do
  if [[ ! -f "$PACKAGE_ROOT/$dockerfile" ]]; then
    error "Staged package is missing Dockerfile: $dockerfile"
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Archive creation — atomic, single-file, non-destructive
# ---------------------------------------------------------------------------

step "Creating archive"
STAGED_ARCHIVE="$STAGING_DIR/${PACKAGE_NAME}.tar.gz"
tar -czf "$STAGED_ARCHIVE" -C "$STAGING_DIR" "$PACKAGE_NAME"

mkdir -p -- "$OUTPUT_DIR_CANONICAL"
ARCHIVE_PATH="$OUTPUT_DIR_CANONICAL/${PACKAGE_NAME}.tar.gz"
TEMP_ARCHIVE="$OUTPUT_DIR_CANONICAL/.${PACKAGE_NAME}.tar.gz.$$"
cp -- "$STAGED_ARCHIVE" "$TEMP_ARCHIVE"
mv -f -- "$TEMP_ARCHIVE" "$ARCHIVE_PATH"

CHECKSUM_PATH="${ARCHIVE_PATH}.sha256"
TEMP_CHECKSUM="$OUTPUT_DIR_CANONICAL/.${PACKAGE_NAME}.tar.gz.sha256.$$"
(cd -- "$OUTPUT_DIR_CANONICAL" && sha256sum "${PACKAGE_NAME}.tar.gz") >"$TEMP_CHECKSUM"
mv -f -- "$TEMP_CHECKSUM" "$CHECKSUM_PATH"

info "Release package ready: $ARCHIVE_PATH"
info "Checksum: $CHECKSUM_PATH"
if [[ "$REQUIRE_DOCKER" -eq 0 ]]; then
  warn "Inventory source: $("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"])' "$INVENTORY_JSON")"
fi
