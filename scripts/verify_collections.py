#!/usr/bin/env python3
"""Verify that the Solr books collection is correctly indexed.

Checks:
1. The books collection is accessible and contains documents
2. Parent and chunk documents are present
3. Embeddings have correct dimensionality (768D for e5-base)

Usage:
    python scripts/verify_collections.py
    python scripts/verify_collections.py --solr-url http://solr:8983
    python scripts/verify_collections.py --json          # machine-readable output
    python scripts/verify_collections.py --verbose       # show per-document details

Environment variables:
    SOLR_HOST (default: localhost), SOLR_PORT (default: 8983)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


SOLR_HOST = os.environ.get("SOLR_HOST", "localhost")
SOLR_PORT = int(os.environ.get("SOLR_PORT", 8983))

COLLECTION = "books"
EXPECTED_EMBEDDING_DIM = 768

# Parent docs have no parent_id_s; chunks have parent_id_s set
PARENT_FILTER = "-parent_id_s:[* TO *]"
CHUNK_FILTER = "parent_id_s:[* TO *]"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CollectionStatus:
    """Status of the Solr collection."""

    collection: str
    total_docs: int = 0
    parent_docs: int = 0
    chunk_docs: int = 0
    sample_embedding_dim: int | None = None
    parent_ids: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class VerificationResult:
    """Result of the verification checks."""

    status: CollectionStatus | None = None
    has_documents: bool = False
    has_chunks: bool = False
    embedding_dim_correct: bool = False
    all_checks_passed: bool = False


# ---------------------------------------------------------------------------
# Solr queries
# ---------------------------------------------------------------------------


def _solr_query(
    solr_url: str,
    collection: str,
    params: dict[str, Any],
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Execute a Solr select query and return the JSON response."""
    url = f"{solr_url}/solr/{collection}/select"
    params.setdefault("wt", "json")
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_doc_count(solr_url: str, collection: str, fq: str | None = None) -> int:
    """Get document count, optionally filtered."""
    params: dict[str, Any] = {"q": "*:*", "rows": 0}
    if fq:
        params["fq"] = fq
    data = _solr_query(solr_url, collection, params)
    return data["response"]["numFound"]


def get_parent_ids(solr_url: str, collection: str, max_rows: int = 50000) -> list[str]:
    """Retrieve all parent document IDs from the collection."""
    params: dict[str, Any] = {
        "q": "*:*",
        "fq": PARENT_FILTER,
        "fl": "id",
        "rows": max_rows,
        "sort": "id asc",
    }
    data = _solr_query(solr_url, collection, params)
    return [doc["id"] for doc in data["response"]["docs"]]


def get_sample_embedding_dim(solr_url: str, collection: str) -> int | None:
    """Get the dimensionality of the first chunk embedding found."""
    params: dict[str, Any] = {
        "q": "*:*",
        "fq": CHUNK_FILTER,
        "fl": "id,embedding_v",
        "rows": 1,
    }
    data = _solr_query(solr_url, collection, params)
    docs = data["response"]["docs"]
    if not docs:
        return None
    embedding = docs[0].get("embedding_v")
    if embedding is None:
        return None
    return len(embedding)


# ---------------------------------------------------------------------------
# Collection inspection
# ---------------------------------------------------------------------------


def inspect_collection(solr_url: str, collection: str) -> CollectionStatus:
    """Gather status information for the collection."""
    status = CollectionStatus(collection=collection)
    try:
        status.total_docs = get_doc_count(solr_url, collection)
        status.parent_docs = get_doc_count(solr_url, collection, fq=PARENT_FILTER)
        status.chunk_docs = get_doc_count(solr_url, collection, fq=CHUNK_FILTER)
        status.sample_embedding_dim = get_sample_embedding_dim(solr_url, collection)
        status.parent_ids = get_parent_ids(solr_url, collection)
    except Exception as exc:
        status.error = str(exc)
    return status


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------


def verify_collection(
    solr_url: str,
    collection: str = COLLECTION,
) -> VerificationResult:
    """Run all verification checks and return structured results."""
    result = VerificationResult()

    result.status = inspect_collection(solr_url, collection)

    if result.status.error:
        return result

    # Check 1: Collection has documents
    result.has_documents = result.status.parent_docs > 0

    # Check 2: Collection has chunks
    result.has_chunks = result.status.chunk_docs > 0

    # Check 3: Embedding dimensionality is 768D (e5-base)
    if result.status.chunk_docs == 0:
        result.embedding_dim_correct = True  # no chunks to verify
    else:
        result.embedding_dim_correct = result.status.sample_embedding_dim == EXPECTED_EMBEDDING_DIM

    result.all_checks_passed = all([
        result.has_documents,
        result.has_chunks,
        result.embedding_dim_correct,
    ])

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_report(result: VerificationResult, verbose: bool = False) -> str:
    """Format a human-readable verification report."""
    lines: list[str] = []
    lines.append("=" * 68)
    lines.append("COLLECTION VERIFICATION REPORT")
    lines.append("=" * 68)

    status = result.status
    if status is None:
        lines.append("\nCollection: NOT AVAILABLE")
    elif status.error:
        lines.append(f"\nCollection: {status.collection}")
        lines.append(f"  \u2717 Error: {status.error}")
    else:
        lines.append(f"\nCollection: {status.collection}")
        lines.append(f"  Total docs:      {status.total_docs}")
        lines.append(f"  Parent docs:     {status.parent_docs}")
        lines.append(f"  Chunk docs:      {status.chunk_docs}")
        dim_str = str(status.sample_embedding_dim) if status.sample_embedding_dim else "N/A (no chunks)"
        lines.append(f"  Embedding dim:   {dim_str} (expected: {EXPECTED_EMBEDDING_DIM})")

        if verbose and status.parent_ids:
            lines.append(f"\n  Parent document IDs ({len(status.parent_ids)}):")
            for doc_id in status.parent_ids:
                lines.append(f"    - {doc_id}")

    lines.append("\n--- Checks ---")

    def _check(passed: bool, label: str) -> str:
        icon = "\u2713" if passed else "\u2717"
        return f"  {icon} {label}"

    lines.append(_check(result.has_documents, "Collection has parent documents"))
    lines.append(_check(result.has_chunks, "Collection has chunk documents"))
    lines.append(_check(result.embedding_dim_correct, f"Embedding dim = {EXPECTED_EMBEDDING_DIM}D (e5-base)"))

    lines.append("")
    if result.all_checks_passed:
        lines.append("\u2713 ALL CHECKS PASSED")
    else:
        lines.append("\u2717 SOME CHECKS FAILED")
    lines.append("=" * 68)

    return "\n".join(lines)


def result_to_dict(result: VerificationResult) -> dict[str, Any]:
    """Serialize verification result to JSON-compatible dict."""
    d: dict[str, Any] = {
        "has_documents": result.has_documents,
        "has_chunks": result.has_chunks,
        "embedding_dim_correct": result.embedding_dim_correct,
        "all_checks_passed": result.all_checks_passed,
    }
    if result.status:
        d["collection"] = {
            "name": result.status.collection,
            "total_docs": result.status.total_docs,
            "parent_docs": result.status.parent_docs,
            "chunk_docs": result.status.chunk_docs,
            "sample_embedding_dim": result.status.sample_embedding_dim,
            "error": result.status.error,
        }
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Solr books collection has correct documents and e5-base embeddings.",
    )
    parser.add_argument(
        "--solr-url",
        default=f"http://{SOLR_HOST}:{SOLR_PORT}",
        help="Solr base URL (default: http://localhost:8983)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all document IDs",
    )
    args = parser.parse_args()

    result = verify_collection(args.solr_url)

    if args.json_output:
        print(json.dumps(result_to_dict(result), indent=2))
    else:
        print(format_report(result, verbose=args.verbose))

    sys.exit(0 if result.all_checks_passed else 1)


if __name__ == "__main__":
    main()
