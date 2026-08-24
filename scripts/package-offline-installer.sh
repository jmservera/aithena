#!/usr/bin/env bash
set -euo pipefail

umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
OUTPUT_ROOT="$REPO_ROOT/staging"
DATE_STAMP="$(date -u +%Y%m%d)"
PACKAGE_NAME="aithena-offline-${DATE_STAMP}"
PACKAGE_DIR="${OUTPUT_ROOT}/${PACKAGE_NAME}"
ARCHIVE_PATH="${OUTPUT_ROOT}/${PACKAGE_NAME}.tar.gz"
DRY_RUN=0
WITHOUT_EMBEDDINGS=0
EMBEDDINGS_VARIANT="torch"

DEFAULT_COMPOSE_FILES=(
  "$REPO_ROOT/docker-compose.yml"
  "$REPO_ROOT/docker/compose.prod.yml"
)
OPENVINO_OVERLAY="$REPO_ROOT/docker/compose.gpu-intel.yml"
PACKAGE_CONFIG_FILES=(
  "docker-compose.yml"
  "docker-compose.prod.yml"
)
PACKAGE_CONFIG_BIND_PATHS=(
  "src/redis/redis.conf"
  "src/rabbitmq/rabbitmq.conf"
  "src/rabbitmq/init-definitions.sh"
  "src/nginx/docker-entrypoint-solr-auth.sh"
  "src/nginx/default.conf.template"
  "src/nginx/html"
  "src/solr/entrypoint.sh"
  "src/solr/log4j2.xml"
  "src/solr/books"
  "src/solr/add-conf-overlay.sh"
)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
step()  { printf "${BLUE}[STEP]${NC}  %s\n" "$*"; }

usage() {
  cat <<'USAGE'
Usage: scripts/package-offline-installer.sh [OPTIONS]

Generate a self-contained offline installer package for Aithena.

Options:
  --dry-run                    Show the plan without exporting images
  --without-embeddings         Omit the embeddings image from the package
  --embeddings-variant VALUE   torch (default) or openvino
  --output-dir DIR             Output directory (default: staging/)
  --help, -h                   Show this help text

Notes:
  - Images are discovered from docker compose config --images.
  - Custom Aithena images must already exist locally.
  - Official images are pulled automatically when missing.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --without-embeddings)
      WITHOUT_EMBEDDINGS=1
      shift
      ;;
    --embeddings-variant)
      EMBEDDINGS_VARIANT="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_ROOT="${2:-}"
      PACKAGE_DIR="${OUTPUT_ROOT}/${PACKAGE_NAME}"
      ARCHIVE_PATH="${OUTPUT_ROOT}/${PACKAGE_NAME}.tar.gz"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      error "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

case "$EMBEDDINGS_VARIANT" in
  torch|openvino) ;;
  *)
    error "Unsupported embeddings variant: ${EMBEDDINGS_VARIANT} (expected: torch|openvino)"
    exit 1
    ;;
esac

for cmd in docker gzip tar df awk sort stat python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    error "Required command not found: $cmd"
    exit 1
  fi
done

if ! docker compose version >/dev/null 2>&1; then
  error "Docker Compose v2 plugin not found."
  exit 1
fi

bytes_to_human() {
  local bytes="${1:-0}"
  local units=(B KiB MiB GiB TiB)
  local unit_index=0
  local value="$bytes"

  while [[ "$value" -ge 1024 && "$unit_index" -lt $((${#units[@]} - 1)) ]]; do
    value=$((value / 1024))
    unit_index=$((unit_index + 1))
  done

  printf '%s %s' "$value" "${units[$unit_index]}"
}

image_filename() {
  local reference="$1"
  local name="${reference##*/}"
  name="${name%%:*}"
  name="${name//[^a-zA-Z0-9._-]/-}"
  printf '%s.tar.gz' "$name"
}

image_is_custom() {
  local reference="$1"
  [[ "$reference" == ghcr.io/jmservera/aithena-* || "$reference" == aithena-* ]]
}

resolve_local_image() {
  local reference="$1"

  if docker image inspect "$reference" >/dev/null 2>&1; then
    printf '%s\n' "$reference"
    return 0
  fi

  if [[ "$reference" == ghcr.io/jmservera/aithena-* ]]; then
    local basename_without_registry="${reference##*/}"
    local local_name="${basename_without_registry%%:*}"
    local fallback_candidates=(
      "$local_name"
      "${local_name}:latest"
    )
    local candidate
    for candidate in "${fallback_candidates[@]}"; do
      if docker image inspect "$candidate" >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    done
  fi

  return 1
}

group_key_for_image() {
  local compose_ref="$1"
  local source_ref="$2"
  local image_id="$3"

  case "$compose_ref:$source_ref" in
    aithena-solr:*|aithena-solr2:*|aithena-solr3:*|aithena-solr-init:*|*:aithena-solr|*:aithena-solr2|*:aithena-solr3|*:aithena-solr-init)
      printf '%s\n' "aithena-solr-cluster"
      return 0
      ;;
  esac

  if [[ "$compose_ref" == ghcr.io/jmservera/aithena-solr-search:* || "$source_ref" == aithena-solr-search* ]]; then
    printf '%s\n' "$image_id"
    return 0
  fi

  if [[ "$compose_ref" == ghcr.io/jmservera/aithena-solr-* ]]; then
    printf '%s\n' "aithena-solr-cluster"
    return 0
  fi

  printf '%s\n' "$image_id"
}

compose_env() {
  AUTH_JWT_SECRET=offline-package-placeholder \
  AUTH_DB_DIR="$REPO_ROOT/volumes/offline-auth-placeholder" \
  SOLR_ADMIN_USER=offline-solr-admin \
  SOLR_ADMIN_PASS=offline-solr-pass \
  SOLR_READONLY_USER=offline-solr-read \
  SOLR_READONLY_PASS=offline-solr-read-pass \
  BOOKS_PATH="$REPO_ROOT/volumes/offline-booklibrary" \
  docker compose "$@"
}

append_csv_unique() {
  local current="$1"
  local value="$2"

  if [[ -z "$current" ]]; then
    printf '%s\n' "$value"
    return 0
  fi

  case ",${current}," in
    *",${value},"*) printf '%s\n' "$current" ;;
    *) printf '%s,%s\n' "$current" "$value" ;;
  esac
}

copy_path() {
  local relative_path="$1"
  local source_path="$REPO_ROOT/$relative_path"
  local target_path="$PACKAGE_DIR/config/$relative_path"

  if [[ ! -e "$source_path" ]]; then
    warn "Skipping missing config path: $relative_path"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY RUN] Would include config/$relative_path"
    return 0
  fi

  mkdir -p "$(dirname "$target_path")"
  if [[ -d "$source_path" ]]; then
    cp -R "$source_path" "$target_path"
  else
    cp "$source_path" "$target_path"
  fi
}

generate_manifest() {
  local manifest_path="$PACKAGE_DIR/images/manifest.tsv"

  {
    printf '# tarball|source_ref|compose_refs|size_bytes\n'
    local image_id
    for image_id in "${GROUP_IDS[@]}"; do
      printf '%s|%s|%s|%s\n' \
        "${FILENAME_BY_ID[$image_id]}" \
        "${SOURCE_REF_BY_ID[$image_id]}" \
        "${COMPOSE_REFS_BY_ID[$image_id]}" \
        "${SIZE_BY_ID[$image_id]}"
    done
  } > "$manifest_path"
}

generate_start_script() {
  local start_script_path="$PACKAGE_DIR/scripts/start.sh"
  local compose_files_literal=""
  local file
  for file in "${PACKAGE_CONFIG_FILES[@]}"; do
    compose_files_literal+=" -f ${file}"
  done

  cat > "$start_script_path" <<EOF_START
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="\$(cd -- "\$(dirname -- "\${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="\$(cd -- "\$SCRIPT_DIR/.." && pwd)"
cd "\$PACKAGE_ROOT/config"

docker compose${compose_files_literal} up -d
EOF_START

  chmod +x "$start_script_path"
}

generate_install_script() {
  local install_script_path="$PACKAGE_DIR/install.sh"
  local compose_files_bash=""
  local omitted_images_bash=""
  local dockerfile_paths_bash=""
  local file
  local image
  local dockerfile_path

  for file in "${PACKAGE_CONFIG_FILES[@]}"; do
    compose_files_bash+="  \"${file}\"\n"
  done
  for image in "${OMITTED_IMAGE_REFS[@]}"; do
    omitted_images_bash+="  \"${image}\"\n"
  done
  for dockerfile_path in "${PACKAGE_DOCKERFILES[@]}"; do
    dockerfile_paths_bash+="  \"${dockerfile_path}\"\n"
  done

  cat > "$install_script_path" <<EOF_INSTALL
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="\$(cd -- "\$(dirname -- "\${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="\$SCRIPT_DIR/config"
IMAGES_DIR="\$SCRIPT_DIR/images"
MANIFEST_PATH="\$IMAGES_DIR/manifest.tsv"
VERSION_PATH="\$SCRIPT_DIR/VERSION"
DRY_RUN=0
SKIP_LOAD=0
LIBRARY_PATH=""
NON_INTERACTIVE=0

COMPOSE_FILES=(
$(printf '%b' "$compose_files_bash"))
)
OMITTED_IMAGES=(
$(printf '%b' "$omitted_images_bash"))
)
DOCKERFILE_PATHS=(
$(printf '%b' "$dockerfile_paths_bash"))
)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { printf "\n${GREEN}[INFO]${NC}  %s\n" "\$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "\$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "\$*" >&2; }
step()  { printf "${BLUE}[STEP]${NC}  %s\n" "\$*"; }

usage() {
  cat <<'USAGE'
Usage: ./install.sh [OPTIONS]

Install Aithena from this offline package.

Options:
  --dry-run               Show the plan without loading images or starting Compose
  --skip-load             Skip docker load (useful if images are already loaded)
  --library-path PATH     Set BOOKS_PATH / BOOK_LIBRARY_PATH when creating .env
  --non-interactive       Do not prompt; use defaults when .env must be created
  --help, -h              Show this help text
USAGE
}

while [[ \$# -gt 0 ]]; do
  case "\$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-load)
      SKIP_LOAD=1
      shift
      ;;
    --library-path)
      LIBRARY_PATH="\${2:-}"
      shift 2
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      error "Unknown option: \$1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "\$MANIFEST_PATH" ]]; then
  error "Package manifest not found: \$MANIFEST_PATH"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  error "Docker is not installed or not on PATH."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  error "Docker Compose v2 plugin not found."
  exit 1
fi

if [[ -f "\$VERSION_PATH" ]]; then
  VERSION="\$(tr -d '[:space:]' < "\$VERSION_PATH")"
else
  VERSION="unknown"
fi

set_env_value() {
  local file_path="\$1"
  local key="\$2"
  local value="\$3"
  local escaped_value
  escaped_value="\$(printf '%s' "\$value" | sed 's/[&|\\]/\\&/g')"

  if grep -q "^\${key}=" "\$file_path"; then
    sed -i "s|^\${key}=.*|\${key}=\${escaped_value}|" "\$file_path"
  else
    printf '\n%s=%s\n' "\$key" "\$value" >> "\$file_path"
  fi
}

read_env_value() {
  local file_path="\$1"
  local key="\$2"
  awk -F= -v target="\$key" '
    \$1 == target {
      value = substr(\$0, index(\$0, "=") + 1)
      print value
      exit
    }
  ' "\$file_path"
}

compose_args=()
for compose_file in "\${COMPOSE_FILES[@]}"; do
  compose_args+=( -f "\$compose_file" )
done

step "Validating package contents"
[[ -d "\$CONFIG_DIR" ]] || { error "Missing config directory: \$CONFIG_DIR"; exit 1; }
[[ -d "\$IMAGES_DIR" ]] || { error "Missing images directory: \$IMAGES_DIR"; exit 1; }
for dockerfile_path in "\${DOCKERFILE_PATHS[@]}"; do
  [[ -f "\$CONFIG_DIR/\$dockerfile_path" ]] || {
    error "Missing Dockerfile required by Compose build context: \$dockerfile_path"
    exit 1
  }
done
info "Package version: \$VERSION"

if [[ "\$SKIP_LOAD" -eq 0 ]]; then
  step "Loading image archives"
  total_archives="\$(grep -vc '^#' "\$MANIFEST_PATH")"
  current_archive=0

  while IFS='|' read -r tarball source_ref compose_refs _size_bytes; do
    [[ -z "\$tarball" || "\$tarball" == \#* ]] && continue
    current_archive=\$((current_archive + 1))

    if [[ "\$DRY_RUN" -eq 1 ]]; then
      info "[DRY RUN] [\${current_archive}/\${total_archives}] Would load \$tarball"
      continue
    fi

    info "[\${current_archive}/\${total_archives}] Loading \$tarball"
    docker load -i "\$IMAGES_DIR/\$tarball" >/dev/null

    IFS=',' read -r -a compose_refs_array <<< "\$compose_refs"
    for compose_ref in "\${compose_refs_array[@]}"; do
      [[ -z "\$compose_ref" ]] && continue
      if [[ "\$compose_ref" != "\$source_ref" ]]; then
        docker tag "\$source_ref" "\$compose_ref"
      fi
    done
  done < "\$MANIFEST_PATH"
else
  warn "Skipping image loading (--skip-load)."
fi

if [[ "\${#OMITTED_IMAGES[@]}" -gt 0 ]]; then
  step "Checking omitted images"
  for omitted_image in "\${OMITTED_IMAGES[@]}"; do
    [[ -z "\$omitted_image" ]] && continue
    if docker image inspect "\$omitted_image" >/dev/null 2>&1; then
      info "Found preloaded omitted image: \$omitted_image"
    else
      error "Missing required image not included in this package: \$omitted_image"
      error "This package was generated with --without-embeddings. Load the image separately, then rerun install.sh."
      exit 1
    fi
  done
fi

ENV_FILE="\$CONFIG_DIR/.env"
step "Preparing environment file"
if [[ -f "\$ENV_FILE" ]]; then
  info "Preserving existing \$ENV_FILE"
else
  [[ -f "\$CONFIG_DIR/.env.example" ]] || { error "Missing config/.env.example"; exit 1; }

  if [[ -z "\$LIBRARY_PATH" ]]; then
    default_library_path="\$HOME/booklibrary"
    if [[ "\$NON_INTERACTIVE" -eq 1 || ! -t 0 ]]; then
      LIBRARY_PATH="\$default_library_path"
      warn "Using default library path: \$LIBRARY_PATH"
    else
      read -r -p "Book library path [\$default_library_path]: " LIBRARY_PATH
      LIBRARY_PATH="\${LIBRARY_PATH:-\$default_library_path}"
    fi
  fi

  if [[ "\$DRY_RUN" -eq 1 ]]; then
    info "[DRY RUN] Would create \$ENV_FILE"
  else
    cp "\$CONFIG_DIR/.env.example" "\$ENV_FILE"
    set_env_value "\$ENV_FILE" "BOOKS_PATH" "\$LIBRARY_PATH"
    set_env_value "\$ENV_FILE" "BOOK_LIBRARY_PATH" "\$LIBRARY_PATH"
    set_env_value "\$ENV_FILE" "AUTH_DB_DIR" "\$HOME/.local/share/aithena/auth"
    chmod 600 "\$ENV_FILE"
    info "Created \$ENV_FILE"
  fi
fi

if [[ -f "\$ENV_FILE" ]]; then
  books_path="\$(read_env_value "\$ENV_FILE" "BOOKS_PATH")"
  auth_db_dir="\$(read_env_value "\$ENV_FILE" "AUTH_DB_DIR")"
else
  books_path="\${LIBRARY_PATH:-\$HOME/booklibrary}"
  auth_db_dir="\$HOME/.local/share/aithena/auth"
fi
books_path="\${books_path:-\$HOME/booklibrary}"
auth_db_dir="\${auth_db_dir:-\$HOME/.local/share/aithena/auth}"

step "Ensuring bind-mount directories exist"
if [[ "\$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would create \$books_path"
  info "[DRY RUN] Would create \$auth_db_dir"
else
  mkdir -p "\$books_path" "\$auth_db_dir"
fi

step "Validating docker compose configuration"
if [[ "\$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would run docker compose config --quiet"
else
  (
    cd "\$CONFIG_DIR"
    docker compose "\${compose_args[@]}" config --quiet
  )
fi

step "Starting Aithena"
if [[ "\$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would run docker compose up -d"
else
  (
    cd "\$CONFIG_DIR"
    docker compose "\${compose_args[@]}" up -d
  )
fi

printf '\n'
info "Offline install complete."
info "Config directory: \$CONFIG_DIR"
info "Books path: \$books_path"
info "If needed later: ./scripts/start.sh"
EOF_INSTALL

  chmod +x "$install_script_path"
}

generate_readme() {
  local readme_path="$PACKAGE_DIR/README.md"
  local embeddings_note
  local overlay_note

  if [[ "$WITHOUT_EMBEDDINGS" -eq 1 ]]; then
    embeddings_note="This package omits the embeddings image. Load it separately on the target host before running install.sh."
  else
    embeddings_note="This package includes the embeddings image (${EMBEDDINGS_VARIANT})."
  fi

  if [[ "$EMBEDDINGS_VARIANT" == "openvino" ]]; then
    overlay_note="OpenVINO package: install.sh starts Compose with docker-compose.gpu-intel.yml. Ensure the target host exposes the Intel GPU runtime expected by that overlay."
  else
    overlay_note="PyTorch package: install.sh starts the standard production Compose stack."
  fi

  cat > "$readme_path" <<EOF_README
# Aithena Offline Package

Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Package: ${PACKAGE_NAME}

## What to do on the target machine

1. Copy \`${PACKAGE_NAME}.tar.gz\` to the offline host.
2. Extract it:

   \`tar xzf ${PACKAGE_NAME}.tar.gz\`

3. Enter the extracted directory.
4. Run:

   \`./install.sh\`

## Notes

- ${embeddings_note}
- ${overlay_note}
- install.sh is idempotent: rerunning it reloads/tags images safely and preserves an existing config/.env.
- If config/.env does not exist yet, install.sh copies config/.env.example and prompts for the book-library path.

## Package layout

\`\`\`
${PACKAGE_NAME}/
├── install.sh
├── README.md
├── images/
├── config/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── .env.example
│   └── src/
└── scripts/
    └── start.sh
\`\`\`
EOF_README
}

compose_files=("${DEFAULT_COMPOSE_FILES[@]}")
if [[ "$EMBEDDINGS_VARIANT" == "openvino" ]]; then
  if [[ ! -f "$OPENVINO_OVERLAY" ]]; then
    error "Missing required OpenVINO overlay: $OPENVINO_OVERLAY"
    exit 1
  fi
  compose_files+=("$OPENVINO_OVERLAY")
  PACKAGE_CONFIG_FILES+=("docker-compose.gpu-intel.yml")
fi

compose_args=()
for compose_file in "${compose_files[@]}"; do
  if [[ ! -f "$compose_file" ]]; then
    error "Missing compose file: $compose_file"
    exit 1
  fi
  compose_args+=( -f "$compose_file" )
done

mapfile -t PACKAGE_DOCKERFILES < <(python3 "$REPO_ROOT/scripts/release_inventory.py" "${compose_files[@]}")
if [[ "${#PACKAGE_DOCKERFILES[@]}" -eq 0 ]]; then
  error "No Dockerfiles discovered from compose build contexts."
  exit 1
fi
python3 "$REPO_ROOT/scripts/release_inventory.py" --check-root "$REPO_ROOT" "${compose_files[@]}"

step "Discovering images from docker compose"
mapfile -t DISCOVERED_IMAGES < <(compose_env "${compose_args[@]}" config --images | sort -u)

if [[ "$WITHOUT_EMBEDDINGS" -eq 1 ]]; then
  filtered_images=()
  OMITTED_IMAGE_REFS=()
  for image_ref in "${DISCOVERED_IMAGES[@]}"; do
    if [[ "$image_ref" == *"aithena-embeddings-server"* ]]; then
      OMITTED_IMAGE_REFS+=("$image_ref")
      continue
    fi
    filtered_images+=("$image_ref")
  done
  DISCOVERED_IMAGES=("${filtered_images[@]}")
else
  OMITTED_IMAGE_REFS=()
fi

if [[ "${#DISCOVERED_IMAGES[@]}" -eq 0 ]]; then
  error "No images discovered from compose configuration."
  exit 1
fi

mkdir -p "$OUTPUT_ROOT"

declare -A SOURCE_REF_BY_ID=()
declare -A COMPOSE_REFS_BY_ID=()
declare -A SIZE_BY_ID=()
declare -A FILENAME_BY_ID=()
declare -A FILENAME_SEEN=()
GROUP_IDS=()
TOTAL_IMAGE_BYTES=0

step "Resolving images"
for compose_image_ref in "${DISCOVERED_IMAGES[@]}"; do
  resolved_source_ref=""
  if resolved_source_ref="$(resolve_local_image "$compose_image_ref" 2>/dev/null)"; then
    :
  elif image_is_custom "$compose_image_ref"; then
    error "Custom image is missing locally: $compose_image_ref"
    error "Build or tag it locally before packaging."
    exit 1
  else
    if [[ "$DRY_RUN" -eq 1 ]]; then
      warn "[DRY RUN] Official image missing locally and would be pulled: $compose_image_ref"
      continue
    fi
    info "Pulling missing official image: $compose_image_ref"
    docker pull "$compose_image_ref"
    resolved_source_ref="$compose_image_ref"
  fi

  image_id="$(docker image inspect --format '{{.Id}}' "$resolved_source_ref")"
  image_size_bytes="$(docker image inspect --format '{{.Size}}' "$resolved_source_ref")"
  group_key="$(group_key_for_image "$compose_image_ref" "$resolved_source_ref" "$image_id")"

  if [[ -z "${SOURCE_REF_BY_ID[$group_key]+x}" ]]; then
    filename_candidate="$(image_filename "$compose_image_ref")"
    if [[ -n "${FILENAME_SEEN[$filename_candidate]+x}" ]]; then
      base_name="${filename_candidate%.tar.gz}"
      suffix=2
      while [[ -n "${FILENAME_SEEN[${base_name}-${suffix}.tar.gz]+x}" ]]; do
        suffix=$((suffix + 1))
      done
      filename_candidate="${base_name}-${suffix}.tar.gz"
    fi

    SOURCE_REF_BY_ID[$group_key]="$resolved_source_ref"
    COMPOSE_REFS_BY_ID[$group_key]="$compose_image_ref"
    SIZE_BY_ID[$group_key]="$image_size_bytes"
    FILENAME_BY_ID[$group_key]="$filename_candidate"
    FILENAME_SEEN[$filename_candidate]=1
    GROUP_IDS+=("$group_key")
    TOTAL_IMAGE_BYTES=$((TOTAL_IMAGE_BYTES + image_size_bytes))
  else
    COMPOSE_REFS_BY_ID[$group_key]="$(append_csv_unique "${COMPOSE_REFS_BY_ID[$group_key]}" "$compose_image_ref")"
  fi
done

if [[ "${#GROUP_IDS[@]}" -eq 0 ]]; then
  error "No exportable images resolved."
  exit 1
fi

ESTIMATED_PACKAGE_BYTES=$((TOTAL_IMAGE_BYTES * 70 / 100))
REQUIRED_FREE_BYTES=$((ESTIMATED_PACKAGE_BYTES * 2 + 2147483648))
AVAILABLE_FREE_BYTES="$(df -Pk "$OUTPUT_ROOT" | awk 'NR==2 {print $4 * 1024}')"

printf '\n'
info "Unique images to export: ${#GROUP_IDS[@]}"
info "Estimated raw image size: $(bytes_to_human "$TOTAL_IMAGE_BYTES")"
info "Estimated package size:  $(bytes_to_human "$ESTIMATED_PACKAGE_BYTES")"
info "Recommended free space:  $(bytes_to_human "$REQUIRED_FREE_BYTES")"
info "Available free space:    $(bytes_to_human "$AVAILABLE_FREE_BYTES")"

if [[ "$AVAILABLE_FREE_BYTES" -lt "$REQUIRED_FREE_BYTES" ]]; then
  error "Not enough free space in $OUTPUT_ROOT for a safe package build."
  exit 1
fi

printf '\n'
step "Image export plan"
current_index=0
for image_id in "${GROUP_IDS[@]}"; do
  current_index=$((current_index + 1))
  info "[${current_index}/${#GROUP_IDS[@]}] ${SOURCE_REF_BY_ID[$image_id]} -> ${FILENAME_BY_ID[$image_id]} ($(bytes_to_human "${SIZE_BY_ID[$image_id]}"))"
  info "        Compose refs: ${COMPOSE_REFS_BY_ID[$image_id]}"
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  warn "Dry run complete. No files were written."
  exit 0
fi

step "Preparing package directory"
rm -rf "$PACKAGE_DIR" "$ARCHIVE_PATH"
mkdir -p "$PACKAGE_DIR/images" "$PACKAGE_DIR/config" "$PACKAGE_DIR/scripts"

step "Copying compose files"
cp "$REPO_ROOT/docker-compose.yml" "$PACKAGE_DIR/config/docker-compose.yml"
cp "$REPO_ROOT/docker/compose.prod.yml" "$PACKAGE_DIR/config/docker-compose.prod.yml"
if [[ "$EMBEDDINGS_VARIANT" == "openvino" ]]; then
  cp "$OPENVINO_OVERLAY" "$PACKAGE_DIR/config/docker-compose.gpu-intel.yml"
fi
cp "$REPO_ROOT/.env.example" "$PACKAGE_DIR/config/.env.example"
cp "$REPO_ROOT/VERSION" "$PACKAGE_DIR/VERSION"

step "Copying runtime config files"
for path in "${PACKAGE_CONFIG_BIND_PATHS[@]}"; do
  copy_path "$path"
done
for path in "${PACKAGE_DOCKERFILES[@]}"; do
  copy_path "$path"
done

step "Generating package scripts"
generate_manifest
generate_install_script
generate_start_script
generate_readme

step "Exporting images"
export_index=0
for image_id in "${GROUP_IDS[@]}"; do
  export_index=$((export_index + 1))
  target_tarball="$PACKAGE_DIR/images/${FILENAME_BY_ID[$image_id]}"
  info "[${export_index}/${#GROUP_IDS[@]}] Saving ${SOURCE_REF_BY_ID[$image_id]}"
  docker save "${SOURCE_REF_BY_ID[$image_id]}" | gzip > "$target_tarball"
done

step "Creating archive"
(
  cd "$OUTPUT_ROOT"
  tar czf "${PACKAGE_NAME}.tar.gz" "$PACKAGE_NAME"
)

ARCHIVE_SIZE_BYTES="$(stat -c '%s' "$ARCHIVE_PATH")"
printf '\n'
info "Offline package ready: $ARCHIVE_PATH"
info "Archive size: $(bytes_to_human "$ARCHIVE_SIZE_BYTES")"
