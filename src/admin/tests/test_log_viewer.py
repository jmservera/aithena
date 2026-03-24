"""Tests for the log_viewer page helpers."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("AUTH_ENABLED", "false")


def _import_log_viewer():
    """Import log_viewer with docker and Streamlit interactive calls mocked."""
    docker_mock = MagicMock()
    docker_mock.from_env.return_value.ping.return_value = True
    docker_mock.from_env.return_value.containers.list.return_value = []

    with patch.dict(
        sys.modules,
        {
            "docker": docker_mock,
            "docker.models": MagicMock(),
            "docker.models.containers": MagicMock(),
        },
    ):
        import importlib

        if "pages.log_viewer" in sys.modules:
            mod = importlib.reload(sys.modules["pages.log_viewer"])
        else:
            mod = importlib.import_module("pages.log_viewer")
        return mod


_mod = _import_log_viewer()
AITHENA_SERVICES = _mod.AITHENA_SERVICES
list_running_containers = _mod.list_running_containers
tail_logs = _mod.tail_logs


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
