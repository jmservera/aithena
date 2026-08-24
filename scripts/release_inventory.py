#!/usr/bin/env python3
"""Release package inventory and validation helper.

This module is the single source of truth for *what ships* in an Aithena
release archive and for *validating* an extracted archive. Both the packaging
script (``scripts/build-release-package.sh``) and the smoke test
(``tests/test-release-package-smoke.sh``) call into it, so the shipped file
list is derived from the actual Compose configuration and the shipped
documentation instead of a hand-maintained partial list.

Subcommands
-----------
manifest        Print the repo-relative paths that must be staged.
doc-rewrites    Print ``<doc>\t<link>`` pairs whose local link targets are not
                shipped and therefore must be rewritten at staging time.
check           Validate a staged/extracted package tree:
                  * every shipped Compose build context + Dockerfile exists
                  * every shipped Compose bind mount / env_file / config /
                    secret local path exists
                  * every local link in shipped docs resolves
                  * documented ``docker compose`` invocations start with the
                    root ``docker-compose.yml`` and order overlays correctly
                  * documented Compose file paths exist in the package
                  * documented installer invocations use ``./installer/run.sh``
                    with flags the installer actually accepts
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess  # noqa: S404 - fixed argv, never shell=True
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# --------------------------------------------------------------------------
# Shipped inventory definition
# --------------------------------------------------------------------------

#: Directory/file roots that always ship. Everything else is derived.
CORE_ROOTS: tuple[str, ...] = (
    "docker-compose.yml",
    "docker",
    "installer",
    "src",
    "scripts",
    "Dockerfile.base",
    "buildall.sh",
    "VERSION",
    "LICENSE",
    ".env.example",
    ".dockerignore",
)

#: Documentation entry points shipped with the archive. The full shipped doc
#: set is the transitive closure of local links from these seeds, restricted
#: by :func:`is_shippable_doc`.
DOC_SEEDS: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "MIGRATION.md",
    "docs/quickstart.md",
    "docs/user-manual.md",
    "docs/admin-manual.md",
    "docs/config/README.md",
    "docs/hardware-requirements.md",
    "docs/deployment-topologies.md",
    "docs/deployment/offline-deployment.md",
    "docs/deployment/ghcr-authentication.md",
    "docs/guides/wsl2-installation.md",
)

#: Documentation subtrees that are project-history or contributor-only content
#: and never ship. Links pointing at them are rewritten to canonical GitHub
#: URLs while staging, so the extracted archive has zero broken local links.
DOC_EXCLUDED_PREFIXES: tuple[str, ...] = (
    "docs/prd/",
    "docs/research/",
    "docs/test-reports/",
    "docs/testing/",
    "docs/release-notes/",
    "docs/architecture/",
    "docs/features/",
    "docs/images/",
    ".github/",
    ".squad/",
    "e2e/",
    "tests/",
)

DOC_EXCLUDED_FILES: tuple[str, ...] = (
    "docs/design-system.md",
    "docs/pre-release-testing.md",
    "docs/release-pipeline.md",
    "docs/v2.3.0-RELEASE-VALIDATION-CHECKLIST.md",
)

GITHUB_BLOB_BASE = "https://github.com/jmservera/aithena/blob/main"
GITHUB_TREE_BASE = "https://github.com/jmservera/aithena/tree/main"

#: Overlays that exist for development/CI/E2E only. They still ship (docs and
#: runbooks reference them), but are explicitly labelled so operators do not
#: mistake them for production overlays.
DEV_ONLY_OVERLAYS: tuple[str, ...] = (
    "docker/compose.dev-ports.yml",
    "docker/compose.ci-ports.yml",
    "docker/compose.e2e.yml",
)

#: Rank used to validate overlay ordering in documented compose commands.
#: A command must list its ``-f`` files in non-decreasing rank order.
COMPOSE_ORDER_RANK: dict[str, int] = {
    "docker-compose.yml": 0,
    "docker/compose.prod.yml": 1,
    "docker/compose.dev-ports.yml": 1,
    "docker/compose.ci-ports.yml": 1,
    "docker/compose.e2e.yml": 1,
    "docker/compose.gpu-nvidia.yml": 2,
    "docker/compose.gpu-intel.yml": 2,
    "docker/compose.ssl.yml": 3,
    "docker/compose.single-node.yml": 4,
    "docker/compose.solr9.yml": 5,
    "docker/compose.solr10.yml": 5,
}

#: Installer entry point that must be used in every shipped document.
INSTALLER_ENTRY_POINT = "./installer/run.sh"

#: Legacy installer invocations that no longer work from a release package.
FORBIDDEN_INSTALLER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"python3?\s+-m\s+installer\b", "use ./installer/run.sh"),
    (r"python3?\s+installer/setup\.py", "use ./installer/run.sh"),
    (r"uv\s+run\s+installer/setup\.py", "use ./installer/run.sh"),
    (r"uv\s+run\s+setup\.py", "use ./installer/run.sh"),
    (r"python3?\s+setup\.py\b", "use ./installer/run.sh"),
)


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates Compose merge tags (``!override``/``!reset``)."""


def _compose_tag(loader: yaml.Loader, tag_suffix: str, node: yaml.Node):  # noqa: ANN202, ARG001
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return None


_ComposeLoader.add_multi_constructor("!", _compose_tag)


def load_compose(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        # _ComposeLoader is a SafeLoader subclass; it only tolerates Compose merge tags.
        data = yaml.load(handle, Loader=_ComposeLoader)  # noqa: S506  # nosec B506
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------
# Compose dependency extraction
# --------------------------------------------------------------------------


@dataclass
class ComposeDep:
    """A local filesystem path a Compose file depends on."""

    compose_file: str
    service: str
    kind: str  # build-context | dockerfile | bind | env_file | config | secret
    path: str  # repo-relative

    def describe(self) -> str:
        return f"{self.compose_file} [{self.service}] {self.kind}: {self.path}"


def _norm(repo_root: Path, raw: str) -> str | None:
    """Normalise a Compose local path to a repo-relative path, or None."""
    raw = raw.strip()
    if not raw or raw.startswith(("/", "~", "$")):
        return None
    if not raw.startswith("."):
        # Named volumes / images / registry refs are not local paths.
        return None
    candidate = (repo_root / raw).resolve()
    try:
        return candidate.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def _bind_source(entry) -> str | None:  # noqa: ANN001
    if isinstance(entry, str):
        source = entry.split(":", 1)[0]
        return source
    if isinstance(entry, dict):
        if entry.get("type", "bind") != "bind":
            return None
        source = entry.get("source")
        return source if isinstance(source, str) else None
    return None


def compose_dependencies(repo_root: Path, compose_files: list[str]) -> list[ComposeDep]:
    """Extract every local path referenced by the given Compose files."""
    deps: list[ComposeDep] = []
    for rel in compose_files:
        compose_path = repo_root / rel
        if not compose_path.is_file():
            continue
        data = load_compose(compose_path)

        for section in ("configs", "secrets"):
            for name, spec in (data.get(section) or {}).items():
                if isinstance(spec, dict) and isinstance(spec.get("file"), str):
                    normalised = _norm(repo_root, spec["file"])
                    if normalised:
                        deps.append(ComposeDep(rel, name, section[:-1], normalised))

        for service, spec in (data.get("services") or {}).items():
            if not isinstance(spec, dict):
                continue

            build = spec.get("build")
            context = None
            if isinstance(build, str):
                context = build
            elif isinstance(build, dict):
                context = build.get("context")
            if isinstance(context, str):
                normalised = _norm(repo_root, context)
                if normalised is not None:
                    deps.append(ComposeDep(rel, service, "build-context", normalised or "."))
                    dockerfile = build.get("dockerfile") if isinstance(build, dict) else None
                    if isinstance(dockerfile, str):
                        if dockerfile.startswith("./") or dockerfile.startswith("../"):
                            df_rel = _norm(repo_root, dockerfile)
                        else:
                            base = repo_root if normalised in ("", ".") else repo_root / normalised
                            df_rel = _norm(repo_root, os.path.relpath(base / dockerfile, repo_root))
                    else:
                        base = repo_root if normalised in ("", ".") else repo_root / normalised
                        df_rel = _norm(repo_root, os.path.relpath(base / "Dockerfile", repo_root))
                    if df_rel:
                        deps.append(ComposeDep(rel, service, "dockerfile", df_rel))

            for entry in spec.get("volumes") or []:
                source = _bind_source(entry)
                if source:
                    normalised = _norm(repo_root, source)
                    if normalised:
                        deps.append(ComposeDep(rel, service, "bind", normalised))

            env_file = spec.get("env_file")
            entries = [env_file] if isinstance(env_file, str) else (env_file or [])
            for entry in entries:
                raw = entry.get("path") if isinstance(entry, dict) else entry
                if isinstance(raw, str):
                    normalised = _norm(repo_root, raw)
                    if normalised:
                        deps.append(ComposeDep(rel, service, "env_file", normalised))

    return deps


def shipped_compose_files(repo_root: Path) -> list[str]:
    files = ["docker-compose.yml"]
    docker_dir = repo_root / "docker"
    files.extend(sorted(p.relative_to(repo_root).as_posix() for p in docker_dir.glob("compose.*.yml")))
    return files


# --------------------------------------------------------------------------
# Documentation link handling
# --------------------------------------------------------------------------

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def is_shippable_doc(rel: str) -> bool:
    if rel in DOC_EXCLUDED_FILES:
        return False
    if any(rel.startswith(prefix) for prefix in DOC_EXCLUDED_PREFIXES):
        return False
    return rel.endswith(".md")


def doc_links(repo_root: Path, rel_doc: str) -> list[tuple[str, str]]:
    """Return ``(raw_link, repo_relative_target)`` for local links in a doc."""
    path = repo_root / rel_doc
    if not path.is_file():
        return []
    out: list[tuple[str, str]] = []
    base = Path(rel_doc).parent
    for match in LINK_RE.finditer(path.read_text(encoding="utf-8")):
        raw = match.group(1)
        if raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = raw.split("#", 1)[0]
        if not target:
            continue
        resolved = os.path.normpath((base / target).as_posix())
        if resolved.startswith(".."):
            continue
        out.append((raw, resolved.replace(os.sep, "/")))
    return out


def doc_closure(repo_root: Path) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Compute the shipped documentation set and the links needing rewrite.

    Returns ``(shipped_docs, rewrites)`` where each rewrite is
    ``(doc, raw_link, repo_relative_target)``.
    """
    shipped: list[str] = []
    seen: set[str] = set()
    queue = [seed for seed in DOC_SEEDS if (repo_root / seed).is_file()]
    rewrites: list[tuple[str, str, str]] = []

    while queue:
        rel = queue.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        shipped.append(rel)
        for raw, target in doc_links(repo_root, rel):
            if target.endswith(".md") and is_shippable_doc(target) and (repo_root / target).is_file():
                if target not in seen:
                    queue.append(target)
            elif not _ships_as_asset(target):
                rewrites.append((rel, raw, target))

    return sorted(shipped), rewrites


def _ships_as_asset(target: str) -> bool:
    """True when a non-markdown link target ships via the core roots."""
    return any(target == root or target.startswith(f"{root}/") for root in CORE_ROOTS)


def rewrite_links(stage_root: Path, repo_root: Path) -> list[tuple[str, int]]:
    """Point local links that are not present in ``stage_root`` at GitHub.

    Runs against the staging tree itself, so the extracted archive is
    guaranteed to have zero broken local links regardless of which documents
    the inventory decided to ship.

    Only targets that exist in ``repo_root`` are rewritten: a link that
    resolves nowhere is a genuine defect and is left untouched so that
    :func:`check_package` fails instead of laundering it into a 404 URL.
    """
    stage_root = stage_root.resolve()
    repo_root = repo_root.resolve()
    changed: list[tuple[str, int]] = []
    for path in sorted(stage_root.rglob("*.md")):
        rel = path.relative_to(stage_root).as_posix()
        text = path.read_text(encoding="utf-8")
        base = Path(rel).parent
        count = 0

        def replace(match: re.Match[str], base: Path = base) -> str:
            nonlocal count
            raw = match.group(1)
            if raw.startswith(("http://", "https://", "mailto:", "#")):
                return match.group(0)
            target, _, anchor = raw.partition("#")
            if not target:
                return match.group(0)
            resolved = os.path.normpath((base / target).as_posix())
            while resolved.startswith("../"):
                resolved = resolved[3:]
            if (stage_root / resolved).exists():
                return match.group(0)
            if not (repo_root / resolved).exists():
                # Genuinely broken link: leave it alone so `check` reports it.
                return match.group(0)
            base_url = GITHUB_TREE_BASE if (repo_root / resolved).is_dir() else GITHUB_BLOB_BASE
            replacement = f"{base_url}/{resolved.rstrip('/')}"
            if anchor:
                replacement = f"{replacement}#{anchor}"
            count += 1
            return match.group(0).replace(raw, replacement)

        new_text = LINK_RE.sub(replace, text)
        if count:
            path.write_text(new_text, encoding="utf-8")
            changed.append((rel, count))
    return changed


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


def git_tracked(repo_root: Path) -> list[str]:
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo_root), "ls-files", "-z"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    # Index-tracked files only: the archive must be reproducible and must never
    # pick up a developer's stray working-tree files. Staged (`git add`ed) files
    # are included, so pre-commit gates validate exactly what will be committed.
    return sorted({entry for entry in result.stdout.split("\0") if entry})


def manifest(repo_root: Path) -> list[str]:
    """Repo-relative files that must be staged into the release archive."""
    tracked = git_tracked(repo_root)
    tracked_set = set(tracked)
    selected: set[str] = set()

    for root in CORE_ROOTS:
        if root in tracked_set:
            selected.add(root)
            continue
        prefix = f"{root}/"
        selected.update(path for path in tracked if path.startswith(prefix))

    docs, _ = doc_closure(repo_root)
    selected.update(doc for doc in docs if doc in tracked_set)

    # Everything the shipped Compose files touch, even if a future overlay
    # references a path outside the core roots.
    for dep in compose_dependencies(repo_root, shipped_compose_files(repo_root)):
        if dep.path in ("", "."):
            continue
        if dep.path in tracked_set:
            selected.add(dep.path)
            continue
        prefix = f"{dep.path}/"
        selected.update(path for path in tracked if path.startswith(prefix))

    return sorted(selected)


# --------------------------------------------------------------------------
# Package validation
# --------------------------------------------------------------------------

COMPOSE_CMD_RE = re.compile(r"docker\s+compose\s+((?:-f\s+\S+\s*)+)")
COMPOSE_FILE_REF_RE = re.compile(r"(?<![\w./-])((?:docker/)?(?:docker-)?compose[\w.-]*\.yml)")
RUN_SH_FLAG_RE = re.compile(r"\./installer/run\.sh((?:\s+--?[\w-]+(?:[= ][^\s`|]+)?)*)")


@dataclass
class CheckReport:
    passed: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def ok(self, message: str) -> None:
        self.passed.append(message)

    def fail(self, message: str) -> None:
        self.failures.append(message)


def installer_flags(package_root: Path) -> set[str]:
    setup = package_root / "installer" / "setup.py"
    if not setup.is_file():
        return set()
    text = setup.read_text(encoding="utf-8")
    flags = set(re.findall(r"add_argument\(\s*\"(--[\w-]+)\"", text))
    flags.update(re.findall(r"add_argument\(\s*\"--[\w-]+\",\s*\"(--[\w-]+)\"", text))
    flags.update({"--help", "-h", "--no-ssl"})
    return flags


def check_package(package_root: Path) -> CheckReport:  # noqa: C901, PLR0912, PLR0915
    report = CheckReport()
    package_root = package_root.resolve()

    # --- Compose files present -------------------------------------------
    compose_files = shipped_compose_files(package_root)
    if "docker-compose.yml" not in compose_files or not (package_root / "docker-compose.yml").is_file():
        report.fail("root docker-compose.yml is missing from the package")
    else:
        report.ok("root docker-compose.yml is present")

    expected_overlays = {
        "docker/compose.prod.yml",
        "docker/compose.ssl.yml",
        "docker/compose.gpu-nvidia.yml",
        "docker/compose.gpu-intel.yml",
        "docker/compose.single-node.yml",
        "docker/compose.solr9.yml",
        "docker/compose.solr10.yml",
        "docker/compose.dev-ports.yml",
        "docker/compose.ci-ports.yml",
        "docker/compose.e2e.yml",
    }
    missing_overlays = sorted(overlay for overlay in expected_overlays if not (package_root / overlay).is_file())
    if missing_overlays:
        report.fail(f"missing documented Compose overlays: {', '.join(missing_overlays)}")
    else:
        report.ok(f"all {len(expected_overlays)} documented Compose overlays are packaged")

    # --- Compose local dependencies --------------------------------------
    deps = compose_dependencies(package_root, compose_files)
    missing_deps = []
    for dep in deps:
        target = package_root / dep.path if dep.path not in ("", ".") else package_root
        if dep.kind == "dockerfile":
            exists = target.is_file()
        elif dep.kind == "build-context":
            exists = target.is_dir()
        else:
            exists = target.exists()
        if not exists:
            missing_deps.append(dep.describe())
    if missing_deps:
        for item in missing_deps:
            report.fail(f"missing Compose dependency: {item}")
    else:
        report.ok(f"all {len(deps)} Compose build contexts, Dockerfiles, and bind mounts exist in the package")

    # --- Dockerfile COPY sources -----------------------------------------
    missing_copy = []
    for dep in deps:
        if dep.kind != "dockerfile":
            continue
        dockerfile = package_root / dep.path
        if not dockerfile.is_file():
            continue
        context_deps = [
            other
            for other in deps
            if other.kind == "build-context" and other.compose_file == dep.compose_file and other.service == dep.service
        ]
        if not context_deps or context_deps[0].path in ("", "."):
            context = package_root
        else:
            context = package_root / context_deps[0].path
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.upper().startswith("COPY "):
                continue
            parts = stripped.split()[1:]
            if any(part.startswith("--from=") for part in parts):
                continue
            parts = [part for part in parts if not part.startswith("--")]
            if len(parts) < 2:
                continue
            for source in parts[:-1]:
                if "$" in source:
                    continue
                if not list(context.glob(source.rstrip("/"))):
                    missing_copy.append(f"{dep.path}: COPY source '{source}' not in package")
    if missing_copy:
        for item in missing_copy:
            report.fail(item)
    else:
        report.ok("every shipped Dockerfile COPY source exists inside its build context")

    # --- Documentation ----------------------------------------------------
    docs = sorted(
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*.md")
        if path.is_file() and not path.relative_to(package_root).as_posix().startswith(("src/", "installer/"))
    )
    if not docs:
        report.fail("no documentation shipped in the package")

    broken_links: list[str] = []
    for doc in docs:
        for raw, target in doc_links(package_root, doc):
            if not (package_root / target).exists():
                broken_links.append(f"{doc} -> {raw}")
    if broken_links:
        for item in broken_links:
            report.fail(f"broken local documentation link: {item}")
    else:
        report.ok(f"all local links in {len(docs)} shipped documents resolve inside the package")

    # --- Documented compose commands -------------------------------------
    ordering_problems: list[str] = []
    missing_compose_refs: list[str] = []
    for doc in docs:
        text = (package_root / doc).read_text(encoding="utf-8")
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in COMPOSE_CMD_RE.finditer(line):
                files = re.findall(r"-f\s+(\S+)", match.group(1))
                files = [item.strip("`'\"\\") for item in files]
                if any(item.startswith(("/", "$", "{", "<")) or item in ("...", "…") for item in files):
                    continue
                if files[0] != "docker-compose.yml":
                    ordering_problems.append(
                        f"{doc}:{lineno}: compose command must start with -f docker-compose.yml -> {line.strip()}"
                    )
                    continue
                ranks = [COMPOSE_ORDER_RANK.get(item) for item in files]
                if any(rank is None for rank in ranks):
                    unknown = [item for item, rank in zip(files, ranks, strict=True) if rank is None]
                    ordering_problems.append(f"{doc}:{lineno}: unknown Compose file(s) {unknown} -> {line.strip()}")
                    continue
                if any(left > right for left, right in zip(ranks, ranks[1:], strict=False)):
                    ordering_problems.append(f"{doc}:{lineno}: overlay order is wrong -> {line.strip()}")
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            for match in COMPOSE_FILE_REF_RE.finditer(line):
                if not in_fence and f"-f {match.group(1)}" not in line:
                    # Prose mentions (including "this file does not exist"
                    # notes) are not copy-pasteable commands.
                    continue
                ref = match.group(1)
                if ref.startswith("docker/") or ref == "docker-compose.yml":
                    if not (package_root / ref).is_file():
                        missing_compose_refs.append(f"{doc}:{lineno}: references missing Compose file '{ref}'")
                elif (
                    ref.startswith(("compose.", "docker-compose."))
                    and not (package_root / "docker" / ref).is_file()
                    and not (package_root / ref).is_file()
                ):
                    # A bare overlay name must still exist under docker/.
                    missing_compose_refs.append(f"{doc}:{lineno}: references missing Compose file '{ref}'")

    for item in ordering_problems + missing_compose_refs:
        report.fail(item)
    if not ordering_problems:
        report.ok(
            "every documented `docker compose -f ...` command starts with docker-compose.yml "
            "and orders overlays correctly"
        )
    if not missing_compose_refs:
        report.ok("every Compose file named in shipped docs exists in the package")

    # --- Documented installer invocations ---------------------------------
    installer_problems: list[str] = []
    known_flags = installer_flags(package_root)
    for doc in docs:
        text = (package_root / doc).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, hint in FORBIDDEN_INSTALLER_PATTERNS:
                if re.search(pattern, line):
                    installer_problems.append(f"{doc}:{lineno}: legacy installer invocation ({hint}) -> {line.strip()}")
            for match in RUN_SH_FLAG_RE.finditer(line):
                for flag in re.findall(r"(?<![\w-])(--[\w-]+)", match.group(1)):
                    if known_flags and flag not in known_flags:
                        installer_problems.append(f"{doc}:{lineno}: ./installer/run.sh does not accept '{flag}'")
    for item in installer_problems:
        report.fail(item)
    if not installer_problems:
        report.ok("every documented installer invocation uses ./installer/run.sh with supported flags")

    # --- Legacy invocations in shipped non-documentation files ------------
    config_problems: list[str] = []
    config_files = [
        ".env.example",
        "docker-compose.yml",
        *sorted(p.relative_to(package_root).as_posix() for p in (package_root / "docker").glob("compose.*.yml")),
    ]
    for rel in config_files:
        target = package_root / rel
        if not target.is_file():
            continue
        for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern, hint in FORBIDDEN_INSTALLER_PATTERNS:
                if re.search(pattern, line):
                    config_problems.append(f"{rel}:{lineno}: legacy installer invocation ({hint})")
    for item in config_problems:
        report.fail(item)
    if not config_problems:
        report.ok("shipped Compose files and .env.example reference ./installer/run.sh only")

    # --- Entry point ------------------------------------------------------
    run_sh = package_root / "installer" / "run.sh"
    if not run_sh.is_file():
        report.fail("installer/run.sh is missing from the package")
    elif not os.access(run_sh, os.X_OK):
        report.fail("installer/run.sh is not executable in the package")
    else:
        report.ok("installer/run.sh ships and is executable")

    for required in ("src/aithena-common", "src/nginx/ssl.conf.template", "src/solr/Dockerfile", "docker-compose.yml"):
        if (package_root / required).exists():
            report.ok(f"required path present: {required}")
        else:
            report.fail(f"required path missing: {required}")

    return report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("manifest", help="Print the files that must be staged")
    sub.add_parser("doc-rewrites", help="Print doc links that must be rewritten while staging")
    sub.add_parser("compose-deps", help="Print local paths referenced by shipped Compose files")
    sub.add_parser("dev-overlays", help="Print development/test-only overlays")
    rewrite = sub.add_parser("rewrite-links", help="Rewrite unshipped local doc links in a staging tree")
    rewrite.add_argument("stage_root", help="Directory containing the staged package")
    check = sub.add_parser("check", help="Validate a staged or extracted package")
    check.add_argument("package_root", help="Directory containing the extracted package")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    if args.command == "manifest":
        for item in manifest(repo_root):
            print(item)
        return 0

    if args.command == "doc-rewrites":
        _, rewrites = doc_closure(repo_root)
        for doc, raw, target in rewrites:
            base_url = GITHUB_TREE_BASE if (repo_root / target).is_dir() else GITHUB_BLOB_BASE
            print(f"{doc}\t{raw}\t{target}\t{base_url}/{target.rstrip('/')}")
        return 0

    if args.command == "compose-deps":
        for dep in compose_dependencies(repo_root, shipped_compose_files(repo_root)):
            print(dep.describe())
        return 0

    if args.command == "dev-overlays":
        for overlay in DEV_ONLY_OVERLAYS:
            print(overlay)
        return 0

    if args.command == "rewrite-links":
        changed = rewrite_links(Path(args.stage_root), repo_root)
        for doc, count in changed:
            print(f"rewrote {count} unshipped link(s) in {doc}")
        return 0

    report = check_package(Path(args.package_root))
    for message in report.passed:
        print(f"  PASS {message}")
    for message in report.failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"check: {len(report.passed)} passed, {len(report.failures)} failed")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
