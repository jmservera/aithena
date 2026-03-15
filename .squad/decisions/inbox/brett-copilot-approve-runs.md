### 2026-03-15: Auto-approve workflow runs on @copilot PRs
**By:** Brett (Infrastructure Architect)
**What:** Created copilot-approve-runs.yml using pull_request_target trigger
**Why:** Manual approval of bot workflow runs blocks the review cycle. Instructions don't work — automation is needed.
**Security:** pull_request_target runs trusted base-branch code. No PR checkout — API-only. Only approves runs from verified @copilot PRs.
**Alternative rejected:** Adding to copilot-pr-ready.yml — wrong timing (triggers on review_requested, not on push).
**Alternative rejected:** Instructions in charter/AGENTS.md — team forgets.
