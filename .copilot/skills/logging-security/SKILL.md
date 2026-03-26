---
name: "logging-security"
description: "Prevent information disclosure in production logs while preserving debugging capability"
domain: "security, logging, error handling"
confidence: "high"
source: "earned — security audit, approved by Kane, applied across all backend services"
---

## Context
When building backend services that expose containers to production environments, logs are scraped by monitoring systems, cloud platforms, and debugging tools. Stack traces in production logs (INFO/ERROR level) expose:
- Internal file paths and directory structure
- Library versions (dependency fingerprinting for attackers)
- Environment configuration and variable values in frames
- Source code line numbers and logic

This is a **defense-in-depth** pattern: applies to solr-search, document-indexer, document-lister, embeddings-server, and admin.

## Patterns

1. **Two-Tier Logging for Exceptions**

   **CRITICAL/ERROR level** (production-safe):
   ```python
   except SomeError as exc:
       logger.error("Operation failed: %s (%s)", message, type(exc).__name__)
   ```

   **DEBUG level** (troubleshooting only):
   ```python
       logger.debug("Full stack trace for debugging:", exc_info=True)
   ```

2. **Never Use `logger.exception()` in Production Error Paths**

   ❌ **Bad** — exposes stack trace at INFO/ERROR level:
   ```python
   except JWTError as exc:
       logger.exception("Token validation failed")  # stack trace exposed
   ```

   ✅ **Good** — error message only, stack trace in DEBUG:
   ```python
   except JWTError as exc:
       logger.error("Token validation failed: %s", type(exc).__name__)
       logger.debug("Stack trace:", exc_info=True)
   ```

3. **Hardcoded Error Messages Are Safe**

   When exception messages are hardcoded (no user input), they're safe for production:
   ```python
   except FileNotFoundError:
       logger.error("Configuration file not found at %s", CONFIG_PATH)  # OK, CONFIG_PATH is from code
   ```

4. **User-Provided Input Must Never Appear at INFO/ERROR Level**

   ❌ **Bad** — includes user input with exception type info:
   ```python
   except Exception as exc:
       logger.error("Failed to process user input %s: %s", user_data, type(exc).__name__)
   ```

   ✅ **Good** — hash/ID only, never raw input:
   ```python
   except Exception as exc:
       logger.error("Failed to process document: %s (ID: %s)", type(exc).__name__, doc_id)
       logger.debug("User data: %s, full trace:", user_data, exc_info=True)
   ```

5. **Exception Type Names Only (No `str(exc)` at Production Level)**

   ❌ **Bad** — `str(exc)` might leak:
   ```python
   logger.error("Solr error: %s", str(exc))  # may expose internal paths
   ```

   ✅ **Good** — exception type is safe:
   ```python
   logger.error("Solr error: %s", type(exc).__name__)
   logger.debug("Details:", exc_info=True)
   ```

6. **Pattern for API Error Responses**

   ```python
   try:
       result = some_operation()
   except AuthError as exc:
       # CRITICAL/ERROR: user-facing message only
       logger.critical("Authentication failed: %s", type(exc).__name__)
       # DEBUG: full context for operators
       logger.debug("Auth context:", exc_info=True)
       # HTTP: return safe error message
       raise HTTPException(status_code=401, detail="Invalid credentials")
   ```

## Examples

Reference implementations in aithena:
- `src/solr-search/main.py` — all error handlers follow pattern
- `src/document-indexer/main.py` lines 379, 383 — document processing errors
- `src/embeddings-server/main.py:20` — model loading errors
- `src/admin/src/pages/shared/config.py` — HTTP client error handling

## Anti-Patterns

- **Don't use `exc_info=True` at CRITICAL/ERROR level** — this exposes stack traces in production logs
- **Don't log raw user input at INFO/ERROR level** — hash it or use ID only
- **Don't rely on `str(exc)` being safe** — custom exception classes might override `__str__` to leak
- **Don't think "we'll filter logs later"** — logs are already shipped to monitoring systems, too late
- **Don't disable DEBUG logging in production** — disable it, but be intentional (don't remove it entirely; set log level to INFO)

## Scope & Enforcement

Applies to all Python backend services. Checked in:
- Code reviews (security audit)
- Bandit security linter (S101, S103, S201 rules)
- Manual inspection during security sprints

This is a **squad decision** approved by Kane (Security Engineer).
