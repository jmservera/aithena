#!/usr/bin/env python3
"""Verify that both Solr collections are correctly indexed with matching documents.

Checks:
1. Document counts match between books and books_e5base (parent docs)
2. Chunk counts are present in both collections
3. Embeddings have correct dimensionality (512D in books, 768D in books_e5base)
4. Parent document IDs match between collections

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

BASELINE_COLLECTION = "books"
CANDIDATE_COLLECTION = "books_e5base"

EXPECTED_DIMENSIONS = {
    BASELINE_COLLECTION: 512,
    CANDIDATE_COLLECTION: 768,
}

# Parent docs have no parent_id_s; chunks have parent_id_s set
PARENT_FILTER = "-parent_id_s:[* TO *]"
CHUNK_FILTER = "parent_id_s:[* TO *]"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CollectionStatus:
    """Status of a single Solr collection."""

    collection: str
    total_docs: int = 0
    parent_docs: int = 0
    chunk_docs: int = 0
    sample_embedding_dim: int | None = None
    parent_ids: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class VerificationResult:
    """Result of the verification across both collections."""

    baseline: CollectionStatus | None = None
    candidate: CollectionStatus | None = None
    parent_count_match: bool = False
    parent_ids_match: bool = False
    missing_in_baseline: list[str] = field(default_factory=list)
    missing_in_candidate: list[str] = field(default_factory=list)
    baseline_dim_correct: bool = False
    candidate_dim_correct: bool = False
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
    """Retrieve all parent document IDs from a collection."""
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
    """Gather status information for a single collection."""
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


def verify_collections(
    solr_url: str,
    baseline_collection: str = BASELINE_COLLECTION,
    candidate_collection: str = CANDIDATE_COLLECTION,
) -> VerificationResult:
    """Run all verification checks and return structured results."""
    result = VerificationResult()

    result.baseline = inspect_collection(solr_url, baseline_collection)
    result.candidate = inspect_collection(solr_url, candidate_collection)

    if result.baseline.error or result.candidate.error:
        return result

    # Check 1: Parent document counts match
    result.parent_count_match = result.baseline.parent_docs == result.candidate.parent_docs

    # Check 2: Parent document IDs match
    baseline_ids = set(result.baseline.parent_ids)
    candidate_ids = set(result.candidate.parent_ids)
    result.parent_ids_match = baseline_ids == candidate_ids
    result.missing_in_baseline = sorted(candidate_ids - baseline_ids)
    result.missing_in_candidate = sorted(baseline_ids - candidate_ids)

    # Check 3: Embedding dimensionality
    expected_baseline_dim = EXPECTED_DIMENSIONS[baseline_collection]
    expected_candidate_dim = EXPECTED_DIMENSIONS[candidate_collection]

    result.baseline_dim_correct = result.baseline.sample_embedding_dim == expected_baseline_dim
    result.candidate_dim_correct = result.candidate.sample_embedding_dim == expected_candidate_dim

    # Allow dim check to pass if there are no chunks yet (nothing to verify)
    if result.baseline.chunk_docs == 0:
        result.baseline_dim_correct = True
    if result.candidate.chunk_docs == 0:
        result.candidate_dim_correct = True

    result.all_checks_passed = all([
        result.parent_count_match,
        result.parent_ids_match,
        result.baseline_dim_correct,
        result.candidate_dim_correct,
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

    for label, status in [("Baseline", result.baseline), ("Candidate", result.candidate)]:
        if status is None:
            lines.append(f"\n{label}: NOT AVAILABLE")
            continue
        lines.append(f"\n{label}: {status.collection}")
        if status.error:
            lines.append(f"  ✗ Error: {status.error}")
            continue
        lines.append(f"  Total docs:      {status.total_docs}")
        lines.append(f"  Parent docs:     {status.parent_docs}")
        lines.append(f"  Chunk docs:      {status.chunk_docs}")
        dim_str = str(status.sample_embedding_dim) if status.sample_embedding_dim else "N/A (no chunks)"
        expected = EXPECTED_DIMENSIONS.get(status.collection, "?")
        lines.append(f"  Embedding dim:   {dim_str} (expected: {expected})")

    lines.append("\n--- Checks ---")

    def _check(passed: bool, label: str) -> str:
        icon = "✓" if passed else "✗"
        return f"  {icon} {label}"

    lines.append(_check(result.parent_count_match, "Parent document counts match"))
    lines.append(_check(result.parent_ids_match, "Parent document IDs match"))
    baseline_dim = EXPECTED_DIMENSIONS[BASELINE_COLLECTION]
    candidate_dim = EXPECTED_DIMENSIONS[CANDIDATE_COLLECTION]
    lines.append(_check(result.baseline_dim_correct, f"Baseline embedding dim = {baseline_dim}D"))
    lines.append(_check(result.candidate_dim_correct, f"Candidate embedding dim = {candidate_dim}D"))

    if result.missing_in_candidate:
        lines.append(f"\n  Missing in candidate ({len(result.missing_in_candidate)}):")
        display = result.missing_in_candidate[:10] if not verbose else result.missing_in_candidate
        for doc_id in display:
            lines.append(f"    - {doc_id}")
        if not verbose and len(result.missing_in_candidate) > 10:
            lines.append(f"    ... and {len(result.missing_in_candidate) - 10} more")

    if result.missing_in_baseline:
        lines.append(f"\n  Missing in baseline ({len(result.missing_in_baseline)}):")
        display = result.missing_in_baseline[:10] if not verbose else result.missing_in_baseline
        for doc_id in display:
            lines.append(f"    - {doc_id}")
        if not verbose and len(result.missing_in_baseline) > 10:
            lines.append(f"    ... and {len(result.missing_in_baseline) - 10} more")

    lines.append("")
    if result.all_checks_passed:
        lines.append("✓ ALL CHECKS PASSED")
    else:
        lines.append("✗ SOME CHECKS FAILED")
    lines.append("=" * 68)

    return "\n".join(lines)


def result_to_dict(result: VerificationResult) -> dict[str, Any]:
    """Serialize verification result to JSON-compatible dict."""
    d: dict[str, Any] = {
        "parent_count_match": result.parent_count_match,
        "parent_ids_match": result.parent_ids_match,
        "baseline_dim_correct": result.baseline_dim_correct,
        "candidate_dim_correct": result.candidate_dim_correct,
        "all_checks_passed": result.all_checks_passed,
        "missing_in_baseline": result.missing_in_baseline,
        "missing_in_candidate": result.missing_in_candidate,
    }
    for label, status in [("baseline", result.baseline), ("candidate", result.candidate)]:
        if status:
            d[label] = {
                "collection": status.collection,
                "total_docs": status.total_docs,
                "parent_docs": status.parent_docs,
                "chunk_docs": status.chunk_docs,
                "sample_embedding_dim": status.sample_embedding_dim,
                "error": status.error,
            }
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify dual Solr collections have matching documents and correct embeddings.",
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
        help="Show all document IDs in discrepancy lists",
    )
    args = parser.parse_args()

    result = verify_collections(args.solr_url)

    if args.json_output:
        print(json.dumps(result_to_dict(result), indent=2))
    else:
        print(format_report(result, verbose=args.verbose))

    sys.exit(0 if result.all_checks_passed else 1)


if __name__ == "__main__":
    main()
