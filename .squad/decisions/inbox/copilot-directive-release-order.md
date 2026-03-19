### 2026-03-19T21:35: User directive — release order enforcement
**By:** Juanma (via Copilot)
**What:** Milestones MUST be released in sequential order: v1.8.0 → v1.8.1 → v1.8.2 → v1.9.0 → v1.10.0. Do not skip ahead. Finish current in-flight work, but then prioritize releasing in the correct order. v1.8.0 has not been released yet — that's the blocker.
**Why:** User request — the team was working on v1.9.0 PRs while v1.8.0 still has 2 open issues (#515 release docs, #514 WCAG). This violates the project's sequential release policy.
