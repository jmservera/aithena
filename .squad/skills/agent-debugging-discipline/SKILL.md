---
name: "agent-debugging-discipline"
description: "Scientific debugging method for AI agents — reproduction before fix, root cause before PR"
domain: "debugging, quality"
confidence: "high"
source: "earned from PR #700 rejection (silent degradation), PO 'scientific method' directive, v1.10.0 retrospective"
author: "Ripley"
created: "2026-03-20"
last_validated: "2026-03-20"
---

## Context

AI agents under time pressure default to "fix the symptom" — making errors disappear rather than understanding them. This is the single most dangerous behavior pattern in multi-agent development. It produces code that masks bugs, silently degrades features, and creates invisible technical debt.

**This skill applies to all bug fixes and error-handling code changes.**

---

## Patterns

### 1. Reproduce Before Fixing

Every bug fix PR must include evidence of reproduction:
- **Exact error message** — copy-paste from logs, not paraphrased
- **Reproduction steps** — commands or API calls that trigger the bug
- **Environment state** — relevant config, data, or service state

Without reproduction evidence, the PR should not be opened.

### 2. Read the Logs First

Before writing any code, read the actual error output:
- **Solr logs** for search issues (query errors, schema mismatches)
- **Service stderr** for Python errors (stack traces, import errors)
- **Browser console** for frontend issues (network errors, state issues)

The fix is almost always in the error message. PR #700's two bugs (kNN field name mismatch + URI too large) were both visible in Solr logs but were never read — the agent jumped straight to code changes.

### 3. Root Cause, Then Fix

Follow this sequence:
1. **Observe** — What is the exact error?
2. **Hypothesize** — What could cause this error?
3. **Test** — Validate hypothesis (check config, query Solr, read code)
4. **Fix** — Change only what's broken
5. **Verify** — Confirm the fix resolves the root cause, not just the symptom

### 4. No Silent Degradation

**RULE:** Error handlers MUST NOT silently change behavior.
- ❌ Catch semantic search error → fall back to keyword search silently
- ❌ Catch batch error → return partial results without warning
- ✅ Catch error → log WARNING with details → return clear error response
- ✅ If degradation is genuinely needed → require Lead/PO approval first

### 5. Domain Knowledge Check

Before fixing any search-related bug:
- Confirm you understand the parent/chunk document hierarchy
- Confirm kNN queries target chunks (where embeddings live), not parents
- Confirm Solr field names match between schema and query code
- If unsure, ASK — don't guess

---

## Examples

**Bad (PR #700 pattern):**
```python
# Silent degradation — NEVER DO THIS
try:
    results = semantic_search(query)
except Exception:
    results = keyword_search(query)  # Masks the real bug!
```

**Good:**
```python
try:
    results = semantic_search(query)
except SolrError as e:
    logger.warning("Semantic search failed: %s", e)
    raise HTTPException(status_code=502, detail="Semantic search unavailable")
```

**Bug fix PR checklist:**
```markdown
## Reproduction Evidence
- Error: `kNN field 'embedding' not found in schema`
- Triggered by: `GET /api/v1/search?q=test&mode=semantic`
- Root cause: Schema uses `embeddings_vector`, code uses `embedding`
- Fix: Update field name in search query builder
- Verification: Same query now returns results
```

---

## Anti-Patterns

- **Jumping to code before reading logs.** The most common agent failure. Always read the error first.
- **"It works now" as the only verification.** Confirm the fix addresses the root cause, not just the symptom.
- **Catch-all exception handlers.** Broad `except Exception` hides real errors. Catch specific exceptions.
- **Fixing in the wrong layer.** A query error is not a UI problem. A schema mismatch is not a network problem. Fix where the bug actually is.
- **Guessing at domain model.** If you don't know whether embeddings are on chunks or parents, STOP and check documentation before proceeding.
