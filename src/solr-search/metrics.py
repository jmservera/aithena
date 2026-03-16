from __future__ import annotations

import threading
from collections.abc import Iterable

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
_SEARCH_MODES = ("keyword", "semantic", "hybrid")
_LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    rendered = ",".join(f'{key}="{_escape_label_value(value)}"' for key, value in labels.items())
    return f"{{{rendered}}}"


def _format_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return format(value, ".17g")


def _format_bucket(bucket: float) -> str:
    return format(bucket, ".17g")


class MetricsRegistry:
    def __init__(
        self,
        search_modes: Iterable[str] = _SEARCH_MODES,
        latency_buckets: Iterable[float] = _LATENCY_BUCKETS,
    ) -> None:
        self._search_modes = tuple(search_modes)
        self._latency_buckets = tuple(latency_buckets)
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._search_requests_total = {mode: 0 for mode in self._search_modes}
            self._search_latency_bucket_counts = {
                mode: [0 for _ in self._latency_buckets] for mode in self._search_modes
            }
            self._search_latency_count = {mode: 0 for mode in self._search_modes}
            self._search_latency_sum = {mode: 0.0 for mode in self._search_modes}
            self._indexing_queue_depth = 0
            self._indexing_failures_total = 0
            self._embeddings_available = 0
            self._solr_live_nodes = 0
            self._failed_keys_last_seen: set[str] = set()

    def increment_search_request(self, mode: str) -> None:
        with self._lock:
            self._search_requests_total[mode] = self._search_requests_total.get(mode, 0) + 1

    def observe_search_latency(self, mode: str, duration_seconds: float) -> None:
        duration = max(duration_seconds, 0.0)
        with self._lock:
            bucket_counts = self._search_latency_bucket_counts.setdefault(
                mode,
                [0 for _ in self._latency_buckets],
            )
            for index, bucket in enumerate(self._latency_buckets):
                if duration <= bucket:
                    bucket_counts[index] += 1
            self._search_latency_count[mode] = self._search_latency_count.get(mode, 0) + 1
            self._search_latency_sum[mode] = self._search_latency_sum.get(mode, 0.0) + duration

    def set_indexing_queue_depth(self, depth: int) -> None:
        with self._lock:
            self._indexing_queue_depth = max(depth, 0)

    def sync_indexing_failures(self, failed_keys: set[str]) -> None:
        with self._lock:
            new_failures = failed_keys - self._failed_keys_last_seen
            self._indexing_failures_total += len(new_failures)
            self._failed_keys_last_seen = set(failed_keys)

    def set_embeddings_available(self, available: int) -> None:
        with self._lock:
            self._embeddings_available = 1 if available else 0

    def set_solr_live_nodes(self, node_count: int) -> None:
        with self._lock:
            self._solr_live_nodes = max(node_count, 0)

    def render(self) -> str:
        with self._lock:
            search_requests_total = dict(self._search_requests_total)
            search_latency_bucket_counts = {
                mode: counts.copy() for mode, counts in self._search_latency_bucket_counts.items()
            }
            search_latency_count = dict(self._search_latency_count)
            search_latency_sum = dict(self._search_latency_sum)
            indexing_queue_depth = self._indexing_queue_depth
            indexing_failures_total = self._indexing_failures_total
            embeddings_available = self._embeddings_available
            solr_live_nodes = self._solr_live_nodes

        lines = [
            "# HELP aithena_search_requests_total Total number of search requests by mode.",
            "# TYPE aithena_search_requests_total counter",
        ]
        for mode in self._search_modes:
            value = search_requests_total.get(mode, 0)
            lines.append(
                f'aithena_search_requests_total{{mode="{_escape_label_value(mode)}"}} {_format_number(value)}'
            )

        lines.extend(
            [
                "# HELP aithena_search_latency_seconds Search request latency in seconds.",
                "# TYPE aithena_search_latency_seconds histogram",
            ]
        )
        for mode in self._search_modes:
            counts = search_latency_bucket_counts.get(mode, [0 for _ in self._latency_buckets])
            for bucket, count in zip(self._latency_buckets, counts, strict=False):
                labels = _format_labels({"mode": mode, "le": _format_bucket(bucket)})
                lines.append(f"aithena_search_latency_seconds_bucket{labels} {_format_number(count)}")
            inf_labels = _format_labels({"mode": mode, "le": "+Inf"})
            total_count = search_latency_count.get(mode, 0)
            lines.append(f"aithena_search_latency_seconds_bucket{inf_labels} {_format_number(total_count)}")
            sum_labels = _format_labels({"mode": mode})
            lines.append(
                f"aithena_search_latency_seconds_sum{sum_labels} {_format_number(search_latency_sum.get(mode, 0.0))}"
            )
            lines.append(f"aithena_search_latency_seconds_count{sum_labels} {_format_number(total_count)}")

        lines.extend(
            [
                "# HELP aithena_indexing_queue_depth Number of queued indexing documents tracked in Redis.",
                "# TYPE aithena_indexing_queue_depth gauge",
                f"aithena_indexing_queue_depth {_format_number(indexing_queue_depth)}",
                (
                    "# HELP aithena_indexing_failures_total Total number of indexing failures "
                    "observed from Redis failed keys since process start."
                ),
                "# TYPE aithena_indexing_failures_total counter",
                f"aithena_indexing_failures_total {_format_number(indexing_failures_total)}",
                "# HELP aithena_embeddings_available Embeddings service availability (1 = up, 0 = down).",
                "# TYPE aithena_embeddings_available gauge",
                f"aithena_embeddings_available {_format_number(embeddings_available)}",
                "# HELP aithena_solr_live_nodes Number of live Solr nodes reported by CLUSTERSTATUS.",
                "# TYPE aithena_solr_live_nodes gauge",
                f"aithena_solr_live_nodes {_format_number(solr_live_nodes)}",
            ]
        )
        return "\n".join(lines) + "\n"


metrics_registry = MetricsRegistry()
