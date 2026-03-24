"""Validate nginx proxy limits match backend limits.

Regression guard for v1.8.2 (#596): file uploads failed because nginx
``client_max_body_size`` (10m) was lower than the backend upload limit
(50MB).  These tests parse the *static* nginx config files and compare
values against the backend ``Settings`` dataclass so the mismatch is
caught before deployment — no Docker required.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]  # src/solr-search/tests -> repo root
NGINX_CONF = REPO_ROOT / "src" / "nginx" / "default.conf"
NGINX_CONF_TEMPLATE = REPO_ROOT / "src" / "nginx" / "default.conf.template"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIZE_RE = re.compile(r"client_max_body_size\s+(\d+)\s*([kmg]?)\s*;", re.IGNORECASE)
_TIMEOUT_RE = re.compile(r"(proxy_read_timeout|proxy_connect_timeout)\s+(\d+)\s*([sm]?)\s*;", re.IGNORECASE)


def _parse_body_size_mb(conf_text: str) -> float | None:
    """Return ``client_max_body_size`` in megabytes, or *None* if absent."""
    match = _SIZE_RE.search(conf_text)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "k":
        return value / 1024
    if unit == "g":
        return value * 1024
    if unit == "m":
        return float(value)
    # bare number → bytes
    return value / (1024 * 1024)


def _parse_timeouts(conf_text: str) -> dict[str, int]:
    """Return proxy timeout directives as ``{name: seconds}``."""
    timeouts: dict[str, int] = {}
    for match in _TIMEOUT_RE.finditer(conf_text):
        name = match.group(1)
        value = int(match.group(2))
        unit = match.group(3).lower()
        if unit == "m":
            value *= 60
        timeouts[name] = value
    return timeouts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNginxBodySize:
    """Ensure nginx allows uploads at least as large as the backend limit."""

    @pytest.fixture()
    def backend_max_upload_mb(self) -> int:
        from config import settings

        return settings.max_upload_size_mb

    def test_default_conf_exists(self) -> None:
        assert NGINX_CONF.exists(), f"nginx config not found at {NGINX_CONF}"

    def test_client_max_body_size_is_set(self) -> None:
        body_size = _parse_body_size_mb(NGINX_CONF.read_text())
        assert body_size is not None, "client_max_body_size not found in nginx config"

    def test_nginx_limit_gte_backend_limit(self, backend_max_upload_mb: int) -> None:
        nginx_mb = _parse_body_size_mb(NGINX_CONF.read_text())
        assert nginx_mb is not None, "client_max_body_size not found in nginx config"
        assert nginx_mb >= backend_max_upload_mb, (
            f"nginx client_max_body_size ({nginx_mb}MB) is smaller than "
            f"backend MAX_UPLOAD_SIZE_MB ({backend_max_upload_mb}MB) — "
            f"uploads will be rejected by the reverse proxy before reaching FastAPI"
        )

    def test_template_matches_static_conf(self) -> None:
        if not NGINX_CONF_TEMPLATE.exists():
            pytest.skip("template not present")
        static_mb = _parse_body_size_mb(NGINX_CONF.read_text())
        template_mb = _parse_body_size_mb(NGINX_CONF_TEMPLATE.read_text())
        assert static_mb == template_mb, (
            f"default.conf ({static_mb}MB) and default.conf.template "
            f"({template_mb}MB) have different client_max_body_size values"
        )


class TestNginxProxyTimeouts:
    """Sanity-check proxy timeout values in the nginx config."""

    def test_proxy_read_timeout_is_reasonable(self) -> None:
        timeouts = _parse_timeouts(NGINX_CONF.read_text())
        read_timeout = timeouts.get("proxy_read_timeout")
        assert read_timeout is not None, "proxy_read_timeout not found in nginx config"
        assert read_timeout >= 60, (
            f"proxy_read_timeout ({read_timeout}s) is too low — "
            f"semantic search and embedding calls can take 30-60s"
        )
        assert read_timeout <= 600, (
            f"proxy_read_timeout ({read_timeout}s) is unreasonably high"
        )

    def test_proxy_connect_timeout_is_reasonable(self) -> None:
        timeouts = _parse_timeouts(NGINX_CONF.read_text())
        connect_timeout = timeouts.get("proxy_connect_timeout")
        assert connect_timeout is not None, "proxy_connect_timeout not found in nginx config"
        assert connect_timeout >= 5, (
            f"proxy_connect_timeout ({connect_timeout}s) is too low"
        )
        assert connect_timeout <= 30, (
            f"proxy_connect_timeout ({connect_timeout}s) is too high — "
            f"connections to local services should be fast"
        )


class TestNginxBodySizeParser:
    """Unit tests for the _parse_body_size_mb helper itself."""

    def test_megabytes(self) -> None:
        assert _parse_body_size_mb("client_max_body_size 64m;") == 64.0

    def test_gigabytes(self) -> None:
        assert _parse_body_size_mb("client_max_body_size 1g;") == 1024.0

    def test_kilobytes(self) -> None:
        assert _parse_body_size_mb("client_max_body_size 512k;") == 0.5

    def test_bytes(self) -> None:
        result = _parse_body_size_mb("client_max_body_size 1048576;")
        assert result is not None
        assert abs(result - 1.0) < 0.01

    def test_missing(self) -> None:
        assert _parse_body_size_mb("server { listen 80; }") is None
