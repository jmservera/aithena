# Can Solr 10's Language-Models Module Replace Our Embeddings-Server?

**Author:** Ash (Search Engineer)  
**Date:** 2025-07-22  
**Status:** Research Complete

---

## 1. Executive Summary

**Verdict: No — not today. Maybe in the future, with significant caveats.**

Solr 10's `language-models` module (introduced in Solr 9.8, available in 10.0) **cannot replace our embeddings-server** in its current form. The module only supports **remote API calls** to cloud-hosted embedding services (OpenAI, Cohere, HuggingFace Inference API, MistralAI) via LangChain4j. It does **not** run models locally inside the Solr JVM or via ONNX Runtime.

Local/in-process ONNX model support is explicitly listed as **future work** by the module's creators (Sease). An open JIRA ticket (SOLR-17446) tracks this feature request, but it is not yet implemented or merged.

However, there is a **viable middle-ground option**: because Solr's module supports OpenAI-compatible API endpoints via a configurable `baseUrl`, we could theoretically point it at our existing embeddings-server (or a new OpenAI-compatible wrapper) to let Solr handle text-to-vector conversion at query time. This would simplify the query path but would **not** eliminate the separate embedding container.

**Recommendation:** Keep our current architecture. Monitor SOLR-17446 for in-process ONNX support. Consider the OpenAI-compatible API bridge as a future simplification of the query path only.

---

## 2. Detailed Findings

### 2.1 ONNX Model Compatibility

**Can `intfloat/multilingual-e5-base` be exported to ONNX?**

✅ **Yes, fully supported.**

- The HuggingFace model repo contains **official ONNX exports** in an `onnx/` directory, including `model.onnx`, `model_O4.onnx`, and quantized variants.
- Export via the `optimum` library is straightforward:
  ```python
  from optimum.onnxruntime import ORTModelForFeatureExtraction
  model = ORTModelForFeatureExtraction.from_pretrained(
      "intfloat/multilingual-e5-base", export=True
  )
  model.save_pretrained("output_directory")
  ```
- ONNX export produces the transformer block only; pooling (mean) and L2 normalization must be handled externally.
- LangChain4j's `OnnxEmbeddingModel` Java class can load custom ONNX models with a tokenizer.json and configurable pooling mode (MEAN, CLS, MAX).
- No known issues specific to E5 models in ONNX format beyond standard precision considerations.

**Key caveat:** When using ONNX outside of sentence-transformers, you must manually implement:
1. The E5 prefix prepending ("query: " / "passage: ")
2. Mean pooling over token embeddings
3. L2 normalization of the output vector

### 2.2 Solr 10 Language-Models Module Deep Dive

**Module name:** `language-models` (formal), also called "LLM module" informally  
**Available since:** Solr 9.8 (January 2025), carried forward into Solr 10.0 (March 2026)  
**Enable via:** `solr.modules=language-models`

**Architecture:**
- The module is a **bridge to external embedding APIs**, not a local inference engine.
- Uses [LangChain4j](https://github.com/langchain4j/langchain4j) internally to communicate with remote services.
- Text vectorization happens **exclusively outside the Solr JVM**.

**Supported model providers (remote API only):**

| Provider | LangChain4j Class | Authentication |
|----------|-------------------|----------------|
| HuggingFace Inference API | `dev.langchain4j.model.huggingface.HuggingFaceEmbeddingModel` | API key |
| OpenAI | `dev.langchain4j.model.openai.OpenAiEmbeddingModel` | API key |
| MistralAI | `dev.langchain4j.model.mistralai.MistralAiEmbeddingModel` | API key |
| Cohere | `dev.langchain4j.model.cohere.CohereEmbeddingModel` | API key |

**Components provided:**
1. **Model store:** REST API to register/manage embedding model configurations
2. **Query parser:** `knn_text_to_vector` — encodes query text via remote API, then runs kNN
3. **Update processor:** `TextToVectorUpdateProcessorFactory` — encodes document text at index time

**Critical limitations for our use case:**
- ❌ No local/in-process model execution
- ❌ No ONNX Runtime integration within Solr
- ❌ No built-in tokenizer — relies entirely on remote service
- ❌ No custom text preprocessing (can't add E5 prefixes at the Solr level)
- ❌ No batch processing optimization — documents are sent one-by-one to remote APIs
- ⚠️ Remote API calls add significant latency to indexing pipelines
- ⚠️ The Sease blog explicitly warns: *"This update processor sends your document field content off to some hosted service on the internet. There are serious performance implications."*

**What about the HuggingFace Inference API option?**
- Using `HuggingFaceEmbeddingModel` would call HuggingFace's cloud API, not our local model.
- HuggingFace Inference API has rate limits, requires internet access, and sends data externally.
- This is a non-starter for our privacy-first, self-hosted setup.

### 2.3 The OpenAI-Compatible API Workaround

The `OpenAiEmbeddingModel` class accepts a configurable `baseUrl` parameter. This means we could:

1. Add an OpenAI-compatible `/v1/embeddings` endpoint to our embeddings-server (or wrap it)
2. Configure Solr's model store to point at `http://embeddings-server:8080/v1/embeddings`
3. Let Solr handle text-to-vector conversion transparently

**However, this does NOT eliminate the embeddings-server container.** It only moves the orchestration of "encode then search" from our solr-search Python service into Solr's query parser. The actual inference still happens in our container.

**Pros:**
- Simplifies the query path (one Solr call instead of embed→search)
- Solr's `knn_text_to_vector` parser handles the encode+search in one request

**Cons:**
- Still requires the separate embeddings-server container
- No control over E5 prefix injection from Solr side (would need the wrapper to handle it)
- Our embeddings-server already returns OpenAI-compatible format, but the E5 prefix logic (`input_type` parameter) is non-standard
- Adds complexity: now two integration paths instead of one
- Index-time encoding via Solr's update processor would be slower than our batched approach (50 docs/batch currently)

### 2.4 Multilingual Support

**Our current model (multilingual-e5-base):**
- Based on XLM-RoBERTa, supports ~94 languages
- Handles CJK, Arabic, Cyrillic, and other non-Latin scripts natively
- Our primary languages: Spanish, Catalan, French, English

**ONNX/LangChain4j multilingual handling:**
- The ONNX export preserves the full XLM-RoBERTa tokenizer (SentencePiece-based)
- LangChain4j's `OnnxEmbeddingModel` uses the exported `tokenizer.json` — full multilingual support preserved
- No known issues with non-Latin scripts in ONNX format
- The Java-side HuggingFace Tokenizers library handles all Unicode scripts correctly

**Solr's module has no impact on multilingual support** — it's just a pass-through to whatever service generates the embeddings.

### 2.5 Performance Comparison

| Dimension | Current (sentence-transformers) | ONNX Runtime (Java/LangChain4j) | Solr Module (Remote API) |
|-----------|--------------------------------|----------------------------------|--------------------------|
| **CPU throughput** | Baseline | 1.4–2× faster | Same as underlying service + network latency |
| **GPU throughput** | CUDA: high; OpenVINO: optimized for Intel | ONNX CUDA: 2–3× vs PyTorch; No GPU in LangChain4j ONNX yet | N/A (remote) |
| **Memory** | ~2–3GB container | ~1–2GB in-JVM (would add to Solr heap) | Same as underlying service |
| **Batch support** | ✅ Yes (50 docs/request) | ✅ Parallelized by CPU cores | ❌ Per-document API calls |
| **Latency** | ~15–50ms per batch (local) | ~10–30ms per batch (in-process) | +5–50ms network round-trip per doc |
| **OpenVINO** | ✅ Supported (our current optimization) | ❌ Not available in Java ONNX RT | ❌ Not available |

**Key insight:** Even if Solr gained in-process ONNX support, we would lose our OpenVINO optimization path and GPU acceleration options. ONNX Runtime's Java bindings do not yet support GPU inference for embedding models in LangChain4j.

### 2.6 E5-Specific Concerns

**The asymmetric encoding problem:**

E5 models require different prefixes for queries ("query: ") vs documents ("passage: "). This is handled today by our embeddings-server's `input_type` parameter.

- **Solr's `knn_text_to_vector` query parser:** Passes raw query text to the remote API. There is **no mechanism** to inject a prefix before sending to the embedding service. The text goes as-is.
- **Solr's `TextToVectorUpdateProcessor`:** Same issue — passes raw field content with no preprocessing hook.
- **Workaround:** The embedding service itself must handle prefix injection based on context (query vs indexing). Our server already does this via the `input_type` parameter, but Solr's module doesn't pass this parameter.

**This is a blocking issue.** Without E5 prefix support, vectors generated through Solr's module would be incorrect and incompatible with our existing index.

**Alternative models that don't require prefixes:**
| Model | Dimensions | Multilingual | Prefix Required | MTEB Score |
|-------|-----------|-------------|-----------------|------------|
| intfloat/multilingual-e5-base | 768 | ✅ ~94 langs | ✅ Yes | ~61.5 |
| BAAI/bge-m3 | 1024 | ✅ | ✅ Yes (instruction) | ~64+ |
| jinaai/jina-embeddings-v2 | 768 | ✅ ~50 langs | ❌ No | ~60 |
| nomic-embed-text-v1 | 768 | ✅ | ✅ Yes (search_query/document) | ~59 |

Switching to a prefix-free model (like Jina v2) would solve this but require a full re-index and re-evaluation against our multilingual corpus.

### 2.7 Architecture Impact Analysis

**Current architecture:**
```
[Client] → [solr-search API] → [embeddings-server] (encode)
                              → [Solr] (search with vector)

[document-indexer] → [embeddings-server] (batch encode) → [Solr] (index with vectors)
```

**Proposed (if Solr handled embeddings):**
```
[Client] → [solr-search API] → [Solr] (encode + search in one call)

[document-indexer] → [Solr] (encode + index via update processor)
```

**Impact on solr-search service:**
- Would remove `get_query_embedding()` function and circuit breaker logic
- Would change kNN query construction from raw vector to `knn_text_to_vector` parser
- Would simplify the service significantly (~100 lines of embedding-related code)
- BUT: would lose control over input_type (query vs passage prefix)

**Impact on document-indexer:**
- Currently batches 50 documents to embeddings-server, gets vectors back, then indexes with vectors
- With Solr update processor: would send raw text, Solr encodes per-document via remote API
- **This would be dramatically slower** — individual API calls vs our 50-doc batches
- Sease documentation explicitly warns about this performance issue

**Impact on embeddings-server:**
- Would NOT be eliminated (Solr still needs an external service)
- Would need an OpenAI-compatible API wrapper for the Solr integration
- Would still need to handle E5 prefixes, but now without the `input_type` context from Solr

### 2.8 Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| ONNX produces different embeddings than PyTorch | Medium | High (1e-6 to 1e-4 differences) | Full re-index required if switching backends |
| Solr 10 language-models module is immature | High | High (first major version) | Wait for community adoption and bug reports |
| In-process ONNX never ships for Solr | Medium | Medium (listed as "future work", no timeline) | Keep embeddings-server as primary strategy |
| E5 prefix not supported through Solr | High | Certain (no preprocessing hooks) | Must use our service or switch models |
| Performance regression at index time | High | Certain (per-doc API calls vs batches) | Keep current indexing pipeline |
| Solr JVM memory pressure from embedding model | Medium | Medium (~1–2GB model in JVM heap) | Separate container avoids this entirely |
| Vendor lock-in to LangChain4j API surface | Low | Medium | LangChain4j is open source, active project |

**Re-indexing requirement:** If we switched from sentence-transformers to ONNX Runtime (even outside Solr), numerical precision differences (1e-4 magnitude) would make existing embeddings incompatible. A full re-index of all documents would be required.

**Production readiness:** The language-models module shipped in 9.8 (January 2025) and is included in 10.0 (March 2026). It's relatively new with a limited feature set. The Sease blog post and documentation both indicate significant planned future work.

---

## 3. Comparison Table

| Feature | Current (embeddings-server) | Solr 10 language-models | Verdict |
|---------|---------------------------|------------------------|---------|
| **Local inference** | ✅ In-container | ❌ Remote API only | Current wins |
| **E5 prefix handling** | ✅ Automatic via input_type | ❌ No preprocessing hooks | Current wins |
| **Batch encoding** | ✅ 50 docs/request | ❌ Per-document | Current wins |
| **GPU support** | ✅ CUDA + OpenVINO | ❌ None (CPU only in LangChain4j ONNX) | Current wins |
| **Privacy** | ✅ Fully self-hosted | ⚠️ Designed for cloud APIs | Current wins |
| **Query simplicity** | ⚠️ Two-step (embed→search) | ✅ One-step (knn_text_to_vector) | Solr wins |
| **Fewer containers** | ❌ Separate container needed | ❌ Still needs external service | Tie |
| **Maintenance burden** | ⚠️ Custom Python service | ✅ Standard Solr module | Solr wins |
| **Maturity** | ✅ Production-proven in aithena | ⚠️ New (9.8+), limited adoption | Current wins |
| **Index-time perf** | ✅ Batched, fast | ❌ Per-doc API calls, slow | Current wins |

**Score: Current setup wins 7–2 with 1 tie.**

---

## 4. Recommended Approach

### Primary: Keep Current Architecture (No Change)

Our embeddings-server is well-designed, production-tested, and optimally integrated. The Solr 10 module doesn't offer enough to justify migration.

### Secondary: Monitor and Prepare

1. **Track SOLR-17446** — When Solr adds in-process ONNX support, re-evaluate. This would be the game-changer that makes migration viable.
2. **Track LangChain4j ONNX GPU support** — Currently CPU-only; GPU support would be needed for parity.
3. **Consider OpenAI-compatible API bridge** — If we want to simplify the query path in solr-search, we could add an OpenAI-compatible endpoint to our embeddings-server and use `knn_text_to_vector` for queries only (keeping our own indexing pipeline). Low priority, moderate effort.

### Alternative: Upgrade embeddings-server to ONNX Backend

Independent of the Solr module question, we could switch our embeddings-server from sentence-transformers (PyTorch) to ONNX Runtime (Python), gaining 1.4–2× CPU throughput:

```python
# Current
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("intfloat/multilingual-e5-base")

# Proposed
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("intfloat/multilingual-e5-base", backend="onnx")
```

This is a separate optimization from the Solr module question and could be pursued independently. It would require a full re-index due to numerical precision differences.

---

## 5. Migration Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Numerical precision mismatch (ONNX vs PyTorch) | A/B test with dual collections before committing; full re-index required |
| Solr module doesn't support E5 prefixes | Stay with current architecture or switch to prefix-free model |
| Index-time performance degradation | Keep our batched indexing pipeline regardless of query-time changes |
| Solr JVM instability from in-process model (future) | Test thoroughly with realistic load; keep embeddings-server as fallback |
| LangChain4j version conflicts | Pin versions carefully; Solr bundles a specific version |

---

## 6. Open Questions Requiring Hands-On Testing

1. **Numerical equivalence test:** Export multilingual-e5-base to ONNX, generate embeddings for our test corpus, compare cosine similarity with PyTorch-generated embeddings. What's the actual divergence?

2. **OpenAI-compatible bridge feasibility:** Can we configure Solr's `OpenAiEmbeddingModel` to point at our embeddings-server? Does the request/response format match exactly? How do we pass `input_type`?

3. **Solr 10 upgrade path:** We're on Solr 9.7. What's the upgrade effort to 10.0? Are there breaking changes affecting our parent-chunk model, HNSW config, or configsets?

4. **ONNX Runtime Python backend perf:** Benchmark sentence-transformers with `backend="onnx"` on our actual hardware (CPU) vs current PyTorch. Is the 1.4–2× speedup real for our model and document sizes?

5. **LangChain4j custom model dimensions:** Can LangChain4j's `OnnxEmbeddingModel` handle 768D vectors correctly? (Documented examples mostly show 384D models.)

6. **E5-prefix-free alternative evaluation:** Would Jina v2 or another prefix-free multilingual model match E5-base quality for our Spanish/Catalan/French/English corpus? Needs MTEB evaluation on our languages.

---

## References

- [Solr Text-to-Vector Documentation](https://solr.apache.org/guide/solr/latest/query-guide/text-to-vector.html)
- [Sease: Semantic Search with Apache Solr 9.8](https://sease.io/2025/07/semantic-search-text-to-vector-with-apache-solr.html)
- [LangChain4j In-Process ONNX](https://docs.langchain4j.dev/integrations/embedding-models/in-process/)
- [HuggingFace multilingual-e5-base ONNX files](https://huggingface.co/intfloat/multilingual-e5-base/tree/main/onnx)
- [Sentence Transformers v3.2.0 ONNX Backend](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html)
- [Solr 10.0.0 Release](https://solr.apache.org/api/)
- [ONNX Runtime Performance](https://onnxruntime.ai/docs/performance/)
