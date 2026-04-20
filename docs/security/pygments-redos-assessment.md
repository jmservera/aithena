# Pygments ReDoS Vulnerability Assessment

**Date:** 2025-07-22
**Issue:** [#1236](https://github.com/jmservera/aithena/issues/1236)
**Dependabot alerts:** #120–#124 (low severity)
**Status:** Monitoring — no patched Pygments version available yet

## Vulnerability Summary

Pygments contains regular expression patterns (in lexers that handle GUID-like
input) that are susceptible to Regular Expression Denial of Service (ReDoS).
An attacker who can supply crafted input to a vulnerable lexer can cause
excessive CPU consumption.

The vulnerability is triggered only when Pygments **actively highlights** or
**lexes** untrusted input. Simply having Pygments installed as a transitive
dependency does not create exposure.

## Affected Services

All six Python services in `src/` include Pygments 2.20.0 in their resolved
dependency tree (`uv.lock`).

| Service | Pygments version | Dependency chain | Runtime? | Exposure |
|---|---|---|---|---|
| **admin** | 2.20.0 | pytest → pygments | Dev only | **None** |
| **aithena-common** | 2.20.0 | pytest → pygments | Dev only | **None** |
| **document-indexer** | 2.20.0 | pytest → pygments | Dev only | **None** |
| **document-lister** | 2.20.0 | pytest → pygments | Dev only | **None** |
| **embeddings-server** | 2.20.0 | nncf → rich → pygments; pytest → pygments | Runtime (via rich) | **None** |
| **solr-search** | 2.20.0 | fastapi[all] → fastapi-cli → typer → rich → pygments; pytest → pygments | Runtime (via rich) | **None** |

### Dependency Chain Details

- **pytest → pygments** (all services): Pygments is used by pytest for syntax
  highlighting in traceability output. This is a **dev-only** dependency and
  never runs in production containers.

- **nncf → rich → pygments** (embeddings-server): The Neural Network
  Compression Framework (nncf) uses Rich for console output formatting. Rich
  depends on Pygments for syntax highlighting in its `Console` and `Syntax`
  classes. However, the embeddings-server does not pass untrusted user input
  through Rich's syntax highlighting pipeline.

- **fastapi[all] → fastapi-cli → typer → rich → pygments** (solr-search):
  FastAPI's CLI tooling (used for `fastapi dev`/`fastapi run` commands) pulls
  in Typer, which uses Rich for terminal output. This chain is for CLI/dev
  tooling and does not process user-supplied content through Pygments lexers at
  runtime.

## Source Code Analysis

A search for direct Pygments imports across all service source code (excluding
`.venv` directories) returned **zero results**. No service directly imports or
invokes Pygments.

```
grep -ri "pygments" src/ --include="*.py" -l | grep -v .venv  # no results
```

## Exposure Assessment

**Overall exposure: None**

1. **No direct usage:** No service imports or calls Pygments directly.
2. **Dev-only in four services:** admin, aithena-common, document-indexer, and
   document-lister only have Pygments via pytest (dev dependency). Production
   container images do not include dev dependencies.
3. **Runtime but unexposed in two services:** embeddings-server and solr-search
   include Pygments at runtime (via rich), but neither service routes untrusted
   user input through Pygments' lexing/highlighting functions. Rich uses
   Pygments only when explicitly asked to render syntax-highlighted code via
   `rich.syntax.Syntax` or `Console.print` with `highlight=True` on code
   objects — neither pattern exists in our code.
4. **ReDoS trigger requires specific input:** The vulnerability requires crafted
   GUID-like strings to be processed by specific Pygments lexer regex patterns.
   Even if Pygments were invoked indirectly, our services do not pass
   user-controlled strings to lexer selection or highlighting functions.

## Current Mitigation Status

| Mitigation | Status |
|---|---|
| No direct Pygments usage in application code | ✅ Verified |
| Dev-only dependency in 4/6 services | ✅ Verified |
| Runtime dependency does not process untrusted input | ✅ Verified |
| Patched Pygments version available | ❌ Not yet released upstream |
| Dependabot alerts acknowledged | ✅ Alerts #120–#124 tracked |

## Monitoring Plan

1. **Watch for upstream fix:** Monitor the [Pygments GitHub
   repository](https://github.com/pygments/pygments) and PyPI for a release
   that addresses the ReDoS patterns. Dependabot will auto-create PRs when a
   patched version is available.

2. **Dependabot auto-update:** Once a patched version is released, Dependabot
   will open pull requests to update `uv.lock` files. Merge those PRs promptly.

3. **Re-assess if architecture changes:** If any service begins processing
   user-supplied content through syntax highlighting (e.g., adding code preview
   features), re-evaluate exposure and consider pinning Pygments or adding input
   validation.

4. **Periodic review:** Re-check this assessment quarterly or when significant
   dependency changes occur.

## Recommendation

**No immediate action required.** The exposure is effectively zero because
Pygments is never invoked on untrusted input. Continue monitoring for an
upstream fix and apply it when available through the normal Dependabot workflow.
