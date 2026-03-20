### 2026-03-20T06:23: User directive
**By:** Juanma (via Copilot)
**What:** Releases must merge dev → main before tagging. Don't upgrade VERSION on dev until the release is cut to main. The full process: finish work on dev → create PR dev → main → merge → tag on main → create GitHub release.
**Why:** User request — captured for team memory. Production releases must flow through main.
