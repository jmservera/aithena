#!/usr/bin/env python3
"""Trigger indexing of documents through both embedding pipelines.

Publishes document file paths to the RabbitMQ fanout exchange so that
both document-indexer (distiluse → books) and document-indexer-e5
(e5-base → books_e5base) receive and process every document.

The script is idempotent — re-running it re-publishes the same paths;
the indexers handle deduplication via Solr's unique key.

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
COLLECTIONS = ("books", "books_e5base")


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
    """Publish file paths to the fanout exchange. Returns count published."""
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


def get_collection_counts(
    solr_host: str = SOLR_HOST,
    solr_port: int = SOLR_PORT,
    collections: tuple[str, ...] = COLLECTIONS,
) -> dict[str, int | str]:
    """Query Solr for document counts in each collection."""
    counts: dict[str, int | str] = {}
    for col in collections:
        url = f"http://{solr_host}:{solr_port}/solr/{col}/select?q=*:*&rows=0&wt=json"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            counts[col] = resp.json()["response"]["numFound"]
        except Exception as exc:
            counts[col] = f"error: {exc}"
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index test corpus through both embedding pipelines.",
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
        help="Only show current collection document counts",
    )
    args = parser.parse_args()

    # Status-only mode
    if args.status_only:
        print("Current collection status:")
        counts = get_collection_counts()
        for col, count in counts.items():
            print(f"  {col}: {count} documents")
        return

    # Discover documents
    print(f"Discovering documents in {args.base_path} (pattern: {args.wildcard})...")
    files = discover_documents(args.base_path, args.wildcard, args.limit)

    if not files:
        print(f"No documents found matching '{args.wildcard}' in {args.base_path}")
        print("Ensure BASE_PATH is set to a directory containing documents.")
        sys.exit(1)

    print(f"Found {len(files)} document(s)")

    if args.dry_run:
        print("\n--- Dry Run (documents that would be published) ---")
        for f in files:
            print(f"  {f}")
        print(f"\nTotal: {len(files)} documents → fanout exchange '{args.exchange}'")
        print("Both indexers (distiluse → books, e5-base → books_e5base) would receive all documents.")
        return

    # Publish
    print(f"\nPublishing {len(files)} documents to exchange '{args.exchange}'...")
    print("Both indexers will receive every document via the fanout exchange.")
    count = publish_documents(files, exchange=args.exchange)
    print(f"\n✓ Published {count} documents to '{args.exchange}' fanout exchange")
    print("  → document-indexer (distiluse → books collection)")
    print("  → document-indexer-e5 (e5-base → books_e5base collection)")

    # Show current status
    print("\nChecking current collection status...")
    counts = get_collection_counts()
    if counts:
        for col, doc_count in counts.items():
            print(f"  {col}: {doc_count} documents")
        print("\nNote: Indexing is asynchronous. Re-run with --status-only to check progress.")
    else:
        print("  (Could not query Solr — services may not be running locally)")


if __name__ == "__main__":
    main()
