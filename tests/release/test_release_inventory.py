"""Regression tests for :mod:`release_inventory`.

The tests assert behaviour that a broken release archive would violate: how
Dockerfile ``COPY`` instructions are parsed, which paths are refused, that the
YAML fallback understands real Compose syntax, and that the inventory derived
from this repository actually tracks implicit Dockerfiles.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import release_inventory as ri

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Dockerfile COPY parsing
# ---------------------------------------------------------------------------


def test_copy_flags_are_not_sources() -> None:
    dockerfile = "FROM python:3.12-slim\nCOPY --chown=app:app pyproject.toml uv.lock ./\n"
    assert ri.dockerfile_copy_sources(dockerfile) == ["pyproject.toml", "uv.lock"]


def test_copy_supports_multiple_sources_and_directories() -> None:
    dockerfile = "FROM base\nCOPY main.py model_utils.py quantization.py config /app/\n"
    assert ri.dockerfile_copy_sources(dockerfile) == [
        "main.py",
        "model_utils.py",
        "quantization.py",
        "config",
    ]


def test_copy_json_array_form() -> None:
    dockerfile = 'FROM base\nCOPY ["src file.py", "other.py", "/app/"]\n'
    assert ri.dockerfile_copy_sources(dockerfile) == ["src file.py", "other.py"]


def test_copy_json_array_with_flags() -> None:
    dockerfile = 'FROM base\nCOPY --chown=1000:1000 ["a.py", "b.py", "/app/"]\n'
    assert ri.dockerfile_copy_sources(dockerfile) == ["a.py", "b.py"]


def test_copy_from_internal_stage_is_ignored() -> None:
    dockerfile = "FROM node:22 AS build\nCOPY . .\nFROM nginx\nCOPY --from=build /app/dist/ /usr/share/nginx/html/\n"
    assert ri.dockerfile_copy_sources(dockerfile) == ["."]


def test_copy_from_external_image_is_ignored() -> None:
    dockerfile = "FROM python:3.12\nCOPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/\n"
    assert ri.dockerfile_copy_sources(dockerfile) == []


def test_copy_line_continuations_are_joined() -> None:
    dockerfile = "FROM base\nCOPY first.py \\\n    second.py \\\n    /app/\n"
    assert ri.dockerfile_copy_sources(dockerfile) == ["first.py", "second.py"]


def test_add_ignores_remote_urls_but_keeps_local_sources() -> None:
    dockerfile = "FROM base\nADD https://example.com/x.tar.gz /tmp/\nADD local.tar.gz /opt/\n"
    assert ri.dockerfile_copy_sources(dockerfile) == ["local.tar.gz"]


def test_comments_and_blank_lines_do_not_produce_sources() -> None:
    dockerfile = "# comment\n\nFROM base\n# COPY should-not-count.py /app/\nCOPY real.py /app/\n"
    assert ri.dockerfile_copy_sources(dockerfile) == ["real.py"]


def test_copy_without_destination_is_rejected() -> None:
    with pytest.raises(ri.InventoryError, match="at least one source"):
        ri.dockerfile_copy_sources("FROM base\nCOPY only-one-token\n")


def test_stage_names_are_detected() -> None:
    dockerfile = "FROM node:22 AS build\nFROM nginx:alpine AS runtime\nFROM scratch\n"
    assert ri.dockerfile_stage_names(dockerfile) == {"build", "runtime"}


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def test_repo_relative_accepts_paths_inside_the_repository(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert ri.repo_relative(tmp_path, "./src", base=tmp_path, origin="test") == "src"


def test_repo_relative_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ri.InventoryError, match="escapes the repository root"):
        ri.repo_relative(tmp_path, "../../etc/passwd", base=tmp_path, origin="test")


def test_repo_relative_rejects_absolute_outside_paths(tmp_path: Path) -> None:
    with pytest.raises(ri.InventoryError, match="escapes the repository root"):
        ri.repo_relative(tmp_path, "/etc/passwd", base=tmp_path, origin="test")


def test_repo_relative_rejects_home_relative_paths(tmp_path: Path) -> None:
    with pytest.raises(ri.InventoryError, match="home-relative"):
        ri.repo_relative(tmp_path, "~/secrets", base=tmp_path, origin="test")


def test_repo_relative_rejects_unresolved_interpolation(tmp_path: Path) -> None:
    with pytest.raises(ri.InventoryError, match="unresolved interpolation"):
        ri.repo_relative(tmp_path, "${BOOKS_PATH}", base=tmp_path, origin="test")


# ---------------------------------------------------------------------------
# YAML fallback
# ---------------------------------------------------------------------------


def test_yaml_fallback_handles_anchors_quoted_hash_and_override(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text(
        "x-common: &common\n"
        "  restart: unless-stopped\n"
        "services:\n"
        "  solr:\n"
        "    <<: *common\n"
        '    command: "solr start # not a comment"\n'
        "    build:\n"
        "      context: ./src/solr\n",
        encoding="utf-8",
    )
    (tmp_path / "overlay.yml").write_text(
        "services:\n  solr:\n    depends_on: !override\n      zoo1:\n        condition: service_healthy\n",
        encoding="utf-8",
    )
    model = ri.compose_config_yaml(tmp_path, ["compose.yml", "overlay.yml"])
    solr = model["services"]["solr"]
    assert solr["restart"] == "unless-stopped"
    assert solr["command"] == "solr start # not a comment"
    assert solr["build"]["context"] == "./src/solr"
    assert solr["depends_on"] == {"zoo1": {"condition": "service_healthy"}}


def test_yaml_fallback_merges_service_volumes_like_compose(tmp_path: Path) -> None:
    """An overlay that redefines volumes must not drop the base bind mounts."""
    (tmp_path / "compose.yml").write_text(
        "services:\n"
        "  nginx:\n"
        "    volumes:\n"
        "      - ./src/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro\n"
        "      - ./src/nginx/html:/usr/share/nginx/html:ro\n",
        encoding="utf-8",
    )
    (tmp_path / "overlay.yml").write_text(
        "services:\n"
        "  nginx:\n"
        "    volumes:\n"
        "      - ./src/nginx/ssl.conf.template:/etc/nginx/templates/ssl.conf.template:ro\n",
        encoding="utf-8",
    )
    volumes = ri.compose_config_yaml(tmp_path, ["compose.yml", "overlay.yml"])["services"]["nginx"]["volumes"]
    assert volumes == [
        "./src/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro",
        "./src/nginx/html:/usr/share/nginx/html:ro",
        "./src/nginx/ssl.conf.template:/etc/nginx/templates/ssl.conf.template:ro",
    ]


def test_yaml_fallback_replaces_a_volume_with_the_same_target(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text(
        "services:\n  solr:\n    volumes:\n      - ./src/solr/a.xml:/opt/conf.xml:ro\n",
        encoding="utf-8",
    )
    (tmp_path / "overlay.yml").write_text(
        "services:\n  solr:\n    volumes:\n      - ./src/solr/b.xml:/opt/conf.xml:ro\n",
        encoding="utf-8",
    )
    volumes = ri.compose_config_yaml(tmp_path, ["compose.yml", "overlay.yml"])["services"]["solr"]["volumes"]
    assert volumes == ["./src/solr/b.xml:/opt/conf.xml:ro"]


def test_yaml_fallback_override_replaces_a_sequence(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text(
        "services:\n  solr:\n    volumes:\n      - ./src/solr/a.xml:/opt/a.xml:ro\n",
        encoding="utf-8",
    )
    (tmp_path / "overlay.yml").write_text(
        "services:\n  solr:\n    volumes: !override\n      - ./src/solr/b.xml:/opt/b.xml:ro\n",
        encoding="utf-8",
    )
    volumes = ri.compose_config_yaml(tmp_path, ["compose.yml", "overlay.yml"])["services"]["solr"]["volumes"]
    assert volumes == ["./src/solr/b.xml:/opt/b.xml:ro"]


def test_yaml_fallback_reset_removes_a_key(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text(
        "services:\n  solr:\n    env_file:\n      - ./config/solr.env\n",
        encoding="utf-8",
    )
    (tmp_path / "overlay.yml").write_text(
        "services:\n  solr:\n    env_file: !reset null\n",
        encoding="utf-8",
    )
    solr = ri.compose_config_yaml(tmp_path, ["compose.yml", "overlay.yml"])["services"]["solr"]
    assert "env_file" not in solr


def test_yaml_fallback_does_not_merge_top_level_sequences(tmp_path: Path) -> None:
    """Only service-level sequences are merged; other lists still replace."""
    (tmp_path / "compose.yml").write_text("x-list:\n  - a\n  - b\n", encoding="utf-8")
    (tmp_path / "overlay.yml").write_text("x-list:\n  - c\n", encoding="utf-8")
    assert ri.compose_config_yaml(tmp_path, ["compose.yml", "overlay.yml"])["x-list"] == ["c"]


def test_ssl_overlay_keeps_base_nginx_bind_mounts() -> None:
    """Regression for the real SSL overlay (#1853): base binds must survive."""
    model = ri.compose_config_yaml(
        REPO_ROOT,
        ["docker-compose.yml", "docker/compose.prod.yml", "docker/compose.ssl.yml"],
    )
    volumes = model["services"]["nginx"]["volumes"]
    assert "./src/nginx/default.conf.template:/etc/nginx/templates/default.conf.template:ro" in volumes
    assert "./src/nginx/ssl.conf.template:/etc/nginx/templates/ssl.conf.template:ro" in volumes


def test_yaml_fallback_rejects_non_mapping_documents(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ri.InventoryError, match="must be a mapping"):
        ri.compose_config_yaml(tmp_path, ["compose.yml"])


# ---------------------------------------------------------------------------
# Build contexts
# ---------------------------------------------------------------------------


def test_implicit_dockerfile_is_derived_from_the_context(tmp_path: Path) -> None:
    (tmp_path / "src" / "svc").mkdir(parents=True)
    (tmp_path / "src" / "svc" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    context = ri.service_build_context(tmp_path, "svc", {"context": "./src/svc"}, base=tmp_path)
    assert context.implicit is True
    assert context.dockerfile == "src/svc/Dockerfile"


def test_explicit_dockerfile_is_not_marked_implicit(tmp_path: Path) -> None:
    (tmp_path / "src" / "svc").mkdir(parents=True)
    (tmp_path / "src" / "svc" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    context = ri.service_build_context(
        tmp_path,
        "svc",
        {"context": ".", "dockerfile": "./src/svc/Dockerfile"},
        base=tmp_path,
    )
    assert context.implicit is False
    assert context.dockerfile == "src/svc/Dockerfile"


def test_missing_implicit_dockerfile_is_fatal(tmp_path: Path) -> None:
    (tmp_path / "src" / "svc").mkdir(parents=True)
    with pytest.raises(ri.InventoryError, match="does not exist"):
        ri.service_build_context(tmp_path, "svc", {"context": "./src/svc"}, base=tmp_path)


# ---------------------------------------------------------------------------
# Whole-repository inventory
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repository_inventory() -> ri.Inventory:
    return ri.collect_inventory(REPO_ROOT)


def test_every_compose_overlay_is_classified() -> None:
    assert ri.audit_overlay_coverage(REPO_ROOT) == []


def test_inventory_tracks_implicit_dockerfiles(repository_inventory: ri.Inventory) -> None:
    implicit = set(repository_inventory.implicit_dockerfiles)
    assert "src/embeddings-server/Dockerfile" in implicit
    assert "src/solr/Dockerfile" in implicit
    assert len(implicit) >= 4


def test_inventory_tracks_the_explicit_solr_search_dockerfile(repository_inventory: ri.Inventory) -> None:
    assert "src/solr-search/Dockerfile" in repository_inventory.dockerfiles


def test_every_dockerfile_is_part_of_required_paths(repository_inventory: ri.Inventory) -> None:
    required = set(repository_inventory.required_paths)
    for dockerfile in repository_inventory.dockerfiles:
        assert dockerfile in required


def test_inventory_ships_every_overlay_and_the_ssl_template(repository_inventory: ri.Inventory) -> None:
    required = set(repository_inventory.required_paths)
    for overlay in ri.SHIPPED_OVERLAY_FILES:
        assert overlay in required
    assert "docker-compose.yml" in required
    assert "src/nginx/ssl.conf.template" in required


def test_inventory_includes_installer_and_common_sources(repository_inventory: ri.Inventory) -> None:
    required = set(repository_inventory.required_paths)
    assert "installer" in required
    assert "src/aithena-common" in required


def test_inventory_includes_referenced_top_level_documents(repository_inventory: ri.Inventory) -> None:
    required = set(repository_inventory.required_paths)
    for document in ("README.md", "CHANGELOG.md", "MIGRATION.md", "docs/quickstart.md"):
        assert document in required


def test_required_paths_never_contain_the_repository_root(repository_inventory: ri.Inventory) -> None:
    assert "." not in repository_inventory.required_paths


def test_copy_sources_include_flagged_and_globbed_entries(repository_inventory: ri.Inventory) -> None:
    copy_sources = set(repository_inventory.copy_sources)
    assert "src/embeddings-server/pyproject.toml" in copy_sources
    assert "src/embeddings-server/scripts/verify_openvino_runtime.py" in copy_sources
    assert "src/solr-search/main.py" in copy_sources
    assert "src/aithena-ui" in copy_sources
    assert not any(source.startswith("--") for source in copy_sources)


# ---------------------------------------------------------------------------
# Extracted-archive validation
# ---------------------------------------------------------------------------


def test_validate_extracted_reports_missing_paths(tmp_path: Path) -> None:
    (tmp_path / "present.txt").write_text("x", encoding="utf-8")
    inventory = {"required_paths": ["present.txt", "missing/file.txt"]}
    assert ri.validate_extracted(tmp_path, inventory) == ["missing/file.txt"]


def test_validate_extracted_rejects_empty_inventory(tmp_path: Path) -> None:
    with pytest.raises(ri.InventoryError, match="no required_paths"):
        ri.validate_extracted(tmp_path, {"required_paths": []})


def test_cli_validate_fails_when_a_dockerfile_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "aithena-0.0.0"
    root.mkdir()
    (root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"required_paths": ["docker-compose.yml", "src/embeddings-server/Dockerfile"]}),
        encoding="utf-8",
    )
    exit_code = ri.main(["validate", "--root", str(root), "--inventory", str(inventory_path)])
    assert exit_code == 1


def test_cli_paths_rejects_unknown_keys(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps({"required_paths": ["a"]}), encoding="utf-8")
    assert ri.main(["paths", "--inventory", str(inventory_path), "--key", "nope"]) == 2


def test_normalised_dockerfile_key_is_still_implicit(tmp_path: Path) -> None:
    """``docker compose config`` always emits build.dockerfile; that must not
    turn a context-relative Dockerfile into an explicit one."""
    context = tmp_path / "svc"
    context.mkdir()
    (context / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    normalised_build = {"context": str(context), "dockerfile": "Dockerfile"}
    from_model = ri.service_build_context(
        tmp_path,
        "svc",
        normalised_build,
        base=tmp_path,
        implicit_services=frozenset({"svc"}),
    )
    assert from_model.implicit is True
    assert from_model.dockerfile == "svc/Dockerfile"

    declared = ri.service_build_context(tmp_path, "svc", normalised_build, base=tmp_path)
    assert declared.implicit is False


def test_services_with_explicit_dockerfile_reads_the_source_files(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text(
        "services:\n"
        "  implicit-svc:\n"
        "    build:\n"
        "      context: ./a\n"
        "  explicit-svc:\n"
        "    build:\n"
        "      context: ./b\n"
        "      dockerfile: b/Dockerfile\n"
        "  no-build-svc:\n"
        "    image: busybox\n",
        encoding="utf-8",
    )
    assert ri.services_with_explicit_dockerfile(tmp_path, ["compose.yml"]) == {"explicit-svc"}


def test_repository_solr_search_is_the_only_explicit_dockerfile() -> None:
    explicit = ri.services_with_explicit_dockerfile(REPO_ROOT, ["docker-compose.yml"])
    assert explicit == {"solr-search"}
