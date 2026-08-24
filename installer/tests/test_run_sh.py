"""Regression tests for the ``installer/run.sh`` entrypoint.

The interpreter probe must try *every* candidate: an interpreter that exists but
cannot import ``aithena_common`` is skipped rather than fatal, and only when no
candidate works does the script fall back to ``uv run`` (exactly once, with
``AITHENA_INSTALLER_UV=1`` exported so ``installer/setup.py`` does not launch uv
a second time).
"""

from __future__ import annotations

import os
import shutil
import subprocess  # noqa: S404 — the tests execute run.sh on purpose
from collections.abc import Sequence
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_SH = REPO_ROOT / "installer" / "run.sh"

#: Every interpreter name run.sh probes, so tests fully control the outcome.
INTERPRETER_NAMES = ("python3", "python", "python3.13", "python3.12")

_FAILING_INTERPRETER = """#!/usr/bin/env bash
# Exists and is executable, but cannot import the installer dependencies.
if [[ "${1:-}" == "-" ]]; then
  cat >/dev/null
  echo "ModuleNotFoundError: No module named 'aithena_common'" >&2
  exit 1
fi
echo "UNEXPECTED-EXEC {name}" >&2
exit 97
"""

_WORKING_INTERPRETER = """#!/usr/bin/env bash
# Import probe succeeds, so run.sh must exec this interpreter.
if [[ "${1:-}" == "-" ]]; then
  cat >/dev/null
  exit 0
fi
echo "EXECUTED {name}"
# One argument per line so tests can detect word splitting.
for arg in "$@"; do
  printf 'ARG[%s]\n' "$arg"
done
exit 0
"""

_FAKE_UV = """#!/usr/bin/env bash
echo "UV-INVOCATION AITHENA_INSTALLER_UV=${AITHENA_INSTALLER_UV:-unset} $*" >>"$UV_LOG"
echo "EXECUTED-UV $*"
exit 0
"""


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body.replace("{name}", path.name), encoding="utf-8")
    path.chmod(0o755)


#: External commands run.sh (and the fake interpreters) need on PATH.
_SYSTEM_COMMANDS = ("bash", "env", "dirname", "basename", "cat")


@pytest.fixture()
def system_bin(tmp_path: Path) -> Path:
    """A minimal PATH entry so tests fully control interpreter/uv discovery."""
    bin_dir = tmp_path / "sysbin"
    bin_dir.mkdir()
    for name in _SYSTEM_COMMANDS:
        resolved = shutil.which(name)
        assert resolved, f"required system command not found: {name}"
        (bin_dir / name).symlink_to(resolved)
    return bin_dir


@pytest.fixture()
def fake_bin(tmp_path: Path) -> Path:
    """A PATH entry that shadows every interpreter run.sh knows about."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in INTERPRETER_NAMES:
        _write_executable(bin_dir / name, _FAILING_INTERPRETER)
    return bin_dir


def _run(
    fake_bin: Path,
    system_bin: Path,
    args: Sequence[str] = (),
    *,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}{os.pathsep}{system_bin}"
    env.pop("AITHENA_PYTHON", None)
    env.pop("AITHENA_INSTALLER_UV", None)
    env.pop("AITHENA_INSTALLER_OFFLINE", None)
    env.update(env_overrides or {})
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        [str(RUN_SH), *args],
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        timeout=120,
    )


def test_run_sh_is_executable() -> None:
    assert RUN_SH.is_file()
    assert os.access(RUN_SH, os.X_OK)


def test_failing_python3_falls_through_to_working_python(fake_bin: Path, system_bin: Path) -> None:
    """python3 exists but cannot import aithena_common; python can, so it wins."""
    _write_executable(fake_bin / "python", _WORKING_INTERPRETER)

    result = _run(fake_bin, system_bin, ["--library-path", "/srv/books"])

    assert result.returncode == 0, result.stderr
    assert "EXECUTED python" in result.stdout
    forwarded = [line[4:-1] for line in result.stdout.splitlines() if line.startswith("ARG[")]
    assert any(arg.endswith("installer/setup.py") for arg in forwarded), forwarded
    assert forwarded[-2:] == ["--library-path", "/srv/books"], forwarded
    assert "UNEXPECTED-EXEC" not in result.stderr


def test_all_interpreters_failing_falls_back_to_uv_once(fake_bin: Path, system_bin: Path, tmp_path: Path) -> None:
    uv_log = tmp_path / "uv.log"
    _write_executable(fake_bin / "uv", _FAKE_UV)

    result = _run(fake_bin, system_bin, ["--help"], env_overrides={"UV_LOG": str(uv_log)})

    assert result.returncode == 0, result.stderr
    invocations = uv_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(invocations) == 1, f"uv must be launched exactly once, got: {invocations}"
    assert "AITHENA_INSTALLER_UV=1" in invocations[0]
    assert "run --project" in invocations[0]
    assert "--offline" not in invocations[0]


def test_offline_flag_uses_uv_offline(fake_bin: Path, system_bin: Path, tmp_path: Path) -> None:
    uv_log = tmp_path / "uv.log"
    _write_executable(fake_bin / "uv", _FAKE_UV)

    result = _run(fake_bin, system_bin, ["--offline"], env_overrides={"UV_LOG": str(uv_log)})

    assert result.returncode == 0, result.stderr
    assert "--offline" in uv_log.read_text(encoding="utf-8")


def test_offline_environment_variable_uses_uv_offline(fake_bin: Path, system_bin: Path, tmp_path: Path) -> None:
    uv_log = tmp_path / "uv.log"
    _write_executable(fake_bin / "uv", _FAKE_UV)

    result = _run(
        fake_bin,
        system_bin,
        [],
        env_overrides={"UV_LOG": str(uv_log), "AITHENA_INSTALLER_OFFLINE": "1"},
    )

    assert result.returncode == 0, result.stderr
    assert "--offline" in uv_log.read_text(encoding="utf-8")


def test_offline_flag_is_not_forwarded_to_setup_py(fake_bin: Path, system_bin: Path) -> None:
    _write_executable(fake_bin / "python", _WORKING_INTERPRETER)

    result = _run(fake_bin, system_bin, ["--offline", "--reset"])

    assert result.returncode == 0, result.stderr
    assert "--offline" not in result.stdout
    assert "--reset" in result.stdout


def test_no_interpreter_and_no_uv_reports_actionable_error(fake_bin: Path, system_bin: Path) -> None:
    result = _run(fake_bin, system_bin)

    assert result.returncode == 1
    assert "could not find a usable Python interpreter" in result.stderr
    assert "Probed interpreters" in result.stderr
    assert "Install uv" in result.stderr
    assert "pip install -e" in result.stderr


def test_probe_failure_lists_every_candidate(fake_bin: Path, system_bin: Path) -> None:
    result = _run(fake_bin, system_bin)

    for name in INTERPRETER_NAMES:
        assert str(fake_bin / name) in result.stderr


def test_aithena_python_override_is_probed_first(fake_bin: Path, system_bin: Path, tmp_path: Path) -> None:
    custom = tmp_path / "custom-python"
    _write_executable(custom, _WORKING_INTERPRETER)

    result = _run(fake_bin, system_bin, [], env_overrides={"AITHENA_PYTHON": str(custom)})

    assert result.returncode == 0, result.stderr
    assert "EXECUTED custom-python" in result.stdout


def test_help_prints_entrypoint_usage(fake_bin: Path, system_bin: Path) -> None:
    _write_executable(fake_bin / "python", _WORKING_INTERPRETER)

    result = _run(fake_bin, system_bin, ["--help"])

    assert result.returncode == 0, result.stderr
    assert "Usage: ./installer/run.sh" in result.stdout
    assert "--offline" in result.stdout
    # --help is still forwarded so the installer prints its own options.
    assert "EXECUTED python" in result.stdout
    forwarded = [line[4:-1] for line in result.stdout.splitlines() if line.startswith("ARG[")]
    assert forwarded[-1] == "--help", forwarded


def test_arguments_with_spaces_are_forwarded_verbatim(fake_bin: Path, system_bin: Path) -> None:
    _write_executable(fake_bin / "python", _WORKING_INTERPRETER)

    result = _run(fake_bin, system_bin, ["--library-path", "/srv/my books", "--admin-user", "a b"])

    assert result.returncode == 0, result.stderr
    forwarded = [line[4:-1] for line in result.stdout.splitlines() if line.startswith("ARG[")]
    assert forwarded[0].endswith("installer/setup.py"), forwarded
    assert forwarded[1:] == ["--library-path", "/srv/my books", "--admin-user", "a b"], forwarded


def test_run_sh_works_from_an_extracted_package_layout(tmp_path: Path, fake_bin: Path, system_bin: Path) -> None:
    """A copied installer/ directory (as shipped in the archive) still runs."""
    package_root = tmp_path / "aithena-0.0.0"
    (package_root / "installer").mkdir(parents=True)
    for name in ("run.sh", "setup.py", "pyproject.toml"):
        target = package_root / "installer" / name
        target.write_bytes((REPO_ROOT / "installer" / name).read_bytes())
    (package_root / "installer" / "run.sh").chmod(0o755)
    _write_executable(fake_bin / "python", _WORKING_INTERPRETER)

    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}{os.pathsep}{system_bin}"
    env.pop("AITHENA_INSTALLER_UV", None)
    result = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [str(package_root / "installer" / "run.sh"), "--help"],
        capture_output=True,
        check=False,
        cwd=package_root,
        env=env,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert str(package_root / "installer" / "setup.py") in result.stdout
