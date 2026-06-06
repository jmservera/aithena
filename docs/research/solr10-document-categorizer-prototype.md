# Solr 10 DocumentCategorizer Prototype Feasibility

**Author:** Ash (Search Engineer)
**Date:** 2026-06-06
**Issue:** #1348
**Status:** Safe scaffold added; runtime classification deferred until model fixture exists

## Verdict

Solr 10 can run ONNX text classifiers at index time through
`solr.processor.DocumentCategorizerUpdateProcessorFactory`, but Aithena should
not enable it by default yet.

The current repository can safely carry schema/config/test scaffolding without
bundling a model. A real runtime prototype still needs a selected ONNX model,
matching `vocab.txt`, Solr `analysis-extras` enabled, FileStore upload steps, and
measured validation.

## Current repo fit

- Solr 10 is the default config target (`luceneMatchVersion` 10.0).
- Runtime Solr modules are currently `extraction,langid`; `analysis-extras` is
  not enabled.
- The production indexing path uses `/update/extract` with the `langid` chain.
- `category_s` is manual/path metadata today, so classifier output must not
  overwrite it until accuracy is validated.
- Added disabled output fields:
  - `topic_category_s`
  - `document_sentiment_s`
- Added disabled config scaffold:
  - `src/solr/books/document-categorizer-prototype.xml`

## Solr 10 requirements

Official Solr 10 OpenNLP tutorial/configuration requires:

1. Start Solr with `analysis-extras`.
2. Upload `model.onnx` and `vocab.txt` to SolrCloud FileStore.
3. Configure `DocumentCategorizerUpdateProcessorFactory` with:
   - `modelFile`
   - `vocabFile`
   - `source`
   - `dest`
4. Invoke it explicitly with `processor=...` or `update.chain=...`.

The scaffold is deliberately not loaded by `solrconfig.xml`; declaring the
processor in active config before the module/model files exist can break core
loading or indexing.

## Use-case evaluation

| Use case | Feasibility | Notes |
| --- | --- | --- |
| Topic classification | Feasible after model selection | Keep output in `topic_category_s`; do not replace `category_s` until validated. |
| Sentiment analysis for ranking | Feasible as a separate experiment | Store in `document_sentiment_s`; only boost after relevance testing. |
| Language detection upgrade | Not a drop-in replacement | Current `langid` writes `language_detected_s`; OpenNLP language detection needs a different processor/model and parity tests. |

## Validation still required

Do not claim accuracy or performance until these run with real data:

1. Select a small multilingual ONNX classifier compatible with Aithena content.
2. Upload the model/vocab to Solr FileStore in a disposable Solr 10 collection.
3. Index a labeled fixture corpus through the categorizer chain.
4. Measure per-document indexing latency and JVM memory with/without the chain.
5. Compare predicted labels against the fixture; document precision/recall.
6. Decide whether topic labels should influence facets/ranking or stay metadata-only.

## Follow-up implementation path

1. Add an opt-in compose/profile overlay that appends `analysis-extras` to
   `SOLR_MODULES`.
2. Add a model fixture download/upload script that is never run implicitly and
   never commits model binaries.
3. Convert `document-categorizer-prototype.xml` into active `solrconfig.xml`
   only after CI/local fixtures exist.
4. Ungate `TestPhase3DocumentCategorization` with real assertions.
