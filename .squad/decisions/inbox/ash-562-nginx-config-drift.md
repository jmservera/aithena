# Decision: Nginx Config Template as Source of Truth

**Date**: 2026-03-20  
**Author**: Ash (Search Engineer)  
**Context**: #562 — Vector/hybrid search 502 errors

## Problem

The nginx `default.conf` file was out of sync with `default.conf.template`:
- **Template** (`default.conf.template`) had `proxy_read_timeout 180s` in `/v1/` location (added in PR #568)
- **Active config** (`default.conf`) was missing these timeouts
- This caused 502 Bad Gateway errors when embedding generation exceeded nginx's default 60s timeout

## Root Cause

`default.conf` appears to have been manually edited or regenerated from an older template, losing the timeout directives.

## Decision

**Nginx template file (`default.conf.template`) is the source of truth.**

### Guidelines:
1. **Always edit** `default.conf.template`, not `default.conf` directly
2. **Regenerate** `default.conf` from template during build/deployment
3. **Review PRs** carefully when both files change — ensure they stay in sync
4. **Add to build process**: Generate `default.conf` from template with envsubst or similar tool (if not already done)

### Why this matters:
- Nginx config drift causes hard-to-debug production issues (like 502s)
- Template-first approach enables environment-specific config via variable substitution
- Single source of truth prevents config divergence

## Action Items

- [x] Fixed immediate issue: added missing timeouts to `default.conf` (PR #626)
- [ ] Document in `.squad/decisions.md` or project README that template is source of truth
- [ ] Verify build process generates `default.conf` from template (or document manual sync requirement)

## Related

- PR #568 — originally added timeouts to template
- PR #626 — fixed config drift in `default.conf`
