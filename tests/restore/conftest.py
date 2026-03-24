"""
Shared fixtures for the Aithena post-restore verification test suite.

Provides:
- Service URL resolution (Solr, API, RabbitMQ, Redis, Admin)
- Docker Compose helpers
- Service reachability checks

Environment variables (with defaults for the local dev stack):
  COMPOSE_FILE        Path to docker-compose.yml (default: repo root)
  COMPOSE_PROJECT     Docker Compose project name (default: aithena)
  SOLR_URL            Solr base URL (default: http://localhost:8983/solr/books)
  SEARCH_API_URL      solr-search base URL (default: http://localhost:8080)
  ADMIN_URL           Admin UI URL (default: http://localhost/admin)
  RABBITMQ_API_URL    RabbitMQ management URL (default: http://localhost:15672)
  RABBITMQ_USER       RabbitMQ username (default: guest)
  RABBITMQ_PASSWORD   RabbitMQ password (default: guest)
  REDIS_HOST          Redis host (default: localhost)
  REDIS_PORT          Redis port (default: 6379)
  AUTH_DB_DIR         Auth DB directory (default: ~/.local/share/aithena/auth)
  VERIFY_TIMEOUT      Per-check timeout in seconds (default: 30)
  VERIFY_USERNAME     Test username for auth verification
  VERIFY_PASSWORD     Test password for auth verification
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

COMPOSE_FILE: str = os.environ.get("COMPOSE_FILE", str(REPO_ROOT / "docker-compose.yml"))
COMPOSE_PROJECT: str = os.environ.get("COMPOSE_PROJECT", "aithena")
SOLR_URL: str = os.environ.get("SOLR_URL", "http://localhost:8983/solr/books")
SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")
ADMIN_URL: str = os.environ.get("ADMIN_URL", "http://localhost/admin")
RABBITMQ_API_URL: str = os.environ.get("RABBITMQ_API_URL", "http://localhost:15672")
RABBITMQ_USER: str = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD: str = os.environ.get("RABBITMQ_PASSWORD", "guest")
REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))
AUTH_DB_DIR: str = os.environ.get(
    "AUTH_DB_DIR",
    str(Path.home() / ".local" / "share" / "aithena" / "auth"),
)
VERIFY_TIMEOUT: int = int(os.environ.get("VERIFY_TIMEOUT", "30"))
VERIFY_USERNAME: str = os.environ.get("VERIFY_USERNAME", "")
VERIFY_PASSWORD: str = os.environ.get("VERIFY_PASSWORD", "")


# ---------------------------------------------------------------------------
# Service URL fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def solr_url() -> str:
    """Base Solr collection URL."""
    return SOLR_URL


@pytest.fixture(scope="session")
def search_api_url() -> str:
    """Base URL for the solr-search API."""
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def admin_url() -> str:
    """Admin UI URL."""
    return ADMIN_URL.rstrip("/")


@pytest.fixture(scope="session")
def rabbitmq_api_url() -> str:
    """RabbitMQ management API URL."""
    return RABBITMQ_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def rabbitmq_credentials() -> tuple[str, str]:
    """RabbitMQ username and password."""
    return (RABBITMQ_USER, RABBITMQ_PASSWORD)


@pytest.fixture(scope="session")
def redis_config() -> dict[str, str | int]:
    """Redis connection parameters."""
    return {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
    }


@pytest.fixture(scope="session")
def auth_db_dir() -> str:
    """Path to the auth database directory."""
    return AUTH_DB_DIR


@pytest.fixture(scope="session")
def verify_timeout() -> int:
    """Timeout in seconds for individual verification checks."""
    return VERIFY_TIMEOUT


@pytest.fixture(scope="session")
def verify_credentials() -> tuple[str, str]:
    """Test credentials for auth verification."""
    return (VERIFY_USERNAME, VERIFY_PASSWORD)


# ---------------------------------------------------------------------------
# Docker Compose helpers
# ---------------------------------------------------------------------------


def _compose_cmd(*args: str) -> list[str]:
    """Build a docker compose command list."""
    return ["docker", "compose", "-f", COMPOSE_FILE, "-p", COMPOSE_PROJECT, *args]


def _docker_available() -> bool:
    """Check if the Docker daemon is reachable."""
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


@pytest.fixture(scope="session")
def compose_cmd():
    """Return a helper to build compose commands."""
    return _compose_cmd
