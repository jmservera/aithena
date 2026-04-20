# Solr 9/10 Schema Compatibility Layer

> **Status**: Active
> **Created**: 2026-07-01
> **Issue**: [#1365](https://github.com/jmservera/aithena/issues/1365)
> **Related**: [Solr 9→10 Migration Plan](solr-9-to-10.md)

---

## Overview

This document describes the compatibility layer that allows the aithena codebase to
work with both **Solr 9.7** and **Solr 10** during the migration window. The layer is
controlled by the `SOLR_VERSION` environment variable and implemented primarily in
`src/solr-search/solr_compat.py`.

---

## Solr 9/10 Differences Affecting the Codebase

### 1. HNSW Parameter Names (LOW impact)

| Solr 9 | Solr 10 | Affected Files |
|--------|---------|----------------|
| `hnswMaxConnections` | `maxConnections` | `src/solr/books/managed-schema.xml:46` |
| `hnswBeamWidth` | `beamWidth` | `src/solr/books/managed-schema.xml:46` |

**Current state**: We use HNSW defaults — no explicit parameters in the schema.
If custom tuning is added later, the compat layer provides version-aware names.

**Compat approach**: `solr_compat.hnsw_params()` returns the correct parameter
names for the detected Solr version.

### 2. CLI Syntax: Single-Dash → Double-Dash (HIGH impact)

| Solr 9 | Solr 10 | Affected Files |
|--------|---------|----------------|
| `solr zk cp … -z HOST` | `solr zk cp … --zk-host HOST` | `docker-compose.yml:737` |
| `solr auth enable -u USER:PASS` | `solr auth enable --credentials USER:PASS` | `docker-compose.yml:741-745` |
| `solr auth enable -z HOST` | `solr auth enable --zk-host HOST` | `docker-compose.yml:745` |
| `solr zk ls … -z HOST` | `solr zk ls … --zk-host HOST` | `docker-compose.yml:791` |
| `solr zk upconfig -z HOST -n NAME -d DIR` | `solr zk upconfig --zk-host HOST --name NAME --dir DIR` | `docker-compose.yml:792` |

**Compat approach**: The `solr-init` entrypoint in `docker-compose.yml` reads
`SOLR_VERSION` and uses version-appropriate CLI flags via shell helper functions.

### 3. `blockUnknown` Default Change (MEDIUM impact)

| Solr 9 | Solr 10 | Affected Files |
|--------|---------|----------------|
| Default: `false` | Default: `true` | `docker-compose.yml:743`, `src/solr/security.json` |

**Current state**: We explicitly set `--block-unknown false` in the CLI and
`"blockUnknown": false` in `security.json`. Both are already safe for Solr 10.

**Compat approach**: No code change needed — explicit setting overrides defaults.

### 4. `luceneMatchVersion` (MEDIUM impact)

| Solr 9 | Solr 10 | Affected Files |
|--------|---------|----------------|
| `9.10` | `10.0` (or higher) | `src/solr/books/solrconfig.xml:39` |

**Compat approach**: Must be updated when switching to Solr 10. The compat layer
documents this but does not auto-modify XML. A version-specific configset or
manual edit is needed at migration time.

### 5. Response Writer Defaults (LOW impact)

| Solr 9 | Solr 10 | Affected Files |
|--------|---------|----------------|
| `wt` supports python/ruby/php/phps | Removed: python, ruby, php, phps | `search_service.py:135,303,338`, `main.py` (multiple) |

**Current state**: We use `wt=json` everywhere — unaffected.

**Compat approach**: No change needed. The compat module documents this for reference.

### 6. Solr Docker Base Image (HIGH impact at migration time)

| Solr 9 | Solr 10 | Affected Files |
|--------|---------|----------------|
| `FROM solr:9.7` (Java 17) | `FROM solr:10` (Java 21) | `src/solr/Dockerfile:5` |

**Compat approach**: Not handled by compat layer — requires Dockerfile change at
migration time.

### 7. Module Rename: `llm` → `language-models` (NO impact)

Not used in current codebase. Documented for future reference only.

---

## Compatibility Module: `solr_compat.py`

**Location**: `src/solr-search/solr_compat.py`

### Version Detection

1. **Environment variable** (`SOLR_VERSION`): Checked first. Values: `"9"` or `"10"`.
2. **Solr API fallback**: Queries `GET /solr/admin/info/system` and parses
   `lucene.solr-spec-version` from the response.
3. **Default**: Falls back to `"9"` if detection fails.

### Provided Functions

| Function | Purpose |
|----------|---------|
| `detect_solr_version()` | Determine major version (9 or 10) |
| `get_solr_version()` | Cached version accessor |
| `hnsw_params(max_connections, beam_width)` | Version-aware HNSW parameter dict |
| `dense_vector_field_type(name, dims, similarity, algorithm)` | Version-aware field type definition dict |
| `is_solr_10()` | Convenience boolean check |

### Usage in Search Service

The compat module is available for any code that needs to build version-specific
Solr schema definitions or HNSW parameters. Currently the search service uses
Solr defaults for HNSW, so no query-path changes are needed. The compat layer
is ready for use when:

- Custom HNSW tuning is added
- Schema management is automated via the Python service
- CLI commands are generated programmatically

---

## Environment Variable

| Variable | Default | Values | Where |
|----------|---------|--------|-------|
| `SOLR_VERSION` | `9` | `9`, `10` | `.env.example`, `docker-compose.yml` |

---

## Migration Checklist

When switching from Solr 9 to 10:

1. [ ] Set `SOLR_VERSION=10` in `.env`
2. [ ] Update `src/solr/Dockerfile` to `FROM solr:10`
3. [ ] Update `src/solr/books/solrconfig.xml` `luceneMatchVersion` to `10.0`
4. [ ] Verify CLI commands in `docker-compose.yml` use double-dash syntax
5. [ ] Re-index all data (required after `luceneMatchVersion` change)
6. [ ] Run full test suite
