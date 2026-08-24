#!/usr/bin/env python3
"""Validate the documentation shipped inside an Aithena release archive.

Two independent checks are provided:

``links``
    Every local Markdown link inside the shipped documents must resolve to a
    file that is present in the archive.  Links to repository content that is
    intentionally not shipped must be rewritten to canonical
    ``https://github.com/jmservera/aithena/blob/main/...`` URLs.  Same-document
    anchors are verified against the document's headings.

``commands``
    Every literal ``docker compose`` command in the shipped documents must start
    with the root ``docker-compose.yml`` before any ``docker/compose.*.yml``
    overlay, because the overlays are not standalone entrypoints.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

CANONICAL_BLOB_PREFIX = "https://github.com/jmservera/aithena/blob/main/"

_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^```")
_COMPOSE_RE = re.compile(r"docker\s+compose\s+(?P<flags>(?:-f\s+\S+\s*)+)")

_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://")

#: Root-level Compose entrypoints that may legitimately appear first, including
#: fully qualified example paths such as ``/path/to/docker-compose.yml``.
_ROOT_COMPOSE_RE = re.compile(r"^(?:[\w./-]*/)?docker-compose[\w.-]*\.ya?ml$")

#: Prose placeholders (``-f ...``, ``-f <file>``) are not literal commands.
_PLACEHOLDER_RE = re.compile(r"\.\.\.|[<>{}$]")
_OVERLAY_RE = re.compile(r"^\.?/?docker/compose\.[\w.-]+\.ya?ml$")


@dataclass(frozen=True)
class Finding:
    """A single documentation defect."""

    path: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.detail}"


def slugify(title: str) -> str:
    """Approximate GitHub's heading-anchor algorithm."""
    text = title.strip().lower()
    text = _LINK_RE.sub(lambda match: match.group("text"), text)
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    # GitHub replaces every single whitespace character with a hyphen; it does
    # not collapse runs, so "A & B" becomes "a--b".
    return re.sub(r"\s", "-", text)


def document_anchors(text: str) -> set[str]:
    return {slugify(match.group("title")) for match in _HEADING_RE.finditer(text)}


def iter_markdown(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.md")):
        if any(part in {"node_modules", ".git", ".venv"} for part in path.parts):
            continue
        yield path


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def check_links(root: Path) -> list[Finding]:
    """Return every unresolvable local link in the archive's Markdown files."""
    findings: list[Finding] = []
    anchor_cache: dict[Path, set[str]] = {}

    for path in iter_markdown(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        for match in _LINK_RE.finditer(text):
            target = match.group("target").strip()
            line = _line_number(text, match.start())
            if not target or target.startswith(_EXTERNAL_PREFIXES):
                continue
            if target.startswith("<") or target.startswith("data:"):
                continue

            file_part, _, anchor = target.partition("#")
            if not file_part:
                anchors = anchor_cache.setdefault(path, document_anchors(text))
                if anchor and anchor.lower() not in anchors:
                    findings.append(Finding(relative, line, f"unknown same-document anchor #{anchor}"))
                continue

            resolved = (path.parent / file_part).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                findings.append(Finding(relative, line, f"link escapes the archive: {target}"))
                continue
            if not resolved.exists():
                findings.append(
                    Finding(
                        relative,
                        line,
                        f"broken local link: {target} (ship the target or rewrite it to {CANONICAL_BLOB_PREFIX}…)",
                    )
                )
                continue
            if anchor and resolved.suffix == ".md":
                anchors = anchor_cache.setdefault(
                    resolved, document_anchors(resolved.read_text(encoding="utf-8", errors="replace"))
                )
                if anchor.lower() not in anchors:
                    findings.append(Finding(relative, line, f"unknown anchor in {file_part}: #{anchor}"))
    return findings


def compose_file_sequences(text: str) -> Iterator[tuple[int, list[str]]]:
    """Yield ``(line_number, compose_files)`` for every ``docker compose`` command."""
    for match in _COMPOSE_RE.finditer(text):
        flags = match.group("flags").split()
        files = [flags[index + 1] for index, flag in enumerate(flags) if flag == "-f" and index + 1 < len(flags)]
        yield _line_number(text, match.start()), files


def check_commands(root: Path) -> list[Finding]:
    """Return every documented Compose command that omits the root compose file."""
    findings: list[Finding] = []
    for path in iter_markdown(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        for line, files in compose_file_sequences(text):
            if not files:
                continue
            first = files[0].strip("`'\"")
            if _PLACEHOLDER_RE.search(first):
                continue
            if _ROOT_COMPOSE_RE.match(first):
                continue
            if _OVERLAY_RE.match(first):
                findings.append(
                    Finding(
                        relative,
                        line,
                        f"Compose overlay used as an entrypoint: -f {first} "
                        "(prefix the command with -f docker-compose.yml)",
                    )
                )
                continue
            findings.append(Finding(relative, line, f"unrecognised Compose entrypoint: -f {first}"))
    return findings


def rewrite_document_links(
    text: str,
    *,
    document: Path,
    root: Path,
) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(rewritten_text, [(old_target, new_target), ...])`` for one document."""
    rewrites: list[tuple[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        target = match.group("target").strip()
        if not target or target.startswith(_EXTERNAL_PREFIXES) or target.startswith(("<", "data:", "#")):
            return match.group(0)
        file_part, _, anchor = target.partition("#")
        if not file_part:
            return match.group(0)
        candidate = (document.parent / file_part).resolve()
        try:
            repo_relative = candidate.relative_to(root).as_posix()
        except ValueError:
            return match.group(0)
        if candidate.exists():
            return match.group(0)
        replacement = CANONICAL_BLOB_PREFIX + repo_relative + (f"#{anchor}" if anchor else "")
        rewrites.append((target, replacement))
        return f"[{match.group('text')}]({replacement})"

    return _LINK_RE.sub(_replace, text), rewrites


def rewrite_links(root: Path) -> list[tuple[str, str, str]]:
    """Rewrite links to unshipped repository content as canonical GitHub URLs.

    Returns ``(document, old_target, new_target)`` triples so the packaging step
    can report exactly what changed.
    """
    resolved_root = root.resolve()
    all_rewrites: list[tuple[str, str, str]] = []
    for path in iter_markdown(root):
        text = path.read_text(encoding="utf-8")
        rewritten, rewrites = rewrite_document_links(text, document=path, root=resolved_root)
        if rewrites:
            path.write_text(rewritten, encoding="utf-8")
            relative = path.relative_to(root).as_posix()
            all_rewrites.extend((relative, old, new) for old, new in rewrites)
    return all_rewrites


def _report(title: str, findings: Sequence[Finding]) -> int:
    if not findings:
        print(f"{title}: OK")
        return 0
    print(f"{title}: {len(findings)} problem(s)", file=sys.stderr)
    for finding in findings:
        print(f"  - {finding}", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "check",
        choices=["links", "commands", "all", "rewrite"],
        help="Which validation to run, or 'rewrite' to canonicalise unshipped links",
    )
    parser.add_argument("--root", required=True, help="Archive root (or repository root) to inspect")
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    if args.check == "rewrite":
        rewrites = rewrite_links(root)
        print(f"Rewrote {len(rewrites)} link(s) to canonical GitHub URLs")
        return 0

    status = 0
    if args.check in {"links", "all"}:
        status |= _report("Markdown links", check_links(root))
    if args.check in {"commands", "all"}:
        status |= _report("Compose commands", check_commands(root))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
