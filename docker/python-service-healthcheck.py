#!/usr/bin/env python3
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def check_http(url: str, timeout: float) -> int:
    if urlparse(url).scheme not in {"http", "https"}:
        return fail(f"http healthcheck only supports http/https URLs: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "aithena-healthcheck/1.0"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310  # noqa: S310
            status = getattr(response, "status", response.getcode())
    except urllib.error.URLError as exc:
        return fail(f"http healthcheck failed for {url}: {exc}")

    if 200 <= status < 400:
        return 0
    return fail(f"http healthcheck returned status {status} for {url}")


def check_process(pattern: str) -> int:
    matcher = re.compile(pattern)
    current_pid = os.getpid()

    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue

        pid = int(proc_dir.name)
        if pid == current_pid:
            continue

        try:
            cmdline = (proc_dir / "cmdline").read_text(encoding="utf-8").replace("\x00", " ").strip()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue

        if cmdline and matcher.search(cmdline):
            return 0

    return fail(f"process healthcheck did not find pattern: {pattern}")


def main() -> int:
    mode = os.environ.get("HEALTHCHECK_MODE", "").strip().lower()
    timeout = float(os.environ.get("HEALTHCHECK_TIMEOUT", "5"))

    if mode == "http":
        url = os.environ.get("HEALTHCHECK_URL", "").strip()
        if not url:
            return fail("HEALTHCHECK_URL is required when HEALTHCHECK_MODE=http")
        return check_http(url, timeout)

    if mode == "process":
        pattern = os.environ.get("HEALTHCHECK_PROCESS", "").strip()
        if not pattern:
            return fail("HEALTHCHECK_PROCESS is required when HEALTHCHECK_MODE=process")
        return check_process(pattern)

    return fail("HEALTHCHECK_MODE must be set to http or process")


if __name__ == "__main__":
    raise SystemExit(main())
