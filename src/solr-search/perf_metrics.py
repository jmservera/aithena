"""In-memory rolling-window performance metrics for A/B evaluation.

Tracks per-request latency, embedding generation time, Solr query time,
request counts, and error rates — all broken down by collection. Data is
kept in a rolling time window (default 60 minutes) so the store stays
bounded without external dependencies.

This module is temporary tooling for the A/B evaluation period (Phase 2).
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

_DEFAULT_WINDOW_SECONDS = 3600  # 60 minutes


@dataclass(frozen=True)
class TimedSample:
    """A single latency measurement attached to a wall-clock timestamp."""

    timestamp: float
    value: float


@dataclass
class _CollectionBucket:
    """Accumulated samples for one collection."""

    request_latencies: list[TimedSample] = field(default_factory=list)
    embedding_latencies: list[TimedSample] = field(default_factory=list)
    solr_latencies: list[TimedSample] = field(default_factory=list)
    request_count: int = 0
    error_count: int = 0


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the *pct*-th percentile from an already-sorted list.

    Uses the "nearest rank" method.  Returns 0.0 for empty lists.
    """
    if not sorted_values:
        return 0.0
    k = max(0, min(int(len(sorted_values) * pct / 100.0 + 0.5) - 1, len(sorted_values) - 1))
    return sorted_values[k]


def _summarize(samples: list[TimedSample]) -> dict[str, float]:
    """Compute avg / p50 / p95 / p99 from a list of ``TimedSample``."""
    if not samples:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
    values = sorted(s.value for s in samples)
    return {
        "avg": round(statistics.mean(values), 4),
        "p50": round(_percentile(values, 50), 4),
        "p95": round(_percentile(values, 95), 4),
        "p99": round(_percentile(values, 99), 4),
        "count": len(values),
    }


class PerfMetricsStore:
    """Thread-safe in-memory performance metrics with a rolling time window.

    Parameters
    ----------
    window_seconds:
        How far back to keep samples (default 3600 = 60 min).
    """

    def __init__(self, window_seconds: int = _DEFAULT_WINDOW_SECONDS) -> None:
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._started_at = time.monotonic()
        self._buckets: dict[str, _CollectionBucket] = defaultdict(_CollectionBucket)

    # ------------------------------------------------------------------
    # Recording helpers (called from request handlers)
    # ------------------------------------------------------------------

    def record_request(
        self,
        collection: str,
        total_latency_s: float,
        *,
        embedding_latency_s: float | None = None,
        solr_latency_s: float | None = None,
        error: bool = False,
    ) -> None:
        """Record one search request with its timing breakdown."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[collection]
            bucket.request_count += 1
            bucket.request_latencies.append(TimedSample(now, total_latency_s))
            if embedding_latency_s is not None:
                bucket.embedding_latencies.append(TimedSample(now, embedding_latency_s))
            if solr_latency_s is not None:
                bucket.solr_latencies.append(TimedSample(now, solr_latency_s))
            if error:
                bucket.error_count += 1

    def record_error(self, collection: str) -> None:
        """Increment error count for *collection* without a full request record."""
        with self._lock:
            self._buckets[collection].error_count += 1

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _prune_samples(self, samples: list[TimedSample], cutoff: float) -> list[TimedSample]:
        """Return only samples whose timestamp >= *cutoff*."""
        return [s for s in samples if s.timestamp >= cutoff]

    def _prune_bucket(self, bucket: _CollectionBucket, cutoff: float) -> None:
        bucket.request_latencies = self._prune_samples(bucket.request_latencies, cutoff)
        bucket.embedding_latencies = self._prune_samples(bucket.embedding_latencies, cutoff)
        bucket.solr_latencies = self._prune_samples(bucket.solr_latencies, cutoff)

    def snapshot(self) -> dict[str, Any]:
        """Return aggregated metrics for all collections within the window.

        The response shape is designed for the ``GET /v1/admin/metrics``
        endpoint.
        """
        now = time.monotonic()
        cutoff = now - self._window_seconds
        uptime_s = round(now - self._started_at, 2)

        with self._lock:
            result: dict[str, Any] = {
                "uptime_seconds": uptime_s,
                "window_seconds": self._window_seconds,
                "collections": {},
            }
            for name, bucket in self._buckets.items():
                self._prune_bucket(bucket, cutoff)
                result["collections"][name] = {
                    "request_count": bucket.request_count,
                    "error_count": bucket.error_count,
                    "error_rate": round(bucket.error_count / max(bucket.request_count, 1), 4),
                    "latency": _summarize(bucket.request_latencies),
                    "embedding_latency": _summarize(bucket.embedding_latencies),
                    "solr_latency": _summarize(bucket.solr_latencies),
                }
            return result

    # ------------------------------------------------------------------
    # Reset (for benchmarking sessions)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all collected data and restart the uptime clock."""
        with self._lock:
            self._buckets.clear()
            self._started_at = time.monotonic()


# Module-level singleton
perf_metrics = PerfMetricsStore()
