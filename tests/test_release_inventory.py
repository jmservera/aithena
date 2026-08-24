from __future__ import annotations

from pathlib import Path

from scripts.release_inventory import _norm, dockerfiles_for_compose, missing_paths


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = [ROOT / "docker-compose.yml", ROOT / "docker" / "compose.prod.yml"]
IMPLICIT_DOCKERFILES = {
    "src/aithena-ui/Dockerfile",
    "src/document-indexer/Dockerfile",
    "src/document-lister/Dockerfile",
    "src/embeddings-server/Dockerfile",
    "src/solr/Dockerfile",
}
EXPLICIT_DOCKERFILES = {"src/solr-search/Dockerfile"}


def test_norm_keeps_relative_paths_without_dot_prefix():
    assert _norm("src/embeddings-server") == "src/embeddings-server"
    assert _norm("./src/embeddings-server") == "src/embeddings-server"


def test_compose_inventory_includes_implicit_and_explicit_dockerfiles():
    dockerfiles = set(dockerfiles_for_compose(COMPOSE_FILES))

    assert IMPLICIT_DOCKERFILES <= dockerfiles
    assert EXPLICIT_DOCKERFILES <= dockerfiles


def test_each_implicit_dockerfile_is_reported_missing(tmp_path):
    for dockerfile in IMPLICIT_DOCKERFILES:
        package_root = tmp_path / dockerfile.replace("/", "-")
        expected_dockerfiles = IMPLICIT_DOCKERFILES | EXPLICIT_DOCKERFILES
        for included in expected_dockerfiles:
            target = package_root / included
            target.parent.mkdir(parents=True, exist_ok=True)
            if included != dockerfile:
                target.write_text("FROM scratch\n", encoding="utf-8")

        assert set(missing_paths(package_root, sorted(expected_dockerfiles))) == {dockerfile}
