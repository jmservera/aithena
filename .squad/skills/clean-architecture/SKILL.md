---
name: "clean-architecture"
description: "Dependency Rule enforcement and layer separation for aithena's microservice architecture"
domain: "architecture, code-quality"
confidence: "low"
source: "Robert C. Martin, 'The Clean Architecture' (2012) — https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html"
author: "Ripley"
created: "2026-03-27"
last_validated: "2026-03-27"
---

## Context

Use this skill when reviewing PRs, designing new features, or refactoring existing services. Clean Architecture ensures aithena's services remain independently deployable, testable without infrastructure, and resilient to framework changes. This is especially critical in our multi-service codebase where Python services (solr-search, document-indexer, document-lister, embeddings-server, admin) and a React frontend must coexist without hidden coupling.

**Authoritative reference:** https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html

---

## The Dependency Rule

> Source code dependencies can only point **inward**. Nothing in an inner circle can know anything about something in an outer circle.

This is the single rule that makes the architecture work. In aithena's context:

```
┌─────────────────────────────────────────────────────────┐
│  Frameworks & Drivers (outermost)                       │
│  FastAPI, Streamlit, Solr, Redis, RabbitMQ, React,      │
│  Docker, Nginx, SQLite drivers                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Interface Adapters                              │    │
│  │  HTTP routes, Solr query builders, RabbitMQ      │    │
│  │  consumers/publishers, Redis clients, JWT codec  │    │
│  │  ┌─────────────────────────────────────────┐     │    │
│  │  │  Use Cases (application logic)          │     │    │
│  │  │  Search orchestration, document indexing │     │    │
│  │  │  workflow, user auth flow, collection    │     │    │
│  │  │  management, backup/restore             │     │    │
│  │  │  ┌─────────────────────────────────┐    │     │    │
│  │  │  │  Entities (domain core)         │    │     │    │
│  │  │  │  Book, Chunk, User, Collection, │    │     │    │
│  │  │  │  Embedding, Password hash logic │    │     │    │
│  │  │  └─────────────────────────────────┘    │     │    │
│  │  └─────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## Core Principles (Mapped to Aithena)

### 1. Independence of Frameworks

Services must not leak framework types across boundaries. FastAPI `Request`/`Response` types belong in the outermost layer — never passed to use case or entity code.

**Aithena example — correct:**
- `search_service.py` contains pure search logic; `main.py` (FastAPI) calls it
- `aithena_common/passwords.py` uses only `argon2-cffi`; no framework imports

**Aithena example — violation:**
- `correlation.py` in solr-search imports `fastapi.Request` and `starlette.middleware` — this mixes middleware (framework) with a cross-cutting concern that should be framework-agnostic

### 2. Testability Without External Elements

Business rules must be testable without Solr, Redis, RabbitMQ, or any running service. If a test needs `sys.path` manipulation to import the module under test, the package structure is broken.

**Aithena pattern:** Use `aithena-common` for shared domain logic. Each service should be an installable Python package (`pyproject.toml` + `uv sync`) so tests import normally.

### 3. Independence of Database

Domain logic must not contain SQL, Solr query syntax, or Redis commands. These belong in adapter modules.

**Aithena example — correct:**
- `aithena_common/auth_db.py` isolates SQLite operations behind `init_auth_db()` and `find_user()` functions
- Document-indexer's chunking logic is pure Python, no Solr dependency

### 4. Independence of External Agencies

Services communicate via well-defined interfaces (HTTP APIs, message queues) — never via direct Python imports across service boundaries.

**Aithena example — correct:**
- document-lister → RabbitMQ → document-indexer (event-driven)
- admin → solr-search via HTTP API calls

**Aithena example — violation:**
- admin's `config.py` uses `sys.path.insert` to reach sibling modules — this is a packaging failure, not a valid dependency

---

## Aithena Layer Mapping

### Entities (innermost — `aithena-common`)

Pure domain objects and business rules with zero framework dependencies:
- Password hashing/verification (`aithena_common/passwords.py`)
- Auth DB schema and user lookup (`aithena_common/auth_db.py`)
- **Should also include:** `AuthenticatedUser`, `parse_ttl_to_seconds()`, logging formatters

### Use Cases (application logic within each service)

Service-specific business workflows:
- `solr-search`: search orchestration, collection management, user CRUD
- `document-indexer`: PDF chunking, embedding generation, Solr indexing pipeline
- `document-lister`: file watching, change detection, queue publishing
- `embeddings-server`: model loading, embedding computation

### Interface Adapters (API/protocol layer)

Convert between external formats and internal domain:
- FastAPI route handlers (`main.py` in solr-search, embeddings-server)
- RabbitMQ consumer callbacks (document-indexer, document-lister)
- Streamlit page renderers (admin)
- Solr query builders, Redis client wrappers

### Frameworks & Drivers (outermost)

Configuration, infrastructure, deployment:
- Docker Compose files, Nginx config, Solr schema XML
- `pyproject.toml` dependency declarations
- CI/CD workflows, installer scripts

---

## Rules for the Team

### R1: No Cross-Service Python Imports

**Never** import a Python module from one service into another. Services are isolated deployable units.

```python
# ❌ FORBIDDEN — cross-service import
sys.path.append("../../src/solr-search")
from auth import hash_password

# ✅ CORRECT — use shared package
from aithena_common.passwords import hash_password

# ✅ CORRECT — use HTTP API
response = requests.get(f"{SOLR_SEARCH_URL}/api/health")
```

### R2: No `sys.path` Manipulation in Production Code

`sys.path.append` / `sys.path.insert` in production code indicates broken packaging. Fix the `pyproject.toml` and install properly.

```python
# ❌ FORBIDDEN in production code
sys.path.insert(0, os.path.dirname(...))

# ✅ CORRECT — proper package structure
# pyproject.toml declares dependencies; `uv sync` installs them
```

**Exception:** Test files may use `sys.path` as a temporary workaround, but this should be migrated to `conftest.py` with proper package installation.

### R3: Shared Logic Goes in `aithena-common`

Any logic needed by 2+ services belongs in `src/aithena-common/`:
- Password hashing ✅ (already there)
- Auth DB schema ✅ (already there)
- TTL parsing, `AuthenticatedUser` model ❌ (still duplicated)
- Logging formatters ❌ (still duplicated in 4 services)
- Correlation ID utilities ❌ (only in solr-search)

`aithena-common` must contain **only** pure business logic — no FastAPI, Streamlit, or framework dependencies.

### R4: Dependencies Flow Inward

When reviewing a PR, verify:
1. **Entity code** imports only stdlib + `aithena-common` dependencies
2. **Use case code** may import entities but not adapters or frameworks
3. **Adapter code** may import use cases and entities, plus one framework
4. **Framework/driver code** (main.py, Dockerfile) glues everything together

### R5: Data Crosses Boundaries as Simple Structures

Don't pass Solr `RowStructure`, FastAPI `Request`, or Redis pipeline objects across layer boundaries. Convert to plain dicts, dataclasses, or typed DTOs at the boundary.

---

## Common Violations to Watch For

| Violation | How to Detect | Fix |
|-----------|---------------|-----|
| Cross-service import | `grep -r "sys.path" src/` | Extract to `aithena-common` or use HTTP API |
| Framework in domain | Entity/use-case file imports `fastapi`, `streamlit`, `pika` | Move framework code to adapter layer |
| Duplicated business logic | Same function in 2+ services | Extract to `aithena-common` |
| God module | Single file with 400+ lines mixing layers | Split into entity, use case, and adapter modules |
| Test requires infrastructure | Test file needs running Solr/Redis/RabbitMQ | Mock at the adapter boundary |

---

## PR Review Checklist

When reviewing any PR, ask:

- [ ] Do new imports respect the Dependency Rule? (inner layers don't import outer)
- [ ] Is any business logic duplicated across services?
- [ ] Are framework types (`Request`, `Response`, `st.session_state`) confined to adapter/framework layers?
- [ ] Can the changed code be tested without running Solr, Redis, or RabbitMQ?
- [ ] Does any production code manipulate `sys.path`?
- [ ] If shared logic is needed, is it in `aithena-common`?

---

## References

- **Authoritative source:** [The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) — Robert C. Martin, 2012
- **Related patterns:** Hexagonal Architecture (Ports & Adapters), Onion Architecture, Dependency Inversion Principle
- **Aithena shared package:** `src/aithena-common/` (pyproject.toml, `aithena_common/` module)
- **Related issue:** #1288 — Extract shared auth library (motivated this skill)
- **Audit findings:** `.squad/decisions/inbox/ripley-clean-architecture-audit.md`
