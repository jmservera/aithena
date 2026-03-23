### 2026-03-22T22:48Z: User directive
**By:** Juanma (via Copilot)
**What:** Always purge Docker images and build cache before running a full build (`docker system prune -af && docker builder prune -af`) to avoid filling up the disk.
**Why:** User request — 123GB disk hit 99% during full stack build. Even with larger disk, proactive cleanup prevents build failures.
