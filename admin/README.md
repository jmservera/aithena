# Aithena Admin Dashboard

A Streamlit-based operations dashboard for monitoring and managing the document indexing pipeline.

## Features

- **Overview page** — metrics cards showing total, queued, processed, and failed document counts, plus live RabbitMQ queue depth via the management API.
- **Document Manager page** — tabbed view (Queued / Processed / Failed) with per-document failure details and safe requeue / clear actions.

## Running locally

```bash
cd admin
uv sync
uv run streamlit run src/main.py
```

When you run the full Docker Compose stack, nginx exposes this dashboard at `http://localhost/admin/streamlit/`.

> **Note:** `src/requirements.txt` is deprecated. Use the `pyproject.toml` with `uv` as shown above.

## Configuration

All settings are read from environment variables (a `.env` file in `admin/src/` is supported via `python-dotenv`).

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `QUEUE_NAME` | `shortembeddings` | Shared queue/key-prefix name (must match `document-lister` and `document-indexer`) |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ hostname |
| `RABBITMQ_MGMT_PORT` | `15672` | RabbitMQ management HTTP API port |
| `RABBITMQ_MGMT_PATH_PREFIX` | _(empty)_ | Optional management UI/API prefix such as `/admin/rabbitmq` when RabbitMQ is reverse-proxied |
| `RABBITMQ_USER` | `guest` | RabbitMQ management API username |
| `RABBITMQ_PASS` | `guest` | RabbitMQ management API password |

## Requeue behaviour

Clicking **Requeue** (individual) or **Requeue All** (batch) deletes the document's Redis entry. The `document-lister` service polls every 10 minutes; on its next scan it will rediscover the file and push it back onto the RabbitMQ queue for reindexing.

Clicking **Clear All** on the Processed tab has the same effect — entries are removed from Redis so the lister treats them as new on the next scan.
