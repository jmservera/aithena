"""
Post-restore verification logic for Aithena.

Pure functions that parse service responses and determine health status.
These functions have NO external dependencies (no HTTP, no Docker) so they
can be unit-tested without infrastructure.

The integration layer (verify-restore.sh, test_verify_restore.py) calls
these functions after fetching live data from each service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(Enum):
    """Outcome of a single verification check."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    """Result of a single verification check."""

    name: str
    status: CheckStatus
    message: str
    details: dict | None = None

    @property
    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class VerificationReport:
    """Aggregated results of all post-restore verification checks."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.status != CheckStatus.FAIL for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def skip_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.SKIP)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    def summary_line(self) -> str:
        total = len(self.checks)
        status = "PASS" if self.all_passed else "FAIL"
        return (
            f"[{status}] {self.pass_count}/{total} passed, "
            f"{self.fail_count} failed, {self.skip_count} skipped"
        )

    def format_human(self) -> str:
        """Format results for human-readable terminal output."""
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("Post-Restore Verification Report")
        lines.append("=" * 60)
        for check in self.checks:
            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(check.status.value, "?")
            lines.append(f"  {icon}  {check.name}: {check.message}")
        lines.append("-" * 60)
        lines.append(self.summary_line())
        lines.append("=" * 60)
        return "\n".join(lines)

    def format_ci(self) -> str:
        """Format results for CI/machine parsing (one check per line)."""
        lines: list[str] = []
        for check in self.checks:
            lines.append(f"{check.status.value}\t{check.name}\t{check.message}")
        lines.append(self.summary_line())
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Solr verification logic
# ---------------------------------------------------------------------------


def verify_solr_cluster_status(cluster_status: dict) -> CheckResult:
    """
    Verify Solr cluster health from a CLUSTERSTATUS API response.

    Expects the ``cluster`` key with ``collections`` and ``live_nodes``.
    Checks that:
    - At least one live node exists
    - The ``books`` collection exists
    - All shards have at least one active replica
    """
    name = "solr_cluster_status"

    cluster = cluster_status.get("cluster", {})
    live_nodes = cluster.get("live_nodes", [])
    if not live_nodes:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message="No live Solr nodes found",
            details={"live_nodes": 0},
        )

    collections = cluster.get("collections", {})
    if "books" not in collections:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message="'books' collection not found in Solr",
            details={"collections": list(collections.keys())},
        )

    books = collections["books"]
    shards = books.get("shards", {})
    unhealthy_shards: list[str] = []

    for shard_name, shard_data in shards.items():
        replicas = shard_data.get("replicas", {})
        active_replicas = [
            r for r in replicas.values() if r.get("state") == "active"
        ]
        if not active_replicas:
            unhealthy_shards.append(shard_name)

    if unhealthy_shards:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Shards with no active replicas: {', '.join(unhealthy_shards)}",
            details={"unhealthy_shards": unhealthy_shards, "live_nodes": len(live_nodes)},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"{len(live_nodes)} nodes, {len(shards)} shard(s) healthy",
        details={"live_nodes": len(live_nodes), "shards": len(shards)},
    )


def verify_solr_doc_count(select_response: dict, min_docs: int = 0) -> CheckResult:
    """
    Verify Solr document count from a /select response.

    Checks that ``response.numFound`` >= *min_docs*.
    """
    name = "solr_doc_count"

    response = select_response.get("response", {})
    num_found = response.get("numFound", 0)

    if num_found < min_docs:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Found {num_found} docs, expected >= {min_docs}",
            details={"numFound": num_found, "min_docs": min_docs},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"{num_found} documents in index",
        details={"numFound": num_found},
    )


def verify_solr_query(select_response: dict, query: str) -> CheckResult:
    """
    Verify that a Solr query returns at least one result.
    """
    name = f"solr_query_{_sanitize_label(query)}"

    response = select_response.get("response", {})
    num_found = response.get("numFound", 0)

    if num_found == 0:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Query '{query}' returned 0 results",
            details={"query": query, "numFound": 0},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"Query '{query}' returned {num_found} result(s)",
        details={"query": query, "numFound": num_found},
    )


# ---------------------------------------------------------------------------
# Redis verification logic
# ---------------------------------------------------------------------------


def verify_redis_ping(pong_response: str | None) -> CheckResult:
    """Verify Redis PING returns PONG."""
    name = "redis_ping"

    if pong_response is not None and pong_response.strip().upper() == "PONG":
        return CheckResult(
            name=name,
            status=CheckStatus.PASS,
            message="Redis responding to PING",
        )

    return CheckResult(
        name=name,
        status=CheckStatus.FAIL,
        message=f"Redis PING failed: got '{pong_response}'",
    )


def verify_redis_key_count(
    db_size: int | None,
    min_keys: int = 0,
) -> CheckResult:
    """Verify Redis has the expected minimum number of keys."""
    name = "redis_key_count"

    if db_size is None:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message="Could not retrieve Redis DBSIZE",
        )

    if db_size < min_keys:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Redis has {db_size} keys, expected >= {min_keys}",
            details={"dbsize": db_size, "min_keys": min_keys},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"Redis has {db_size} key(s)",
        details={"dbsize": db_size},
    )


# ---------------------------------------------------------------------------
# RabbitMQ verification logic
# ---------------------------------------------------------------------------


def verify_rabbitmq_accessible(status_code: int | None) -> CheckResult:
    """Verify RabbitMQ management API is accessible."""
    name = "rabbitmq_accessible"

    if status_code == 200:
        return CheckResult(
            name=name,
            status=CheckStatus.PASS,
            message="RabbitMQ management API accessible",
        )

    return CheckResult(
        name=name,
        status=CheckStatus.FAIL,
        message=f"RabbitMQ management API returned status {status_code}",
        details={"status_code": status_code},
    )


def verify_rabbitmq_queues(
    queues_response: list[dict],
    expected_queues: list[str] | None = None,
) -> CheckResult:
    """
    Verify RabbitMQ queues exist and are healthy.

    If *expected_queues* is provided, checks that all named queues exist.
    Otherwise, just checks that at least one queue exists.
    """
    name = "rabbitmq_queues"

    queue_names = [q.get("name", "") for q in queues_response]

    if expected_queues:
        missing = [q for q in expected_queues if q not in queue_names]
        if missing:
            return CheckResult(
                name=name,
                status=CheckStatus.FAIL,
                message=f"Missing queues: {', '.join(missing)}",
                details={"missing": missing, "found": queue_names},
            )

        return CheckResult(
            name=name,
            status=CheckStatus.PASS,
            message=f"All {len(expected_queues)} expected queue(s) present",
            details={"queues": queue_names},
        )

    if not queue_names:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message="No queues found in RabbitMQ",
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"{len(queue_names)} queue(s) found",
        details={"queues": queue_names},
    )


def verify_rabbitmq_exchanges(
    exchanges_response: list[dict],
    expected_exchanges: list[str] | None = None,
) -> CheckResult:
    """Verify RabbitMQ exchanges exist."""
    name = "rabbitmq_exchanges"

    exchange_names = [e.get("name", "") for e in exchanges_response]

    if expected_exchanges:
        missing = [e for e in expected_exchanges if e not in exchange_names]
        if missing:
            return CheckResult(
                name=name,
                status=CheckStatus.FAIL,
                message=f"Missing exchanges: {', '.join(missing)}",
                details={"missing": missing, "found": exchange_names},
            )
        return CheckResult(
            name=name,
            status=CheckStatus.PASS,
            message=f"All {len(expected_exchanges)} expected exchange(s) present",
            details={"exchanges": exchange_names},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"{len(exchange_names)} exchange(s) found",
        details={"exchanges": exchange_names},
    )


# ---------------------------------------------------------------------------
# Auth / collections DB verification logic
# ---------------------------------------------------------------------------


def verify_auth_db_integrity(
    table_names: list[str],
    user_count: int | None,
) -> CheckResult:
    """
    Verify the auth SQLite database has expected tables and data.

    Checks:
    - ``users`` table exists
    - At least one user record exists
    """
    name = "auth_db_integrity"

    if "users" not in table_names:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message="'users' table not found in auth DB",
            details={"tables": table_names},
        )

    if user_count is None or user_count < 1:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Auth DB has {user_count} users, expected >= 1",
            details={"tables": table_names, "user_count": user_count},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"Auth DB healthy: {user_count} user(s), tables={table_names}",
        details={"tables": table_names, "user_count": user_count},
    )


def verify_collections_db_integrity(
    table_names: list[str],
) -> CheckResult:
    """
    Verify the collections SQLite database structure.

    The collections DB is a newer feature — if the file doesn't exist that's
    not a failure, but if it does, the schema should be valid.
    """
    name = "collections_db_integrity"

    if not table_names:
        return CheckResult(
            name=name,
            status=CheckStatus.SKIP,
            message="Collections DB not found or empty (optional)",
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"Collections DB has {len(table_names)} table(s)",
        details={"tables": table_names},
    )


# ---------------------------------------------------------------------------
# Docker Compose service verification logic
# ---------------------------------------------------------------------------


def verify_compose_services(
    service_statuses: dict[str, str],
    expected_services: list[str] | None = None,
) -> CheckResult:
    """
    Verify Docker Compose services are running.

    *service_statuses* maps service name → status string (e.g. "running",
    "exited", "restarting").
    """
    name = "compose_services_healthy"

    if not service_statuses:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message="No Docker Compose services found",
        )

    not_running = {
        svc: status
        for svc, status in service_statuses.items()
        if status.lower() not in ("running",)
    }

    if expected_services:
        missing = [s for s in expected_services if s not in service_statuses]
        if missing:
            return CheckResult(
                name=name,
                status=CheckStatus.FAIL,
                message=f"Missing services: {', '.join(missing)}",
                details={"missing": missing, "not_running": not_running},
            )

    if not_running:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"{len(not_running)} service(s) not running: {', '.join(not_running.keys())}",
            details={"not_running": not_running},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"All {len(service_statuses)} service(s) running",
        details={"services": list(service_statuses.keys())},
    )


# ---------------------------------------------------------------------------
# Log error detection
# ---------------------------------------------------------------------------

# Patterns that indicate real errors (not warnings or debug noise)
_ERROR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bERROR\b", re.IGNORECASE),
    re.compile(r"\bFATAL\b", re.IGNORECASE),
    re.compile(r"\bPANIC\b", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"Exception in thread", re.IGNORECASE),
]

# Patterns that are known false positives
_ERROR_EXCLUSIONS: list[re.Pattern[str]] = [
    re.compile(r"No such file or directory.*\.swp", re.IGNORECASE),
    re.compile(r"error_log", re.IGNORECASE),
    re.compile(r"error\.log", re.IGNORECASE),
    re.compile(r"loglevel.*error", re.IGNORECASE),
    re.compile(r"ERROR_REPORTING", re.IGNORECASE),
]


def verify_no_log_errors(
    log_lines: list[str],
    max_errors: int = 0,
) -> CheckResult:
    """
    Scan log lines for error-level entries.

    Returns FAIL if more than *max_errors* genuine error lines are found.
    """
    name = "no_log_errors"

    error_lines: list[str] = []
    for line in log_lines:
        if any(pat.search(line) for pat in _ERROR_PATTERNS):
            if not any(exc.search(line) for exc in _ERROR_EXCLUSIONS):
                error_lines.append(line.strip())

    if len(error_lines) > max_errors:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Found {len(error_lines)} error(s) in logs (max allowed: {max_errors})",
            details={"error_count": len(error_lines), "sample_errors": error_lines[:5]},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"No unexpected errors in logs ({len(log_lines)} lines scanned)",
        details={"lines_scanned": len(log_lines)},
    )


# ---------------------------------------------------------------------------
# Disk usage verification
# ---------------------------------------------------------------------------


def verify_disk_usage(
    usage_percent: float | None,
    max_percent: float = 90.0,
) -> CheckResult:
    """
    Verify disk usage is within acceptable limits.

    *usage_percent* is the percentage of disk used (0-100).
    """
    name = "disk_usage"

    if usage_percent is None:
        return CheckResult(
            name=name,
            status=CheckStatus.SKIP,
            message="Could not determine disk usage",
        )

    if usage_percent > max_percent:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"Disk usage {usage_percent:.1f}% exceeds threshold ({max_percent:.1f}%)",
            details={"usage_percent": usage_percent, "max_percent": max_percent},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.PASS,
        message=f"Disk usage {usage_percent:.1f}% (threshold: {max_percent:.1f}%)",
        details={"usage_percent": usage_percent, "max_percent": max_percent},
    )


# ---------------------------------------------------------------------------
# Admin UI verification
# ---------------------------------------------------------------------------


def verify_admin_ui_accessible(status_code: int | None) -> CheckResult:
    """Verify the Admin UI is accessible."""
    name = "admin_ui_accessible"

    if status_code is not None and 200 <= status_code < 400:
        return CheckResult(
            name=name,
            status=CheckStatus.PASS,
            message="Admin UI accessible",
            details={"status_code": status_code},
        )

    return CheckResult(
        name=name,
        status=CheckStatus.FAIL,
        message=f"Admin UI returned status {status_code}",
        details={"status_code": status_code},
    )


# ---------------------------------------------------------------------------
# Auth login verification
# ---------------------------------------------------------------------------


def verify_auth_login(status_code: int | None, has_token: bool = False) -> CheckResult:
    """Verify login endpoint works with test credentials."""
    name = "auth_login"

    if status_code is None:
        return CheckResult(
            name=name,
            status=CheckStatus.SKIP,
            message="No test credentials configured (set VERIFY_USERNAME/VERIFY_PASSWORD)",
        )

    if status_code == 200 and has_token:
        return CheckResult(
            name=name,
            status=CheckStatus.PASS,
            message="Login successful, token received",
        )

    return CheckResult(
        name=name,
        status=CheckStatus.FAIL,
        message=f"Login failed: status={status_code}, token={'yes' if has_token else 'no'}",
        details={"status_code": status_code, "has_token": has_token},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_label(text: str) -> str:
    """Convert text to a safe label for check names."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()[:40]
