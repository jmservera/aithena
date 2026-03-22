# OQ-1 Resolved: RabbitMQ Fanout Exchange for Dual-Model A/B Test

**By:** Ash (Search Engineer) + Brett (Infrastructure Architect)  
**Decision:** OQ-1 — RabbitMQ Queue Topology  
**Status:** DECIDED  
**Timestamp:** 2026-03-22T12:08:51Z

## Decision Summary

**Chosen:** Fanout exchange pattern (Option A)

The A/B embedding model test requires both `document-indexer` (distiluse baseline) and `document-indexer-e5` (e5-base candidate) to process every document. RabbitMQ round-robin competing consumer pattern would deliver each message to only ONE indexer.

**Solution:** Replace direct queue publishing with a fanout exchange (`documents`). The publisher sends once; the exchange copies every message to all bound queues. Each indexer consumes independently.

## Topology

```
document-lister
      │
      ▼
┌──────────────────┐
│ exchange: documents  (fanout, durable)
└──┬───────────┬───┘
   │           │
   ▼           ▼
indexer_baseline  indexer_e5base
   │               │
   ▼               ▼
document-indexer  document-indexer-e5
```

## Rationale

- **Textbook RabbitMQ pattern** for "one message → many consumers"
- **Guaranteed delivery** to all bound queues (atomic at exchange level)
- **Consumer independence:** Each has own queue, acknowledgment, backpressure, retry
- **Horizontal scalability:** Adding a third model later = bind one more queue (zero producer changes)
- **Clean rollback:** Remove the e5 queue; baseline continues unchanged

## Blocked Items Released

- **P1-3 (Parker):** Producer/consumer RabbitMQ changes — NOW UNBLOCKED
- **P1-4 (Brett):** Docker Compose A/B services — NOW UNBLOCKED

## Next Steps

OQ-1 implementation proceeds in PR #886 (Parker) and PR #885 (Brett).
