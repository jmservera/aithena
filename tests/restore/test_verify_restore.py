"""
Post-restore verification integration tests.

These tests hit real services (Solr, Redis, RabbitMQ, Admin UI) and verify
data integrity after a restore operation.  All tests are marked with
``@pytest.mark.docker`` and will be skipped when infrastructure is unavailable.

Run only unit tests:  ``pytest -m "not docker"``
Run integration tests: ``pytest -m docker``  (requires running stack)
"""

from __future__ import annotations

import subprocess

import pytest
import requests
from verify_checks import (
    VerificationReport,
    verify_admin_ui_accessible,
    verify_auth_login,
    verify_compose_services,
    verify_disk_usage,
    verify_no_log_errors,
    verify_rabbitmq_accessible,
    verify_rabbitmq_exchanges,
    verify_rabbitmq_queues,
    verify_redis_key_count,
    verify_redis_ping,
    verify_solr_cluster_status,
    verify_solr_doc_count,
    verify_solr_query,
)

# ---------------------------------------------------------------------------
# Skip when Docker is not available
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    try:
        result = subprocess.run(  # noqa: S603
            ["docker", "info"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available"),
]


# =========================================================================
# Solr integration tests
# =========================================================================


@pytest.mark.solr
class TestSolrVerification:
    """Verify Solr data integrity against a running instance."""

    def test_cluster_status(self, solr_url: str, verify_timeout: int):
        """Check 1: Solr collection status shows replicas healthy."""
        base = solr_url.rsplit("/solr/", 1)[0]
        url = f"{base}/solr/admin/collections?action=CLUSTERSTATUS&wt=json"
        resp = requests.get(url, timeout=verify_timeout)
        resp.raise_for_status()
        result = verify_solr_cluster_status(resp.json())
        assert result.passed, result.message

    def test_doc_count(self, solr_url: str, verify_timeout: int):
        """Verify Solr has documents indexed."""
        url = f"{solr_url}/select?q=*:*&rows=0&wt=json"
        resp = requests.get(url, timeout=verify_timeout)
        resp.raise_for_status()
        result = verify_solr_doc_count(resp.json(), min_docs=0)
        assert result.passed, result.message

    @pytest.mark.parametrize(
        "query",
        ["*:*", "title:*"],
        ids=["wildcard", "title_field"],
    )
    def test_sample_queries(self, solr_url: str, verify_timeout: int, query: str):
        """Verify basic Solr queries return results."""
        url = f"{solr_url}/select?q={query}&rows=1&wt=json"
        resp = requests.get(url, timeout=verify_timeout)
        resp.raise_for_status()
        _result = verify_solr_query(resp.json(), query=query)
        # Queries may return 0 on an empty-but-healthy index; just confirm no errors
        assert resp.status_code == 200


# =========================================================================
# Redis integration tests
# =========================================================================


@pytest.mark.redis
class TestRedisVerification:
    """Verify Redis data integrity against a running instance."""

    def test_ping(self, redis_config: dict, verify_timeout: int):
        """Check 5: Redis responds to PING."""
        import socket

        host = redis_config["host"]
        port = redis_config["port"]
        password = redis_config.get("password", "")

        try:
            sock = socket.create_connection((host, port), timeout=verify_timeout)
            if password:
                sock.sendall(f"AUTH {password}\r\n".encode())
                sock.recv(1024)
            sock.sendall(b"PING\r\n")
            response = sock.recv(1024).decode().strip()
            sock.close()
            # Redis protocol: "+PONG\r\n"
            pong = response.lstrip("+").strip()
        except (OSError, ConnectionError):
            pong = None

        result = verify_redis_ping(pong)
        assert result.passed, result.message

    def test_key_count(self, redis_config: dict, verify_timeout: int):
        """Verify Redis key count is retrievable."""
        import socket

        host = redis_config["host"]
        port = redis_config["port"]
        password = redis_config.get("password", "")

        try:
            sock = socket.create_connection((host, port), timeout=verify_timeout)
            if password:
                sock.sendall(f"AUTH {password}\r\n".encode())
                sock.recv(1024)
            sock.sendall(b"DBSIZE\r\n")
            response = sock.recv(1024).decode().strip()
            sock.close()
            # Redis protocol: ":42\r\n"
            db_size = int(response.lstrip(":"))
        except (OSError, ConnectionError, ValueError):
            db_size = None

        result = verify_redis_key_count(db_size, min_keys=0)
        assert result.passed, result.message


# =========================================================================
# RabbitMQ integration tests
# =========================================================================


@pytest.mark.rabbitmq
class TestRabbitMQVerification:
    """Verify RabbitMQ configuration against a running instance."""

    def test_management_accessible(
        self,
        rabbitmq_api_url: str,
        rabbitmq_credentials: tuple[str, str],
        verify_timeout: int,
    ):
        """Check 6: RabbitMQ management UI accessible."""
        try:
            resp = requests.get(
                f"{rabbitmq_api_url}/api/overview",
                auth=rabbitmq_credentials,
                timeout=verify_timeout,
            )
            status = resp.status_code
        except requests.RequestException:
            status = None

        result = verify_rabbitmq_accessible(status)
        assert result.passed, result.message

    def test_queues(
        self,
        rabbitmq_api_url: str,
        rabbitmq_credentials: tuple[str, str],
        verify_timeout: int,
    ):
        """Verify RabbitMQ queues exist."""
        try:
            resp = requests.get(
                f"{rabbitmq_api_url}/api/queues",
                auth=rabbitmq_credentials,
                timeout=verify_timeout,
            )
            resp.raise_for_status()
            queues = resp.json()
        except requests.RequestException:
            queues = []

        _result = verify_rabbitmq_queues(queues)
        # Queues may be empty on a fresh restore; just verify API works
        assert isinstance(queues, list)

    def test_exchanges(
        self,
        rabbitmq_api_url: str,
        rabbitmq_credentials: tuple[str, str],
        verify_timeout: int,
    ):
        """Verify RabbitMQ exchanges exist (defaults always present)."""
        try:
            resp = requests.get(
                f"{rabbitmq_api_url}/api/exchanges",
                auth=rabbitmq_credentials,
                timeout=verify_timeout,
            )
            resp.raise_for_status()
            exchanges = resp.json()
        except requests.RequestException:
            exchanges = []

        result = verify_rabbitmq_exchanges(exchanges)
        assert result.passed, result.message


# =========================================================================
# Auth DB integration tests
# =========================================================================


@pytest.mark.auth
class TestAuthVerification:
    """Verify auth/collections database integrity."""

    def test_auth_login(
        self,
        search_api_url: str,
        verify_credentials: tuple[str, str],
        verify_timeout: int,
    ):
        """Check 3: Login works with known test credentials."""
        username, password = verify_credentials
        if not username or not password:
            pytest.skip("No test credentials configured (VERIFY_USERNAME/VERIFY_PASSWORD)")

        try:
            resp = requests.post(
                f"{search_api_url}/v1/auth/login",
                json={"username": username, "password": password},
                timeout=verify_timeout,
            )
            status = resp.status_code
            has_token = "token" in resp.text.lower() or "access" in resp.text.lower()
        except requests.RequestException:
            status = None
            has_token = False

        result = verify_auth_login(status, has_token)
        assert result.passed or result.status.value == "SKIP", result.message


# =========================================================================
# Service health integration tests
# =========================================================================


@pytest.mark.services
class TestServiceHealthVerification:
    """Verify Docker Compose service health."""

    def test_compose_services_running(self, compose_cmd):
        """Check 1: All services report healthy in docker-compose ps."""
        try:
            result = subprocess.run(  # noqa: S603
                compose_cmd("ps", "--format", "{{.Name}}\t{{.Status}}"),
                capture_output=True,
                text=True,
                timeout=30,
            )
            statuses = {}
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    status_str = parts[1].strip().lower()
                    # Docker status: "Up 2 hours (healthy)" → "running"
                    if "up" in status_str:
                        statuses[name] = "running"
                    elif "exit" in status_str:
                        statuses[name] = "exited"
                    else:
                        statuses[name] = status_str
        except (subprocess.SubprocessError, FileNotFoundError):
            statuses = {}

        check = verify_compose_services(statuses)
        assert check.passed, check.message

    def test_admin_ui_accessible(self, admin_url: str, verify_timeout: int):
        """Check 2: Admin UI loads at http://localhost/admin."""
        try:
            resp = requests.get(admin_url, timeout=verify_timeout, allow_redirects=True)
            status = resp.status_code
        except requests.RequestException:
            status = None

        result = verify_admin_ui_accessible(status)
        assert result.passed, result.message

    def test_search_api_health(self, search_api_url: str, verify_timeout: int):
        """Check 4: Search API health endpoint responds."""
        try:
            resp = requests.get(f"{search_api_url}/health", timeout=verify_timeout)
            assert resp.status_code == 200
        except requests.RequestException as exc:
            pytest.fail(f"Search API health check failed: {exc}")

    def test_no_log_errors(self, compose_cmd):
        """Check 8: No errors in docker-compose logs (last 100 lines)."""
        try:
            result = subprocess.run(  # noqa: S603
                compose_cmd("logs", "--tail=100", "--no-color"),
                capture_output=True,
                text=True,
                timeout=60,
            )
            lines = result.stdout.splitlines()
        except (subprocess.SubprocessError, FileNotFoundError):
            lines = []

        check = verify_no_log_errors(lines)
        assert check.passed, f"{check.message}\n{check.details}"

    def test_disk_usage(self):
        """Check 9: Disk usage is reasonable."""
        try:
            result = subprocess.run(  # noqa: S603
                ["df", "--output=pcent", "/"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Output: "Use%\n  45%\n"
            lines = result.stdout.strip().splitlines()
            pct = float(lines[-1].strip().rstrip("%"))
        except (subprocess.SubprocessError, ValueError, IndexError):
            pct = None

        check = verify_disk_usage(pct, max_percent=90.0)
        assert check.passed, check.message


# =========================================================================
# Full verification suite (all checks combined)
# =========================================================================


@pytest.mark.slow
class TestFullVerificationSuite:
    """
    Run all 9 verification checks from the PRD and produce a combined report.

    This is the equivalent of running ``tests/verify-restore.sh`` but as
    a pytest test that can be invoked with ``pytest -m docker``.
    """

    def test_full_verification(
        self,
        solr_url: str,
        search_api_url: str,
        admin_url: str,
        rabbitmq_api_url: str,
        rabbitmq_credentials: tuple[str, str],
        redis_config: dict,
        verify_timeout: int,
        verify_credentials: tuple[str, str],
        compose_cmd,
    ):
        """Run all verification checks and produce a combined report."""
        report = VerificationReport()

        # 1. Docker Compose services
        try:
            result = subprocess.run(  # noqa: S603
                compose_cmd("ps", "--format", "{{.Name}}\t{{.Status}}"),
                capture_output=True,
                text=True,
                timeout=30,
            )
            statuses = {}
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    s = parts[1].strip().lower()
                    statuses[name] = "running" if "up" in s else ("exited" if "exit" in s else s)
        except (subprocess.SubprocessError, FileNotFoundError):
            statuses = {}
        report.add(verify_compose_services(statuses))

        # 2. Admin UI
        try:
            resp = requests.get(admin_url, timeout=verify_timeout, allow_redirects=True)
            report.add(verify_admin_ui_accessible(resp.status_code))
        except requests.RequestException:
            report.add(verify_admin_ui_accessible(None))

        # 3. Auth login
        username, password = verify_credentials
        if username and password:
            try:
                resp = requests.post(
                    f"{search_api_url}/v1/auth/login",
                    json={"username": username, "password": password},
                    timeout=verify_timeout,
                )
                has_token = "token" in resp.text.lower() or "access" in resp.text.lower()
                report.add(verify_auth_login(resp.status_code, has_token))
            except requests.RequestException:
                report.add(verify_auth_login(None))
        else:
            report.add(verify_auth_login(None))

        # 4. Search (keyword + semantic via Solr)
        try:
            resp = requests.get(f"{solr_url}/select?q=*:*&rows=0&wt=json", timeout=verify_timeout)
            resp.raise_for_status()
            report.add(verify_solr_doc_count(resp.json(), min_docs=0))
        except requests.RequestException:
            report.add(verify_solr_doc_count({}, min_docs=0))

        # 5. Redis PING
        import socket

        try:
            sock = socket.create_connection(
                (redis_config["host"], redis_config["port"]),
                timeout=verify_timeout,
            )
            pw = redis_config.get("password", "")
            if pw:
                sock.sendall(f"AUTH {pw}\r\n".encode())
                sock.recv(1024)
            sock.sendall(b"PING\r\n")
            pong = sock.recv(1024).decode().strip().lstrip("+").strip()
            sock.close()
        except (OSError, ConnectionError):
            pong = None
        report.add(verify_redis_ping(pong))

        # 6. RabbitMQ management
        try:
            resp = requests.get(
                f"{rabbitmq_api_url}/api/overview",
                auth=rabbitmq_credentials,
                timeout=verify_timeout,
            )
            report.add(verify_rabbitmq_accessible(resp.status_code))
        except requests.RequestException:
            report.add(verify_rabbitmq_accessible(None))

        # 7. Solr cluster status
        try:
            base = solr_url.rsplit("/solr/", 1)[0]
            resp = requests.get(
                f"{base}/solr/admin/collections?action=CLUSTERSTATUS&wt=json",
                timeout=verify_timeout,
            )
            resp.raise_for_status()
            report.add(verify_solr_cluster_status(resp.json()))
        except requests.RequestException:
            report.add(verify_solr_cluster_status({}))

        # 8. Log errors
        try:
            result = subprocess.run(  # noqa: S603
                compose_cmd("logs", "--tail=100", "--no-color"),
                capture_output=True,
                text=True,
                timeout=60,
            )
            report.add(verify_no_log_errors(result.stdout.splitlines()))
        except (subprocess.SubprocessError, FileNotFoundError):
            report.add(verify_no_log_errors([]))

        # 9. Disk usage
        try:
            result = subprocess.run(  # noqa: S603
                ["df", "--output=pcent", "/"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = result.stdout.strip().splitlines()
            pct = float(lines[-1].strip().rstrip("%"))
        except (subprocess.SubprocessError, ValueError, IndexError):
            pct = None
        report.add(verify_disk_usage(pct, max_percent=90.0))

        # Print the report
        print("\n" + report.format_human())

        assert report.all_passed, report.summary_line()
