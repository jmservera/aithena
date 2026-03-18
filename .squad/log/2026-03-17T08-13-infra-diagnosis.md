# Session Log — 2026-03-17T08-13 Infra Diagnosis & Redis Auth

**Agents:** Brett (Infrastructure Architect), Parker (Backend Dev)  
**Focus:** Docker Compose cascading failures + Redis auth wiring

## Diagnostics

**RabbitMQ auth failure:** Stale Docker volume with old credentials. Code-level env var names are correct.

**ZooKeeper health check noise:** `mntr` + grep SIGPIPE cosmetic issue; health check passes correctly. Simplified to `ruok`.

**Solr timing:** document-indexer lacked compose-level dependency, started polling before Solr ready. Added `solr: condition: service_healthy`.

**Redis auth:** solr-search ConnectionPool missing password parameter. Fixed + tested (193 tests pass).

## Remediation

✅ docker-compose.yml: ZK health check simplified, document-indexer → solr dependency added  
✅ src/solr-search/main.py: Redis password added to ConnectionPool  
⚠️ Operational: Clear `/source/volumes/rabbitmq-data/` and restart to fix RabbitMQ init issue

---

**Timestamp:** 2026-03-17T08-13Z
