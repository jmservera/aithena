# Decision: v1.10.0 Retrospective Process Changes

**Author:** Ripley (Project Lead)  
**Date:** 2026-03-20  
**Status:** APPROVED  
**Trigger:** v1.10.0 Wave 0/1 retrospective — PR #700 PO rejection, PR #701 near-miss, cross-branch contamination

## Decisions

### 1. Branch Hygiene: Always branch from origin/dev

**Rule:** All agents must create feature branches using:
```bash
git fetch origin
git checkout -b squad/<issue>-<slug> origin/dev
```

Never branch from local `dev` or an existing local working tree. Before creating a branch, verify `git status` shows a clean working tree. If unclean, stash or discard before branching.

**Reason:** Multiple cross-branch contamination incidents in Wave 0 — Parker's auth changes leaked into Ash's branches, Scribe's commits landed on wrong branches, Brett's backup scripts appeared on Ash's folder facet PR. All caused by branching from a polluted local state.

### 2. Bug Fixes Require Reproduction Evidence

**Rule:** Before opening a PR for any bug fix, the assigned agent must post a comment on the issue with:
1. **Reproduction steps** — how to trigger the bug
2. **Error evidence** — actual log output, stack trace, or observable behavior
3. **Root cause analysis** — why the bug occurs (not just what symptom it causes)

No PR should be opened for a bug fix without this evidence.

**Reason:** PR #700 was rejected because it treated the symptom (502 error) instead of diagnosing the root cause (kNN field name mismatch + URI too large). The real fix was only found when actual Solr error logs were read. PO directive: "reproduce the bug, read the logs, analyze what's happening."

### 3. No Silent Degradation of User-Visible Behavior

**Rule:** Error handlers must NOT silently change search mode (e.g., semantic → keyword), drop results, or reduce functionality without:
- Logging a WARNING-level message
- Returning a clear indication to the user/API consumer that degradation occurred
- Explicit approval from Ripley (Lead) or Juanma (PO) in a squad decision

**Reason:** PR #700 proposed silently degrading semantic search to keyword search on kNN failure. This would have hidden two real bugs and permanently degraded search quality for users without them knowing. Error handling should make problems visible, not invisible.

### 4. Pre-PR Self-Review Checklist

**Rule:** Before opening a PR, the implementing agent must verify:
- [ ] `git diff --stat origin/dev` shows ONLY files related to this issue
- [ ] Security implications reviewed (auth flows, input validation, permissions)
- [ ] Data model impact assessed (parent/chunk docs, cross-service data flows)
- [ ] Error handling doesn't silently change user-visible behavior
- [ ] Tests cover the specific bug/feature, not just happy path

**Reason:** 4-5 Copilot review rounds per PR in Wave 0 indicates quality issues at submission time. Security (backup script permissions), auth flows (cookie handling), and data model (chunk vs parent docs) were all caught by reviewers, not by the implementing agent.

### 5. Data Model Documentation Required

**Rule:** Critical data model relationships must be documented in service READMEs or `docs/architecture/`. The first required document is the Solr parent/chunk document relationship:
- Parent documents: book metadata (title, author, path, etc.)
- Chunk documents: text chunks with `embedding_v` vectors, linked via `parent_id_s`
- kNN queries MUST target chunks (embeddings live there)
- Results are de-duplicated by `parent_id_s` after retrieval

**Reason:** PR #701 nearly broke semantic search because the implementing agent didn't understand that embeddings live on chunk documents, not parent documents. This knowledge was implicit in the document-indexer code and not documented anywhere.

## Impact

- **All agents:** Must follow branch hygiene and pre-PR checklist immediately
- **Ash:** Owns data model documentation (R2 action item)
- **Lambert:** Must create semantic search integration test on chunks (R5 action item)
- **Ripley:** Will enforce reproduction evidence requirement on Wave 2 bug fixes
- **Brett:** Will document merge chain workflow (R7 action item)
