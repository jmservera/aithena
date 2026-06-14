# Ripley — History

## Core Context

Ripley is the project lead for architecture, roadmap, release gates, coordination, and final quality review.

- Aithena is an on-prem book-library search stack: Solr/SolrCloud for metadata/full-text, FastAPI services for search/auth/embeddings, RabbitMQ workers, Redis, nginx, and a React/Vite UI.
- Search uses a parent/chunk model: embeddings live on chunks, book results are grouped by `parent_id_s`, and hybrid search uses app-side RRF.
- Ownership split: Parker backend, Dallas UI, Brett infra/CI, Ash schema/search, Kane security, Lambert QA, Newt release/docs, Copilot scoped implementation.
- Release discipline: research → implementation → validation → merge; docs and validation evidence gate tags; published tags are immutable.
- Never accept silent degradation in search/auth/error handling; prefer explicit warnings/errors unless the Lead/PO has approved fallback behavior.

## Active Patterns

- Branch from fresh `origin/dev` and avoid cross-branch contamination.
- Data-model assumptions are deliverables: document parent/chunk behavior before patches land.
- Required checks and resolved review threads are real merge gates; GraphQL thread resolution is often necessary.
- Security or auth regressions outrank release-noise cleanup.

## Recent Learnings

### 2026-06-06 — Lead quality review for PRs #1712 / #1711 / #1710
- `bits=7` Solr 10 scalar quantization support, Solr 9 BYTE fallback rewrites, and benchmark evidence gates were directionally correct.
- Optional int8 support can merge only when docs remain honest that recall/memory evidence is still pending.

### 2026-06-06 — v2.5.1 validation dispatch
- Start only active validation work when prerequisite evidence exists.
- Route #1344 implementation/validation to Bishop + Lambert, keep Ash consulted for schema/search details, and defer optional backlog items until Phase 2 and benchmark evidence land.

### 2026-06-05 — OpenVINO post-mortem coordination (#1662)
- The root cause was `uv sync --inexact` drift that CI host assumptions did not catch.
- Prevent recurrence with verification inside the built image, then record the decision where future infra/release work will see it.

### 2026-06-04 — Nap / reskill maintenance pass
- History bloat comes from keeping session logs instead of consolidating reusable patterns.
- Healthy targets are roughly <=8KB for histories and <=1.5KB for charters after extracting durable knowledge into skills/decisions.
