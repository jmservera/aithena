#!/bin/sh
set -eu

# ──────────────────────────────────────────────────────────────────────────────
# Generate RabbitMQ definitions.json from environment variables.
#
# Runs at container startup BEFORE rabbitmq-server, via entrypoint override.
# Produces /etc/rabbitmq/definitions.json which RabbitMQ loads on boot via the
# load_definitions directive in rabbitmq.conf.
#
# Per-service users with minimal permissions:
#   lister  — publish to the 'documents' fanout exchange (document-lister)
#   indexer — consume from shortembeddings* queues (document-indexer variants)
#   search  — publish to default exchange for upload indexing, monitoring tag
#             for management API health checks (solr-search)
#   admin   — full administrator for management UI (not used by services)
#
# Environment variables (all have development defaults — override for production):
#   RABBITMQ_LISTER_PASS   (default: lister_dev_pass)
#   RABBITMQ_INDEXER_PASS  (default: indexer_dev_pass)
#   RABBITMQ_SEARCH_PASS   (default: search_dev_pass)
#   RABBITMQ_ADMIN_PASS    (default: admin_dev_pass)
# ──────────────────────────────────────────────────────────────────────────────

LISTER_PASS="${RABBITMQ_LISTER_PASS:-lister_dev_pass}"
INDEXER_PASS="${RABBITMQ_INDEXER_PASS:-indexer_dev_pass}"
SEARCH_PASS="${RABBITMQ_SEARCH_PASS:-search_dev_pass}"
ADMIN_PASS="${RABBITMQ_ADMIN_PASS:-admin_dev_pass}"

cat > /etc/rabbitmq/definitions.json << DEFS
{
  "users": [
    {
      "name": "lister",
      "password": "${LISTER_PASS}",
      "tags": ""
    },
    {
      "name": "indexer",
      "password": "${INDEXER_PASS}",
      "tags": ""
    },
    {
      "name": "search",
      "password": "${SEARCH_PASS}",
      "tags": "monitoring"
    },
    {
      "name": "admin",
      "password": "${ADMIN_PASS}",
      "tags": "administrator"
    }
  ],
  "vhosts": [
    {
      "name": "/"
    }
  ],
  "permissions": [
    {
      "user": "lister",
      "vhost": "/",
      "configure": "^documents$",
      "write": "^documents$",
      "read": "^$"
    },
    {
      "user": "indexer",
      "vhost": "/",
      "configure": "^(documents|shortembeddings.*)$",
      "write": "^documents$",
      "read": "^shortembeddings.*$"
    },
    {
      "user": "search",
      "vhost": "/",
      "configure": "^shortembeddings$",
      "write": "^$",
      "read": "^$"
    },
    {
      "user": "admin",
      "vhost": "/",
      "configure": ".*",
      "write": ".*",
      "read": ".*"
    }
  ],
  "exchanges": [
    {
      "name": "documents",
      "vhost": "/",
      "type": "fanout",
      "durable": true,
      "auto_delete": false,
      "internal": false,
      "arguments": {}
    }
  ],
  "queues": [
    {
      "name": "shortembeddings",
      "vhost": "/",
      "durable": true,
      "auto_delete": false,
      "arguments": {}
    },
    {
      "name": "shortembeddings_e5base",
      "vhost": "/",
      "durable": true,
      "auto_delete": false,
      "arguments": {}
    }
  ],
  "bindings": [
    {
      "source": "documents",
      "vhost": "/",
      "destination": "shortembeddings",
      "destination_type": "queue",
      "routing_key": "",
      "arguments": {}
    },
    {
      "source": "documents",
      "vhost": "/",
      "destination": "shortembeddings_e5base",
      "destination_type": "queue",
      "routing_key": "",
      "arguments": {}
    }
  ]
}
DEFS

echo "RabbitMQ definitions generated with per-service users: lister, indexer, search, admin"

# Hand off to the official RabbitMQ Docker entrypoint
exec /usr/local/bin/docker-entrypoint.sh "$@"
