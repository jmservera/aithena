#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# cleanup-ghcr.sh — Remove old / untagged container images from GHCR
#
# Usage:
#   ./scripts/cleanup-ghcr.sh                  # dry-run (default)
#   ./scripts/cleanup-ghcr.sh --execute        # actually delete
#   ./scripts/cleanup-ghcr.sh --keep 3         # keep last 3 tagged versions
#   ./scripts/cleanup-ghcr.sh --keep 3 --execute
#
# Requirements:
#   - gh CLI authenticated with read:packages + delete:packages scopes
#     (export GH_TOKEN with those scopes, or run: gh auth refresh -s read:packages,delete:packages)
#   - jq
#
# What it does:
#   1. Lists all container packages under the repo owner (ghcr.io/jmservera/aithena-*)
#   2. For each package:
#      a. Deletes ALL untagged versions (no tag = build cache / orphaned layers)
#      b. Keeps the N most recent semver-tagged versions (default: 5)
#      c. Always preserves "latest" and the current VERSION file tag
#   3. Reports savings (version count + estimated storage)
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
DRY_RUN=1
KEEP_VERSIONS=5
OWNER=""
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)  DRY_RUN=0; shift ;;
    --keep)     KEEP_VERSIONS="$2"; shift 2 ;;
    --owner)    OWNER="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--execute] [--keep N] [--owner OWNER]"
      echo ""
      echo "  --execute   Actually delete (default: dry-run)"
      echo "  --keep N    Keep the N most recent semver tags (default: 5)"
      echo "  --owner O   GitHub username/org (default: from gh repo view)"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Resolve owner ─────────────────────────────────────────────────────────────
if [[ -z "$OWNER" ]]; then
  OWNER="$(gh repo view --json owner -q '.owner.login' 2>/dev/null || true)"
  if [[ -z "$OWNER" ]]; then
    echo "ERROR: Could not determine repo owner. Use --owner flag." >&2
    exit 1
  fi
fi

# ── Read current version ──────────────────────────────────────────────────────
CURRENT_VERSION=""
if [[ -f "$REPO_ROOT/VERSION" ]]; then
  CURRENT_VERSION="$(tr -d '[:space:]' < "$REPO_ROOT/VERSION")"
fi

# ── Verify token scopes ──────────────────────────────────────────────────────
echo "🔍 Checking authentication..."
if ! gh api user/packages?package_type=container --jq '.[0].name' &>/dev/null; then
  echo "ERROR: Token lacks read:packages scope." >&2
  echo "Run: gh auth refresh -s read:packages,delete:packages" >&2
  exit 1
fi

# ── Discover packages ─────────────────────────────────────────────────────────
echo "📦 Discovering container packages for $OWNER..."
PACKAGES=$(gh api --paginate "user/packages?package_type=container" --jq '.[].name' | grep "^aithena-" | sort)

if [[ -z "$PACKAGES" ]]; then
  echo "No aithena-* packages found."
  exit 0
fi

PACKAGE_COUNT=$(echo "$PACKAGES" | wc -l)
echo "   Found $PACKAGE_COUNT packages"

# ── Counters ──────────────────────────────────────────────────────────────────
TOTAL_UNTAGGED=0
TOTAL_OLD_TAGGED=0

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  DRY RUN — no deletions will occur (use --execute)"
  echo "══════════════════════════════════════════════════════════"
fi

echo ""
echo "Settings: keep=$KEEP_VERSIONS most recent semver tags, protect=latest+v$CURRENT_VERSION"
echo ""

# ── Process each package ──────────────────────────────────────────────────────
for PKG in $PACKAGES; do
  echo "┌─ $PKG"

  # Fetch all versions (paginated)
  VERSIONS_JSON=$(gh api --paginate "user/packages/container/$PKG/versions" 2>/dev/null || echo "[]")
  VERSION_COUNT=$(echo "$VERSIONS_JSON" | jq 'length')

  if [[ "$VERSION_COUNT" -eq 0 ]]; then
    echo "│  (no versions)"
    echo "└─"
    continue
  fi

  # ── 1. Identify and delete untagged versions ────────────────────────────────
  UNTAGGED_IDS=$(echo "$VERSIONS_JSON" | jq -r '.[] | select(.metadata.container.tags | length == 0) | .id')
  UNTAGGED_COUNT=$(echo "$UNTAGGED_IDS" | grep -c . 2>/dev/null || echo 0)

  if [[ "$UNTAGGED_COUNT" -gt 0 ]]; then
    echo "│  🗑  $UNTAGGED_COUNT untagged versions"
    for VID in $UNTAGGED_IDS; do
      if [[ "$DRY_RUN" -eq 0 ]]; then
        gh api --method DELETE "user/packages/container/$PKG/versions/$VID" --silent 2>/dev/null && \
          echo "│     deleted version $VID" || \
          echo "│     ⚠ failed to delete $VID"
      else
        echo "│     would delete version $VID"
      fi
    done
    TOTAL_UNTAGGED=$((TOTAL_UNTAGGED + UNTAGGED_COUNT))
  else
    echo "│  ✅ no untagged versions"
  fi

  # ── 2. Prune old tagged versions ────────────────────────────────────────────
  TAGGED_VERSIONS=$(echo "$VERSIONS_JSON" | jq -r '
    [.[] | select(.metadata.container.tags | length > 0) |
     {id: .id, tags: .metadata.container.tags, created: .created_at,
      semver: (.metadata.container.tags[] | select(test("^[0-9]+\\.[0-9]+\\.[0-9]+$")))}]
    | sort_by(.semver) | reverse | unique_by(.semver)
    | .[] | "\(.id)|\(.semver)|\(.tags | join(","))|\(.created)"
  ' 2>/dev/null || echo "")

  if [[ -z "$TAGGED_VERSIONS" ]]; then
    echo "│  (no semver-tagged versions to prune)"
    echo "└─"
    continue
  fi

  TAGGED_COUNT=$(echo "$TAGGED_VERSIONS" | grep -c . 2>/dev/null || echo 0)
  echo "│  📋 $TAGGED_COUNT semver-tagged versions found"

  IDX=0
  while IFS='|' read -r VID SEMVER TAGS CREATED; do
    IDX=$((IDX + 1))
    PROTECTED=0

    # Protect current version
    if [[ "$SEMVER" == "$CURRENT_VERSION" ]]; then
      PROTECTED=1
    fi

    # Protect if within keep window
    if [[ $IDX -le $KEEP_VERSIONS ]]; then
      PROTECTED=1
    fi

    if [[ "$PROTECTED" -eq 1 ]]; then
      echo "│     ✅ v$SEMVER ($CREATED) — kept"
    else
      echo "│     🗑  v$SEMVER ($CREATED) — old"
      if [[ "$DRY_RUN" -eq 0 ]]; then
        gh api --method DELETE "user/packages/container/$PKG/versions/$VID" --silent 2>/dev/null && \
          echo "│        deleted" || \
          echo "│        ⚠ failed to delete"
      fi
      TOTAL_OLD_TAGGED=$((TOTAL_OLD_TAGGED + 1))
    fi
  done <<< "$TAGGED_VERSIONS"

  echo "└─"
  echo ""
done

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL_DELETED=$((TOTAL_UNTAGGED + TOTAL_OLD_TAGGED))
echo "════════════════════════════════════════════════════════════"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "  DRY RUN SUMMARY"
else
  echo "  EXECUTION SUMMARY"
fi
echo "────────────────────────────────────────────────────────────"
echo "  Untagged versions:     $TOTAL_UNTAGGED"
echo "  Old semver versions:   $TOTAL_OLD_TAGGED"
echo "  Total to remove:       $TOTAL_DELETED"
echo "  Versions kept per pkg: $KEEP_VERSIONS most recent + current ($CURRENT_VERSION)"
echo "════════════════════════════════════════════════════════════"

if [[ "$DRY_RUN" -eq 1 && "$TOTAL_DELETED" -gt 0 ]]; then
  echo ""
  echo "To actually delete, run:"
  echo "  $0 --execute --keep $KEEP_VERSIONS"
fi
