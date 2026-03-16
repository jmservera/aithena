# Retrospective: Process Gaps — v1.0.1 through v1.2.0

**Date:** 2026-03-17  
**Facilitator:** Ripley (Lead)  
**Requested by:** Juanma (Product Owner)  
**Scope:** Post-v1.0.0 process health assessment  
**Status:** Action items pending team acknowledgment

---

## 1. What Happened? (Facts Only)

### a) Releases That Never Shipped

| Milestone | Issues | Closed | GitHub Release | Git Tag | VERSION bump | dev→main merge |
|-----------|--------|--------|----------------|---------|-------------|----------------|
| v1.0.1    | 8      | 8/8    | ❌ None        | ❌ None | ❌ No       | ❌ No          |
| v1.1.0    | 7      | 7/7    | ❌ None        | ❌ No   | ❌ No       | ❌ No          |
| v1.2.0    | 14     | 14/14  | ❌ None        | ❌ No   | ❌ No       | ❌ No          |

- **29 issues completed across 3 milestones. Zero releases shipped.**
- Last actual release: **v1.0.0**. Last tag: `v1.0.0`.
- `VERSION` file still reads `1.0.0`.
- `dev` branch is **35 commits ahead** of the `v1.0.0` tag.
- `main` branch has not received a merge from `dev` since v1.0.0.
- All three milestones remain "open" on GitHub despite being fully completed.

### b) Design Review Ceremony: Never Executed

- `ceremonies.md` defines a **Design Review** ceremony: auto-triggered before multi-agent tasks involving 2+ agents modifying shared systems.
- **It was never run. Not once.**
- Consequences observed:
  - **Workspace corruption** from parallel agents modifying the same files (circuit breaker PR #340 + correlation IDs PR #341 both touched `solr-search/main.py`, `requirements`, shared config)
  - **Admin auth + structured logging conflict** — two agents modifying the same service's startup code without interface agreement
  - My own history.md records the lesson: _"Token transport matters as much as token format — once nginx-gated browser tools enter scope, a pure localStorage + header plan is incomplete"_ — this was discovered during implementation, not during design

### c) Documentation Stopped After v1.0.0

**What we generated (v0.x era):**
- Release notes: `v0.10.0`, `v0.11.0`, `v0.12.0`, `v1.0.0` ✅
- Test reports: `v0.4.0` through `v1.0.0` (8 reports) ✅
- Feature guides, user manual, admin manual ✅

**What we generated (post v1.0.0):**
- Release notes for v1.0.1: ❌ None
- Release notes for v1.1.0: ❌ None
- Release notes for v1.2.0: ❌ None
- Test reports for v1.0.1: ❌ None
- Test reports for v1.1.0: ❌ None
- Test reports for v1.2.0: ❌ None
- CHANGELOG file: ❌ Never existed
- README still says "Current Release: v1.0.0"

**Irony:** We have a recorded decision called **"Documentation-First Release Process"** (authored by Newt) that explicitly requires feature guides, test reports, and README updates _before_ release approval. It was written and approved. Then immediately ignored for the next three milestones.

### d) No Integration Test Strategy

- E2E tests exist (`e2e/search.spec.ts`, `e2e/upload.spec.ts`) using Playwright with synthetic PDFs from `e2e/create-sample-docs.py`.
- Issue #343 (backend integration tests for the document pipeline: lister → RabbitMQ → indexer → Solr) sits untouched in v1.3.0.
- No real test corpus exists. No test document strategy is defined.
- The backend pipeline is tested only at the unit level (each service in isolation). The full pipeline path has zero automated validation.

### e) Additional Gaps Identified

1. **Milestones never closed on GitHub.** All completed milestones (v1.0.1, v1.1.0, v1.2.0) remain "open." This makes project tracking unreliable — you can't tell what's done vs. in-progress by looking at GitHub.

2. **No version bump process.** `VERSION` has said `1.0.0` for 35 commits. No one owns bumping it. No automation triggers it.

3. **Security discipline was one-and-done.** v1.0.1 was a security-gated release (ecdsa baseline exception, CodeQL triage, secrets-outside-env fixes). Then we immediately stopped doing security gates for v1.1.0 and v1.2.0, even though we'd established the pattern.

4. **dev→main promotion doesn't happen.** We defined "main is production-only, merges from dev at release boundaries." But no release boundary has occurred since v1.0.0, so `main` is frozen at a 35-commit-old state.

5. **Label/assignee hygiene degrades over time.** My own history records a Ralph diagnostic session where 9 issues had incorrect Copilot assignees, 6 had multiple `squad:*` owners, and 6 carried contradictory `go:*` labels. We fixed it reactively, not preventively.

6. **Merged branches never deleted.** 38 branches from merged PRs remain on the remote. Plus ~28 abandoned/stale branches — **66 total stale remote branches**. No branch cleanup happens after merge. GitHub's "auto-delete head branches" setting is not enabled. This clutters the branch namespace, confuses `git branch -r` output, and makes it harder to identify active work.

---

## 2. Root Cause Analysis

### Primary Root Cause: No "Release Owner" Role

The fundamental problem is structural: **nobody owns the release process.** We have:
- A Lead (Ripley) who plans milestones and reviews PRs
- A Coordinator (Ralph) who routes work to agents
- Agents (Parker, Dallas, Kane, etc.) who implement issues
- A Product Manager (Newt) who writes release criteria

But **nobody's job is to say: "All issues are closed. Now do the release."** The Coordinator sees "milestone complete" and moves to the next milestone. The Lead sees "PRs approved" and starts planning the next scope. Newt wrote the documentation-first process but has no enforcement mechanism.

The result: we have a highly efficient **issue-closing machine** with no **release-shipping discipline.**

### Contributing Cause 1: Ceremony Triggers Are Passive

The Design Review ceremony is defined as `Trigger: auto` with `Condition: multi-agent task involving 2+ agents modifying shared systems.` But "auto" means nothing — there is no automation that detects this condition and invokes the ceremony. It relies on whoever is assigning work to notice the overlap and call for a design review. Nobody does, because the work assignment process is:
1. Issue gets created with a label
2. Coordinator routes it to an agent
3. Agent starts coding

There is no step 2.5 where someone checks: "Wait, is another agent also modifying `solr-search/main.py` right now?"

### Contributing Cause 2: Milestone Completion ≠ Release Readiness

We conflate "all issues closed" with "ready to ship." They are different things. A completed milestone still needs:
- VERSION bump
- Release notes and test report
- dev→main merge
- Git tag
- GitHub Release
- Milestone closure on GitHub
- README update

None of these are tracked as issues in the milestone. They're invisible post-completion work that falls through the cracks every single time.

### Contributing Cause 3: Documentation Is Treated As Optional Post-Work

Despite the "Documentation-First Release Process" decision, docs are never gated. No PR check enforces it. No issue template includes it. Newt's decision says "does NOT approve release until all artifacts are committed" — but there's no actual approval step in the workflow. Work completes, the milestone empties, and everyone moves on.

### Contributing Cause 4: No Integration Test Investment

Unit tests are mandatory (TDD is in the charter). E2E tests exist as a separate concern. But the middle layer — integration tests that validate service-to-service contracts — was planned (#343) but never prioritized. Each milestone adds complexity to the pipeline, but the test investment stays at the edges.

### Contributing Cause 5: No Branch Lifecycle Management

GitHub's "Automatically delete head branches" setting was never enabled. No post-merge cleanup step exists in the workflow. When Ralph merges a PR, the branch stays. When @copilot creates a PR that gets merged or closed, the branch stays. After 50+ merged PRs, this accumulates into 66 stale branches that clutter the remote, make `git fetch` slower, and obscure which branches represent active work.

---

## 3. What Should Change?

### Change 1: Create Explicit "Release" Issues in Every Milestone

Every milestone gets a final issue: **"Release vX.Y.Z"** — assigned to the Lead (or a designated Release Owner), blocked by all other milestone issues. This issue's checklist:
- [ ] All milestone issues closed
- [ ] VERSION file bumped
- [ ] CHANGELOG.md updated
- [ ] Release notes written (`docs/release-notes-vX.Y.Z.md`)
- [ ] Test report written (`docs/test-report-vX.Y.Z.md`)
- [ ] README.md updated (current release version, feature list)
- [ ] dev merged to main
- [ ] Git tag created
- [ ] GitHub Release published
- [ ] Milestone closed on GitHub

This makes the release work **visible and trackable**, not invisible post-completion ceremony.

### Change 2: Make Design Review a Blocking Gate

When the Coordinator assigns 2+ issues that touch the same service, a Design Review issue is auto-created and linked as a blocker to the implementation issues. The implementation issues cannot be assigned until the Design Review is resolved. The Lead facilitates, participants are the agents whose work overlaps.

Concrete trigger: if two issues in the same milestone have overlapping file paths in their descriptions or acceptance criteria (e.g., both mention `solr-search`), the Design Review gate activates.

### Change 3: Enforce Documentation Gate in Release Issue

The Release issue (Change 1) cannot be closed until Newt confirms documentation artifacts exist. This is the enforcement mechanism that the Documentation-First decision was missing. Newt gets tagged as a reviewer on the Release PR.

### Change 4: Create a CHANGELOG.md

Start a CHANGELOG following Keep a Changelog format. Every PR description should note what changed under Added/Changed/Fixed/Removed. The release issue owner compiles these into the CHANGELOG entry. Retroactively create entries for v1.0.1, v1.1.0, and v1.2.0 from the merged PRs.

### Change 5: Automate What Can Be Automated

- **VERSION bump:** A PR that updates the VERSION file is part of the Release issue. Consider a GitHub Action that validates VERSION matches the milestone tag.
- **Milestone closure:** After GitHub Release is published, auto-close the milestone.
- **Stale milestone detection:** Weekly check: "Are there milestones where all issues are closed but the milestone is still open?" Alert the Lead.

### Change 6: Prioritize Integration Tests

Issue #343 should move from v1.3.0 backlog to the immediate next milestone. The pipeline (lister → RabbitMQ → indexer → Solr) is the most critical untested path. Every feature we add increases the blast radius of an undetected pipeline failure.

---

## 4. Action Items

| # | Action | Owner | Measurable Outcome | Priority |
|---|--------|-------|--------------------|----------|
| 1 | **Retroactive release: Ship v1.0.1, v1.1.0, v1.2.0** — Write release notes, test reports, bump VERSION to 1.2.0, merge dev→main, create tags + GitHub Releases, close milestones | Ripley + Newt | 3 GitHub Releases exist, milestones closed, VERSION=1.2.0 | **P0 — Do first** |
| 2 | **Create CHANGELOG.md** retroactively covering v1.0.1–v1.2.0 | Newt | CHANGELOG.md exists in repo root with entries for all 3 releases | P1 |
| 3 | **Add "Release vX.Y.Z" issue template** with the full checklist from Change 1 | Ripley | `.github/ISSUE_TEMPLATE/release.md` exists and is used for v1.3.0 | P1 |
| 4 | **Add release issue to v1.3.0 milestone now** | Ripley | Issue created, assigned, linked as final blocker | P1 |
| 5 | **Implement Design Review blocking gate** — Update Coordinator routing to detect multi-agent file overlap and create Design Review issue | Ripley + Ralph | Next multi-agent milestone has a Design Review issue auto-created | P1 |
| 6 | **Promote #343 (integration tests) to immediate priority** | Ripley | Issue moved to current sprint, assigned, started | P2 |
| 7 | **Weekly milestone hygiene check** — Coordinator scans for fully-completed-but-open milestones | Ralph | Script or cron check runs weekly, alerts on stale milestones | P2 |
| 8 | **Update README.md** to reflect actual shipped state after retroactive releases | Newt | README shows current version, features match reality | P0 (part of item 1) |
| 9 | **Clean up 66 stale remote branches** — delete all merged branches, enable GitHub auto-delete head branches setting | Brett | 0 stale branches, auto-delete enabled in repo settings | P1 |
| 10 | **Add branch cleanup to merge checklist** — after every PR merge, delete the head branch (or confirm auto-delete is on) | Ralph | Every merged PR's branch is deleted within minutes of merge | P1 |

---

## 5. Systemic Takeaway

We built a team that is excellent at **executing issues** and terrible at **finishing releases.** The agents close issues, the Lead plans milestones, the Coordinator routes work — and nobody shepherds the output into an actual shipment. 

This is the classic "last mile" problem. The fix isn't motivational — it's structural. **Make the release work visible as tracked issues inside the milestone, not invisible post-work that "someone" does.** Until the release checklist is an issue with an owner and a due date, it will keep falling through the cracks.

The Design Review gap is the same pattern at a different scale: the ceremony exists on paper but has no enforcement mechanism. Passive triggers produce zero compliance. Active blockers produce 100% compliance.

**The team doesn't need to work harder. The team needs the release and design gates to be first-class tracked work, not afterthoughts.**

---

*Retrospective facilitated by Ripley (Lead), 2026-03-17. Findings to be reviewed by full squad.*
