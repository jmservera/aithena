#!/usr/bin/env bash
# =============================================================================
# Release Package Builder
# =============================================================================
# Stages a complete release archive with all required files, Dockerfiles,
# documentation, overlays, and supporting infrastructure. Enforces destructive
# safety via path canonicalization and rejects dangerous targets.
# =============================================================================
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
# shellcheck disable=SC2034
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
VERSION="${1:-0.0.0}"
OUTPUT_DIR="${2:-}"
ARCHIVE="${3:-}"
# shellcheck disable=SC2034
CHECKSUM="${4:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default output directory
if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="${REPO_ROOT}/.release-artifacts"
fi

# Default archive path
if [[ -z "$ARCHIVE" ]]; then
  ARCHIVE="${OUTPUT_DIR}/aithena-${VERSION}.tar.gz"
fi

# Parse arguments for options
if [[ "$*" == *"--checksum"* ]]; then
  GENERATE_CHECKSUM=1
else
  GENERATE_CHECKSUM=0
fi

if [[ "$*" == *"--output-dir"* ]]; then
  # Shift to get value after flag
  for ((i=1; i<=$#; i++)); do
    if [[ "${!i}" == "--output-dir" ]]; then
      ((i++))
      OUTPUT_DIR="${!i}"
      break
    fi
  done
fi

if [[ "$*" == *"--archive"* ]]; then
  for ((i=1; i<=$#; i++)); do
    if [[ "${!i}" == "--archive" ]]; then
      ((i++))
      ARCHIVE="${!i}"
      break
    fi
  done
fi

if [[ "$*" == *"--version"* ]]; then
  for ((i=1; i<=$#; i++)); do
    if [[ "${!i}" == "--version" ]]; then
      ((i++))
      VERSION="${!i}"
      break
    fi
  done
fi

echo "=== Release Package Builder ==="
echo "Version: $VERSION"
echo "Output: $OUTPUT_DIR"
echo "Archive: $ARCHIVE"

# Safety: canonicalize paths
REPO_ROOT_REAL=$(realpath -e "$REPO_ROOT")
OUTPUT_DIR_REAL=$(realpath -m "$OUTPUT_DIR")  # -m allows non-existent paths
ARCHIVE_REAL=$(realpath -m "$ARCHIVE")

# Reject dangerous targets
reject_target() {
  local target="$1"
  local reason="$2"
  echo -e "${RED}ERROR: Rejecting destructive target${NC}"
  echo "Target: $target"
  echo "Reason: $reason"
  exit 1
}

if [[ "$OUTPUT_DIR_REAL" == "/" ]]; then
  reject_target "$OUTPUT_DIR_REAL" "Cannot use root directory"
fi

if [[ "$OUTPUT_DIR_REAL" == "$HOME" ]]; then
  reject_target "$OUTPUT_DIR_REAL" "Cannot use home directory"
fi

# Check for containment in dangerous paths
if [[ "$OUTPUT_DIR_REAL" == "$REPO_ROOT_REAL" ]]; then
  reject_target "$OUTPUT_DIR_REAL" "Output directory cannot be repo root (risk of overwriting source)"
fi

# Stage directory must not contain symlink loops
STAGE_DIR="${OUTPUT_DIR_REAL}/aithena-${VERSION}"
if mkdir -p "$OUTPUT_DIR_REAL"; then
  true
else
  echo -e "${RED}ERROR: Cannot create output directory${NC}" >&2
  exit 1
fi

# Clean old staging
if [[ -e "$STAGE_DIR" ]]; then
  rm -rf "$STAGE_DIR"
fi
mkdir -p "$STAGE_DIR"

echo ""
echo "== Stage 1: Core Files =="

# Copy root docker-compose.yml
if [[ -f "$REPO_ROOT_REAL/docker-compose.yml" ]]; then
  cp "$REPO_ROOT_REAL/docker-compose.yml" "$STAGE_DIR/"
  echo "✓ Root docker-compose.yml"
else
  echo "✗ ERROR: Root docker-compose.yml not found" >&2
  exit 1
fi

# Copy installer
if [[ -d "$REPO_ROOT_REAL/installer" ]]; then
  cp -r "$REPO_ROOT_REAL/installer" "$STAGE_DIR/"
  echo "✓ Installer scripts"
else
  echo "✗ ERROR: Installer directory not found" >&2
  exit 1
fi

# Copy aithena-common
if [[ -d "$REPO_ROOT_REAL/src/aithena-common" ]]; then
  mkdir -p "$STAGE_DIR/src"
  cp -r "$REPO_ROOT_REAL/src/aithena-common" "$STAGE_DIR/src/"
  echo "✓ src/aithena-common"
else
  echo "✗ ERROR: src/aithena-common not found" >&2
  exit 1
fi

echo ""
echo "== Stage 2: Compose Files =="

# Copy main docker directory with all overlays
if [[ -d "$REPO_ROOT_REAL/docker" ]]; then
  mkdir -p "$STAGE_DIR/docker"
  
  # Required overlays
  OVERLAYS=(
    "compose.prod.yml"
    "compose.ssl.yml"
    "compose.gpu-nvidia.yml"
    "compose.gpu-intel.yml"
    "compose.single-node.yml"
    "compose.solr9.yml"
    "compose.solr10.yml"
    "compose.dev-ports.yml"
  )
  
  for overlay in "${OVERLAYS[@]}"; do
    if [[ -f "$REPO_ROOT_REAL/docker/$overlay" ]]; then
      cp "$REPO_ROOT_REAL/docker/$overlay" "$STAGE_DIR/docker/"
      echo "✓ docker/$overlay"
    else
      echo "⚠ docker/$overlay not found (optional overlay)"
    fi
  done
else
  echo "✗ ERROR: docker directory not found" >&2
  exit 1
fi

echo ""
echo "== Stage 3: Build Contexts & Dockerfiles =="

# Use release_inventory.py to derive all required Dockerfiles and sources
if command -v python3 >/dev/null 2>&1 && [[ -f "$REPO_ROOT_REAL/scripts/release_inventory.py" ]]; then
  INVENTORY_FILE="$STAGE_DIR/.inventory.json"
  python3 "$REPO_ROOT_REAL/scripts/release_inventory.py" \
    --compose-dir "$REPO_ROOT_REAL" --format json >"$INVENTORY_FILE"
  
  echo "✓ Inventory generated"

  # Extract build contexts and copy their Dockerfiles + sources
  python3 -c "
import json
import sys
from pathlib import Path
import shutil

repo_root = Path('$REPO_ROOT_REAL')
stage_dir = Path('$STAGE_DIR')
inventory_file = '$INVENTORY_FILE'

with open(inventory_file) as f:
  inventory = json.load(f)

for context, info in inventory.get('build_contexts', {}).items():
  # Handle root context specially
  if context == '.':
    context_real = repo_root
    stage_context = stage_dir
  else:
    context_real = repo_root / context
    stage_context = stage_dir / context
  
  # Resolve dockerfile path (may be absolute or relative to context)
  dockerfile_rel = info['dockerfile'].lstrip('./')
  dockerfile_src = context_real / dockerfile_rel

  if dockerfile_src.exists():
    # Create context directory in stage
    stage_context.mkdir(parents=True, exist_ok=True)

    # Copy Dockerfile to stage context
    stage_dockerfile = stage_context / Path(dockerfile_rel).name
    shutil.copy2(dockerfile_src, stage_dockerfile)
    implicit = 'implicit' if info['implicit'] else 'explicit'
    
    # Format output path
    if context == '.':
      display_path = dockerfile_rel
    else:
      display_path = f'{context}/{info[\"dockerfile\"]}'
    
    print(f'✓ {display_path} ({implicit})', file=sys.stderr)

    # Copy COPY sources referenced in Dockerfile
    for src in info.get('copy_sources', []):
      src_path = context_real / src
      if src_path.exists():
        dest_path = stage_context / Path(src).name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
          shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        else:
          shutil.copy2(src_path, dest_path)
        print(f'  ✓ COPY source: {src}', file=sys.stderr)
      else:
        print(f'  ⚠ COPY source not found: {src}', file=sys.stderr)
  else:
    print(f'✗ Dockerfile not found: {dockerfile_src}', file=sys.stderr)
    sys.exit(1)

print('Build contexts staged', file=sys.stderr)
"
else
  echo "⚠ Python/inventory script not available; skipping automatic Dockerfile collection"
fi

echo ""
echo "== Stage 4: Bind Mounts & Configuration ==="

# Copy .env.example
if [[ -f "$REPO_ROOT_REAL/.env.example" ]]; then
  cp "$REPO_ROOT_REAL/.env.example" "$STAGE_DIR/"
  echo "✓ .env.example"
fi

# Copy SSL template if referenced
if [[ -f "$REPO_ROOT_REAL/src/nginx/ssl.conf.template" ]]; then
  mkdir -p "$STAGE_DIR/src/nginx"
  cp "$REPO_ROOT_REAL/src/nginx/ssl.conf.template" "$STAGE_DIR/src/nginx/"
  echo "✓ SSL template"
fi

echo ""
echo "== Stage 5: Documentation ==="

# Ship markdown documentation with corrected paths
DOCS=(
  "README.md"
  "docs/quickstart.md"
  "docs/admin-manual.md"
  "docs/user-manual.md"
  "docs/config/README.md"
  "docs/deployment-topologies.md"
  "docs/GPU.md"
  "docs/WSL2.md"
  "CHANGELOG.md"
  "MIGRATION.md"
)

for doc in "${DOCS[@]}"; do
  if [[ -f "$REPO_ROOT_REAL/$doc" ]]; then
    DOC_DIR=$(dirname "$STAGE_DIR/$doc")
    mkdir -p "$DOC_DIR"
    cp "$REPO_ROOT_REAL/$doc" "$STAGE_DIR/$doc"
    echo "✓ $doc"
  fi
done

# Remove .inventory.json before archiving (internal only)
rm -f "$STAGE_DIR/.inventory.json"

echo ""
echo "== Stage 6: Archive Creation ==="

# Create archive
mkdir -p "$(dirname "$ARCHIVE_REAL")"
tar -czf "$ARCHIVE_REAL" -C "$OUTPUT_DIR_REAL" "aithena-${VERSION}"

if [[ -f "$ARCHIVE_REAL" ]]; then
  SIZE=$(du -h "$ARCHIVE_REAL" | cut -f1)
  echo "✓ Archive created: $ARCHIVE_REAL ($SIZE)"
else
  echo "✗ Archive creation failed" >&2
  exit 1
fi

# Generate checksum if requested
if [[ $GENERATE_CHECKSUM -eq 1 ]]; then
  CHECKSUM_FILE="${ARCHIVE_REAL}.sha256"
  (cd "$(dirname "$ARCHIVE_REAL")" && sha256sum "$(basename "$ARCHIVE_REAL")" >"$CHECKSUM_FILE")
  if [[ -f "$CHECKSUM_FILE" ]]; then
    echo "✓ Checksum: $(cat "$CHECKSUM_FILE")"
  fi
fi

echo ""
echo -e "${GREEN}✅ Release package built successfully${NC}"
echo "Archive: $ARCHIVE_REAL"
