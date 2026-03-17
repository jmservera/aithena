### 2026-03-17T18:00:00Z: Copilot PR Review Gate — Mandatory

**By:** Juanma (Product Owner)
**What:** Before merging ANY PR, the squad MUST review all comments from `copilot-pull-request-reviewer`. Apply suggestions that make sense. For suggestions that don't apply, resolve the thread with a comment explaining why. No PR may be merged with unreviewed Copilot comments.
**Why:** User directive — quality gate to catch issues before merge. Copilot automatic review is now active on all PRs.

#### Implementation Rules

1. **After every commit/push** to a PR branch, wait for `copilot-pull-request-reviewer` to post its review.
2. **Read all review comments** using `gh pr view <N> --json reviewThreads` or the GitHub MCP tools.
3. **For each comment:**
   - If the suggestion is valid → apply the fix, commit, push.
   - If the suggestion doesn't apply → resolve the thread with a brief comment explaining why (e.g., "False positive — this is intentional because X").
4. **All review threads must be resolved** before merging.
5. This applies to ALL PRs: squad agent PRs, Dependabot PRs, manual PRs.
6. The `--admin` flag to bypass reviews is NO LONGER acceptable for skipping this step.
