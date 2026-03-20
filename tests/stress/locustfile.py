"""
Locust load test definitions for Aithena.

User classes simulate four real-world personas hitting the solr-search API:
  - SearchUser   — keyword, semantic, and hybrid search queries
  - BrowseUser   — pagination, faceted filtering, similar books
  - UploadUser   — document uploads via multipart/form-data
  - AdminUser    — queue monitoring, requeue, metadata edits

Three pre-defined load shapes (set via ``--config`` or ``LOCUST_SCENARIO``):
  light   (5 users):   80% search, 20% browse
  medium  (10 users):  60% search, 20% browse, 20% upload
  heavy   (25 users):  50% search, 25% upload, 25% admin

Run headless for CI::

    locust -f tests/stress/locustfile.py --headless \\
        -u 10 -r 2 --run-time 60s \\
        --csv tests/stress/results/medium \\
        --host http://localhost:8080

Environment variables:
    SEARCH_API_URL      Base URL (default http://localhost:8080)
    LOCUST_SCENARIO     light | medium | heavy (overrides -u/-r)
    LOCUST_RUN_TIME     Duration string e.g. "120s" (default 60s)
"""

from __future__ import annotations

import io
import json
import logging
import os
import random
from typing import Any

from locust import HttpUser, between, events, tag, task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared query / data pools (deterministic, no Faker dependency at runtime)
# ---------------------------------------------------------------------------

SEARCH_QUERIES: list[str] = [
    "python programming",
    "machine learning",
    "data science",
    "artificial intelligence",
    "web development",
    "algorithms",
    "deep learning",
    "natural language processing",
    "computer vision",
    "distributed systems",
    "database design",
    "operating systems",
    "software engineering",
    "cloud computing",
    "cybersecurity",
    "quantum computing",
    "blockchain",
    "robotics",
    "game development",
    "functional programming",
]

FACET_AUTHORS: list[str] = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
]

FACET_CATEGORIES: list[str] = [
    "Computer Science",
    "Mathematics",
    "Engineering",
    "Physics",
    "Biology",
]

FACET_LANGUAGES: list[str] = ["en", "es", "fr", "de"]

SEARCH_MODES: list[str] = ["keyword", "semantic", "hybrid"]

METADATA_CATEGORIES: list[str] = [
    "Science",
    "Technology",
    "Engineering",
    "Mathematics",
    "Fiction",
]

# ---------------------------------------------------------------------------
# Load-scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "light": {
        "users": 5,
        "spawn_rate": 1,
        "run_time": "60s",
        "weights": {"search": 80, "browse": 20, "upload": 0, "admin": 0},
    },
    "medium": {
        "users": 10,
        "spawn_rate": 2,
        "run_time": "120s",
        "weights": {"search": 60, "browse": 20, "upload": 20, "admin": 0},
    },
    "heavy": {
        "users": 25,
        "spawn_rate": 5,
        "run_time": "180s",
        "weights": {"search": 50, "browse": 0, "upload": 25, "admin": 25},
    },
}

DEFAULT_SCENARIO = "medium"


def get_scenario() -> dict[str, Any]:
    """Return the active scenario configuration."""
    name = os.environ.get("LOCUST_SCENARIO", DEFAULT_SCENARIO).lower()
    return SCENARIOS.get(name, SCENARIOS[DEFAULT_SCENARIO])


# ---------------------------------------------------------------------------
# Helper functions (unit-testable, no Locust dependency)
# ---------------------------------------------------------------------------


def build_search_params(
    query: str,
    mode: str = "keyword",
    page: int = 1,
    page_size: int = 10,
    fq_author: str | None = None,
    fq_category: str | None = None,
    fq_language: str | None = None,
) -> dict[str, str | int]:
    """Build query-string parameters for ``GET /search``."""
    params: dict[str, str | int] = {
        "q": query,
        "mode": mode,
        "page": page,
        "page_size": page_size,
    }
    if fq_author:
        params["fq_author"] = fq_author
    if fq_category:
        params["fq_category"] = fq_category
    if fq_language:
        params["fq_language"] = fq_language
    return params


def build_facet_params(
    query: str | None = None,
    fq_author: str | None = None,
    fq_category: str | None = None,
) -> dict[str, str]:
    """Build query-string parameters for ``GET /facets``."""
    params: dict[str, str] = {}
    if query:
        params["q"] = query
    if fq_author:
        params["fq_author"] = fq_author
    if fq_category:
        params["fq_category"] = fq_category
    return params


def build_books_params(page: int = 1, page_size: int = 20) -> dict[str, int]:
    """Build query-string parameters for ``GET /books``."""
    return {"page": page, "page_size": page_size}


def make_tiny_pdf() -> bytes:
    """Return a minimal valid PDF bytestring for upload tests."""
    content = (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF\n"
    )
    return content


def parse_search_response(data: dict) -> dict[str, Any]:
    """Extract summary metrics from a search API response."""
    return {
        "total": data.get("total", 0),
        "result_count": len(data.get("results", [])),
        "has_facets": bool(data.get("facets")),
    }


def choose_random_query(rng: random.Random | None = None) -> str:
    """Pick a random search query from the pool."""
    r = rng or random
    return r.choice(SEARCH_QUERIES)


def choose_random_mode(rng: random.Random | None = None) -> str:
    """Pick a random search mode."""
    r = rng or random
    return r.choice(SEARCH_MODES)


# ---------------------------------------------------------------------------
# Locust event hooks — write JSON summary alongside CSV
# ---------------------------------------------------------------------------


@events.quitting.add_listener
def _write_json_summary(environment, **_kwargs):
    """Dump aggregated stats to a JSON file next to the CSV output."""
    stats = environment.stats
    if not stats.total.num_requests:
        return

    results_dir = os.environ.get(
        "STRESS_RESULTS_DIR",
        os.path.join(os.path.dirname(__file__), "results"),
    )
    os.makedirs(results_dir, exist_ok=True)

    summary = {
        "scenario": os.environ.get("LOCUST_SCENARIO", DEFAULT_SCENARIO),
        "total_requests": stats.total.num_requests,
        "total_failures": stats.total.num_failures,
        "error_rate_percent": round(
            (stats.total.num_failures / max(stats.total.num_requests, 1)) * 100, 2
        ),
        "requests_per_second": round(stats.total.current_rps, 2),
        "avg_response_time_ms": round(stats.total.avg_response_time, 2),
        "p50_ms": stats.total.get_response_time_percentile(0.50),
        "p95_ms": stats.total.get_response_time_percentile(0.95),
        "p99_ms": stats.total.get_response_time_percentile(0.99),
        "endpoints": {},
    }

    for entry in stats.entries.values():
        key = f"{entry.method} {entry.name}"
        summary["endpoints"][key] = {
            "num_requests": entry.num_requests,
            "num_failures": entry.num_failures,
            "avg_ms": round(entry.avg_response_time, 2),
            "p95_ms": entry.get_response_time_percentile(0.95),
            "p99_ms": entry.get_response_time_percentile(0.99),
            "rps": round(entry.current_rps, 2),
        }

    path = os.path.join(results_dir, "locust_summary.json")
    with open(path, "w") as fh:
        json.dump(summary, fh, indent=2)
    logger.info("Locust JSON summary written to %s", path)


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------


class SearchUser(HttpUser):
    """Simulates a user performing search operations.

    Covers keyword, semantic, and hybrid search with optional facet filters.
    """

    weight = 3
    wait_time = between(1, 3)

    @tag("search", "keyword")
    @task(5)
    def keyword_search(self):
        query = choose_random_query()
        params = build_search_params(query, mode="keyword")
        self.client.get("/search", params=params, name="/search [keyword]")

    @tag("search", "semantic")
    @task(3)
    def semantic_search(self):
        query = choose_random_query()
        params = build_search_params(query, mode="semantic")
        self.client.get("/search", params=params, name="/search [semantic]")

    @tag("search", "hybrid")
    @task(2)
    def hybrid_search(self):
        query = choose_random_query()
        params = build_search_params(query, mode="hybrid")
        self.client.get("/search", params=params, name="/search [hybrid]")

    @tag("search", "faceted")
    @task(2)
    def faceted_search(self):
        query = choose_random_query()
        params = build_search_params(
            query,
            mode="keyword",
            fq_author=random.choice(FACET_AUTHORS),
            fq_category=random.choice(FACET_CATEGORIES),
        )
        self.client.get("/search", params=params, name="/search [faceted]")

    @tag("search")
    @task(1)
    def search_page_two(self):
        query = choose_random_query()
        params = build_search_params(query, mode="keyword", page=2)
        self.client.get("/search", params=params, name="/search [page2]")


class BrowseUser(HttpUser):
    """Simulates a user browsing books, facets, and stats."""

    weight = 1
    wait_time = between(2, 5)

    @tag("browse")
    @task(3)
    def list_books(self):
        page = random.randint(1, 5)
        params = build_books_params(page=page, page_size=20)
        self.client.get("/books", params=params, name="/books")

    @tag("browse", "facets")
    @task(2)
    def get_facets(self):
        params = build_facet_params(
            query=choose_random_query(),
            fq_category=random.choice(FACET_CATEGORIES),
        )
        self.client.get("/facets", params=params, name="/facets")

    @tag("browse")
    @task(2)
    def view_stats(self):
        self.client.get("/stats", name="/stats")

    @tag("browse")
    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")

    @tag("browse")
    @task(1)
    def get_collections(self):
        self.client.get("/v1/collections", name="/v1/collections")


class UploadUser(HttpUser):
    """Simulates a user uploading documents."""

    weight = 1
    wait_time = between(5, 10)

    def on_start(self):
        self._pdf_bytes = make_tiny_pdf()

    @tag("upload")
    @task
    def upload_document(self):
        files = {"file": ("test_upload.pdf", io.BytesIO(self._pdf_bytes), "application/pdf")}
        self.client.post("/v1/upload", files=files, name="/v1/upload")


class AdminUser(HttpUser):
    """Simulates an administrator monitoring and managing the queue."""

    weight = 1
    wait_time = between(3, 8)

    @tag("admin")
    @task(3)
    def list_documents(self):
        self.client.get("/v1/admin/documents", name="/v1/admin/documents")

    @tag("admin")
    @task(2)
    def list_failed_documents(self):
        self.client.get(
            "/v1/admin/documents",
            params={"status": "failed"},
            name="/v1/admin/documents [failed]",
        )

    @tag("admin")
    @task(1)
    def requeue_failed(self):
        self.client.post(
            "/v1/admin/documents/requeue-failed",
            name="/v1/admin/documents/requeue-failed",
        )

    @tag("admin")
    @task(1)
    def view_status(self):
        self.client.get("/v1/status", name="/v1/status")

    @tag("admin")
    @task(1)
    def view_containers(self):
        self.client.get("/v1/admin/containers", name="/v1/admin/containers")
