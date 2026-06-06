"""Tests for benchmark pre-flight checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pre_flight_check import check_docker_compose  # noqa: E402


@patch("pre_flight_check.shutil.which")
def test_docker_compose_check_uses_version_subcommand(mock_which: MagicMock, monkeypatch) -> None:
    mock_which.return_value = "/usr/bin/docker"
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="Docker Compose version v2.40.3\n"))
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = check_docker_compose()

    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == ["/usr/bin/docker", "compose", "version"]
    assert result.passed is True
    assert "Docker Compose version v2.40.3" in result.message
