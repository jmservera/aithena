# Decision: nginx X-Frame-Options strategy for iframe-served content

**Date:** 2025-07-22
**Author:** Dallas (Frontend Dev)
**Context:** Issue #1234 — PDF viewer iframe blocked by X-Frame-Options

## Decision

All nginx locations that serve content displayed inside iframes (currently `/documents/`) must:

1. **Use `proxy_hide_header X-Frame-Options;`** before `add_header` to strip any upstream X-Frame-Options and avoid duplicate conflicting headers.
2. **Set `add_header X-Frame-Options "SAMEORIGIN" always;`** to allow same-origin iframe embedding.
3. **Re-declare all security headers** (`X-Content-Type-Options`, `Referrer-Policy`, HSTS in SSL) at location level because `add_header` suppresses server-level directives.

Additionally, named locations used as error handlers (e.g. `@auth_error`) must have their own `add_header` directives since they inherit from the server block, not the calling location.

## Rationale

nginx's `add_header` behaviour has two non-obvious interactions:
- Location-level `add_header` completely suppresses server-level `add_header` directives
- Named locations inherit headers from the *server* block, not the calling location
- `add_header` doesn't strip upstream headers; `proxy_hide_header` is needed for that

These created edge cases where some PDF requests received `X-Frame-Options: DENY` despite the `/documents/` location setting SAMEORIGIN.

## Impact

Parker/Ash: If you add new nginx locations for iframe-served content, follow this pattern. If the backend starts adding security headers, the `proxy_hide_header` directive ensures no conflicts.
