"""
Search latency benchmarks for Aithena.

Measures search performance across configurable index sizes for:
    - Keyword (BM25) search via solr-search API
    - Semantic (kNN) search via embeddings + Solr
    - Hybrid (RRF) search combining both
    - Faceted search with filters (language, author, year)
    - Embedding generation in isolation
    - Concurrent user search simulation
    - Cold-start latency after service restart

Index sizes tested: 1K, 5K, 10K, 25K, 50K pages.

Latency percentiles captured per (index-size, search-mode) pair:
    - p50, p95, p99
    - mean, min, max

Results are written as JSON/CSV to ``tests/stress/results/<timestamp>/``.

PRD targets (medium deployment, §6.1):
    p50 < 500 ms, p95 < 1500 ms, p99 < 3000 ms

Tests requiring Docker are marked ``@pytest.mark.docker`` and skip
gracefully when infrastructure is unavailable.  Pure metric-calculation
and report-generation logic is covered by unit tests that run locally.
"""

from __future__ import annotations

import csv
import io
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Index size presets (number of pages in Solr)
# ---------------------------------------------------------------------------

INDEX_SIZES: dict[str, int] = {
    "1k": 1_000,
    "5k": 5_000,
    "10k": 10_000,
    "25k": 25_000,
    "50k": 50_000,
}

# ---------------------------------------------------------------------------
# Search modes supported by the solr-search API
# ---------------------------------------------------------------------------

SEARCH_MODES: list[str] = ["keyword", "semantic", "hybrid"]

# ---------------------------------------------------------------------------
# Query corpus — 50 representative queries across categories
# ---------------------------------------------------------------------------

QUERY_CORPUS: list[dict[str, str]] = [
    # Single-word queries
    {"q": "python", "type": "single_word"},
    {"q": "mathematics", "type": "single_word"},
    {"q": "history", "type": "single_word"},
    {"q": "science", "type": "single_word"},
    {"q": "philosophy", "type": "single_word"},
    {"q": "algorithms", "type": "single_word"},
    {"q": "biology", "type": "single_word"},
    {"q": "economics", "type": "single_word"},
    {"q": "physics", "type": "single_word"},
    {"q": "literature", "type": "single_word"},
    # Multi-word queries
    {"q": "machine learning", "type": "multi_word"},
    {"q": "data structures", "type": "multi_word"},
    {"q": "artificial intelligence", "type": "multi_word"},
    {"q": "software engineering", "type": "multi_word"},
    {"q": "world history", "type": "multi_word"},
    {"q": "quantum mechanics", "type": "multi_word"},
    {"q": "linear algebra", "type": "multi_word"},
    {"q": "operating systems", "type": "multi_word"},
    {"q": "deep learning", "type": "multi_word"},
    {"q": "organic chemistry", "type": "multi_word"},
    # Phrase queries
    {"q": '"design patterns"', "type": "phrase"},
    {"q": '"natural language processing"', "type": "phrase"},
    {"q": '"computer vision"', "type": "phrase"},
    {"q": '"functional programming"', "type": "phrase"},
    {"q": '"graph theory"', "type": "phrase"},
    {"q": '"distributed systems"', "type": "phrase"},
    {"q": '"neural networks"', "type": "phrase"},
    {"q": '"climate change"', "type": "phrase"},
    {"q": '"human anatomy"', "type": "phrase"},
    {"q": '"number theory"', "type": "phrase"},
    # Natural-language questions
    {"q": "how do databases handle concurrent transactions", "type": "question"},
    {"q": "what is the theory of relativity", "type": "question"},
    {"q": "explain object oriented programming principles", "type": "question"},
    {"q": "how does photosynthesis work in plants", "type": "question"},
    {"q": "what causes economic recessions", "type": "question"},
    {"q": "how to implement a search engine from scratch", "type": "question"},
    {"q": "what are the main causes of the French revolution", "type": "question"},
    {"q": "how do neural networks learn representations", "type": "question"},
    {"q": "explain the fundamentals of cryptography", "type": "question"},
    {"q": "what is the difference between TCP and UDP", "type": "question"},
    # Multilingual queries (Spanish, Catalan, French, English)
    {"q": "inteligencia artificial aplicaciones", "type": "multilingual_es"},
    {"q": "programación orientada a objetos", "type": "multilingual_es"},
    {"q": "intel·ligència artificial", "type": "multilingual_ca"},
    {"q": "aprenentatge automàtic", "type": "multilingual_ca"},
    {"q": "apprentissage automatique", "type": "multilingual_fr"},
    {"q": "réseaux de neurones artificiels", "type": "multilingual_fr"},
    {"q": "introduction to computer science", "type": "multilingual_en"},
    {"q": "advanced statistical methods", "type": "multilingual_en"},
    {"q": "ciencia de datos y estadística", "type": "multilingual_es"},
    {"q": "bases de données relationnelles", "type": "multilingual_fr"},
]

# Facet filter combinations for faceted search overhead measurement
FACET_FILTERS: list[dict[str, str]] = [
    {"fq_language": "English"},
    {"fq_language": "Spanish"},
    {"fq_author": "Test Author"},
    {"fq_year": "2020"},
    {"fq_language": "English", "fq_year": "2020"},
    {"fq_language": "English", "fq_author": "Test Author"},
]

# Concurrency levels for simultaneous user simulation
CONCURRENCY_LEVELS: list[int] = [5, 10, 25]

# Default repetitions per query for stable percentiles
DEFAULT_REPETITIONS: int = 100

# PRD §6.1 latency targets (medium deployment, milliseconds)
LATENCY_TARGETS_MS: dict[str, float] = {
    "p50": 500.0,
    "p95": 1500.0,
    "p99": 3000.0,
}


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchBenchmarkConfig:
    """Configuration for a search latency benchmark run."""

    index_size_label: str
    index_size_pages: int
    search_mode: str
    repetitions: int = DEFAULT_REPETITIONS

    def __post_init__(self) -> None:
        if self.index_size_pages < 0:
            msg = f"index_size_pages must be >= 0, got {self.index_size_pages}"
            raise ValueError(msg)
        if self.search_mode not in SEARCH_MODES:
            msg = f"search_mode must be one of {SEARCH_MODES}, got {self.search_mode!r}"
            raise ValueError(msg)
        if self.repetitions < 1:
            msg = f"repetitions must be >= 1, got {self.repetitions}"
            raise ValueError(msg)


@dataclass(frozen=True)
class ConcurrencyConfig:
    """Configuration for concurrent search simulation."""

    concurrent_users: int
    search_mode: str = "keyword"

    def __post_init__(self) -> None:
        if self.concurrent_users < 1:
            msg = f"concurrent_users must be >= 1, got {self.concurrent_users}"
            raise ValueError(msg)
        if self.search_mode not in SEARCH_MODES:
            msg = f"search_mode must be one of {SEARCH_MODES}, got {self.search_mode!r}"
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Metric result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LatencyPercentiles:
    """Computed latency percentiles for a set of measurements."""

    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    stddev_ms: float = 0.0
    sample_count: int = 0


@dataclass
class SearchLatencyMetrics:
    """Aggregated metrics for one search latency benchmark run."""

    index_size_label: str
    index_size_pages: int
    search_mode: str
    query_count: int

    # Latency
    latency: LatencyPercentiles = field(default_factory=LatencyPercentiles)

    # Throughput
    queries_per_second: float = 0.0
    total_elapsed_seconds: float = 0.0

    # Outcomes
    succeeded: int = 0
    failed: int = 0
    failure_rate_percent: float = 0.0

    # Breakdown by query type
    latency_by_query_type: dict[str, dict[str, float]] = field(default_factory=dict)

    # Metadata
    started_at: str = ""
    finished_at: str = ""


@dataclass
class FacetedSearchMetrics:
    """Metrics for faceted search overhead measurement."""

    index_size_label: str
    base_latency_ms: float = 0.0
    faceted_latency_ms: float = 0.0
    overhead_ms: float = 0.0
    overhead_percent: float = 0.0
    filter_counts: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class EmbeddingLatencyMetrics:
    """Metrics for isolated embedding generation time."""

    query_count: int = 0
    latency: LatencyPercentiles = field(default_factory=LatencyPercentiles)
    tokens_per_second: float = 0.0


@dataclass
class ConcurrentSearchMetrics:
    """Metrics for concurrent user search simulation."""

    concurrent_users: int = 0
    search_mode: str = ""
    per_user_latency: LatencyPercentiles = field(default_factory=LatencyPercentiles)
    total_queries: int = 0
    total_elapsed_seconds: float = 0.0
    throughput_qps: float = 0.0
    error_count: int = 0


@dataclass
class ColdStartMetrics:
    """Metrics for cold-start latency measurement."""

    first_query_ms: float = 0.0
    warmed_up_p50_ms: float = 0.0
    warmup_overhead_ms: float = 0.0
    warmup_overhead_percent: float = 0.0


# ---------------------------------------------------------------------------
# Pure metric helpers (unit-testable, no Docker required)
# ---------------------------------------------------------------------------


def calculate_percentiles(latencies_ms: list[float]) -> LatencyPercentiles:
    """Compute p50, p95, p99, mean, min, max, stddev from latency samples.

    >>> p = calculate_percentiles([100.0, 200.0, 300.0, 400.0, 500.0])
    >>> p.p50_ms
    300.0
    >>> p.mean_ms
    300.0
    >>> p.min_ms
    100.0
    >>> p.max_ms
    500.0
    >>> p.sample_count
    5
    """
    if not latencies_ms:
        return LatencyPercentiles()

    sorted_latencies = sorted(latencies_ms)
    n = len(sorted_latencies)

    def _percentile(data: list[float], pct: float) -> float:
        """Compute the pct-th percentile using linear interpolation."""
        if not data:
            return 0.0
        k = (pct / 100.0) * (len(data) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(data[int(k)], 2)
        return round(data[f] * (c - k) + data[c] * (k - f), 2)

    stddev = round(statistics.stdev(sorted_latencies), 2) if n > 1 else 0.0

    return LatencyPercentiles(
        p50_ms=_percentile(sorted_latencies, 50),
        p95_ms=_percentile(sorted_latencies, 95),
        p99_ms=_percentile(sorted_latencies, 99),
        mean_ms=round(statistics.mean(sorted_latencies), 2),
        min_ms=round(sorted_latencies[0], 2),
        max_ms=round(sorted_latencies[-1], 2),
        stddev_ms=stddev,
        sample_count=n,
    )


def calculate_throughput_qps(query_count: int, elapsed_seconds: float) -> float:
    """Return queries per second.

    >>> calculate_throughput_qps(100, 10.0)
    10.0
    >>> calculate_throughput_qps(0, 10.0)
    0.0
    >>> calculate_throughput_qps(50, 0.0)
    0.0
    """
    if query_count < 0:
        msg = f"query_count must be >= 0, got {query_count}"
        raise ValueError(msg)
    if elapsed_seconds < 0:
        msg = f"elapsed_seconds must be >= 0, got {elapsed_seconds}"
        raise ValueError(msg)
    if elapsed_seconds == 0:
        return 0.0
    return round(query_count / elapsed_seconds, 2)


def calculate_failure_rate(succeeded: int, failed: int) -> float:
    """Return failure rate as a percentage.

    >>> calculate_failure_rate(95, 5)
    5.0
    >>> calculate_failure_rate(0, 0)
    0.0
    """
    if succeeded < 0:
        msg = f"succeeded must be >= 0, got {succeeded}"
        raise ValueError(msg)
    if failed < 0:
        msg = f"failed must be >= 0, got {failed}"
        raise ValueError(msg)
    total = succeeded + failed
    if total == 0:
        return 0.0
    return round((failed / total) * 100.0, 2)


def calculate_facet_overhead(
    base_latency_ms: float, faceted_latency_ms: float
) -> tuple[float, float]:
    """Compute the overhead of faceted search vs base search.

    Returns (overhead_ms, overhead_percent).

    >>> calculate_facet_overhead(100.0, 150.0)
    (50.0, 50.0)
    >>> calculate_facet_overhead(0.0, 50.0)
    (50.0, 0.0)
    """
    overhead_ms = round(faceted_latency_ms - base_latency_ms, 2)
    if base_latency_ms > 0:
        overhead_pct = round((overhead_ms / base_latency_ms) * 100.0, 2)
    else:
        overhead_pct = 0.0
    return overhead_ms, overhead_pct


def calculate_cold_start_overhead(
    first_query_ms: float, warmed_p50_ms: float
) -> tuple[float, float]:
    """Compute cold-start overhead vs warmed-up p50.

    Returns (overhead_ms, overhead_percent).

    >>> calculate_cold_start_overhead(500.0, 100.0)
    (400.0, 400.0)
    >>> calculate_cold_start_overhead(100.0, 0.0)
    (100.0, 0.0)
    """
    overhead_ms = round(first_query_ms - warmed_p50_ms, 2)
    if warmed_p50_ms > 0:
        overhead_pct = round((overhead_ms / warmed_p50_ms) * 100.0, 2)
    else:
        overhead_pct = 0.0
    return overhead_ms, overhead_pct


def group_latencies_by_query_type(
    queries: list[dict[str, str]],
    latencies_ms: list[float],
) -> dict[str, dict[str, float]]:
    """Group latencies by query type and compute per-type p50.

    >>> qs = [{"q": "a", "type": "single"}, {"q": "b", "type": "phrase"}]
    >>> lats = [100.0, 200.0]
    >>> result = group_latencies_by_query_type(qs, lats)
    >>> result["single"]["p50_ms"]
    100.0
    >>> result["phrase"]["p50_ms"]
    200.0
    """
    by_type: dict[str, list[float]] = {}
    for query, latency in zip(queries, latencies_ms):
        qtype = query.get("type", "unknown")
        by_type.setdefault(qtype, []).append(latency)

    result: dict[str, dict[str, float]] = {}
    for qtype, lats in by_type.items():
        pcts = calculate_percentiles(lats)
        result[qtype] = {
            "p50_ms": pcts.p50_ms,
            "p95_ms": pcts.p95_ms,
            "mean_ms": pcts.mean_ms,
            "count": float(pcts.sample_count),
        }
    return result


def build_search_latency_metrics(
    *,
    config: SearchBenchmarkConfig,
    latencies_ms: list[float],
    queries: list[dict[str, str]],
    succeeded: int,
    failed: int,
    total_elapsed_seconds: float,
    started_at: str,
    finished_at: str,
) -> SearchLatencyMetrics:
    """Assemble a ``SearchLatencyMetrics`` from raw observations."""
    percentiles = calculate_percentiles(latencies_ms)
    query_count = succeeded + failed

    return SearchLatencyMetrics(
        index_size_label=config.index_size_label,
        index_size_pages=config.index_size_pages,
        search_mode=config.search_mode,
        query_count=query_count,
        latency=percentiles,
        queries_per_second=calculate_throughput_qps(succeeded, total_elapsed_seconds),
        total_elapsed_seconds=round(total_elapsed_seconds, 2),
        succeeded=succeeded,
        failed=failed,
        failure_rate_percent=calculate_failure_rate(succeeded, failed),
        latency_by_query_type=group_latencies_by_query_type(queries, latencies_ms),
        started_at=started_at,
        finished_at=finished_at,
    )


# ---------------------------------------------------------------------------
# Response parsers (unit-testable, no Docker required)
# ---------------------------------------------------------------------------


def parse_search_response(response_json: dict) -> dict[str, Any]:
    """Parse a solr-search API search response.

    >>> parse_search_response({"total": 42, "results": [{"id": "1"}], "mode": "keyword"})
    {'total': 42, 'result_count': 1, 'mode': 'keyword'}
    """
    return {
        "total": response_json.get("total", 0),
        "result_count": len(response_json.get("results", [])),
        "mode": response_json.get("mode", "unknown"),
    }


def parse_facets_response(response_json: dict) -> dict[str, int]:
    """Parse a solr-search facets response, returning facet field counts.

    >>> parse_facets_response({"facets": {"author": [{"value": "A", "count": 3}], "year": []}})
    {'author': 1, 'year': 0}
    """
    facets = response_json.get("facets", {})
    return {name: len(values) for name, values in facets.items()}


def parse_embeddings_response(response_json: dict) -> dict[str, Any]:
    """Parse an embeddings-server response.

    >>> parse_embeddings_response({"data": [{"embedding": [0.1]*512}], "model": "m1"})
    {'embedding_count': 1, 'dimension': 512, 'model': 'm1'}
    """
    data = response_json.get("data", [])
    dim = len(data[0].get("embedding", [])) if data else 0
    return {
        "embedding_count": len(data),
        "dimension": dim,
        "model": response_json.get("model", "unknown"),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_latency_report(metrics: SearchLatencyMetrics) -> dict[str, Any]:
    """Build a JSON-serialisable report dict from search latency metrics."""
    report = asdict(metrics)
    report["_generated_at"] = datetime.now(tz=UTC).isoformat()
    report["_version"] = "1.0.0"

    # PRD pass/fail against latency targets
    latency = metrics.latency
    report["targets"] = LATENCY_TARGETS_MS
    report["passed"] = (
        latency.p50_ms <= LATENCY_TARGETS_MS["p50"]
        and latency.p95_ms <= LATENCY_TARGETS_MS["p95"]
        and latency.p99_ms <= LATENCY_TARGETS_MS["p99"]
        and metrics.failure_rate_percent < 5.0
    )
    report["pass_criteria"] = {
        "p50_ms": f"<= {LATENCY_TARGETS_MS['p50']}",
        "p95_ms": f"<= {LATENCY_TARGETS_MS['p95']}",
        "p99_ms": f"<= {LATENCY_TARGETS_MS['p99']}",
        "failure_rate_percent": "< 5.0",
    }
    return report


def generate_comparison_report(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine multiple run reports into a comparison table."""
    if not reports:
        return {"runs": [], "comparison": {}}

    comparison: dict[str, Any] = {
        "runs": [],
        "comparison": {
            "fastest_p50": None,
            "fastest_p95": None,
            "highest_throughput": None,
        },
    }

    best_p50 = float("inf")
    best_p95 = float("inf")
    best_qps = 0.0

    for r in reports:
        summary = {
            "index_size_label": r.get("index_size_label", "unknown"),
            "search_mode": r.get("search_mode", "unknown"),
            "p50_ms": r.get("latency", {}).get("p50_ms", 0),
            "p95_ms": r.get("latency", {}).get("p95_ms", 0),
            "p99_ms": r.get("latency", {}).get("p99_ms", 0),
            "queries_per_second": r.get("queries_per_second", 0),
            "failure_rate_percent": r.get("failure_rate_percent", 0),
            "passed": r.get("passed", False),
        }
        comparison["runs"].append(summary)

        p50 = summary["p50_ms"]
        if p50 > 0 and p50 < best_p50:
            best_p50 = p50
            comparison["comparison"]["fastest_p50"] = summary

        p95 = summary["p95_ms"]
        if p95 > 0 and p95 < best_p95:
            best_p95 = p95
            comparison["comparison"]["fastest_p95"] = summary

        qps = summary["queries_per_second"]
        if qps > best_qps:
            best_qps = qps
            comparison["comparison"]["highest_throughput"] = summary

    comparison["_generated_at"] = datetime.now(tz=UTC).isoformat()
    return comparison


def write_report(report: dict[str, Any], output_dir: Path, filename: str) -> Path:
    """Write a report dict to a JSON file, returning the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return path


def write_csv_report(
    reports: list[dict[str, Any]], output_dir: Path, filename: str
) -> Path:
    """Write latency reports as a CSV file for analysis tools."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.csv"

    fieldnames = [
        "index_size_label",
        "index_size_pages",
        "search_mode",
        "query_count",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "mean_ms",
        "min_ms",
        "max_ms",
        "stddev_ms",
        "queries_per_second",
        "failure_rate_percent",
        "passed",
    ]

    rows: list[dict[str, Any]] = []
    for r in reports:
        latency = r.get("latency", {})
        rows.append({
            "index_size_label": r.get("index_size_label", ""),
            "index_size_pages": r.get("index_size_pages", 0),
            "search_mode": r.get("search_mode", ""),
            "query_count": r.get("query_count", 0),
            "p50_ms": latency.get("p50_ms", 0),
            "p95_ms": latency.get("p95_ms", 0),
            "p99_ms": latency.get("p99_ms", 0),
            "mean_ms": latency.get("mean_ms", 0),
            "min_ms": latency.get("min_ms", 0),
            "max_ms": latency.get("max_ms", 0),
            "stddev_ms": latency.get("stddev_ms", 0),
            "queries_per_second": r.get("queries_per_second", 0),
            "failure_rate_percent": r.get("failure_rate_percent", 0),
            "passed": r.get("passed", False),
        })

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue())
    return path


# ---------------------------------------------------------------------------
# Docker service helpers (used by integration tests)
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Return True if Docker daemon is reachable."""
    try:
        import docker as docker_sdk

        client = docker_sdk.from_env()
        client.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def _search_api_query(
    search_api_url: str,
    query: str,
    mode: str = "keyword",
    extra_params: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[float, dict]:
    """Execute a single search query and return (latency_ms, response_json).

    Raises on HTTP errors or connection failures.
    """
    import requests

    params: dict[str, str] = {"q": query, "mode": mode, "page_size": "20"}
    if extra_params:
        params.update(extra_params)

    start = time.monotonic()
    resp = requests.get(f"{search_api_url}/search", params=params, timeout=timeout)
    elapsed_ms = (time.monotonic() - start) * 1000.0
    resp.raise_for_status()
    return round(elapsed_ms, 2), resp.json()


def _facets_api_query(
    search_api_url: str,
    query: str,
    filters: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[float, dict]:
    """Execute a facets query and return (latency_ms, response_json)."""
    import requests

    params: dict[str, str] = {"q": query}
    if filters:
        params.update(filters)

    start = time.monotonic()
    resp = requests.get(f"{search_api_url}/facets", params=params, timeout=timeout)
    elapsed_ms = (time.monotonic() - start) * 1000.0
    resp.raise_for_status()
    return round(elapsed_ms, 2), resp.json()


def _embeddings_query(
    embeddings_url: str,
    text: str,
    timeout: float = 30.0,
) -> tuple[float, dict]:
    """Generate embeddings for text and return (latency_ms, response_json)."""
    import requests

    start = time.monotonic()
    resp = requests.post(
        f"{embeddings_url}/v1/embeddings/",
        json={"input": text},
        timeout=timeout,
    )
    elapsed_ms = (time.monotonic() - start) * 1000.0
    resp.raise_for_status()
    return round(elapsed_ms, 2), resp.json()


def _run_concurrent_queries(
    search_api_url: str,
    queries: list[dict[str, str]],
    mode: str,
    concurrent_users: int,
) -> list[tuple[float, bool]]:
    """Run queries concurrently and return list of (latency_ms, success)."""
    import concurrent.futures

    results: list[tuple[float, bool]] = []

    def _worker(query: dict[str, str]) -> tuple[float, bool]:
        try:
            latency_ms, _resp = _search_api_query(search_api_url, query["q"], mode)
            return latency_ms, True
        except Exception:  # noqa: BLE001
            return 0.0, False

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as pool:
        futures = [pool.submit(_worker, q) for q in queries]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    return results


# =========================================================================
# UNIT TESTS — run without Docker
# =========================================================================


class TestCalculatePercentiles:
    """Unit tests for calculate_percentiles()."""

    def test_basic_percentiles(self) -> None:
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        p = calculate_percentiles(latencies)
        assert p.p50_ms == 300.0
        assert p.min_ms == 100.0
        assert p.max_ms == 500.0
        assert p.mean_ms == 300.0
        assert p.sample_count == 5

    def test_single_value(self) -> None:
        p = calculate_percentiles([42.0])
        assert p.p50_ms == 42.0
        assert p.p95_ms == 42.0
        assert p.p99_ms == 42.0
        assert p.mean_ms == 42.0
        assert p.stddev_ms == 0.0
        assert p.sample_count == 1

    def test_empty_list(self) -> None:
        p = calculate_percentiles([])
        assert p.p50_ms == 0.0
        assert p.p95_ms == 0.0
        assert p.p99_ms == 0.0
        assert p.mean_ms == 0.0
        assert p.sample_count == 0

    def test_two_values(self) -> None:
        p = calculate_percentiles([100.0, 200.0])
        assert p.p50_ms == 150.0
        assert p.min_ms == 100.0
        assert p.max_ms == 200.0
        assert p.sample_count == 2

    def test_unsorted_input(self) -> None:
        p = calculate_percentiles([500.0, 100.0, 300.0, 200.0, 400.0])
        assert p.p50_ms == 300.0
        assert p.min_ms == 100.0
        assert p.max_ms == 500.0

    def test_p95_p99_high_tail(self) -> None:
        latencies = list(range(1, 101))
        latencies_f = [float(x) for x in latencies]
        p = calculate_percentiles(latencies_f)
        assert p.p50_ms == 50.5
        assert p.p95_ms >= 95.0
        assert p.p99_ms >= 99.0
        assert p.sample_count == 100

    def test_stddev_computed(self) -> None:
        p = calculate_percentiles([10.0, 20.0, 30.0])
        assert p.stddev_ms > 0.0

    def test_identical_values(self) -> None:
        p = calculate_percentiles([100.0, 100.0, 100.0])
        assert p.p50_ms == 100.0
        assert p.p95_ms == 100.0
        assert p.stddev_ms == 0.0


class TestCalculateThroughputQps:
    """Unit tests for calculate_throughput_qps()."""

    def test_basic(self) -> None:
        assert calculate_throughput_qps(100, 10.0) == 10.0

    def test_zero_queries(self) -> None:
        assert calculate_throughput_qps(0, 10.0) == 0.0

    def test_zero_elapsed(self) -> None:
        assert calculate_throughput_qps(50, 0.0) == 0.0

    def test_fractional(self) -> None:
        result = calculate_throughput_qps(30, 3.0)
        assert result == 10.0

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="query_count must be >= 0"):
            calculate_throughput_qps(-1, 10.0)

    def test_negative_elapsed_raises(self) -> None:
        with pytest.raises(ValueError, match="elapsed_seconds must be >= 0"):
            calculate_throughput_qps(10, -1.0)


class TestCalculateFailureRate:
    """Unit tests for calculate_failure_rate()."""

    def test_no_failures(self) -> None:
        assert calculate_failure_rate(100, 0) == 0.0

    def test_all_failures(self) -> None:
        assert calculate_failure_rate(0, 100) == 100.0

    def test_mixed(self) -> None:
        assert calculate_failure_rate(95, 5) == 5.0

    def test_zero_total(self) -> None:
        assert calculate_failure_rate(0, 0) == 0.0

    def test_negative_succeeded_raises(self) -> None:
        with pytest.raises(ValueError, match="succeeded must be >= 0"):
            calculate_failure_rate(-1, 0)

    def test_negative_failed_raises(self) -> None:
        with pytest.raises(ValueError, match="failed must be >= 0"):
            calculate_failure_rate(0, -1)


class TestCalculateFacetOverhead:
    """Unit tests for calculate_facet_overhead()."""

    def test_positive_overhead(self) -> None:
        overhead_ms, overhead_pct = calculate_facet_overhead(100.0, 150.0)
        assert overhead_ms == 50.0
        assert overhead_pct == 50.0

    def test_zero_base(self) -> None:
        overhead_ms, overhead_pct = calculate_facet_overhead(0.0, 50.0)
        assert overhead_ms == 50.0
        assert overhead_pct == 0.0

    def test_no_overhead(self) -> None:
        overhead_ms, overhead_pct = calculate_facet_overhead(100.0, 100.0)
        assert overhead_ms == 0.0
        assert overhead_pct == 0.0

    def test_negative_overhead(self) -> None:
        overhead_ms, overhead_pct = calculate_facet_overhead(200.0, 150.0)
        assert overhead_ms == -50.0
        assert overhead_pct == -25.0


class TestCalculateColdStartOverhead:
    """Unit tests for calculate_cold_start_overhead()."""

    def test_typical(self) -> None:
        overhead_ms, overhead_pct = calculate_cold_start_overhead(500.0, 100.0)
        assert overhead_ms == 400.0
        assert overhead_pct == 400.0

    def test_zero_warmed(self) -> None:
        overhead_ms, overhead_pct = calculate_cold_start_overhead(100.0, 0.0)
        assert overhead_ms == 100.0
        assert overhead_pct == 0.0

    def test_no_overhead(self) -> None:
        overhead_ms, overhead_pct = calculate_cold_start_overhead(100.0, 100.0)
        assert overhead_ms == 0.0
        assert overhead_pct == 0.0


class TestGroupLatenciesByQueryType:
    """Unit tests for group_latencies_by_query_type()."""

    def test_single_types(self) -> None:
        queries = [
            {"q": "a", "type": "single_word"},
            {"q": "b", "type": "phrase"},
        ]
        latencies = [100.0, 200.0]
        result = group_latencies_by_query_type(queries, latencies)
        assert result["single_word"]["p50_ms"] == 100.0
        assert result["phrase"]["p50_ms"] == 200.0

    def test_multiple_same_type(self) -> None:
        queries = [
            {"q": "a", "type": "single_word"},
            {"q": "b", "type": "single_word"},
            {"q": "c", "type": "single_word"},
        ]
        latencies = [100.0, 200.0, 300.0]
        result = group_latencies_by_query_type(queries, latencies)
        assert result["single_word"]["p50_ms"] == 200.0
        assert result["single_word"]["count"] == 3.0

    def test_empty(self) -> None:
        result = group_latencies_by_query_type([], [])
        assert result == {}

    def test_missing_type_key(self) -> None:
        queries = [{"q": "a"}]
        latencies = [100.0]
        result = group_latencies_by_query_type(queries, latencies)
        assert "unknown" in result


# ---------------------------------------------------------------------------
# Configuration dataclass tests
# ---------------------------------------------------------------------------


class TestSearchBenchmarkConfig:
    """Unit tests for SearchBenchmarkConfig validation."""

    def test_valid_config(self) -> None:
        cfg = SearchBenchmarkConfig(
            index_size_label="1k",
            index_size_pages=1000,
            search_mode="keyword",
        )
        assert cfg.index_size_label == "1k"
        assert cfg.index_size_pages == 1000
        assert cfg.repetitions == DEFAULT_REPETITIONS

    def test_custom_repetitions(self) -> None:
        cfg = SearchBenchmarkConfig(
            index_size_label="5k",
            index_size_pages=5000,
            search_mode="semantic",
            repetitions=50,
        )
        assert cfg.repetitions == 50

    def test_negative_pages_raises(self) -> None:
        with pytest.raises(ValueError, match="index_size_pages must be >= 0"):
            SearchBenchmarkConfig(
                index_size_label="bad", index_size_pages=-1, search_mode="keyword"
            )

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="search_mode must be one of"):
            SearchBenchmarkConfig(
                index_size_label="1k", index_size_pages=1000, search_mode="invalid"
            )

    def test_zero_repetitions_raises(self) -> None:
        with pytest.raises(ValueError, match="repetitions must be >= 1"):
            SearchBenchmarkConfig(
                index_size_label="1k",
                index_size_pages=1000,
                search_mode="keyword",
                repetitions=0,
            )


class TestConcurrencyConfig:
    """Unit tests for ConcurrencyConfig validation."""

    def test_valid_config(self) -> None:
        cfg = ConcurrencyConfig(concurrent_users=10)
        assert cfg.concurrent_users == 10
        assert cfg.search_mode == "keyword"

    def test_invalid_users_raises(self) -> None:
        with pytest.raises(ValueError, match="concurrent_users must be >= 1"):
            ConcurrencyConfig(concurrent_users=0)

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="search_mode must be one of"):
            ConcurrencyConfig(concurrent_users=5, search_mode="bad")


# ---------------------------------------------------------------------------
# Response parser tests
# ---------------------------------------------------------------------------


class TestParseSearchResponse:
    """Unit tests for parse_search_response()."""

    def test_typical_response(self) -> None:
        resp = {"total": 42, "results": [{"id": "1"}, {"id": "2"}], "mode": "keyword"}
        parsed = parse_search_response(resp)
        assert parsed["total"] == 42
        assert parsed["result_count"] == 2
        assert parsed["mode"] == "keyword"

    def test_empty_response(self) -> None:
        parsed = parse_search_response({})
        assert parsed["total"] == 0
        assert parsed["result_count"] == 0

    def test_semantic_mode(self) -> None:
        resp = {"total": 5, "results": [{"id": "1"}], "mode": "semantic"}
        parsed = parse_search_response(resp)
        assert parsed["mode"] == "semantic"


class TestParseFacetsResponse:
    """Unit tests for parse_facets_response()."""

    def test_typical_response(self) -> None:
        resp = {
            "facets": {
                "author": [{"value": "A", "count": 3}, {"value": "B", "count": 1}],
                "year": [{"value": "2020", "count": 5}],
                "language": [],
            }
        }
        parsed = parse_facets_response(resp)
        assert parsed["author"] == 2
        assert parsed["year"] == 1
        assert parsed["language"] == 0

    def test_empty_facets(self) -> None:
        parsed = parse_facets_response({"facets": {}})
        assert parsed == {}

    def test_missing_facets_key(self) -> None:
        parsed = parse_facets_response({})
        assert parsed == {}


class TestParseEmbeddingsResponse:
    """Unit tests for parse_embeddings_response()."""

    def test_typical_response(self) -> None:
        resp = {
            "data": [{"embedding": [0.1] * 512, "index": 0}],
            "model": "all-MiniLM-L6-v2",
        }
        parsed = parse_embeddings_response(resp)
        assert parsed["embedding_count"] == 1
        assert parsed["dimension"] == 512
        assert parsed["model"] == "all-MiniLM-L6-v2"

    def test_empty_data(self) -> None:
        parsed = parse_embeddings_response({"data": [], "model": "m"})
        assert parsed["embedding_count"] == 0
        assert parsed["dimension"] == 0

    def test_missing_fields(self) -> None:
        parsed = parse_embeddings_response({})
        assert parsed["embedding_count"] == 0
        assert parsed["model"] == "unknown"


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------


class TestGenerateLatencyReport:
    """Unit tests for generate_latency_report()."""

    def _make_metrics(self, **overrides: Any) -> SearchLatencyMetrics:
        defaults: dict[str, Any] = {
            "index_size_label": "1k",
            "index_size_pages": 1000,
            "search_mode": "keyword",
            "query_count": 100,
            "latency": LatencyPercentiles(
                p50_ms=120.0,
                p95_ms=350.0,
                p99_ms=800.0,
                mean_ms=150.0,
                min_ms=50.0,
                max_ms=1200.0,
                stddev_ms=100.0,
                sample_count=100,
            ),
            "queries_per_second": 10.0,
            "total_elapsed_seconds": 10.0,
            "succeeded": 100,
            "failed": 0,
            "failure_rate_percent": 0.0,
        }
        defaults.update(overrides)
        return SearchLatencyMetrics(**defaults)

    def test_report_contains_required_fields(self) -> None:
        metrics = self._make_metrics()
        report = generate_latency_report(metrics)

        assert "index_size_label" in report
        assert "search_mode" in report
        assert "latency" in report
        assert "queries_per_second" in report
        assert "targets" in report
        assert "passed" in report
        assert "pass_criteria" in report
        assert "_generated_at" in report
        assert "_version" in report

    def test_report_passes_under_targets(self) -> None:
        metrics = self._make_metrics()
        report = generate_latency_report(metrics)
        assert report["passed"] is True

    def test_report_fails_over_p50_target(self) -> None:
        latency = LatencyPercentiles(p50_ms=600.0, p95_ms=800.0, p99_ms=1000.0)
        metrics = self._make_metrics(latency=latency)
        report = generate_latency_report(metrics)
        assert report["passed"] is False

    def test_report_fails_over_p95_target(self) -> None:
        latency = LatencyPercentiles(p50_ms=100.0, p95_ms=2000.0, p99_ms=2500.0)
        metrics = self._make_metrics(latency=latency)
        report = generate_latency_report(metrics)
        assert report["passed"] is False

    def test_report_fails_over_p99_target(self) -> None:
        latency = LatencyPercentiles(p50_ms=100.0, p95_ms=500.0, p99_ms=4000.0)
        metrics = self._make_metrics(latency=latency)
        report = generate_latency_report(metrics)
        assert report["passed"] is False

    def test_report_fails_high_failure_rate(self) -> None:
        metrics = self._make_metrics(failure_rate_percent=10.0)
        report = generate_latency_report(metrics)
        assert report["passed"] is False


class TestWriteReport:
    """Unit tests for write_report()."""

    def test_writes_json_file(self, tmp_path: Path) -> None:
        report = {"index_size_label": "1k", "p50_ms": 120.0}
        path = write_report(report, tmp_path, "test_report")
        assert path.exists()
        assert path.suffix == ".json"
        loaded = json.loads(path.read_text())
        assert loaded["index_size_label"] == "1k"

    def test_creates_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        path = write_report({"x": 1}, nested, "deep")
        assert path.exists()


class TestWriteCsvReport:
    """Unit tests for write_csv_report()."""

    def test_writes_csv_file(self, tmp_path: Path) -> None:
        reports = [
            {
                "index_size_label": "1k",
                "index_size_pages": 1000,
                "search_mode": "keyword",
                "query_count": 100,
                "latency": {
                    "p50_ms": 120.0,
                    "p95_ms": 350.0,
                    "p99_ms": 800.0,
                    "mean_ms": 150.0,
                    "min_ms": 50.0,
                    "max_ms": 1200.0,
                    "stddev_ms": 100.0,
                },
                "queries_per_second": 10.0,
                "failure_rate_percent": 0.0,
                "passed": True,
            }
        ]
        path = write_csv_report(reports, tmp_path, "test_csv")
        assert path.exists()
        assert path.suffix == ".csv"

        content = path.read_text()
        assert "index_size_label" in content
        assert "1k" in content
        assert "keyword" in content

    def test_multiple_rows(self, tmp_path: Path) -> None:
        reports = [
            {
                "index_size_label": size,
                "index_size_pages": pages,
                "search_mode": "keyword",
                "query_count": 100,
                "latency": {"p50_ms": 100.0 * i, "p95_ms": 200.0 * i, "p99_ms": 300.0 * i},
                "queries_per_second": 10.0 / i,
                "failure_rate_percent": 0.0,
                "passed": True,
            }
            for i, (size, pages) in enumerate(INDEX_SIZES.items(), 1)
        ]
        path = write_csv_report(reports, tmp_path, "multi")
        content = path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == len(INDEX_SIZES) + 1  # header + data rows


class TestGenerateComparisonReport:
    """Unit tests for generate_comparison_report()."""

    def test_empty_reports(self) -> None:
        result = generate_comparison_report([])
        assert result["runs"] == []

    def test_single_report(self) -> None:
        reports = [
            {
                "index_size_label": "1k",
                "search_mode": "keyword",
                "latency": {"p50_ms": 100.0, "p95_ms": 200.0, "p99_ms": 300.0},
                "queries_per_second": 10.0,
                "failure_rate_percent": 0.0,
                "passed": True,
            }
        ]
        result = generate_comparison_report(reports)
        assert len(result["runs"]) == 1
        assert result["comparison"]["fastest_p50"]["index_size_label"] == "1k"

    def test_finds_best_across_runs(self) -> None:
        reports = [
            {
                "index_size_label": "1k",
                "search_mode": "keyword",
                "latency": {"p50_ms": 50.0, "p95_ms": 100.0, "p99_ms": 200.0},
                "queries_per_second": 20.0,
                "failure_rate_percent": 0.0,
                "passed": True,
            },
            {
                "index_size_label": "50k",
                "search_mode": "keyword",
                "latency": {"p50_ms": 200.0, "p95_ms": 500.0, "p99_ms": 1000.0},
                "queries_per_second": 5.0,
                "failure_rate_percent": 1.0,
                "passed": True,
            },
        ]
        result = generate_comparison_report(reports)
        assert result["comparison"]["fastest_p50"]["index_size_label"] == "1k"
        assert result["comparison"]["highest_throughput"]["index_size_label"] == "1k"


# ---------------------------------------------------------------------------
# Build metrics tests
# ---------------------------------------------------------------------------


class TestBuildSearchLatencyMetrics:
    """Unit tests for build_search_latency_metrics()."""

    def test_assembles_correctly(self) -> None:
        config = SearchBenchmarkConfig(
            index_size_label="1k",
            index_size_pages=1000,
            search_mode="keyword",
            repetitions=5,
        )
        queries = [
            {"q": "python", "type": "single_word"},
            {"q": "machine learning", "type": "multi_word"},
            {"q": '"design patterns"', "type": "phrase"},
        ]
        latencies = [100.0, 200.0, 150.0]

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=queries,
            succeeded=3,
            failed=0,
            total_elapsed_seconds=5.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:05Z",
        )

        assert metrics.index_size_label == "1k"
        assert metrics.search_mode == "keyword"
        assert metrics.query_count == 3
        assert metrics.latency.p50_ms == 150.0
        assert metrics.latency.min_ms == 100.0
        assert metrics.latency.max_ms == 200.0
        assert metrics.queries_per_second == 0.6
        assert metrics.failure_rate_percent == 0.0
        assert "single_word" in metrics.latency_by_query_type
        assert "multi_word" in metrics.latency_by_query_type
        assert "phrase" in metrics.latency_by_query_type

    def test_with_failures(self) -> None:
        config = SearchBenchmarkConfig(
            index_size_label="5k",
            index_size_pages=5000,
            search_mode="semantic",
        )
        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=[100.0, 200.0],
            queries=[{"q": "a", "type": "t"}, {"q": "b", "type": "t"}],
            succeeded=8,
            failed=2,
            total_elapsed_seconds=10.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:10Z",
        )

        assert metrics.failure_rate_percent == 20.0
        assert metrics.succeeded == 8
        assert metrics.failed == 2


# =========================================================================
# MOCKED SEARCH TESTS — test orchestration logic without Docker
# =========================================================================


class TestMockedSearchBenchmark:
    """
    Test the search benchmark logic with mocked infrastructure.

    Verifies metric collection, percentile computation, result assembly,
    and report writing without requiring Docker.
    """

    def test_full_keyword_benchmark_mock(self, tmp_path: Path) -> None:
        """Simulate a keyword search benchmark run."""
        config = SearchBenchmarkConfig(
            index_size_label="1k",
            index_size_pages=1000,
            search_mode="keyword",
            repetitions=10,
        )

        # Simulate latencies with realistic distribution
        latencies = [80.0, 95.0, 110.0, 105.0, 120.0, 90.0, 200.0, 85.0, 115.0, 300.0]
        queries = QUERY_CORPUS[:10]

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=queries,
            succeeded=10,
            failed=0,
            total_elapsed_seconds=1.5,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:01.5Z",
        )

        assert metrics.latency.p50_ms > 0
        assert metrics.latency.p95_ms >= metrics.latency.p50_ms
        assert metrics.latency.p99_ms >= metrics.latency.p95_ms
        assert metrics.queries_per_second > 0

        report = generate_latency_report(metrics)
        path = write_report(report, tmp_path, "keyword_1k")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["search_mode"] == "keyword"
        assert loaded["passed"] is True

    def test_full_semantic_benchmark_mock(self, tmp_path: Path) -> None:
        """Simulate a semantic search benchmark run (higher latency)."""
        config = SearchBenchmarkConfig(
            index_size_label="5k",
            index_size_pages=5000,
            search_mode="semantic",
            repetitions=10,
        )

        # Semantic search typically has higher latency
        latencies = [200.0, 250.0, 300.0, 280.0, 350.0, 220.0, 500.0, 210.0, 260.0, 700.0]
        queries = QUERY_CORPUS[10:20]

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=queries,
            succeeded=10,
            failed=0,
            total_elapsed_seconds=3.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:03Z",
        )

        report = generate_latency_report(metrics)
        path = write_report(report, tmp_path, "semantic_5k")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["search_mode"] == "semantic"

    def test_full_hybrid_benchmark_mock(self, tmp_path: Path) -> None:
        """Simulate a hybrid search benchmark run."""
        config = SearchBenchmarkConfig(
            index_size_label="10k",
            index_size_pages=10000,
            search_mode="hybrid",
            repetitions=10,
        )

        latencies = [250.0, 310.0, 350.0, 330.0, 400.0, 270.0, 600.0, 280.0, 340.0, 900.0]
        queries = QUERY_CORPUS[20:30]

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=queries,
            succeeded=10,
            failed=0,
            total_elapsed_seconds=4.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:04Z",
        )

        report = generate_latency_report(metrics)
        assert report["passed"] is True

    @pytest.mark.parametrize(
        "size_label,size_pages",
        list(INDEX_SIZES.items()),
        ids=list(INDEX_SIZES.keys()),
    )
    def test_parametrized_index_sizes(
        self, size_label: str, size_pages: int, tmp_path: Path
    ) -> None:
        """Verify metric assembly works for all index sizes."""
        config = SearchBenchmarkConfig(
            index_size_label=size_label,
            index_size_pages=size_pages,
            search_mode="keyword",
        )

        # Scale latency with index size (logarithmic growth)
        base = 80.0
        scale_factor = math.log2(size_pages / 1000 + 1) + 1
        latencies = [
            round(base * scale_factor * (0.8 + 0.4 * (i % 5) / 4), 2)
            for i in range(20)
        ]

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=QUERY_CORPUS[:20],
            succeeded=20,
            failed=0,
            total_elapsed_seconds=sum(latencies) / 1000.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:01:00Z",
        )

        assert metrics.latency.p50_ms > 0
        assert metrics.queries_per_second > 0

        report = generate_latency_report(metrics)
        path = write_report(report, tmp_path / size_label, f"search_{size_label}")
        assert path.exists()

    @pytest.mark.parametrize("mode", SEARCH_MODES, ids=SEARCH_MODES)
    def test_parametrized_search_modes(
        self, mode: str, tmp_path: Path
    ) -> None:
        """Verify metric assembly works for all search modes."""
        config = SearchBenchmarkConfig(
            index_size_label="1k",
            index_size_pages=1000,
            search_mode=mode,
        )

        # Mode-dependent base latency
        mode_base = {"keyword": 80.0, "semantic": 200.0, "hybrid": 280.0}
        base = mode_base.get(mode, 100.0)
        latencies = [round(base * (1 + 0.1 * i), 2) for i in range(10)]

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=QUERY_CORPUS[:10],
            succeeded=10,
            failed=0,
            total_elapsed_seconds=sum(latencies) / 1000.0,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:05Z",
        )

        assert metrics.search_mode == mode
        assert metrics.latency.p50_ms > 0

    def test_faceted_search_overhead_mock(self, tmp_path: Path) -> None:
        """Simulate faceted search overhead measurement."""
        base_latency = 100.0
        faceted_latencies = {
            "fq_language=English": 115.0,
            "fq_author=Author": 120.0,
            "fq_year=2020": 110.0,
            "fq_language+fq_year": 130.0,
        }

        metrics = FacetedSearchMetrics(
            index_size_label="1k",
            base_latency_ms=base_latency,
        )

        for filt, lat in faceted_latencies.items():
            overhead_ms, overhead_pct = calculate_facet_overhead(base_latency, lat)
            metrics.filter_counts[filt] = {
                "latency_ms": lat,
                "overhead_ms": overhead_ms,
                "overhead_percent": overhead_pct,
            }

        metrics.faceted_latency_ms = statistics.mean(faceted_latencies.values())
        overhead_ms, overhead_pct = calculate_facet_overhead(
            base_latency, metrics.faceted_latency_ms
        )
        metrics.overhead_ms = overhead_ms
        metrics.overhead_percent = overhead_pct

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        path = write_report(report, tmp_path, "facet_overhead")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["overhead_ms"] > 0
        assert len(loaded["filter_counts"]) == 4

    def test_embedding_latency_mock(self, tmp_path: Path) -> None:
        """Simulate isolated embedding generation time measurement."""
        latencies = [15.0, 18.0, 20.0, 17.0, 22.0, 16.0, 25.0, 19.0, 21.0, 30.0]
        percentiles = calculate_percentiles(latencies)

        metrics = EmbeddingLatencyMetrics(
            query_count=10,
            latency=percentiles,
            tokens_per_second=round(10 * 15 / (sum(latencies) / 1000.0), 2),
        )

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        path = write_report(report, tmp_path, "embedding_latency")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["latency"]["p50_ms"] > 0
        assert loaded["tokens_per_second"] > 0

    def test_concurrent_search_mock(self, tmp_path: Path) -> None:
        """Simulate concurrent search measurement."""
        for num_users in CONCURRENCY_LEVELS:
            latencies = [
                round(100.0 * (1 + 0.05 * num_users) + 20.0 * (i % 5), 2)
                for i in range(num_users * 10)
            ]
            percentiles = calculate_percentiles(latencies)
            total_elapsed = max(latencies) / 1000.0 * 3  # simulated wall time

            metrics = ConcurrentSearchMetrics(
                concurrent_users=num_users,
                search_mode="keyword",
                per_user_latency=percentiles,
                total_queries=len(latencies),
                total_elapsed_seconds=round(total_elapsed, 2),
                throughput_qps=calculate_throughput_qps(len(latencies), total_elapsed),
                error_count=0,
            )

            report = asdict(metrics)
            report["_generated_at"] = datetime.now(tz=UTC).isoformat()
            path = write_report(report, tmp_path, f"concurrent_{num_users}")
            assert path.exists()

            loaded = json.loads(path.read_text())
            assert loaded["concurrent_users"] == num_users
            assert loaded["throughput_qps"] > 0

    def test_cold_start_mock(self, tmp_path: Path) -> None:
        """Simulate cold-start latency measurement."""
        first_query_ms = 800.0
        warmed_latencies = [100.0, 120.0, 110.0, 105.0, 115.0, 95.0, 130.0, 108.0, 112.0, 125.0]
        warmed_p50 = calculate_percentiles(warmed_latencies).p50_ms

        overhead_ms, overhead_pct = calculate_cold_start_overhead(first_query_ms, warmed_p50)

        metrics = ColdStartMetrics(
            first_query_ms=first_query_ms,
            warmed_up_p50_ms=warmed_p50,
            warmup_overhead_ms=overhead_ms,
            warmup_overhead_percent=overhead_pct,
        )

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        path = write_report(report, tmp_path, "cold_start")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert loaded["warmup_overhead_ms"] > 0
        assert loaded["first_query_ms"] > loaded["warmed_up_p50_ms"]

    def test_comparison_report_across_sizes(self, tmp_path: Path) -> None:
        """Generate a comparison report across simulated index sizes and modes."""
        all_reports = []
        for size_label, size_pages in INDEX_SIZES.items():
            for mode in SEARCH_MODES:
                config = SearchBenchmarkConfig(
                    index_size_label=size_label,
                    index_size_pages=size_pages,
                    search_mode=mode,
                )
                base = {"keyword": 80.0, "semantic": 200.0, "hybrid": 280.0}[mode]
                scale = math.log2(size_pages / 1000 + 1) + 1
                latencies = [round(base * scale * (0.9 + 0.2 * (i % 5) / 4), 2) for i in range(20)]

                metrics = build_search_latency_metrics(
                    config=config,
                    latencies_ms=latencies,
                    queries=QUERY_CORPUS[:20],
                    succeeded=20,
                    failed=0,
                    total_elapsed_seconds=sum(latencies) / 1000.0,
                    started_at="2025-01-01T00:00:00Z",
                    finished_at="2025-01-01T00:01:00Z",
                )
                report = generate_latency_report(metrics)
                all_reports.append(report)

        comparison = generate_comparison_report(all_reports)
        path = write_report(comparison, tmp_path, "comparison")
        assert path.exists()

        loaded = json.loads(path.read_text())
        assert len(loaded["runs"]) == len(INDEX_SIZES) * len(SEARCH_MODES)
        assert loaded["comparison"]["fastest_p50"] is not None

        # Also write CSV
        csv_path = write_csv_report(all_reports, tmp_path, "latency_curves")
        assert csv_path.exists()
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == len(INDEX_SIZES) * len(SEARCH_MODES) + 1

    def test_full_benchmark_with_mocked_api(self, tmp_path: Path) -> None:
        """End-to-end mock: simulate calling the search API and collecting metrics."""
        import requests as requests_mod

        call_count = 0

        def mock_get(url: str, params: dict | None = None, timeout: float = 30.0) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "total": 42,
                "results": [{"id": f"doc_{i}"} for i in range(5)],
                "mode": (params or {}).get("mode", "keyword"),
                "facets": {},
            }
            return resp

        config = SearchBenchmarkConfig(
            index_size_label="1k",
            index_size_pages=1000,
            search_mode="keyword",
            repetitions=5,
        )

        with patch.object(requests_mod, "get", side_effect=mock_get):
            latencies = []
            succeeded = 0
            failed = 0
            test_queries = QUERY_CORPUS[:5]

            start = time.monotonic()
            for query in test_queries:
                try:
                    latency_ms, resp_json = _search_api_query(
                        "http://mock:8080", query["q"], config.search_mode
                    )
                    latencies.append(latency_ms)
                    succeeded += 1
                except Exception:  # noqa: BLE001
                    failed += 1
            total_elapsed = time.monotonic() - start

        assert succeeded == 5
        assert failed == 0
        assert len(latencies) == 5

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=test_queries,
            succeeded=succeeded,
            failed=failed,
            total_elapsed_seconds=total_elapsed,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:05Z",
        )

        assert metrics.query_count == 5
        assert metrics.failure_rate_percent == 0.0

        report = generate_latency_report(metrics)
        path = write_report(report, tmp_path, "mocked_api_run")
        assert path.exists()


# =========================================================================
# INTEGRATION TESTS — require Docker infrastructure
# =========================================================================


@pytest.mark.docker
@pytest.mark.search
@pytest.mark.slow
class TestSearchLatencyBenchmark:
    """
    Integration benchmarks for search latency across index sizes.

    These tests require the full Docker Compose stack to be running
    with a pre-populated Solr index. They are skipped automatically
    when Docker is unavailable.
    """

    @pytest.fixture(autouse=True)
    def _skip_without_docker(self) -> None:
        if not _docker_available():
            pytest.skip("Docker daemon not available — skipping integration test")

    @pytest.mark.parametrize(
        "mode",
        SEARCH_MODES,
        ids=SEARCH_MODES,
    )
    def test_search_latency_by_mode(
        self,
        mode: str,
        search_api_url: str,
        write_result,
        timer,
    ) -> None:
        """Measure search latency for each search mode."""
        import requests

        # Determine current index size
        try:
            resp = requests.get(f"{search_api_url}/search", params={"q": "", "mode": "keyword", "page_size": "1"}, timeout=10)
            total = resp.json().get("total", 0) if resp.ok else 0
        except Exception:  # noqa: BLE001
            total = 0

        size_label = "unknown"
        for label, size in sorted(INDEX_SIZES.items(), key=lambda x: x[1], reverse=True):
            if total >= size:
                size_label = label
                break

        config = SearchBenchmarkConfig(
            index_size_label=size_label,
            index_size_pages=total,
            search_mode=mode,
            repetitions=DEFAULT_REPETITIONS,
        )

        latencies: list[float] = []
        succeeded = 0
        failed = 0
        queries_used: list[dict[str, str]] = []

        started_at = datetime.now(tz=UTC).isoformat()
        t = timer()
        with t:
            for _rep in range(config.repetitions):
                query = QUERY_CORPUS[_rep % len(QUERY_CORPUS)]
                queries_used.append(query)
                try:
                    latency_ms, _resp = _search_api_query(
                        search_api_url, query["q"], mode
                    )
                    latencies.append(latency_ms)
                    succeeded += 1
                except Exception:  # noqa: BLE001
                    failed += 1

        finished_at = datetime.now(tz=UTC).isoformat()

        metrics = build_search_latency_metrics(
            config=config,
            latencies_ms=latencies,
            queries=queries_used,
            succeeded=succeeded,
            failed=failed,
            total_elapsed_seconds=t.elapsed,
            started_at=started_at,
            finished_at=finished_at,
        )

        report = generate_latency_report(metrics)
        write_result(f"search_latency_{mode}_{size_label}", report)

        # Assertions
        if succeeded > 0:
            assert metrics.latency.p50_ms > 0
            assert metrics.queries_per_second > 0

    def test_faceted_search_overhead(
        self,
        search_api_url: str,
        write_result,
    ) -> None:
        """Measure the latency overhead of adding facet filters."""
        # Baseline: unfaceted search
        base_latencies: list[float] = []
        test_query = "science"

        for _ in range(20):
            try:
                lat, _ = _search_api_query(search_api_url, test_query, "keyword")
                base_latencies.append(lat)
            except Exception:  # noqa: BLE001
                pass

        base_p50 = calculate_percentiles(base_latencies).p50_ms if base_latencies else 0.0

        # Faceted queries
        filter_results: dict[str, dict[str, float]] = {}
        for filters in FACET_FILTERS:
            filter_latencies: list[float] = []
            for _ in range(20):
                try:
                    lat, _ = _facets_api_query(search_api_url, test_query, filters)
                    filter_latencies.append(lat)
                except Exception:  # noqa: BLE001
                    pass

            if filter_latencies:
                faceted_p50 = calculate_percentiles(filter_latencies).p50_ms
                overhead_ms, overhead_pct = calculate_facet_overhead(base_p50, faceted_p50)
                filter_key = "&".join(f"{k}={v}" for k, v in filters.items())
                filter_results[filter_key] = {
                    "latency_ms": faceted_p50,
                    "overhead_ms": overhead_ms,
                    "overhead_percent": overhead_pct,
                }

        avg_faceted = (
            statistics.mean(v["latency_ms"] for v in filter_results.values())
            if filter_results
            else 0.0
        )
        overhead_ms, overhead_pct = calculate_facet_overhead(base_p50, avg_faceted)

        metrics = FacetedSearchMetrics(
            index_size_label="current",
            base_latency_ms=base_p50,
            faceted_latency_ms=round(avg_faceted, 2),
            overhead_ms=overhead_ms,
            overhead_percent=overhead_pct,
            filter_counts=filter_results,
        )

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        write_result("faceted_search_overhead", report)

    def test_embedding_generation_latency(
        self,
        write_result,
    ) -> None:
        """Measure isolated embedding generation time."""
        embeddings_url = "http://localhost:8085"
        latencies: list[float] = []

        for query in QUERY_CORPUS[:20]:
            try:
                lat, _ = _embeddings_query(embeddings_url, query["q"])
                latencies.append(lat)
            except Exception:  # noqa: BLE001
                pass

        if not latencies:
            pytest.skip("Embeddings server not reachable")

        percentiles = calculate_percentiles(latencies)
        avg_tokens = 15  # approximate tokens per query
        total_time_sec = sum(latencies) / 1000.0
        tokens_per_sec = round(len(latencies) * avg_tokens / total_time_sec, 2) if total_time_sec > 0 else 0.0

        metrics = EmbeddingLatencyMetrics(
            query_count=len(latencies),
            latency=percentiles,
            tokens_per_second=tokens_per_sec,
        )

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        write_result("embedding_latency", report)

        assert percentiles.p50_ms > 0


@pytest.mark.docker
@pytest.mark.search
@pytest.mark.concurrent
@pytest.mark.slow
class TestConcurrentSearchLatency:
    """Concurrent search latency simulation."""

    @pytest.fixture(autouse=True)
    def _skip_without_docker(self) -> None:
        if not _docker_available():
            pytest.skip("Docker daemon not available — skipping integration test")

    @pytest.mark.parametrize(
        "num_users",
        CONCURRENCY_LEVELS,
        ids=[f"{n}users" for n in CONCURRENCY_LEVELS],
    )
    def test_concurrent_search(
        self,
        num_users: int,
        search_api_url: str,
        write_result,
        timer,
    ) -> None:
        """Measure search latency under concurrent load."""
        queries = QUERY_CORPUS * (num_users // len(QUERY_CORPUS) + 1)
        queries = queries[:num_users * 10]

        t = timer()
        with t:
            results = _run_concurrent_queries(
                search_api_url, queries, "keyword", num_users
            )

        latencies = [lat for lat, ok in results if ok]
        errors = sum(1 for _, ok in results if not ok)

        if not latencies:
            pytest.skip("No successful queries in concurrent test")

        percentiles = calculate_percentiles(latencies)

        metrics = ConcurrentSearchMetrics(
            concurrent_users=num_users,
            search_mode="keyword",
            per_user_latency=percentiles,
            total_queries=len(results),
            total_elapsed_seconds=round(t.elapsed, 2),
            throughput_qps=calculate_throughput_qps(len(latencies), t.elapsed),
            error_count=errors,
        )

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        write_result(f"concurrent_{num_users}_users", report)

        assert percentiles.p50_ms > 0
        assert metrics.throughput_qps > 0


@pytest.mark.docker
@pytest.mark.search
@pytest.mark.slow
class TestColdStartLatency:
    """Cold-start latency measurement after service restart."""

    @pytest.fixture(autouse=True)
    def _skip_without_docker(self) -> None:
        if not _docker_available():
            pytest.skip("Docker daemon not available — skipping integration test")

    def test_cold_start_latency(
        self,
        search_api_url: str,
        write_result,
    ) -> None:
        """Measure first-query latency vs warmed-up latency."""
        # Warm up with a few queries first, then measure cold start
        # Note: true cold-start requires service restart, which is disruptive.
        # This test measures first-query-of-session latency as a proxy.

        # First query (cold cache)
        try:
            first_lat, _ = _search_api_query(
                search_api_url, "test cold start query", "keyword"
            )
        except Exception:  # noqa: BLE001
            pytest.skip("Search API not reachable")
            return  # unreachable but satisfies type checker

        # Warm-up queries
        warmed_latencies: list[float] = []
        for _ in range(20):
            try:
                lat, _ = _search_api_query(search_api_url, "science", "keyword")
                warmed_latencies.append(lat)
            except Exception:  # noqa: BLE001
                pass

        if not warmed_latencies:
            pytest.skip("Could not collect warm-up latencies")

        warmed_p50 = calculate_percentiles(warmed_latencies).p50_ms
        overhead_ms, overhead_pct = calculate_cold_start_overhead(first_lat, warmed_p50)

        metrics = ColdStartMetrics(
            first_query_ms=first_lat,
            warmed_up_p50_ms=warmed_p50,
            warmup_overhead_ms=overhead_ms,
            warmup_overhead_percent=overhead_pct,
        )

        report = asdict(metrics)
        report["_generated_at"] = datetime.now(tz=UTC).isoformat()
        write_result("cold_start_latency", report)

        # First query should complete (no assertion on being slower — cache may be warm)
        assert first_lat > 0
