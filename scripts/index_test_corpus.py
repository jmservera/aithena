#!/usr/bin/env python3
"""Trigger indexing of documents through the e5-base embedding pipeline.

Publishes document file paths to the RabbitMQ exchange so that the
document-indexer (e5-base → books) receives and processes every document.

The script is idempotent — re-running it re-publishes the same paths;
the indexer handles deduplication via Solr's unique key.

Usage:
    python scripts/index_test_corpus.py                          # defaults
    python scripts/index_test_corpus.py --base-path /data/docs   # custom path
    python scripts/index_test_corpus.py --limit 10               # first N files
    python scripts/index_test_corpus.py --dry-run                # list without publishing

Environment variables (override defaults):
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS
    BASE_PATH, DOCUMENT_WILDCARD, EXCHANGE_NAME
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import uuid

import pika
import requests

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")
BASE_PATH = os.environ.get("BASE_PATH", "/data/documents/")
DOCUMENT_WILDCARD = os.environ.get("DOCUMENT_WILDCARD", "*.pdf")
EXCHANGE_NAME = os.environ.get("EXCHANGE_NAME", "documents")

SOLR_HOST = os.environ.get("SOLR_HOST", "localhost")
SOLR_PORT = int(os.environ.get("SOLR_PORT", 8983))
COLLECTION = "books"


def discover_documents(base_path: str, wildcard: str, limit: int | None = None) -> list[str]:
    """Recursively find documents matching the wildcard pattern."""
    pattern = os.path.join(base_path, "**", wildcard)
    files = sorted(glob.glob(pattern, recursive=True))
    if limit is not None:
        files = files[:limit]
    return files


def publish_documents(
    files: list[str],
    host: str = RABBITMQ_HOST,
    port: int = RABBITMQ_PORT,
    user: str = RABBITMQ_USER,
    password: str = RABBITMQ_PASS,
    exchange: str = EXCHANGE_NAME,
) -> int:
    """Publish file paths to the exchange. Returns count published."""
    credentials = pika.PlainCredentials(user, password)
    params = pika.ConnectionParameters(host=host, port=port, credentials=credentials)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.exchange_declare(exchange=exchange, exchange_type="fanout", durable=True)

    published = 0
    for filepath in files:
        correlation_id = str(uuid.uuid4())
        channel.basic_publish(
            exchange=exchange,
            routing_key="",
            body=filepath,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers={"X-Correlation-ID": correlation_id},
            ),
        )
        published += 1
        if published % 10 == 0:
            print(f"  Published {published}/{len(files)}...", flush=True)

    connection.close()
    return published


def get_collection_count(
    solr_host: str = SOLR_HOST,
    solr_port: int = SOLR_PORT,
    collection: str = COLLECTION,
) -> int | str:
    """Query Solr for document count in the collection."""
    url = f"http://{solr_host}:{solr_port}/solr/{collection}/select?q=*:*&rows=0&wt=json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()["response"]["numFound"]
    except Exception as exc:
        return f"error: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index test corpus through the e5-base embedding pipeline.",
    )
    parser.add_argument(
        "--base-path",
        default=BASE_PATH,
        help=f"Root directory containing documents (default: {BASE_PATH})",
    )
    parser.add_argument(
        "--wildcard",
        default=DOCUMENT_WILDCARD,
        help=f"File pattern to match (default: {DOCUMENT_WILDCARD})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N documents (default: all)",
    )
    parser.add_argument(
        "--exchange",
        default=EXCHANGE_NAME,
        help=f"RabbitMQ exchange name (default: {EXCHANGE_NAME})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List documents without publishing",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only show current collection document count",
    )
    args = parser.parse_args()

    # Status-only mode
    if args.status_only:
        print("Current collection status:")
        count = get_collection_count()
        print(f"  {COLLECTION}: {count} documents")
        return

    # Discover documents
    print(f"Discovering documents in {args.base_path} (pattern: {args.wildcard})...")
    files = discover_documents(args.base_path, args.wildcard, args.limit)

    if not files:
        print(f"No documents found matching \'{args.wildcard}\' in {args.base_path}")
        print("Ensure BASE_PATH is set to a directory containing documents.")
        sys.exit(1)

    print(f"Found {len(files)} document(s)")

    if args.dry_run:
        print("\n--- Dry Run (documents that would be published) ---")
        for f in files:
            print(f"  {f}")
        print(f"\nTotal: {len(files)} documents \u2192 exchange \'{args.exchange}\'")
        print(f"The document-indexer (e5-base \u2192 {COLLECTION}) would receive all documents.")
        return

    # Publish
    print(f"\nPublishing {len(files)} documents to exchange \'{args.exchange}\'...")
    count = publish_documents(files, exchange=args.exchange)
    print(f"\n\u2713 Published {count} documents to \'{args.exchange}\' exchange")
    print(f"  \u2192 document-indexer (e5-base \u2192 {COLLECTION} collection)")

    # Show current status
    print("\nChecking current collection status...")
    doc_count = get_collection_count()
    print(f"  {COLLECTION}: {doc_count} documents")
    print("\nNote: Indexing is asynchronous. Re-run with --status-only to check progress.")


if __name__ == "__main__":
    main()
