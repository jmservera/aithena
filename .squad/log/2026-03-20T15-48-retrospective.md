# v1.10.0 Mid-Milestone Retrospective

**Date:** 2026-03-20  
**Facilitator:** Ripley (Project Lead)  
**Scope:** Wave 0 (bug fixes) + Wave 1 (foundations)  
**Trigger:** PR #700 PO rejection, PR #701 critical review catch, cross-branch contamination, PO intervention on debugging methodology

---

## 1. What Happened (Facts)

### Wave 0: Bug Fixes — 7 bugs, 5 PRs merged, 1 PR rejected

| PR | Issue | What happened | Outcome |
|-----|-------|--------------|---------|
| #700 | #646 | Parker proposed degrading semantic search to keyword on kNN failure. PO rejected: "fix the root cause, don't mask it." | **CLOSED without merge** |
| #701 | #648 | Ash's initial approach filtered out chunk documents from kNN queries. Copilot reviewer caught that this would break semantic search entirely (embeddings live on chunks, not parents). Reworked to use `EXCLUDE_CHUNK_FQ` filter only on the final result set. | MERGED after rework |
| #702 | #647, #561 | Parker fixed auth cookie persistence + admin login loop. Copilot reviewer found multiple auth flow issues in first pass. | MERGED after review fixes |
| #703 | #667 | Book card overlap + PDF viewer URL normalization. Straightforward fix. | MERGED |
| #705 | #646 | **Real root cause #1:** kNN field name mismatch — code queried `book_embedding` but Solr schema uses `embedding_v`. Found by reading actual Solr error logs after PO intervention. | MERGED |
| #706 | #704 | **Real root cause #2:** Solr GET requests with embedding vectors exceeded 8192-byte URI limit. Switched to POST. Found from error log: `o.e.j.h.HttpParser URI is too large >8192`. | MERGED |

### Wave 1: Foundations — 10 issues, 10 PRs merged

| PR | Issue | Description | Notes |
|-----|-------|-------------|-------|
| #707 | #677 | series_s field in Solr schema | Clean |
| #708 | #650 | folder_path_s search facet | Clean |
| #709 | #681 | Single document metadata edit API | Clean |
| #710 | #657 | Tier 1 critical backup script | Copilot caught security issues: umask, flock, key permissions, pinentry-mode |
| #711 | #655 | Collections backend CRUD API | SQL injection false positive flagged by Copilot (parameterized queries are safe) |
| #713 | #692 | Lint consolidation (merge lint-frontend into ci.yml) | Clean |
| #714 | #670 | Collections Docker volume + mount | Clean |
| #715 | #690 | Bandit security scan required | Clean |
| #716 | #689 | Dependabot refactor | **CLOSED** — approach didn't work, superseded by #717 |
| #717 | #699 | Squad workflow cleanup + composite actions | Clean |

### Cross-Branch Contamination Incidents

- Parker's auth cookie changes (PR #702 branch) leaked into Ash's duplicate books PR (#701 branch)
- Scribe's documentation commits landed on wrong branches
- Brett's backup script files appeared on Ash's folder facet branch
- **Root cause:** Multiple agents creating branches from a polluted local working tree instead of fresh checkouts from `origin/dev`

### Coverage Threshold Near-Miss

- `test_search_service.py` was at 87.82% vs 88% threshold
- Required adding sort clause tests to cross the line
- Indicates the threshold is set at the right level (tight enough to catch gaps, not so high it blocks real work)

### Key Metrics

| Metric | Value |
|--------|-------|
| Issues closed | 19 of 53 (36%) |
| PRs merged | 15 |
| PRs rejected/closed | 2 (#700, #716) |
| Copilot review rounds with fixes | 4-5 |
| Cross-branch contamination incidents | 3+ |
| PO interventions | 2 (PR #700 rejection, scientific debugging directive) |

---

## 2. Root Cause Analysis

### Problem A: Symptom-fixing instead of root-cause investigation (PR #700)

**What happened:** Parker's first response to a 502 error was to add a try/except that silently degrades semantic search to keyword search. This would have hidden the real bugs (field name mismatch + URI too large) and permanently broken semantic search quality for users.

**Root cause:** The agent jumped to "make the error go away" instead of asking "why is this error happening?" No reproduction step was attempted. No logs were read. No Solr query was manually tested.

**Contributing factors:**
- No explicit debugging checklist in the squad workflow
- Bug issues didn't require a "reproduction evidence" section before implementation
- The agent treated the symptom (HTTP 502) as the problem instead of a signal

### Problem B: Incomplete domain understanding (PR #701)

**What happened:** Ash's initial fix for duplicate books excluded chunk documents from kNN queries. This would have broken semantic search because embeddings are stored on chunk documents, not parent documents.

**Root cause:** The agent didn't understand the data model well enough. The document-indexer creates parent documents (book metadata) and child documents (text chunks with embeddings). kNN search MUST query chunks, then results are de-duplicated by parent_id.

**Contributing factors:**
- No data model documentation in the codebase (the parent/chunk relationship is implicit in document-indexer code)
- The agent didn't trace the full search pipeline before making changes
- No integration test covering "semantic search returns results from chunk embeddings"

### Problem C: Cross-branch contamination (multiple incidents)

**What happened:** Commits from one agent's work appeared on another agent's feature branch. Auth changes, backup scripts, and documentation commits all bled across branches.

**Root cause:** Agents created branches from the local working tree (which had uncommitted or staged changes from other agents' work) instead of creating branches from a clean `origin/dev` checkout.

**Contributing factors:**
- Shared local repository with no workspace isolation between agents
- No pre-branch validation step ("is my working tree clean?")
- No CI check that detects unrelated changes in a PR (e.g., "this PR modifies files outside its declared scope")

### Problem D: Review iteration overhead (4-5 rounds)

**What happened:** Multiple PRs required several rounds of Copilot review feedback before merging. While each round caught real issues, the volume suggests quality wasn't right on first submission.

**Root cause:** Agents submit code without running a self-review checklist. Security concerns (backup script permissions), auth flow completeness (cookie handling), and edge cases (SQL injection patterns) were all caught by external review rather than by the implementing agent.

---

## 3. What Should Change

### ✅ What worked well

1. **Copilot code review caught real bugs.** PR #701's semantic search breakage would have been a production disaster. The review process is working as a safety net.
2. **PO intervention was timely and direct.** Juanma's "scientific method" directive and PR #700 rejection saved weeks of hidden bugs.
3. **Wave-based execution is the right model.** Bug fixes first, then foundations — the sequencing prevented building on broken ground.
4. **Wave 1 execution was clean.** 10 PRs merged with only expected review feedback. The team learned from Wave 0.
5. **Coverage threshold caught a real gap.** The 88% threshold on test_search_service.py forced adding sort clause tests that improve actual coverage.

### ❌ What needs to change

1. **Bug fixes require reproduction evidence before implementation.** "I read the error message and wrote a fix" is not debugging. The fix for #646 was only found when someone read the actual Solr error logs.
2. **Agents must create branches from clean `origin/dev`, never from local working tree.** Cross-branch contamination wastes everyone's time and erodes trust in PRs.
3. **Domain model documentation must exist.** The parent/chunk document relationship is critical knowledge that lives only in code. New agents (or agents working in unfamiliar areas) need architectural docs.
4. **Self-review before PR submission.** Agents should run through a checklist (security, auth flows, edge cases, data model impact) before opening a PR.
5. **Error handling must not silently degrade functionality.** Try/except blocks that change user-visible behavior (semantic → keyword) must be explicitly approved by the PO or Lead.

---

## 4. Action Items

### Immediate (before Wave 2 starts)

| ID | Action | Owner | Acceptance Criteria |
|----|--------|-------|-------------------|
| **R1** | **Add branch hygiene rule to squad workflow:** All agents must run `git fetch origin && git checkout -b <branch> origin/dev` when creating new branches. Never branch from local `dev` or working tree. | Ripley | Rule documented in decisions.md; enforced in agent charters |
| **R2** | **Create data model documentation:** Document the parent document / chunk document relationship in `src/solr-search/README.md` or `docs/architecture/`. Must explain: parent docs hold metadata, chunks hold text + embeddings, kNN queries target chunks, results are grouped/de-duped by parent_id. | Ash | Document exists and is linked from solr-search README |
| **R3** | **Add "Reproduction Evidence" section to bug issue template:** Before any fix is implemented, the assigned agent must add a comment with: (1) how to reproduce, (2) what the error log says, (3) what the root cause is. No PR should be opened without this. | Ripley | Template updated; first Wave 2 bug fix follows this process |
| **R4** | **Add pre-PR self-review checklist:** Before opening a PR, agents must verify: (a) no unrelated files in diff, (b) security implications reviewed, (c) auth flow tested end-to-end if touched, (d) data model impact assessed, (e) error handling doesn't silently change behavior. | Ripley | Checklist documented in `.squad/templates/pr-checklist.md` |

### Before Wave 2 implementation

| ID | Action | Owner | Acceptance Criteria |
|----|--------|-------|-------------------|
| **R5** | **Add integration test for semantic search on chunk embeddings:** A test that verifies kNN search returns results when embeddings exist only on chunk documents. This is the gap that PR #701 nearly fell into. | Lambert | Test exists in solr-search test suite and passes |
| **R6** | **Establish "no silent degradation" rule:** Any error handler that changes the search mode (e.g., semantic → keyword) or drops results silently must be explicitly approved in a squad decision. Log a warning and return a clear error to the user instead. | Ripley | Rule in decisions.md; existing degradation code reviewed |

### Process improvements (ongoing)

| ID | Action | Owner | Acceptance Criteria |
|----|--------|-------|-------------------|
| **R7** | **Sequential merge chain documentation:** Document the rebase-after-merge workflow for Wave 1-style batch merges. Include the exact commands and expected "base branch was modified" handling. | Brett | Runbook in `.squad/templates/merge-chain.md` |
| **R8** | **Review the Parker bottleneck:** Parker is primary on 20+ v1.10.0 issues. For Wave 2, explicitly reassign 5+ issues to other agents (Ash for search-related, Brett for infra). Track agent load in kickoff. | Ripley | Wave 2 kickoff shows no agent with >10 open issues |

---

## 5. Retrospective Verdict

**Wave 0 was rough.** A rejected PR, a near-miss that would have broken semantic search, cross-branch contamination, and a PO intervention are all signs the team was moving too fast without enough rigor. The "scientific debugging" directive was necessary and correct.

**Wave 1 was significantly better.** 10 PRs merged with normal review feedback. The team internalized the Wave 0 lessons. The coverage threshold caught a real gap. Security review on the backup script was thorough.

**The trend is positive, but the process gaps are real.** Without the action items above, Wave 2 (UI components, secondary APIs) will hit the same problems at a higher complexity level. The data model documentation gap is especially dangerous as collections and metadata editing add new cross-service data flows.

**Grade: C+ for Wave 0, B+ for Wave 1.** Target: A- for Wave 2 by implementing R1-R6 before starting.

---

*Retrospective conducted by Ripley, Project Lead. Action items tracked in squad decisions.*
