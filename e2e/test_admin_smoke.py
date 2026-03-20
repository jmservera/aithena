"""
E2E smoke tests for the solr-search admin and health endpoints.

These tests run against the live stack and verify that the API surface is
reachable and returns the expected response shapes.  They are entirely
deterministic — no fixture data required — and are appropriate for use as
post-deploy smoke checks.

Prerequisites:
  • The stack is running and solr-search is reachable at SEARCH_API_URL.
  • Set SEARCH_API_URL to override (default: http://localhost:8080).

What these tests cover
~~~~~~~~~~~~~~~~~~~~~~
- /health and /v1/health — fast liveness probe
- /info and /v1/info   — service metadata fields
- /version             — build version and commit
- /v1/status           — aggregated service health shape
- /v1/admin/containers — container version/health snapshot

All tests skip if the API is not reachable (same behaviour as test_upload_index_search.py).
"""

from __future__ import annotations

import os

import pytest
import requests

SEARCH_API_URL: str = os.environ.get("SEARCH_API_URL", "http://localhost:8080")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_url() -> str:
    """Resolved base URL for the solr-search API."""
    return SEARCH_API_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_available(api_url: str) -> None:
    """Skip all tests in this module if the API is not reachable."""
    try:
        resp = requests.get(f"{api_url}/health", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"solr-search API not reachable at {api_url} — start the stack first "
            f"(see README.md §E2E Tests). Error: {exc}"
        )


# ---------------------------------------------------------------------------
# Health checks (deterministic — no indexed data required)
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Liveness probes for the solr-search service."""

    def test_health_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /health must return HTTP 200."""
        resp = requests.get(f"{api_url}/health", timeout=5)
        assert resp.status_code == 200

    def test_v1_health_alias_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /v1/health must return HTTP 200 (versioned alias)."""
        resp = requests.get(f"{api_url}/v1/health", timeout=5)
        assert resp.status_code == 200

    def test_health_response_is_json(self, api_url: str, api_available: None) -> None:
        """Health endpoint must return a JSON body."""
        resp = requests.get(f"{api_url}/health", timeout=5)
        body = resp.json()
        assert isinstance(body, dict), f"Expected dict, got {type(body)}"

    def test_health_body_contains_status_field(self, api_url: str, api_available: None) -> None:
        """Health JSON body must include a 'status' field."""
        resp = requests.get(f"{api_url}/health", timeout=5)
        body = resp.json()
        assert "status" in body, f"'status' field missing from health response: {body}"


# ---------------------------------------------------------------------------
# Info endpoint
# ---------------------------------------------------------------------------


class TestInfoEndpoint:
    """Service metadata endpoint coverage."""

    def test_info_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /info must return HTTP 200."""
        resp = requests.get(f"{api_url}/info", timeout=5)
        assert resp.status_code == 200

    def test_v1_info_alias_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /v1/info must return HTTP 200 (versioned alias)."""
        resp = requests.get(f"{api_url}/v1/info", timeout=5)
        assert resp.status_code == 200

    def test_info_contains_required_fields(self, api_url: str, api_available: None) -> None:
        """Info response must include 'title' and 'version' fields."""
        resp = requests.get(f"{api_url}/info", timeout=5)
        body = resp.json()
        assert "title" in body, f"'title' missing from /info: {body}"
        assert "version" in body, f"'version' missing from /info: {body}"

    def test_info_title_is_non_empty_string(self, api_url: str, api_available: None) -> None:
        """The 'title' field must be a non-empty string."""
        resp = requests.get(f"{api_url}/info", timeout=5)
        title = resp.json().get("title", "")
        assert isinstance(title, str) and title.strip(), f"'title' is empty or not a string: {title!r}"


# ---------------------------------------------------------------------------
# Version endpoint
# ---------------------------------------------------------------------------


class TestVersionEndpoint:
    """Build version metadata coverage."""

    def test_version_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /version must return HTTP 200."""
        resp = requests.get(f"{api_url}/version", timeout=5)
        assert resp.status_code == 200

    def test_version_contains_version_field(self, api_url: str, api_available: None) -> None:
        """Version response must include a 'version' field."""
        resp = requests.get(f"{api_url}/version", timeout=5)
        body = resp.json()
        assert "version" in body, f"'version' missing from /version: {body}"

    def test_version_contains_commit_field(self, api_url: str, api_available: None) -> None:
        """Version response must include a 'commit' field."""
        resp = requests.get(f"{api_url}/version", timeout=5)
        body = resp.json()
        assert "commit" in body, f"'commit' missing from /version: {body}"

    def test_version_field_is_non_empty(self, api_url: str, api_available: None) -> None:
        """The 'version' field in /version must be a non-empty string."""
        resp = requests.get(f"{api_url}/version", timeout=5)
        version = resp.json().get("version", "")
        assert isinstance(version, str) and version.strip(), f"'version' is empty: {version!r}"


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    """Aggregated service health status coverage."""

    def test_status_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /v1/status must return HTTP 200."""
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        assert resp.status_code == 200

    def test_status_slash_alias_returns_200(self, api_url: str, api_available: None) -> None:
        """GET /v1/status/ must return HTTP 200 (trailing slash alias)."""
        resp = requests.get(f"{api_url}/v1/status/", timeout=10)
        assert resp.status_code == 200

    def test_status_contains_solr_key(self, api_url: str, api_available: None) -> None:
        """Status response must include a 'solr' key."""
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        body = resp.json()
        assert "solr" in body, f"'solr' key missing from /v1/status: {body}"

    def test_status_contains_services_key(self, api_url: str, api_available: None) -> None:
        """Status response must include a 'services' key."""
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        body = resp.json()
        assert "services" in body, f"'services' key missing from /v1/status: {body}"

    def test_status_services_contains_expected_keys(self, api_url: str, api_available: None) -> None:
        """Status 'services' block must contain entries for solr, redis, and rabbitmq."""
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        services = resp.json().get("services", {})
        for key in ("solr", "redis", "rabbitmq"):
            assert key in services, f"'{key}' missing from status.services: {services}"

    def test_status_service_values_are_strings(self, api_url: str, api_available: None) -> None:
        """Each service status value must be a non-empty string."""
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        services = resp.json().get("services", {})
        for key, value in services.items():
            assert isinstance(value, str) and value, f"Service '{key}' has invalid status: {value!r}"

    def test_status_indexing_key_present(self, api_url: str, api_available: None) -> None:
        """Status response must include an 'indexing' key."""
        resp = requests.get(f"{api_url}/v1/status", timeout=10)
        body = resp.json()
        assert "indexing" in body, f"'indexing' key missing from /v1/status: {body}"


# ---------------------------------------------------------------------------
# Admin containers endpoint
# ---------------------------------------------------------------------------


class TestAdminContainersEndpoint:
    """Container version/health snapshot coverage."""

    def test_admin_containers_returns_200(
        self, api_url: str, api_available: None, admin_api_headers: dict[str, str]
    ) -> None:
        """GET /v1/admin/containers must return HTTP 200."""
        resp = requests.get(f"{api_url}/v1/admin/containers", headers=admin_api_headers, timeout=10)
        assert resp.status_code == 200

    def test_admin_containers_slash_alias_returns_200(
        self, api_url: str, api_available: None, admin_api_headers: dict[str, str]
    ) -> None:
        """GET /v1/admin/containers/ must return HTTP 200 (trailing slash alias)."""
        resp = requests.get(f"{api_url}/v1/admin/containers/", headers=admin_api_headers, timeout=10)
        assert resp.status_code == 200

    def test_admin_containers_contains_containers_list(
        self, api_url: str, api_available: None, admin_api_headers: dict[str, str]
    ) -> None:
        """Admin containers response must include a 'containers' list."""
        resp = requests.get(f"{api_url}/v1/admin/containers", headers=admin_api_headers, timeout=10)
        body = resp.json()
        assert "containers" in body, f"'containers' key missing from /v1/admin/containers: {body}"
        assert isinstance(body["containers"], list), (
            f"'containers' must be a list, got {type(body['containers'])}"
        )

    def test_admin_containers_list_is_non_empty(
        self, api_url: str, api_available: None, admin_api_headers: dict[str, str]
    ) -> None:
        """The containers list must include at least one entry."""
        resp = requests.get(f"{api_url}/v1/admin/containers", headers=admin_api_headers, timeout=10)
        containers = resp.json().get("containers", [])
        assert len(containers) > 0, "Expected at least one container entry in /v1/admin/containers."

    def test_admin_containers_entries_have_required_fields(
        self, api_url: str, api_available: None, admin_api_headers: dict[str, str]
    ) -> None:
        """Each container entry must include 'name', 'status', 'type', 'version', and 'commit'."""
        resp = requests.get(f"{api_url}/v1/admin/containers", headers=admin_api_headers, timeout=10)
        containers = resp.json().get("containers", [])
        required_fields = {"name", "status", "type", "version", "commit"}
        for entry in containers:
            missing = required_fields - entry.keys()
            assert not missing, f"Container entry missing fields {missing}: {entry}"

    def test_admin_containers_includes_solr_search_entry(
        self, api_url: str, api_available: None, admin_api_headers: dict[str, str]
    ) -> None:
        """The containers list must include an entry for 'solr-search'."""
        resp = requests.get(f"{api_url}/v1/admin/containers", headers=admin_api_headers, timeout=10)
        containers = resp.json().get("containers", [])
        names = [c.get("name") for c in containers]
        assert "solr-search" in names, f"'solr-search' not found in container names: {names}"
