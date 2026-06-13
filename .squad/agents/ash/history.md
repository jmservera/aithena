# Ash — History

## Core Context

Ash owns Solr schema, search relevance, hybrid retrieval, and embedding-evaluation design.

**Search/data model:** Aithena is a strict parent/chunk system. Parent docs hold book metadata; chunk docs hold text, page ranges, and embeddings. kNN always runs on chunks and results are normalized back to parent books.

**Critical invariant:** `-parent_id_s:[* TO *]` (chunk exclusion) belongs on the keyword/hybrid BM25 leg only. Never apply it to semantic kNN queries or they return zero useful results.

**Search modes:**
- **Keyword:** edismax/BM25 on text, with highlights and facets.
- **Semantic:** chunk-level kNN, no chunk exclusion, no BM25-only decorations.
- **Hybrid:** parallel BM25 + kNN with RRF fusion (`k=60`) and book-level dedupe.

**Current embedding posture:** multilingual-e5-base / 768D is the active direction; optional byte/int8 support exists, but release claims remain evidence-gated.

## Key Patterns

- **Preserve parent/chunk correctness first.** Most Aithena search bugs come from mixing parent-only metadata flows with chunk-only vector flows.
- **Delete and reindex symmetrically.** A delete must remove the parent doc and every chunk matching `parent_id_s`.
- **Use POST bodies for large vector queries.** GET URLs become fragile once vectors exceed a few KB.
- **Align timeouts across the stack.** Embeddings calls need long client timeouts and nginx `proxy_read_timeout` must stay above them to avoid 502s.
- **Schema changes are a coordination point.** Query code, indexer writes, docs, and UI assumptions must move together.
- **Model or Solr-version comparisons need paired evidence.** Publish only same-host, same-corpus runs with run metadata, corpus size, latency data, Docker memory samples, and failed-query IDs.
- **Solr 10 `language-models` is not local inference.** It is a remote-API bridge; embeddings-server remains required for local multilingual models and prefix handling.
- **Native Solr RRF is not a drop-in replacement today.** Combined Query fuses Solr document IDs directly, while Aithena BM25 returns parents and semantic search returns chunks.
- **Quantization is an option, not a promise.** Keep float32 and byte/int8 paths explicit, benchmarked, and documented.

## Skill References

- `.squad/skills/solr-operations/SKILL.md`
- `.squad/skills/aithena-ab-testing-benchmarking/SKILL.md`
- `.squad/skills/vector-quantization-evaluation/SKILL.md`
- `.squad/skills/embedding-model-selection/SKILL.md`

## Boundaries / Open Gaps

- High confidence: schema design, hybrid search boundaries, RRF fusion, multilingual analysis, model-evaluation setup.
- Medium confidence: day-2 SolrCloud operations and failover; lean on Brett for cluster/Compose specifics.
- Still open: advanced relevance tuning beyond RRF, HNSW performance tuning at scale, OCR-quality workflows, and production incident playbooks.
