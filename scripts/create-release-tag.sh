#!/bin/sh
# create-release-tag.sh — Safe tag creation for Aithena releases.
#
# Prevents stale-tag issues by enforcing:
#   1. Must be on the main branch
#   2. HEAD must match origin/main exactly (no stale local state)
#   3. Tag must not already exist locally or on the remote
#   4. VERSION file must contain valid stable semver (X.Y.Z)
set -eu

# ── Read and validate VERSION ────────────────────────────────────────
VERSION_FILE="VERSION"
if [ ! -f "$VERSION_FILE" ]; then
  echo "ERROR: VERSION file not found at repo root" >&2
  exit 1
fi

VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")

# Strict stable-semver check (no pre-release or build metadata)
case "$VERSION" in
  [0-9]*.[0-9]*.[0-9]*)
    # Further validate each component is purely numeric
    MAJOR=$(echo "$VERSION" | cut -d. -f1)
    MINOR=$(echo "$VERSION" | cut -d. -f2)
    PATCH=$(echo "$VERSION" | cut -d. -f3)
    case "$MAJOR$MINOR$PATCH" in
      *[!0-9]*) echo "ERROR: VERSION '$VERSION' is not valid semver (X.Y.Z)" >&2; exit 1 ;;
    esac
    ;;
  *)
    echo "ERROR: VERSION '$VERSION' is not valid semver (X.Y.Z)" >&2
    exit 1
    ;;
esac

TAG="v$VERSION"
echo "Preparing to create tag $TAG from VERSION file..."

# ── Ensure we are on main and fully up-to-date ───────────────────────
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "Switching to main branch..."
  git checkout main
fi

echo "Fetching latest from origin..."
git fetch origin main

echo "Fast-forwarding local main to origin/main..."
git merge --ff-only origin/main

# ── Verify HEAD matches origin/main exactly ──────────────────────────
EXPECTED_SHA=$(git rev-parse origin/main)
ACTUAL_SHA=$(git rev-parse HEAD)

if [ "$EXPECTED_SHA" != "$ACTUAL_SHA" ]; then
  echo "ERROR: HEAD ($ACTUAL_SHA) does not match origin/main ($EXPECTED_SHA)" >&2
  echo "       Your local main has diverged. Resolve before tagging." >&2
  exit 1
fi

# ── Verify tag does not already exist ────────────────────────────────
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "ERROR: Tag $TAG already exists locally" >&2
  exit 1
fi

if git ls-remote --tags origin "$TAG" | grep -q "$TAG"; then
  echo "ERROR: Tag $TAG already exists on origin" >&2
  exit 1
fi

# ── Create and push annotated tag ────────────────────────────────────
echo "Creating annotated tag $TAG on commit $ACTUAL_SHA"
git tag -a "$TAG" -m "Release $TAG"
git push origin "$TAG"

echo "✅ Tag $TAG pushed to origin successfully"
