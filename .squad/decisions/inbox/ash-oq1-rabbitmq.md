# OQ-1 Decision: RabbitMQ Queue Topology for A/B Test

**Decision:** Use a **fanout exchange** (Option A) to deliver every document message to both indexers.

**Authors:** Ash (Search Engineer) + Brett (Infrastructure)
**Date:** 2025-01-XX
**Status:** DECIDED
**Blocks:** P1-3 (Parker), P1-4 (Brett)

---

## Context

The A/B embedding model test requires two `document-indexer` instances:

| Service | Collection | Embedding Model | Chunk Config |
|---------|-----------|----------------|-------------|
| `document-indexer` (baseline) | `books` | distiluse 512D | 90w / 10w overlap |
| `document-indexer-e5` (new) | `books_e5base` | e5-base 768D | 300w / 50w overlap |

Both must process **every** document. Today, `document-lister` publishes directly to the `shortembeddings` queue (`exchange=""`). If two consumers share one queue, RabbitMQ round-robins — each document reaches only ONE indexer.

## Options Evaluated

### Option A: Fanout Exchange ✅ CHOSEN

Publisher sends to a **fanout exchange** (`documents`). The exchange copies every message to all bound queues. Each indexer consumes from its own dedicated queue.

```
document-lister
      │
      ▼
 ┌─────────────────────┐
 │  exchange: documents │  (type: fanout)
 │  (fanout)            │
 └──┬──────────────┬────┘
    │              │
    ▼              ▼
┌────────┐   ┌──────────────┐
│indexer_ │   │indexer_       │
│baseline │   │e5base         │
└───┬────┘   └───┬───────────┘
    │            │
    ▼            ▼
document-    document-
indexer      indexer-e5
```

**Pros:**
- Textbook RabbitMQ pattern for "one message → many consumers"
- Guaranteed delivery to every bound queue (atomic at the exchange level)
- Each consumer has independent acknowledgment, backpressure, and retry
- Adding a third model later = bind one more queue (zero producer changes)
- Rollback = remove the e5 queue binding; baseline continues unchanged

**Cons:**
- Two copies of each message stored in RabbitMQ (trivial — messages are ~100 byte file paths)
- Requires a small change to the producer's publish call

### Option B: Publish Twice ❌ REJECTED

Producer publishes to two separate queues explicitly.

**Why rejected:**
- **Tight coupling:** Producer must know about every consumer. Adding/removing a model means changing `document-lister`.
- **Partial failure risk:** If publish #1 succeeds and #2 fails, collections diverge silently. No transactional guarantee across two publishes without publisher confirms + manual compensation.
- **Rollback pain:** Removing the A/B test means editing the producer again.
- **Scaling:** Every new consumer = more producer code, more failure modes.

### Option C: Sequential Indexing ❌ REJECTED

A single indexer processes both collections in sequence.

**Why rejected:**
- **Doubles latency:** Each document takes 2× as long (sequential embedding calls to two different servers with different chunk configs).
- **Complexity explosion:** One indexer must carry two chunk configs, two embedding endpoints, two Solr collections. Violates single-responsibility.
- **Blast radius:** A bug in e5 indexing path crashes the baseline indexer too.
- **Rollback pain:** Must surgically remove e5 code paths from the indexer codebase.
- **No parallelism:** Wastes the fact that we have two separate embedding servers.

## Decision Details

### 1. New Exchange

| Property | Value |
|----------|-------|
| Name | `documents` |
| Type | `fanout` |
| Durable | `true` |
| Auto-delete | `false` |

The exchange is declared by `document-lister` at startup (idempotent `exchange_declare`). Using a generic name (`documents`) rather than `shortembeddings_fanout` so it remains useful beyond the A/B test.

### 2. New Queues

| Queue | Bound To | Consumer |
|-------|----------|----------|
| `indexer_baseline` | `documents` exchange | `document-indexer` |
| `indexer_e5base` | `documents` exchange | `document-indexer-e5` |

Each queue is declared and bound by its consumer at startup (idempotent `queue_declare` + `queue_bind`). This follows the same self-declaring pattern the codebase already uses.

### 3. Deprecate Direct Queue Publishing

The old `shortembeddings` queue becomes unused. It can be deleted manually via the RabbitMQ management UI after confirming the new topology works, or left to drain.

### 4. Redis Key Isolation

The indexer already uses `/{QUEUE_NAME}/{file_path}` as its Redis key pattern. Since each indexer will have a different `QUEUE_NAME`, their processing state is automatically isolated. No Redis changes needed.

---

## Implementation Plan

### Files to Modify

#### A. `src/document-lister/document_lister/__init__.py`
Add a new config variable:
```python
EXCHANGE_NAME = os.environ.get("EXCHANGE_NAME", "documents")
```

#### B. `src/document-lister/document_lister/__main__.py`
1. Import `EXCHANGE_NAME`
2. In `list_files()` (~line 152): After queue_declare, add exchange declaration and binding:
   ```python
   channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)
   ```
3. In `push_file_to_queue()` (~line 122): Change the publish call:
   ```python
   channel.basic_publish(
       exchange=EXCHANGE_NAME,    # was: ""
       routing_key="",            # was: QUEUE_NAME  (fanout ignores routing key)
       body=f"{file}",
       properties=pika.BasicProperties(
           delivery_mode=2,
           headers={"X-Correlation-ID": correlation_id},
       ),
   )
   ```
4. **Keep** the `queue_declare` for backward compatibility during rolling deploys, but it's no longer the primary delivery target.

#### C. `src/document-indexer/document_indexer/__init__.py`
Add a new config variable:
```python
EXCHANGE_NAME = os.environ.get("EXCHANGE_NAME", "documents")
```

#### D. `src/document-indexer/document_indexer/__main__.py`
1. Import `EXCHANGE_NAME`
2. In `get_queue()` (~line 63): After `queue_declare`, add queue-to-exchange binding:
   ```python
   channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout", durable=True)
   channel.queue_bind(queue=QUEUE_NAME, exchange=EXCHANGE_NAME)
   ```
   Both calls are idempotent — safe to call on every reconnect.

#### E. `docker-compose.yml` — Existing Services
Update environment variables for existing services:

**document-lister:**
```yaml
- EXCHANGE_NAME=documents
# QUEUE_NAME can be removed or kept for Redis key compat
```

**document-indexer (baseline):**
```yaml
- QUEUE_NAME=indexer_baseline
- EXCHANGE_NAME=documents
- SOLR_COLLECTION=books
```

#### F. `docker-compose.yml` — New Services (P1-4 scope, Brett)
Add `document-indexer-e5` service:
```yaml
document-indexer-e5:
  build:
    context: ./src/document-indexer
  environment:
    - QUEUE_NAME=indexer_e5base
    - EXCHANGE_NAME=documents
    - SOLR_COLLECTION=books_e5base
    - EMBEDDINGS_HOST=embeddings-server-e5
    - EMBEDDINGS_PORT=8085
    - CHUNK_SIZE=300
    - CHUNK_OVERLAP=50
    # ... (other standard env vars)
```

This uses the **same Docker image** as the baseline indexer — only env vars differ.

### What Stays Unchanged

- **Consumer callback logic** — `callback()` in document-indexer is untouched
- **Message format** — still plain file path strings with correlation ID headers
- **Redis tracking** — automatically isolated by different `QUEUE_NAME` values
- **Acknowledgment** — still manual `basic_ack` per message
- **Backpressure** — still `prefetch_count=1` per consumer
- **Solr indexing** — `SOLR_COLLECTION` env var already parameterizes the target

### Rollback Plan (Post-A/B)

1. Remove `document-indexer-e5` service from docker-compose
2. Optionally revert producer to `exchange=""` / `routing_key=QUEUE_NAME`
3. Or simply leave the fanout exchange in place (it works fine with a single bound queue)
4. Delete the `indexer_e5base` queue via RabbitMQ management UI

### Migration / Deployment Order

1. **Deploy document-lister first** with exchange support (it declares the exchange)
2. **Deploy updated document-indexer** with `QUEUE_NAME=indexer_baseline` (it declares + binds its queue)
3. **Deploy document-indexer-e5** with `QUEUE_NAME=indexer_e5base` (it declares + binds its queue)
4. Messages in the old `shortembeddings` queue drain to zero, then the queue can be deleted

### Testing

- Verify with RabbitMQ management UI (`/admin/rabbitmq`) that:
  - Exchange `documents` exists (type: fanout, durable)
  - Queue `indexer_baseline` is bound to `documents`
  - Queue `indexer_e5base` is bound to `documents`
- Publish one test message → confirm it appears in BOTH queues
- Each indexer processes its copy independently

---

## Task Assignment

| Change | Owner | Ticket |
|--------|-------|--------|
| Producer changes (document-lister exchange publish) | Parker | P1-3 |
| Consumer changes (document-indexer queue binding) | Parker | P1-3 |
| Docker Compose: new services + env vars | Brett | P1-4 |
| Integration testing | Ash + Brett | P1-4 acceptance |
