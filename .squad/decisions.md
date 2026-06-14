# Squad Decisions

> Active decision ledger. Detailed and older records live in `.squad/decisions-archive.md`.

## Recent decisions

### 2026-06-13: Keep embeddings-server on its specialized base image
**By:** Brett  
**Status:** Proposed  
**Related:** #1748, #1662  
**What:** Extract a shared `Dockerfile.base` for the standard Python services (`document-lister`, `document-indexer`, `solr-search`), but keep `src/embeddings-server/Dockerfile` on `ghcr.io/jmservera/embeddings-server-base:${BASE_TAG}`.  
**Why:** The standard services can share lightweight Python layers safely, while embeddings-server still depends on heavyweight model/runtime layers and the OpenVINO drift-release gate.

### 2026-06-13: Legacy scripts migration scope
**By:** Brett (Infrastructure Architect)  
**Status:** Proposed  
**Related:** #1742, #1755, #1758  
**What:** Treat `./manage.sh` as the canonical operator entrypoint for routine lifecycle and validation work, while the root `scripts/` directory remains legacy during the deprecation window. Keep specialized backup/restore, migration, offline export, and package-maintenance helpers as documented manual runbooks for now.  
**Why:** This gives operators one obvious default without forcing an immediate redesign of every niche operational helper.

### 2026-06-13: Shared build-service discovery
**By:** Brett (Infrastructure Architect)  
**Status:** Proposed  
**Related:** #1744  
**What:** Centralize build-service discovery in `scripts/lib/build-services.sh`, and have both `buildall.sh` and `manage.sh` source it. Discovery should start from `find src -name Dockerfile`, while Python prep narrows the list to directories that also contain `pyproject.toml`.  
**Why:** New buildable services register automatically and the shell entrypoints stay aligned instead of drifting on separate service lists.

### 2026-06-13: Canonical environment template
**By:** Brett (Infrastructure Architect), Parker (Backend Dev)  
**Status:** Proposed  
**Related:** #1740, #1452, #1716  
**What:** Keep a single checked-in `.env.example` as the canonical environment template for development, production, and offline deployment. Every supported variable should have an explicit default assignment, `.env.prod.example` should stay removed, and generated runtime env files may still override values and preserve secrets as needed.  
**Why:** One canonical template prevents drift between docs, Compose defaults, installer output, and release packaging.

### 2026-06-13: manage.sh compose targeting
**By:** Brett  
**Status:** Proposed  
**Related:** #1739  
**What:** `manage.sh` should default to the same compose-file chain used by installer-generated `start.sh`, not a hard-coded `docker-compose.yml`. `AITHENA_COMPOSE_FILES` and standard `COMPOSE_FILE` remain supported overrides for tests and automation.  
**Why:** Day-2 commands must target the same stack definition operators actually run, while still allowing isolated overrides.

### 2026-06-13: Root Makefile auto-discovers local test suites
**By:** Parker (Backend Dev)  
**Status:** Proposed  
**Related:** #1741, #1452  
**What:** Use the root `Makefile` as the local orchestration layer, discovering Python services from `src/*/pyproject.toml`, exposing aggregate lint/format/test targets, and only including Playwright or stress targets when their directories exist.  
**Why:** This keeps local verification aligned with the repo layout without hard-coding service lists that can drift.

### 2026-06-13: CI workflows call root Makefile test entrypoints
**By:** Brett (Infrastructure Architect)  
**Status:** Proposed  
**Related:** #1747, #1741, #1452  
**What:** Route GitHub Actions test execution through root `Makefile` targets instead of calling pytest, Vitest, or Playwright directly. Workflows may still override runner-specific flags and the Python launcher through make variables.  
**Why:** Centralizing test orchestration removes duplicated workflow wiring while preserving existing artifacts and install flows.

### 2026-06-07: Docs describe shipped v2.5 behavior
**By:** Newt (Product Manager)  
**Status:** Proposed  
**Related:** #1452, #1344  
**What:** When documentation conflicts, operator-facing docs must match shipped code, runtime behavior, and current migration runbooks. Future hardening or optimization work should be labeled as follow-up work, not documented as already shipped.  
**Why:** The v2.5 docs audit found drift around standalone mode, `blockUnknown`, HNSW parameter names, and quantization claims.

### 2026-06-06: Gate Solr 9.7 vs Solr 10 performance claims on paired evidence
**By:** Ash  
**Status:** Proposed  
**Related:** #1354, #1711  
**What:** Do not publish Solr 9.7 vs Solr 10 performance claims unless both reports come from the same host and corpus, with benchmark JSON, Docker stats, corpus metadata, startup/index timing, and failed-query IDs. `scripts/benchmark/compare_solr_versions.py` should treat missing or mismatched evidence as invalid.  
**Why:** Unpaired runs can mislead on memory, indexing, or query claims; the same evidence rule should carry forward to future runtime and quantization benchmarks.
