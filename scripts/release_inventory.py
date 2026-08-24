#!/usr/bin/env python3
"""Release package inventory helpers."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _norm(path: str) -> str | None:
    """Return a safe repository-relative path, or None for absolute/escaping paths."""
    if os.path.isabs(path):
        return None
    normalized = os.path.normpath(path).replace(os.sep, "/")
    if normalized == ".":
        return "."
    if normalized.startswith("../") or normalized == "..":
        return None
    return normalized.removeprefix("./")


def _strip_value(value: str) -> str:
    value = value.strip()
    if value and value[0] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    return value


def _iter_builds(compose_file: Path) -> list[dict[str, str]]:
    builds: list[dict[str, str]] = []
    lines = compose_file.read_text(encoding="utf-8").splitlines()
    in_services = False
    in_service = False
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.split("#", 1)[0].rstrip()
        stripped = line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if not stripped:
            index += 1
            continue
        if indent == 0:
            in_services = stripped == "services:"
            in_service = False
            index += 1
            continue
        if not in_services:
            index += 1
            continue
        if indent == 2 and stripped.endswith(":"):
            in_service = True
            index += 1
            continue
        if not in_service or indent != 4 or not stripped.startswith("build:"):
            index += 1
            continue

        value = _strip_value(stripped.removeprefix("build:").strip())
        if value:
            builds.append({"context": value})
            index += 1
            continue

        build: dict[str, str] = {}
        index += 1
        while index < len(lines):
            child_raw = lines[index]
            child_line = child_raw.split("#", 1)[0].rstrip()
            child_stripped = child_line.strip()
            child_indent = len(child_raw) - len(child_raw.lstrip(" "))
            if child_stripped and child_indent <= 4:
                break
            if child_stripped and child_indent == 6 and ":" in child_stripped:
                key, child_value = child_stripped.split(":", 1)
                if key in {"context", "dockerfile"}:
                    build[key] = _strip_value(child_value)
            index += 1
        if build:
            builds.append(build)

    return builds


def dockerfiles_for_compose(compose_files: list[Path]) -> list[str]:
    dockerfiles: set[str] = set()
    for compose_file in compose_files:
        for build in _iter_builds(compose_file):
            context = _norm(build.get("context", "."))
            if context is None:
                continue
            dockerfile = _norm(build.get("dockerfile", "Dockerfile"))
            if dockerfile is None:
                continue
            dockerfile_path = _norm(str(Path(context) / dockerfile))
            if dockerfile_path is not None:
                dockerfiles.add(dockerfile_path)
    return sorted(dockerfiles)


def missing_paths(root: Path, relative_paths: list[str]) -> list[str]:
    return [path for path in relative_paths if not (root / path).is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect release package build-context inventory.")
    parser.add_argument("compose_files", nargs="+", type=Path)
    parser.add_argument("--check-root", type=Path, help="Validate discovered Dockerfiles below this root")
    args = parser.parse_args(argv)

    dockerfiles = dockerfiles_for_compose(args.compose_files)
    if args.check_root is None:
        for dockerfile in dockerfiles:
            print(dockerfile)
        return 0

    missing = missing_paths(args.check_root, dockerfiles)
    if missing:
        print("Missing Dockerfile(s) required by Compose build contexts:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
