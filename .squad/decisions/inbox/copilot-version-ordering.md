### 2026-03-16: Version ordering — release milestones sequentially
**By:** Juanma (via Copilot)
**What:** Milestones MUST be released in numeric order. v0.10.0 and v0.11.0 were shipped before v0.9.0, breaking semver ordering. Fix: v0.9.0 renamed to v0.12.0. Going forward, never skip or reorder version numbers. If a milestone is not ready, defer the release — don't ship a higher version first.
**Why:** Semver ordering matters for tooling and user expectations. Alphabetical sorting of version strings is misleading (0.10 < 0.9 alphabetically but 0.10 > 0.9 numerically).
