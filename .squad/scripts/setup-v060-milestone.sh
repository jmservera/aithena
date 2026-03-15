#!/usr/bin/env bash
# v0.6.0 Milestone & Issue Setup Script
# Run after authenticating: gh auth login
# Usage: bash .squad/scripts/setup-v060-milestone.sh

set -euo pipefail

REPO="jmservera/aithena"
MILESTONE="v0.6.0"

echo "🏗️ Setting up v0.6.0 milestone and issues for $REPO"
echo ""

# Check gh auth
if ! gh auth status &>/dev/null; then
  echo "❌ gh CLI not authenticated. Run: gh auth login"
  exit 1
fi

# --- Create milestone ---
echo "📌 Creating milestone: $MILESTONE"
gh api repos/$REPO/milestones -f title="$MILESTONE" -f description="Production Hardening & Security" -f state="open" 2>/dev/null || echo "  (milestone may already exist)"

# Get milestone number
MS_NUM=$(gh api repos/$REPO/milestones --jq ".[] | select(.title==\"$MILESTONE\") | .number")
echo "  Milestone number: $MS_NUM"

# --- Create labels ---
echo ""
echo "🏷️ Creating labels..."
for label in "release:v0.6.0" "squad:copilot" "squad:parker" "squad:dallas" "squad:brett" "squad:kane"; do
  gh label create "$label" --repo "$REPO" 2>/dev/null && echo "  Created: $label" || echo "  Exists: $label"
done

# --- Create new issues for v0.5.0 follow-ups (Group 5) ---
echo ""
echo "📝 Creating v0.5.0 follow-up issues..."

ISSUE_178=$(gh issue create --repo "$REPO" \
  --title "Fix admin iframe sandbox: remove allow-popups" \
  --body "## Context
Per Newt's v0.5.0 release review, the AdminPage.tsx iframe has \`allow-popups\` in its sandbox attribute which is unnecessary and a security concern.

## Task
Remove \`allow-popups\` from the \`sandbox\` attribute in \`aithena-ui/src/pages/AdminPage.tsx\`.

**Expected:** \`sandbox=\"allow-same-origin allow-scripts allow-forms\"\`

## Acceptance Criteria
- [ ] \`allow-popups\` removed from sandbox attribute
- [ ] Admin page still loads correctly
- [ ] Vitest test verifies sandbox attribute" \
  --milestone "$MILESTONE" \
  --label "release:v0.6.0,squad:copilot,bug" \
  2>/dev/null | tail -1)
echo "  Created: $ISSUE_178 (sandbox fix)"

ISSUE_179=$(gh issue create --repo "$REPO" \
  --title "Add LRU cache eviction to useSimilarBooks" \
  --body "## Context
Per Newt's v0.5.0 release review, the \`useSimilarBooks\` hook uses a module-level cache (\`Map\`) that grows unboundedly. Long-lived sessions could accumulate excessive memory.

## Task
Add LRU eviction to the similar books cache in \`aithena-ui/src/hooks/useSimilarBooks.ts\`.

## Acceptance Criteria
- [ ] Cache limited to 100 entries (configurable constant)
- [ ] Least-recently-used entries evicted when limit reached
- [ ] Existing cache behavior preserved (hit returns cached data)
- [ ] Vitest test verifies eviction behavior" \
  --milestone "$MILESTONE" \
  --label "release:v0.6.0,squad:copilot,enhancement" \
  2>/dev/null | tail -1)
echo "  Created: $ISSUE_179 (LRU cache)"

ISSUE_180=$(gh issue create --repo "$REPO" \
  --title "Add 'Facets unavailable in semantic mode' UI hint" \
  --body "## Context
Per Newt's v0.5.0 release review, semantic search returns empty facet arrays but the UI shows nothing. Users may think facets are broken.

## Task
Show a message in the FacetPanel when \`mode=semantic\`: \"Facets are only available in keyword mode\"

## Acceptance Criteria
- [ ] FacetPanel shows informational message when search mode is \`semantic\`
- [ ] Message disappears when switching to \`keyword\` or \`hybrid\` mode
- [ ] Vitest test verifies message appears/disappears based on mode
- [ ] Accessible (proper ARIA attributes)" \
  --milestone "$MILESTONE" \
  --label "release:v0.6.0,squad:copilot,enhancement" \
  2>/dev/null | tail -1)
echo "  Created: $ISSUE_180 (facet hint)"

ISSUE_181=$(gh issue create --repo "$REPO" \
  --title "Add backend test for invalid search mode parameter" \
  --body "## Context
Per Newt's v0.5.0 release review, there's no backend test for \`GET /v1/search?mode=invalid\`. The API should return 400 Bad Request for invalid mode values.

## Task
Add test in \`solr-search/tests/\` that validates invalid search mode handling.

## Acceptance Criteria
- [ ] Test verifies \`GET /v1/search?q=test&mode=invalid\` returns 400
- [ ] Test verifies \`GET /v1/search?q=test&mode=keyword\` returns 200 (control)
- [ ] Error response includes descriptive message
- [ ] If the endpoint doesn't currently validate mode, add validation" \
  --milestone "$MILESTONE" \
  --label "release:v0.6.0,squad:copilot,bug" \
  2>/dev/null | tail -1)
echo "  Created: $ISSUE_181 (invalid mode test)"

# --- Assign existing issues to milestone + labels ---
echo ""
echo "🎯 Assigning existing issues to milestone and labels..."

# Group 1: Security Foundation (squad:copilot only — 🟢 good fit)
for issue in 88 89 90; do
  gh issue edit "$issue" --repo "$REPO" --milestone "$MILESTONE" --add-label "release:v0.6.0,squad:copilot"
  echo "  #$issue → milestone + squad:copilot"
done

# Group 2: Security Validation (squad:copilot + squad:kane review)
for issue in 97 98; do
  gh issue edit "$issue" --repo "$REPO" --milestone "$MILESTONE" --add-label "release:v0.6.0,squad:copilot,squad:kane"
  echo "  #$issue → milestone + squad:copilot + squad:kane"
done

# Group 3: Upload endpoint (squad:copilot + squad:parker review)
gh issue edit 49 --repo "$REPO" --milestone "$MILESTONE" --add-label "release:v0.6.0,squad:copilot,squad:parker"
echo "  #49 → milestone + squad:copilot + squad:parker"

# Group 4: Upload UI (squad:copilot + squad:dallas review — after #49)
gh issue edit 50 --repo "$REPO" --milestone "$MILESTONE" --add-label "release:v0.6.0,squad:copilot,squad:dallas"
echo "  #50 → milestone + squad:copilot + squad:dallas"

# Group 6: Hardening (squad:copilot + squad:brett review)
gh issue edit 52 --repo "$REPO" --milestone "$MILESTONE" --add-label "release:v0.6.0,squad:copilot,squad:brett"
echo "  #52 → milestone + squad:copilot + squad:brett"

echo ""
echo "✅ v0.6.0 setup complete!"
echo ""
echo "📋 Summary:"
echo "  - Milestone: $MILESTONE (ID: $MS_NUM)"
echo "  - New issues: 4 created (follow-ups from v0.5.0)"
echo "  - Existing issues: 8 assigned to milestone"
echo "  - Total v0.6.0 scope: 12 issues"
echo ""
echo "🚀 Next steps:"
echo "  1. Group 1 (SEC-1/2/3) + Group 5 (follow-ups) → copilot picks up immediately"
echo "  2. Groups 2/3/4/6 → copilot implements, squad member reviews PR"
echo "  3. Ralph monitors: 'Ralph, go'"
