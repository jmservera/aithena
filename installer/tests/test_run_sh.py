from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_SH = ROOT / "installer" / "run.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["AITHENA_INSTALLER_SETUP_PY"] = str(tmp_path / "setup.py")
    env["AITHENA_INSTALLER_PYTHON_CANDIDATES"] = "python3"
    return env


def test_run_sh_uses_uv_when_python_candidate_lacks_dependencies(tmp_path: Path):
    _write_executable(
        tmp_path / "python3",
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-c" ]]; then exit 1; fi\n'
        "exit 42\n",
    )
    _write_executable(
        tmp_path / "uv",
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" > "$AITHENA_INSTALLER_UV_ARGS_FILE"\n'
        "exit 0\n",
    )
    args_file = tmp_path / "uv-args.txt"
    env = _base_env(tmp_path)
    env["AITHENA_INSTALLER_UV_ARGS_FILE"] = str(args_file)

    completed = subprocess.run([str(RUN_SH), "--help"], env=env, check=False)

    assert completed.returncode == 0
    assert args_file.read_text(encoding="utf-8").startswith("run --project ")


def test_run_sh_continues_to_next_python_candidate(tmp_path: Path):
    _write_executable(
        tmp_path / "python3",
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-c" ]]; then exit 1; fi\n'
        "exit 42\n",
    )
    _write_executable(
        tmp_path / "python",
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-c" ]]; then exit 0; fi\n'
        'printf "%s\\n" "$*" > "$AITHENA_INSTALLER_PYTHON_ARGS_FILE"\n'
        "exit 0\n",
    )
    args_file = tmp_path / "python-args.txt"
    env = _base_env(tmp_path)
    env["AITHENA_INSTALLER_PYTHON_CANDIDATES"] = "python3 python"
    env["AITHENA_INSTALLER_PYTHON_ARGS_FILE"] = str(args_file)

    completed = subprocess.run([str(RUN_SH), "--help"], env=env, check=False)

    assert completed.returncode == 0
    assert args_file.read_text(encoding="utf-8").endswith("setup.py --help\n")


def test_run_sh_fails_actionably_after_all_candidates_exhausted(tmp_path: Path):
    (tmp_path / "dirname").symlink_to("/usr/bin/dirname")
    (tmp_path / "cat").symlink_to("/usr/bin/cat")
    _write_executable(
        tmp_path / "python3",
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-c" ]]; then exit 1; fi\n'
        "exit 42\n",
    )
    env = _base_env(tmp_path)
    env["PATH"] = str(tmp_path)

    completed = subprocess.run(["/usr/bin/bash", str(RUN_SH)], env=env, capture_output=True, check=False, text=True)

    assert completed.returncode == 1
    assert "Install uv and rerun" in completed.stderr
