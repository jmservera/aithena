"""Tests for the log_viewer page helpers.

The log_viewer module is now import-safe — UI/Docker I/O only runs inside
Streamlit context via render_page(). Helpers can be imported directly.
"""

from __future__ import annotations

import os

from unittest.mock import MagicMock

os.environ.setdefault("AUTH_ENABLED", "false")

from pages.log_viewer import AITHENA_SERVICES, list_running_containers, tail_logs


def _make_container(name: str, labels: dict | None = None) -> MagicMock:
    """Create a mock Docker container."""
    container = MagicMock()
    container.name = name
    container.labels = labels or {}
    return container


class TestListRunningContainers:
    def test_matches_known_services(self):
        client = MagicMock()
        client.containers.list.return_value = [
            _make_container("aithena-solr-search-1"),
            _make_container("aithena-redis-1"),
            _make_container("unrelated-service"),
        ]

        result = list_running_containers(client)
        assert "solr-search" in result
        assert "redis" in result
        assert "unrelated-service" not in result

    def test_matches_by_project_label(self):
        client = MagicMock()
        client.containers.list.return_value = [
            _make_container(
                "custom-worker",
                labels={"com.docker.compose.project": "aithena"},
            ),
        ]

        result = list_running_containers(client)
        assert "custom-worker" in result

    def test_empty_container_list(self):
        client = MagicMock()
        client.containers.list.return_value = []

        result = list_running_containers(client)
        assert result == {}


class TestTailLogs:
    def test_bytes_decoded(self):
        container = MagicMock()
        container.logs.return_value = b"2024-01-01T00:00:00Z line1\n2024-01-01T00:00:01Z line2\n"

        output = tail_logs(container, 100)
        assert "line1" in output
        assert "line2" in output
        container.logs.assert_called_once_with(tail=100, timestamps=True)

    def test_string_passthrough(self):
        container = MagicMock()
        container.logs.return_value = "already a string"

        output = tail_logs(container, 50)
        assert output == "already a string"


class TestAithenaServices:
    def test_known_services_present(self):
        assert "solr-search" in AITHENA_SERVICES
        assert "document-indexer" in AITHENA_SERVICES
        assert "redis" in AITHENA_SERVICES
