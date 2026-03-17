# Decision: v1.3.0 Release Documentation Strategy

**Date:** 2026-03-17  
**Author:** Newt (Product Manager)  
**Status:** Implemented

## Context

v1.3.0 ships 8 backend and observability issues:
- BE-1: Structured JSON logging
- BE-2: Admin dashboard authentication
- BE-3: pytest-cov coverage configuration
- BE-4: URL-based search state (useSearchParams)
- BE-5: Circuit breaker for Redis/Solr failures
- BE-6: Correlation ID tracking
- BE-7: Observability runbook
- BE-8: Integration tests

This is the third major release (after v1.0.0 restructure and v1.2.0 frontend quality). v1.3.0 focuses on operational excellence: structured logging, resilience, observability, and developer/operator tooling.

## Decision

1. **Release notes title:** "Backend Excellence & Observability" — captures the dual focus on operational infrastructure and visibility
2. **Release notes format:** Mirror v1.2.0 structure (summary, detailed changes by category, breaking changes, upgrade instructions, validation)
3. **Breaking changes disclosure:** Three real breaking changes (JSON log format, admin auth requirement, URL parameter structure) require explicit documentation
4. **Manual updates:** Update both user and admin manuals, not just release notes
   - User manual: Add shareable search links section (UX feature from BE-4)
   - Admin manual: Add comprehensive v1.3.0 section with structured logging, admin auth, circuit breaker, correlation IDs, URL state

## Rationale

### Why this codename?
v1.3.0 delivers infrastructure that operators rely on (structured logging, correlation IDs, observability runbook) plus resilience patterns (circuit breaker). "Backend Excellence & Observability" accurately describes the payload.

### Why expand the admin manual?
Operators deploying v1.3.0 need to:
- Configure and understand JSON log format
- Set up admin authentication (impacts access patterns)
- Understand circuit breaker fallback behavior
- Learn correlation ID tracing for debugging

The release notes mention these features; the admin manual provides operational procedures.

### Why add shareable links to user manual?
URL-based state (BE-4) is a pure frontend UX improvement. Users benefit from documentation on:
- How to copy and share search URLs
- Browser history navigation
- What gets encoded in the URL

This positions the feature for end users, not just developers.

## Implementation

- ✅ Created `docs/release-notes-v1.3.0.md` (8.6 KB) with standard structure
- ✅ Updated `CHANGELOG.md` with v1.3.0 entry in Keep a Changelog format
- ✅ Updated `docs/user-manual.md`:
  - Changed release notes reference from v1.0.0 to v1.3.0
  - Added "Shareable search links (v1.3.0+)" section with browser history, URL structure
- ✅ Updated `docs/admin-manual.md`:
  - Changed release notes reference from v1.0.0 to v1.3.0
  - Added comprehensive v1.3.0 Deployment Updates section covering:
    - Structured JSON logging (config, examples, jq parsing)
    - Admin dashboard authentication (behavior, env vars, setup)
    - Circuit breaker (behavior table, health check examples)
    - Correlation ID tracking (flow, debugging examples)
    - Observability runbook (reference)
    - URL-based search state (parameter structure, UX benefits)

## Future Implications

1. **Log tooling:** After v1.3.0, assume operators are using JSON log parsing. New operational procedures can reference correlation IDs and structured fields.
2. **Documentation maintenance:** The observability runbook (BE-7) is now the canonical reference for debugging workflows; keep it updated as services evolve.
3. **Auth pattern:** Admin dashboard now requires login; future admin features should assume authenticated access.
4. **Circuit breaker pattern:** Available for other services (embeddings, etc.); can be reused in future resilience work.

