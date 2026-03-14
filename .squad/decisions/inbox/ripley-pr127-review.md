### Ripley — PR #127 Review (Stats Tab — CollectionStats)

**Author:** Ripley (Lead)
**Date:** 2026-03-14
**Status:** CHANGES REQUESTED

**Context:**
PR #127 from @copilot adds a Stats tab with `CollectionStats` component, `useStats()` hook, and `StatsPage` integration. It targets `dev` and claims to integrate with the PR #123 router architecture.

**Decision:**
Requested changes — **stale branch**. Same class of issue as PR #128 (Status tab). The branch forks from `19decee` (15+ commits behind dev), and ~80% of the diff duplicates infrastructure already merged via PR #123 and commit `2cbb26c`. The branch has merge conflicts in `solr-search/` files and cannot merge cleanly.

**Quality Assessment:**
The genuinely new stats code (CollectionStats.tsx, hooks/stats.tsx, stats CSS) is well-written — clean TypeScript, proper React patterns, cancellation in useEffect, responsive CSS grid. This work should be preserved after rebase.

**Action Required:**
Rebase on current `dev` (`origin/dev` @ `5ea18b3`), then the diff should only contain the 4 genuinely new/modified stats files.

**Pattern Noted:**
This is the second PR in a row (after #128) where @copilot's branch was stale due to forking before the router merge. Future copilot-assigned issues should be created AFTER prerequisite PRs are merged, or the issue description should explicitly state "rebase on dev before opening PR."
