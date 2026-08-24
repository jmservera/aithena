"""Regressions for the generated offline installer scripts.

Criterion 10 of issue #1854: ``scripts/package-offline-installer.sh`` must emit
a syntactically valid ``install.sh`` whose bash arrays (``COMPOSE_FILES``,
``OMITTED_IMAGES``) are written correctly, and the generated script must run
safely without Docker for its read-only modes.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGER = REPO_ROOT / "scripts" / "package-offline-installer.sh"


def _emit(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(PACKAGER), "--emit-scripts-only", str(target), *extra],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def _array_block(text: str, name: str) -> list[str]:
    """Return the literal lines of a ``name=( ... )`` bash array declaration."""
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith(f"{name}=(")]
    assert len(starts) == 1, f"expected exactly one {name} declaration, found {len(starts)}"
    start = starts[0]
    for end in range(start, len(lines)):
        if lines[end].rstrip() == ")":
            return lines[start : end + 1]
    raise AssertionError(f"unterminated {name} array declaration")


def _array_values(script: Path, name: str) -> list[str]:
    """Evaluate the emitted declaration with bash and return its elements."""
    block = "\n".join(_array_block(script.read_text(encoding="utf-8"), name))
    probe = f'{block}\nprintf "%s\\n" "${{{name}[@]+"${{{name}[@]}}"}}"\n'
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.splitlines() if line]


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("offline-scripts")
    result = _emit(target)
    assert result.returncode == 0, result.stdout + result.stderr
    return target


def test_emit_scripts_only_generates_the_documented_files(generated: Path) -> None:
    for name in ("install.sh", "scripts/start.sh", "README.md"):
        assert (generated / name).is_file(), f"missing generated file: {name}"


def test_generated_install_script_is_executable(generated: Path) -> None:
    mode = (generated / "install.sh").stat().st_mode
    assert mode & 0o111, "generated install.sh must be executable"


def test_generated_install_script_parses(generated: Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(generated / "install.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_compose_files_array_is_emitted_as_a_single_array(generated: Path) -> None:
    script = generated / "install.sh"
    block = _array_block(script.read_text(encoding="utf-8"), "COMPOSE_FILES")
    assert block[-1].rstrip() == ")"
    assert sum(line.count(")") for line in block) == 1, "stray closing parenthesis in COMPOSE_FILES"

    values = _array_values(script, "COMPOSE_FILES")
    assert values, "COMPOSE_FILES must not be empty"
    assert values[0] == "docker-compose.yml", values
    assert all(value.endswith(".yml") for value in values), values


def test_omitted_images_array_is_emitted_as_a_single_array(generated: Path) -> None:
    script = generated / "install.sh"
    block = _array_block(script.read_text(encoding="utf-8"), "OMITTED_IMAGES")
    assert sum(line.count(")") for line in block) == 1, "stray closing parenthesis in OMITTED_IMAGES"
    assert _array_values(script, "OMITTED_IMAGES") == []


def test_omitted_images_expansion_is_set_u_safe(generated: Path) -> None:
    """An empty OMITTED_IMAGES array must not abort the generated script under ``set -u``."""
    block = "\n".join(_array_block((generated / "install.sh").read_text(encoding="utf-8"), "OMITTED_IMAGES"))
    probe = f'set -euo pipefail\n{block}\nif [[ "${{#OMITTED_IMAGES[@]}}" -gt 0 ]]; then echo nonempty; fi\necho ok\n'
    result = subprocess.run(["bash", "-c", probe], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_generated_install_script_help_runs_without_docker(generated: Path, tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    shutil.copy2(generated / "install.sh", sandbox / "install.sh")
    result = subprocess.run(
        ["bash", str(sandbox / "install.sh"), "--help"],
        capture_output=True,
        text=True,
        cwd=sandbox,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Usage" in result.stdout or "usage" in result.stdout


def test_generated_start_script_parses(generated: Path) -> None:
    result = subprocess.run(
        ["bash", "-n", str(generated / "scripts" / "start.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_without_embeddings_records_the_omitted_image(tmp_path: Path) -> None:
    target = tmp_path / "no-embeddings"
    target.mkdir()
    result = _emit(target, "--without-embeddings")
    assert result.returncode == 0, result.stdout + result.stderr

    script = target / "install.sh"
    omitted = _array_values(script, "OMITTED_IMAGES")
    assert omitted, "--without-embeddings must record the omitted image"
    assert any("embeddings" in value for value in omitted), omitted

    parsed = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert parsed.returncode == 0, parsed.stderr
