# Ripley: Clean Architecture Audit & Skill Creation

**Timestamp:** 2026-03-29T10:20:00Z  
**Status:** ✅ Complete  
**Violations Found:** 7 (2 high-severity, 3 medium, 2 low)

## Summary

Completed comprehensive Clean Architecture audit across full aithena codebase. Identified dependency violations, duplicated logic, and framework mixing. Violations range from critical (admin sys.path manipulation in production) to transitional (benchmark scripts). Created `.squad/skills/clean-architecture/SKILL.md` as team reference.

## Violations Summary

| # | Severity | Issue | File | Fix Priority |
|---|----------|-------|------|--------------|
| V1 | 🔴 High | Admin sys.path manipulation in production | `src/admin/src/pages/shared/config.py` | P1 |
| V2 | 🔴 High | Duplicated auth logic (admin vs solr-search) | `src/admin/src/auth.py`, `src/solr-search/auth.py` | P1 |
| V3 | 🟡 Medium | Duplicated logging config (4 services) | solr-search, document-lister, document-indexer, admin | P2 |
| V4 | 🟡 Medium | Framework mixed with domain (correlation.py) | `src/solr-search/correlation.py` | P2 |
| V5 | 🟡 Medium | Test imports use sys.path.append (30+ files) | `src/solr-search/tests/*.py` | P3 |
| V6 | 🟢 Low | Reset password script sys.path.insert | `src/solr-search/reset_password.py` | P3 |
| V7 | 🟢 Low | Benchmark script sys.path manipulation | `scripts/benchmark/tests/test_*.py` | P3 |

## Key Findings

1. **aithena-common Extraction (#1288) is Foundation** — Now used by installer; needs expansion to cover shared auth entities (AuthenticatedUser, parse_ttl_to_seconds, JWT utils, logging)

2. **High-Severity Dependency Violations:**
   - Admin service imports from core directories via sys.path, indicating it's not a proper package
   - Auth logic duplicated between admin (env-var + hmac) and solr-search (DB + Argon2) — no common abstraction

3. **Framework Leakage** — FastAPI-specific code (Request, Response, middleware) mixed with generic correlation ID logic in solr-search

## Skill Created

**`.squad/skills/clean-architecture/SKILL.md`** — Team reference for:
- Dependency Rule mapped to aithena layers
- 5 concrete architecture rules (R1–R5)
- PR review checklist
- Common violation detection patterns
- Examples of correct vs incorrect imports

## Recommendations for Phase 2

Expand `aithena-common` with:
- `auth_models.py` — `AuthenticatedUser`, `AuthSettings`
- `ttl.py` — `parse_ttl_to_seconds()`
- `jwt_utils.py` — JWT encode/decode (shared logic)
- `logging_setup.py` — `AithenaJsonFormatter`, unified `setup_logging()`

Migrate solr-search and admin to depend on these shared entities. Split correlation.py into pure logic (common) + FastAPI middleware (solr-search-specific).

## Architecture Principle

**Dependency Inversion Applied:**
```
installer ──────────────┐
admin ──────────────────┼──→ aithena-common (entities + pure logic)
solr-search ────────────┤
document-indexer ───────┘
```

All services depend inward. No cross-service coupling except via HTTP APIs.
