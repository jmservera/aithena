#!/usr/bin/env python3
"""Derive the file inventory required by an Aithena source release archive.

The inventory is derived from the authoritative Docker Compose configuration
(``docker compose config --format json``).  When the Docker CLI is unavailable
the module falls back to a deterministic YAML merge performed with PyYAML,
which understands anchors, arbitrary indentation and quoted ``#`` characters.
No line-oriented text scraping is used anywhere.

Two subcommands are provided:

``generate``
    Emit the inventory as JSON (build contexts, Dockerfiles, ``COPY`` sources,
    bind-mounted config paths, ``env_file`` / ``configs`` / ``secrets`` files
    and the curated documentation set).

``validate``
    Re-check an inventory against an extracted release archive and fail with a
    non-zero exit status listing every missing path.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess  # noqa: S404 — list-argument docker invocations, never shell=True
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # PyYAML is only needed for the deterministic no-Docker fallback parser.
    import yaml
except ImportError:  # pragma: no cover — exercised by the extracted-package validator
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Compose files that are always part of the release artifact, in overlay order.
BASE_COMPOSE_FILES: tuple[str, ...] = (
    "docker-compose.yml",
    "docker/compose.prod.yml",
)

#: Every documented overlay that ships inside the archive.  Overlays listed here
#: are copied verbatim *and* inventoried (their build contexts and Dockerfiles
#: are validated).  Overlays that are intentionally not shipped must be listed
#: in :data:`UNSHIPPED_COMPOSE_FILES` so archive documentation stays consistent.
SHIPPED_OVERLAY_FILES: tuple[str, ...] = (
    "docker/compose.ssl.yml",
    "docker/compose.gpu-nvidia.yml",
    "docker/compose.gpu-intel.yml",
    "docker/compose.single-node.yml",
    "docker/compose.solr9.yml",
    "docker/compose.solr10.yml",
    "docker/compose.e2e.yml",
    "docker/compose.ci-ports.yml",
    "docker/compose.dev-ports.yml",
)

#: Overlays deliberately excluded from the archive.  Kept explicit (and empty)
#: so that "silently omitted" can never happen unnoticed: every overlay in
#: ``docker/`` must appear in exactly one of the two tuples above.
UNSHIPPED_COMPOSE_FILES: tuple[str, ...] = ()

#: Compose overlay combinations that ``docker compose config`` must accept.
SUPPORTED_COMPOSE_COMBINATIONS: tuple[tuple[str, ...], ...] = (
    ("docker-compose.yml",),
    ("docker-compose.yml", "docker/compose.prod.yml"),
    ("docker-compose.yml", "docker/compose.prod.yml", "docker/compose.ssl.yml"),
    ("docker-compose.yml", "docker/compose.gpu-nvidia.yml"),
    ("docker-compose.yml", "docker/compose.gpu-intel.yml"),
    ("docker-compose.yml", "docker/compose.single-node.yml"),
    ("docker-compose.yml", "docker/compose.single-node.yml", "docker/compose.solr9.yml"),
    ("docker-compose.yml", "docker/compose.single-node.yml", "docker/compose.solr10.yml"),
    ("docker-compose.yml", "docker/compose.e2e.yml"),
    ("docker-compose.yml", "docker/compose.ci-ports.yml"),
    ("docker-compose.yml", "docker/compose.dev-ports.yml"),
)

#: Repository files that are copied into the archive regardless of Compose.
STATIC_PACKAGE_PATHS: tuple[str, ...] = (
    ".env.example",
    "CHANGELOG.md",
    "Dockerfile.base",
    "LICENSE",
    "MIGRATION.md",
    "README.md",
    "VERSION",
    "buildall.sh",
    "manage.sh",
    "docker/python-service-healthcheck.py",
    "docker/solr-init.sh",
    "scripts/MIGRATION.md",
    "scripts/init-volumes.sh",
    "scripts/package-offline-installer.sh",
    "scripts/release_inventory.py",
    "scripts/export-images.sh",
    "scripts/backup.sh",
    "scripts/restore.sh",
    "scripts/lib",
    "src/aithena-common",
    "src/nginx",
    "installer",
    "installer/run.sh",
    "installer/setup.py",
)

#: Documentation shipped inside the archive.  Every local link inside these
#: documents must either resolve inside the archive or be rewritten to a
#: canonical GitHub URL (enforced by ``tests/test-release-package-smoke.sh``).
SHIPPED_DOC_PATHS: tuple[str, ...] = (
    "docs/quickstart.md",
    "docs/user-manual.md",
    "docs/admin-manual.md",
    "docs/hardware-requirements.md",
    "docs/release-pipeline.md",
    "docs/config/README.md",
    "docs/deployment/production.md",
    "docs/deployment/release-packaging.md",
    "docs/deployment/failover-runbook.md",
    "docs/deployment/ghcr-authentication.md",
    "docs/deployment/offline-deployment.md",
    "docs/deployment/sizing-guide.md",
    "docs/guides/intel-gpu-wsl2.md",
    "docs/guides/wsl2-installation.md",
    "docs/guides/gpu-troubleshooting.md",
    "docs/admin/disaster-recovery-runbook.md",
    "docs/migration/solr-9-to-10.md",
    "docs/migration/solr-10-production-runbook.md",
)

#: Environment defaults used when interpolating Compose files.  They only need
#: to be syntactically valid; no service is ever started.
COMPOSE_ENV_DEFAULTS: dict[str, str] = {
    "AUTH_JWT_SECRET": "release-inventory-placeholder",
    "BOOKS_PATH": "/var/empty/aithena-books",
    "BOOK_LIBRARY_PATH": "/var/empty/aithena-books",
    "AUTH_DB_DIR": "/var/empty/aithena-auth",
    "HF_TOKEN": "release-inventory-placeholder",
    "RABBITMQ_ADMIN_USER": "admin",
    "RABBITMQ_ADMIN_PASS": "release-inventory-placeholder",  # noqa: S106 — placeholder, not a credential
    "SOLR_ADMIN_USER": "solr_admin",
    "SOLR_ADMIN_PASS": "release-inventory-placeholder",  # noqa: S106 — placeholder, not a credential
    "SOLR_READONLY_USER": "solr_read",
    "SOLR_READONLY_PASS": "release-inventory-placeholder",  # noqa: S106 — placeholder, not a credential
}

#: ``COPY``/``ADD`` flags that never denote a build-context source.
_COPY_FLAG_PREFIX = "--"

_URL_SCHEMES = ("http://", "https://", "git@", "ftp://")


class InventoryError(RuntimeError):
    """Raised when the inventory cannot be derived safely."""


@dataclass(frozen=True)
class BuildContext:
    """A Compose build context and the Dockerfile that belongs to it."""

    service: str
    context: str
    dockerfile: str
    implicit: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "context": self.context,
            "dockerfile": self.dockerfile,
            "implicit": self.implicit,
        }


@dataclass
class Inventory:
    """Everything a release archive must contain."""

    version: str
    source: str
    compose_files: list[str] = field(default_factory=list)
    unshipped_compose_files: list[str] = field(default_factory=list)
    build_contexts: list[BuildContext] = field(default_factory=list)
    dockerfiles: list[str] = field(default_factory=list)
    implicit_dockerfiles: list[str] = field(default_factory=list)
    copy_sources: list[str] = field(default_factory=list)
    bind_paths: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    secret_files: list[str] = field(default_factory=list)
    static_paths: list[str] = field(default_factory=list)
    doc_paths: list[str] = field(default_factory=list)
    runtime_paths: list[str] = field(default_factory=list)

    @property
    def required_paths(self) -> list[str]:
        """Every repo-relative path that must exist in the extracted archive."""
        paths: set[str] = set()
        paths.update(self.compose_files)
        paths.update(self.dockerfiles)
        paths.update(ctx.context for ctx in self.build_contexts)
        paths.discard(".")
        paths.update(self.copy_sources)
        paths.update(self.bind_paths)
        paths.update(self.env_files)
        paths.update(self.config_files)
        paths.update(self.secret_files)
        paths.update(self.static_paths)
        paths.update(self.doc_paths)
        return sorted(paths)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "compose_files": self.compose_files,
            "unshipped_compose_files": self.unshipped_compose_files,
            "build_contexts": [ctx.as_dict() for ctx in self.build_contexts],
            "dockerfiles": self.dockerfiles,
            "implicit_dockerfiles": self.implicit_dockerfiles,
            "copy_sources": self.copy_sources,
            "bind_paths": self.bind_paths,
            "env_files": self.env_files,
            "config_files": self.config_files,
            "secret_files": self.secret_files,
            "static_paths": self.static_paths,
            "doc_paths": self.doc_paths,
            "runtime_paths": self.runtime_paths,
            "required_paths": self.required_paths,
        }


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _is_inside(repo_root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return False
    return True


def repo_relative(repo_root: Path, raw: str, *, base: Path, origin: str) -> str:
    """Normalise ``raw`` to a repo-relative path or raise :class:`InventoryError`.

    ``raw`` may be absolute (``docker compose config`` resolves paths) or
    relative to ``base``.  Anything that escapes ``repo_root`` — including
    ``..`` traversal, ``~`` expansion and absolute host paths — is rejected.
    """
    if not raw or raw.strip() != raw:
        raise InventoryError(f"{origin}: invalid path {raw!r}")
    if raw.startswith("~"):
        raise InventoryError(f"{origin}: home-relative path is not packageable: {raw!r}")
    if "${" in raw or "$(" in raw:
        raise InventoryError(f"{origin}: unresolved interpolation in path: {raw!r}")

    candidate = Path(raw)
    absolute = candidate if candidate.is_absolute() else (base / candidate)
    resolved = Path(os.path.normpath(absolute))
    if not _is_inside(repo_root, resolved):
        raise InventoryError(f"{origin}: path escapes the repository root: {raw!r}")
    relative = resolved.relative_to(repo_root).as_posix()
    return relative or "."


def _require_exists(repo_root: Path, relative: str, origin: str) -> str:
    if not (repo_root / relative).exists():
        raise InventoryError(f"{origin}: referenced path does not exist: {relative}")
    return relative


# ---------------------------------------------------------------------------
# Compose loading
# ---------------------------------------------------------------------------


def docker_available() -> bool:
    """Return ``True`` when a working ``docker compose`` CLI is present."""
    if shutil.which("docker") is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["docker", "compose", "version"],  # noqa: S607 — resolved via PATH on purpose
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _compose_env() -> dict[str, str]:
    env = dict(os.environ)
    for key, value in COMPOSE_ENV_DEFAULTS.items():
        env.setdefault(key, value)
    return env


def compose_config_json(repo_root: Path, compose_files: Sequence[str]) -> dict[str, Any]:
    """Return the merged Compose model from ``docker compose config``."""
    argv: list[str] = ["docker", "compose"]
    for compose_file in compose_files:
        argv += ["-f", str(repo_root / compose_file)]
    argv += ["config", "--format", "json"]

    completed = subprocess.run(  # noqa: S603 — fixed argv, no shell
        argv,
        capture_output=True,
        check=False,
        cwd=repo_root,
        env=_compose_env(),
        text=True,
        timeout=600,
    )
    if completed.returncode != 0:
        raise InventoryError(f"docker compose config failed ({shlex.join(argv)}):\n{completed.stderr.strip()}")
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover — malformed CLI output
        raise InventoryError(f"docker compose config produced invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):  # pragma: no cover — defensive
        raise InventoryError("docker compose config did not return a mapping")
    return parsed


class _Override:
    """Marker for a value tagged ``!override`` in a Compose overlay."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


def _compose_loader() -> type:
    """Build (once) a SafeLoader that understands ``!override`` and ``!reset``.

    Anchors, aliases, merge keys, arbitrary indentation and quoted ``#`` are
    handled natively by PyYAML, so the fallback stays deterministic.
    """
    if yaml is None:
        raise InventoryError(
            "PyYAML is required to derive the inventory without the Docker CLI; "
            "install it with 'pip install pyyaml' or run with --require-docker."
        )
    cached = getattr(_compose_loader, "_cached", None)
    if cached is not None:
        return cached

    class ComposeYamlLoader(yaml.SafeLoader):
        """SafeLoader that understands the Compose merge tags."""

    def _construct_override(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
        if isinstance(node, yaml.ScalarNode):
            return _Override(loader.construct_scalar(node))
        if isinstance(node, yaml.SequenceNode):
            return _Override(loader.construct_sequence(node, deep=True))
        if isinstance(node, yaml.MappingNode):
            return _Override(loader.construct_mapping(node, deep=True))
        raise InventoryError(f"unsupported !override node: {node!r}")  # pragma: no cover — defensive

    def _construct_reset(loader: yaml.SafeLoader, node: yaml.Node) -> None:  # noqa: ARG001 — loader unused
        return _Override(None)

    ComposeYamlLoader.add_constructor("!override", _construct_override)
    ComposeYamlLoader.add_constructor("!reset", _construct_reset)
    _compose_loader._cached = ComposeYamlLoader  # type: ignore[attr-defined]
    return ComposeYamlLoader


#: Service keys whose sequences Compose merges (rather than replaces) across
#: overlays.  ``volumes`` is merged on the container-side target, everything
#: else on the literal entry.
_MERGED_SEQUENCE_KEYS: frozenset[str] = frozenset(
    {"volumes", "env_file", "ports", "expose", "configs", "secrets", "devices", "dns", "tmpfs"}
)


def _sequence_identity(key: str, entry: Any) -> str:
    """Return the merge key Compose uses for ``entry`` inside ``key``."""
    if key == "volumes":
        if isinstance(entry, Mapping):
            target = entry.get("target")
            if isinstance(target, str):
                return target
        elif isinstance(entry, str):
            parts = entry.split(":")
            if len(parts) >= 2:
                return parts[1]
            return parts[0]
    if isinstance(entry, Mapping):
        return json.dumps(entry, sort_keys=True)
    return str(entry)


def _merge_sequence(key: str, existing: Sequence[Any], overlay: Sequence[Any]) -> list[Any]:
    """Merge two Compose sequences the way ``docker compose config`` does."""
    merged: dict[str, Any] = {_sequence_identity(key, entry): entry for entry in existing}
    for entry in overlay:
        merged[_sequence_identity(key, entry)] = entry
    return list(merged.values())


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any], *, key_path: tuple[str, ...] = ()) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, _Override):
            if value.value is None:
                base.pop(key, None)
            else:
                base[key] = value.value
            continue
        existing = base.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            base[key] = _deep_merge(dict(existing), value, key_path=(*key_path, key))
        elif (
            isinstance(existing, list)
            and isinstance(value, list)
            and key in _MERGED_SEQUENCE_KEYS
            and key_path[:1] == ("services",)
        ):
            base[key] = _merge_sequence(key, existing, value)
        else:
            base[key] = value
    return base


def _strip_overrides(value: Any) -> Any:
    """Unwrap any ``!override`` markers left in a merged document."""
    if isinstance(value, _Override):
        return _strip_overrides(value.value)
    if isinstance(value, dict):
        return {key: _strip_overrides(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_strip_overrides(item) for item in value]
    return value


def compose_config_yaml(repo_root: Path, compose_files: Sequence[str]) -> dict[str, Any]:
    """Deterministic Compose merge used when the Docker CLI is unavailable.

    PyYAML resolves anchors/aliases, indentation and quoted ``#`` correctly, so
    the fallback stays faithful to the authoritative model for the structural
    keys the inventory needs (``build``, ``volumes``, ``env_file``, ``configs``
    and ``secrets``).
    """
    merged: dict[str, Any] = {}
    for compose_file in compose_files:
        path = repo_root / compose_file
        loader = _compose_loader()
        try:
            with path.open(encoding="utf-8") as handle:
                document = yaml.load(handle, Loader=loader)  # noqa: S506 — custom SafeLoader subclass
        except yaml.YAMLError as exc:
            raise InventoryError(f"{compose_file}: unparseable Compose YAML: {exc}") from exc
        if document is None:
            continue
        if not isinstance(document, dict):
            raise InventoryError(f"{compose_file}: top-level Compose document must be a mapping")
        _deep_merge(merged, document)
    return _strip_overrides(merged)


def load_compose_model(
    repo_root: Path,
    compose_files: Sequence[str],
    *,
    require_docker: bool = False,
) -> tuple[dict[str, Any], str]:
    """Return ``(model, source)`` where source is the provenance of the model."""
    if docker_available():
        return compose_config_json(repo_root, compose_files), "docker-compose-config"
    if require_docker:
        raise InventoryError("Docker Compose CLI is required (--require-docker) but was not usable")
    return compose_config_yaml(repo_root, compose_files), "yaml-fallback"


# ---------------------------------------------------------------------------
# Dockerfile parsing
# ---------------------------------------------------------------------------


def _logical_dockerfile_lines(text: str) -> Iterator[str]:
    """Yield Dockerfile instructions with continuations joined and comments removed."""
    buffer = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        if buffer and stripped.startswith("#"):
            # Comment lines inside a continuation are ignored by BuildKit.
            continue
        if stripped.endswith("\\"):
            buffer += stripped[:-1].rstrip() + " "
            continue
        buffer += stripped
        if buffer:
            yield buffer
        buffer = ""
    if buffer:
        yield buffer


def _split_instruction(line: str) -> tuple[str, str]:
    parts = line.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0].upper(), ""
    return parts[0].upper(), parts[1]


def _copy_arguments(argument_text: str) -> tuple[list[str], list[str]]:
    """Return ``(flags, operands)`` for a ``COPY``/``ADD`` instruction body."""
    stripped = argument_text.strip()
    flags: list[str] = []
    while stripped.startswith(_COPY_FLAG_PREFIX):
        flag, _, rest = stripped.partition(" ")
        flags.append(flag)
        stripped = rest.strip()
        if not stripped:
            break

    if stripped.startswith("["):
        try:
            operands = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InventoryError(f"malformed JSON-array COPY operands: {argument_text!r}") from exc
        if not all(isinstance(item, str) for item in operands):
            raise InventoryError(f"malformed JSON-array COPY operands: {argument_text!r}")
    else:
        operands = shlex.split(stripped)
    return flags, list(operands)


def dockerfile_stage_names(text: str) -> set[str]:
    """Return the lower-cased names of every named build stage in ``text``."""
    stages: set[str] = set()
    for line in _logical_dockerfile_lines(text):
        instruction, arguments = _split_instruction(line)
        if instruction != "FROM":
            continue
        tokens = arguments.split()
        if len(tokens) >= 3 and tokens[-2].upper() == "AS":
            stages.add(tokens[-1].lower())
    return stages


def dockerfile_copy_sources(text: str) -> list[str]:
    """Return the build-context-relative sources referenced by ``COPY``/``ADD``.

    Flags (``--chown``, ``--from``, ``--chmod``, ``--link`` …) are never treated
    as sources.  ``COPY --from=<anything>`` is skipped: the content comes from
    another stage or an external image, not from the build context.  Remote URLs
    used by ``ADD`` are skipped as well.
    """
    stage_names = dockerfile_stage_names(text)
    sources: list[str] = []
    for line in _logical_dockerfile_lines(text):
        instruction, arguments = _split_instruction(line)
        if instruction not in {"COPY", "ADD"}:
            continue
        flags, operands = _copy_arguments(arguments)
        if any(flag.startswith("--from=") for flag in flags):
            # Either an internal stage or an external image; both are produced
            # during the build and are not packaged from the build context.
            continue
        if len(operands) < 2:
            raise InventoryError(f"{instruction} needs at least one source and a destination: {line!r}")
        for operand in operands[:-1]:
            if operand.startswith(_URL_SCHEMES):
                continue
            sources.append(operand)
    # ``stage_names`` is only needed to make the --from semantics explicit; keep
    # the lookup meaningful for callers that want to reason about it.
    del stage_names
    return sources


def resolve_copy_sources(
    repo_root: Path,
    context_relative: str,
    dockerfile_relative: str,
) -> list[str]:
    """Resolve every ``COPY`` source of a Dockerfile to concrete repo paths."""
    dockerfile_path = repo_root / dockerfile_relative
    text = dockerfile_path.read_text(encoding="utf-8")
    context_dir = repo_root / context_relative
    origin = dockerfile_relative

    resolved: set[str] = set()
    for raw_source in dockerfile_copy_sources(text):
        if raw_source in {".", "./"}:
            if context_relative == ".":
                raise InventoryError(f"{origin}: refusing to package the whole repository for COPY '.'")
            resolved.add(context_relative)
            continue
        if any(char in raw_source for char in "*?["):
            matches = sorted(context_dir.glob(raw_source))
            if not matches:
                raise InventoryError(f"{origin}: COPY pattern matches nothing: {raw_source!r}")
            for match in matches:
                resolved.add(repo_relative(repo_root, str(match), base=context_dir, origin=origin))
            continue
        relative = repo_relative(repo_root, raw_source, base=context_dir, origin=origin)
        if relative == ".":
            raise InventoryError(f"{origin}: COPY source resolves to the repository root: {raw_source!r}")
        resolved.add(_require_exists(repo_root, relative, origin))
    return sorted(resolved)


# ---------------------------------------------------------------------------
# Inventory collection
# ---------------------------------------------------------------------------


def service_build_context(
    repo_root: Path,
    service_name: str,
    build: Any,
    *,
    base: Path,
) -> BuildContext:
    origin = f"service {service_name}"
    if isinstance(build, str):
        context_raw, dockerfile_raw = build, None
    elif isinstance(build, Mapping):
        context_raw = build.get("context")
        dockerfile_raw = build.get("dockerfile")
        if not isinstance(context_raw, str):
            raise InventoryError(f"{origin}: build.context must be a string")
        if dockerfile_raw is not None and not isinstance(dockerfile_raw, str):
            raise InventoryError(f"{origin}: build.dockerfile must be a string")
    else:
        raise InventoryError(f"{origin}: unsupported build definition of type {type(build).__name__}")

    context_relative = repo_relative(repo_root, context_raw, base=base, origin=origin)
    _require_exists(repo_root, context_relative, origin)

    implicit = dockerfile_raw is None
    if implicit:
        dockerfile_relative = "Dockerfile" if context_relative == "." else f"{context_relative}/Dockerfile"
    else:
        dockerfile_relative = repo_relative(
            repo_root,
            dockerfile_raw,
            base=repo_root / context_relative,
            origin=origin,
        )
        # ``docker compose config`` reports dockerfile relative to the context,
        # while raw Compose files may declare it relative to the project root.
        if not (repo_root / dockerfile_relative).is_file():
            dockerfile_relative = repo_relative(repo_root, dockerfile_raw, base=base, origin=origin)
    _require_exists(repo_root, dockerfile_relative, origin)
    return BuildContext(
        service=service_name,
        context=context_relative,
        dockerfile=dockerfile_relative,
        implicit=implicit,
    )


def _iter_volume_sources(service: Mapping[str, Any]) -> Iterator[str]:
    volumes = service.get("volumes") or []
    if not isinstance(volumes, list):
        raise InventoryError("service volumes must be a list")
    for entry in volumes:
        if isinstance(entry, str):
            source = entry.split(":", 1)[0]
            if source.startswith(("./", "../")):
                yield source
            continue
        if isinstance(entry, Mapping):
            if entry.get("type") != "bind":
                continue
            source = entry.get("source")
            if isinstance(source, str):
                yield source
            continue
        raise InventoryError(f"unsupported volume entry: {entry!r}")


def _iter_env_files(service: Mapping[str, Any]) -> Iterator[str]:
    env_file = service.get("env_file")
    if env_file is None:
        return
    entries = env_file if isinstance(env_file, list) else [env_file]
    for entry in entries:
        if isinstance(entry, str):
            yield entry
        elif isinstance(entry, Mapping) and isinstance(entry.get("path"), str):
            yield entry["path"]
        else:
            raise InventoryError(f"unsupported env_file entry: {entry!r}")


def _iter_file_backed_top_level(model: Mapping[str, Any], key: str) -> Iterator[str]:
    section = model.get(key) or {}
    if not isinstance(section, Mapping):
        raise InventoryError(f"top-level {key} must be a mapping")
    for name, definition in section.items():
        if not isinstance(definition, Mapping):
            continue
        file_path = definition.get("file")
        if file_path is None:
            continue
        if not isinstance(file_path, str):
            raise InventoryError(f"{key}.{name}.file must be a string")
        yield file_path


def collect_inventory(
    repo_root: Path,
    *,
    compose_files: Sequence[str] | None = None,
    require_docker: bool = False,
) -> Inventory:
    """Build the complete release inventory for ``repo_root``."""
    files = list(compose_files) if compose_files is not None else [*BASE_COMPOSE_FILES, *SHIPPED_OVERLAY_FILES]
    for compose_file in files:
        _require_exists(repo_root, compose_file, "compose file list")

    combinations = (
        [tuple(compose_files)] if compose_files is not None else [tuple(c) for c in SUPPORTED_COMPOSE_COMBINATIONS]
    )
    version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()

    bind_paths: set[str] = set()
    env_files: set[str] = set()
    runtime_paths: set[str] = set()
    contexts: dict[tuple[str, str], BuildContext] = {}
    config_files: set[str] = set()
    secret_files: set[str] = set()
    sources: set[str] = set()

    for combination in combinations:
        model, source = load_compose_model(repo_root, list(combination), require_docker=require_docker)
        sources.add(source)
        origin_prefix = " + ".join(combination)
        services = model.get("services") or {}
        if not isinstance(services, Mapping):
            raise InventoryError(f"{origin_prefix}: Compose model has no usable services mapping")

        for service_name, service in sorted(services.items()):
            if not isinstance(service, Mapping):
                raise InventoryError(f"{origin_prefix}: service {service_name} is not a mapping")
            origin = f"{origin_prefix}: service {service_name}"
            build = service.get("build")
            if build is not None:
                context = service_build_context(repo_root, service_name, build, base=repo_root)
                contexts[(context.context, context.dockerfile)] = context

            for raw_source in _iter_volume_sources(service):
                try:
                    relative = repo_relative(repo_root, raw_source, base=repo_root, origin=origin)
                except InventoryError:
                    if raw_source.startswith(("./", "../")):
                        raise
                    # Absolute, host-provided runtime paths (book library, auth
                    # database) are created by the installer, never packaged.
                    runtime_paths.add(raw_source)
                    continue
                bind_paths.add(_require_exists(repo_root, relative, origin))

            for raw_env_file in _iter_env_files(service):
                relative = repo_relative(repo_root, raw_env_file, base=repo_root, origin=origin)
                env_files.add(_require_exists(repo_root, relative, origin))

        for raw in _iter_file_backed_top_level(model, "configs"):
            relative = repo_relative(repo_root, raw, base=repo_root, origin=f"{origin_prefix}: configs")
            config_files.add(_require_exists(repo_root, relative, f"{origin_prefix}: configs"))
        for raw in _iter_file_backed_top_level(model, "secrets"):
            relative = repo_relative(repo_root, raw, base=repo_root, origin=f"{origin_prefix}: secrets")
            secret_files.add(_require_exists(repo_root, relative, f"{origin_prefix}: secrets"))

    if not contexts:
        raise InventoryError("no build contexts discovered — the Compose model is incomplete")

    inventory = Inventory(version=version, source="+".join(sorted(sources)))
    inventory.compose_files = sorted(files)
    inventory.unshipped_compose_files = sorted(UNSHIPPED_COMPOSE_FILES)
    inventory.build_contexts = sorted(contexts.values(), key=lambda ctx: (ctx.context, ctx.service))
    inventory.dockerfiles = sorted({ctx.dockerfile for ctx in inventory.build_contexts})
    inventory.implicit_dockerfiles = sorted({ctx.dockerfile for ctx in inventory.build_contexts if ctx.implicit})
    if not inventory.implicit_dockerfiles:
        raise InventoryError("expected at least one implicit (context-relative) Dockerfile")

    copy_sources: set[str] = set()
    for context in inventory.build_contexts:
        copy_sources.update(resolve_copy_sources(repo_root, context.context, context.dockerfile))
    inventory.copy_sources = sorted(copy_sources)

    inventory.bind_paths = sorted(bind_paths)
    inventory.env_files = sorted(env_files)
    inventory.config_files = sorted(config_files)
    inventory.secret_files = sorted(secret_files)
    inventory.runtime_paths = sorted(runtime_paths)
    inventory.static_paths = sorted(_require_exists(repo_root, path, "static paths") for path in STATIC_PACKAGE_PATHS)
    inventory.doc_paths = sorted(_require_exists(repo_root, path, "shipped docs") for path in SHIPPED_DOC_PATHS)
    return inventory


def audit_overlay_coverage(repo_root: Path) -> list[str]:
    """Return overlays present on disk but classified neither shipped nor unshipped."""
    known = {*BASE_COMPOSE_FILES, *SHIPPED_OVERLAY_FILES, *UNSHIPPED_COMPOSE_FILES}
    on_disk = {path.relative_to(repo_root).as_posix() for path in (repo_root / "docker").glob("compose.*.yml")}
    return sorted(on_disk - known)


def validate_extracted(root: Path, inventory: Mapping[str, Any]) -> list[str]:
    """Return the paths from ``inventory`` that are missing under ``root``."""
    required = inventory.get("required_paths")
    if not isinstance(required, list) or not required:
        raise InventoryError("inventory has no required_paths to validate")
    return [relative for relative in required if not (root / relative).exists()]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Emit the release inventory as JSON")
    generate.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root (default: script parent)")
    generate.add_argument("--output", help="Write JSON here instead of stdout")
    generate.add_argument(
        "--require-docker",
        action="store_true",
        help="Fail instead of falling back to the deterministic YAML parser",
    )

    paths = subparsers.add_parser("paths", help="Print one inventory key per line (for shell consumption)")
    paths.add_argument("--inventory", required=True, help="Inventory JSON produced by 'generate'")
    paths.add_argument("--key", required=True, help="Inventory key to print, for example required_paths")

    validate = subparsers.add_parser("validate", help="Validate an extracted archive against an inventory")
    validate.add_argument("--root", required=True, help="Extracted archive root (aithena-<version>/)")
    validate.add_argument("--inventory", required=True, help="Inventory JSON produced by 'generate'")

    return parser


def _run_generate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    unclassified = audit_overlay_coverage(repo_root)
    if unclassified:
        print(
            "Compose overlays are neither shipped nor explicitly unshipped: " + ", ".join(unclassified),
            file=sys.stderr,
        )
        return 2
    inventory = collect_inventory(repo_root, require_docker=args.require_docker)
    payload = json.dumps(inventory.as_dict(), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


def _run_paths(args: argparse.Namespace) -> int:
    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    if args.key not in inventory:
        print(f"unknown inventory key: {args.key}", file=sys.stderr)
        return 2
    values = inventory[args.key]
    if not isinstance(values, list):
        print(f"inventory key is not a list: {args.key}", file=sys.stderr)
        return 2
    for value in values:
        if isinstance(value, str):
            if "\n" in value:
                print(f"refusing to emit a path containing a newline: {value!r}", file=sys.stderr)
                return 2
            print(value)
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    missing = validate_extracted(root, inventory)
    if missing:
        print(f"Release archive is missing {len(missing)} required path(s):", file=sys.stderr)
        for relative in missing:
            print(f"  - {relative}", file=sys.stderr)
        return 1
    print(f"Validated {len(inventory['required_paths'])} required path(s) under {root}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    try:
        if args.command == "generate":
            return _run_generate(args)
        if args.command == "paths":
            return _run_paths(args)
        return _run_validate(args)
    except InventoryError as exc:
        print(f"release-inventory error: {exc}", file=sys.stderr)
        return 2


def iter_required_paths(inventory: Inventory) -> Iterable[str]:
    """Convenience helper used by the packaging shell script."""
    return inventory.required_paths


if __name__ == "__main__":
    raise SystemExit(main())
