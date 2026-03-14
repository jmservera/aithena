### 2026-03-14T15:31: User directive — branching strategy + release gating
**By:** jmservera / Juanma (via Copilot)
**What:**
1. Create a `dev` branch for all active work
2. The current default branch (`jmservera/solrstreamlitui` or whatever it becomes) is the "production-ready" branch
3. At the end of each phase, when the solution works, merge dev → default and create a semver tag
4. ONLY Ripley (Lead) or Juanma (Product Owner) can merge to the default branch and create release tags. Nobody else.
5. Think about CI/CD workflows needed for this (tag-triggered builds, release notes, etc.)
**Why:** User request — production readiness, always have a working version available via semver tags
