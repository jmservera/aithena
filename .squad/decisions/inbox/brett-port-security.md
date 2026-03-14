### Brett — Production vs Development Port Publishing

**Date:** 2026-03-14  
**By:** Copilot working as Brett

**What changed:**
- `docker-compose.yml` now publishes host ports only for `nginx` (`80`, `443`).
- All other formerly published service ports were moved behind the Compose network with `expose:`.
- New `docker-compose.override.yml` restores direct host access for local debugging (`redis`, `rabbitmq`, `solr-search`, `streamlit-admin`, `redis-commander`, `zoo1`-`zoo3`, `solr`-`solr3`, and `embeddings-server`).

**Ingress audit:**
- nginx already proxies the public UI (`/`), search API (`/v1/`, `/documents/`), Solr admin (`/admin/solr/` and `/solr/`), RabbitMQ management (`/admin/rabbitmq/`), Streamlit admin (`/admin/streamlit/`), and Redis Commander (`/admin/redis/`).
- Redis, RabbitMQ AMQP (`5672`), ZooKeeper, the secondary Solr nodes, and the embeddings server remain internal-only in production.

**Why:**
- Reduces host attack surface for production-style deployments.
- Keeps the existing local debugging workflow intact because `docker compose up` auto-loads the override file.
- Aligns with earlier squad hardening guidance to reduce published host ports and prefer nginx as the entry point.

**Notes for teammates:**
- Use `docker compose -f docker-compose.yml up` for nginx-only production exposure.
- Use plain `docker compose up` for the usual local stack with debug ports restored automatically.
- The embeddings server keeps a dev host port on `8085` because external local tools may still call it directly.
