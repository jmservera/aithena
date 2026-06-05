"""Safe Solr 10 E2E preflight tests and gated runtime scenarios.

The concrete E2E scenarios in this module intentionally split into two groups:
- static preflight tests that can run before the full Solr 10 runtime switch;
- runtime scenarios that remain skipped until their docker-compose/API fixtures exist.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path
from typing import Any

import pytest
import yaml
from solr10_gates import assert_supported_solr10_scalar_bits

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
COMPOSE_PROD_PATH = REPO_ROOT / "docker" / "compose.prod.yml"
E2E_COMPOSE_PATH = REPO_ROOT / "docker" / "compose.e2e.yml"
SOLR10_COMPOSE_PATH = REPO_ROOT / "docker" / "compose.solr10.yml"
SOLR_INIT_SCRIPT_PATH = REPO_ROOT / "docker" / "solr-init.sh"
SECURITY_JSON_PATH = REPO_ROOT / "src" / "solr" / "security.json"
MANAGED_SCHEMA_PATH = REPO_ROOT / "src" / "solr" / "books" / "managed-schema.xml"

CLUSTER_SOLR_SERVICES = ("solr", "solr2", "solr3")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), f"{path} must parse as a YAML mapping"
    return data


def _load_security_json() -> dict[str, Any]:
    with SECURITY_JSON_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), "security.json must parse as a JSON object"
    return data


def _solr_init_script(compose_path: Path) -> str:
    services = _load_yaml(compose_path).get("services", {})
    solr_init = services.get("solr-init", {})
    entrypoint = solr_init.get("entrypoint", [])
    assert len(entrypoint) >= 3, f"Unexpected solr-init entrypoint in {compose_path.name}: {entrypoint}"
    return str(entrypoint[2])


def _service_env(service: dict[str, Any]) -> dict[str, str]:
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return {str(key): str(value) for key, value in environment.items()}
    if isinstance(environment, list):
        result: dict[str, str] = {}
        for item in environment:
            key, _, value = str(item).partition("=")
            result[key] = value
        return result
    raise AssertionError(f"Unsupported compose environment shape: {environment!r}")


class TestSolr10SafePreflight:
    """Non-invasive checks that can land before the Solr 10 runtime switch."""

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_compose_services_pass_through_solr_version(self) -> None:
        """All Solr containers must accept SOLR_VERSION without changing the default."""
        for compose_path in (COMPOSE_PATH, COMPOSE_PROD_PATH):
            services = _load_yaml(compose_path).get("services", {})
            for service_name in (*CLUSTER_SOLR_SERVICES, "solr-init"):
                assert service_name in services, f"{compose_path.name} is missing service {service_name!r}"
                env = _service_env(services[service_name])
                assert env.get("SOLR_VERSION") == "${SOLR_VERSION:-9}", (
                    f"{compose_path.name}:{service_name} must default SOLR_VERSION to 9 "
                    "while allowing Solr 10 E2E runs via environment override"
                )

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_solr10_compose_overlay_is_explicit_opt_in(self) -> None:
        """The runtime slice must keep defaults on Solr 9 and isolate Solr 10 behind an overlay."""
        overlay_services = _load_yaml(SOLR10_COMPOSE_PATH).get("services", {})
        assert set(overlay_services) == {*CLUSTER_SOLR_SERVICES, "solr-init"}

        for service_name, service in overlay_services.items():
            env = _service_env(service)
            build_args = service.get("build", {}).get("args", {})
            assert env.get("SOLR_VERSION") == "10", f"{service_name} must opt into Solr 10 CLI behavior"
            assert build_args.get("SOLR_BASE_IMAGE") == "solr:10", (
                f"{service_name} must build from the Solr 10 base image only via the opt-in overlay"
            )

        for compose_path in (COMPOSE_PATH, COMPOSE_PROD_PATH):
            services = _load_yaml(compose_path).get("services", {})
            for service_name in (*CLUSTER_SOLR_SERVICES, "solr-init"):
                build_args = services[service_name].get("build", {}).get("args", {})
                assert build_args.get("SOLR_BASE_IMAGE") != "solr:10", (
                    f"{compose_path.name}:{service_name} must not force Solr 10 in the default runtime"
                )

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_solr10_configset_upload_uses_native_schema(self) -> None:
        """The Solr 9 schema rewrite must be gated so Solr 10 uploads native config."""
        scripts = [
            _solr_init_script(COMPOSE_PATH),
            _solr_init_script(COMPOSE_PROD_PATH),
            SOLR_INIT_SCRIPT_PATH.read_text(encoding="utf-8"),
        ]
        rewrite_patterns = (
            's/hnswM="/hnswMaxConnections="/g',
            's/hnswEfConstruction="/hnswBeamWidth="/g',
            's/class="solr.ScalarQuantizedDenseVectorField"/class="solr.DenseVectorField"/g',
            's/ bits="7"/ vectorEncoding="BYTE"/g',
        )

        for script in scripts:
            assert "solr_major_version" in script
            assert (
                re.search(r'if \[ "\$?\$?\(solr_major_version\)" = "9" \]; then', script)
                or 'if [ "$(solr_major_version)" = "9" ]; then' in script
                or 'if [ "$$(solr_major_version)" = "9" ]; then' in script
            ), "Solr 9 compatibility rewrites must be guarded by SOLR_VERSION=9"
            for pattern in rewrite_patterns:
                assert pattern in script, f"Missing Solr 9 compatibility rewrite: {pattern}"

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_active_schema_is_solr10_native(self) -> None:
        """The checked-in books configset must use Solr 10 vector type names."""
        schema = ET.parse(MANAGED_SCHEMA_PATH).getroot()  # nosec B314
        field_types = {field_type.attrib.get("name"): field_type.attrib for field_type in schema.findall("fieldType")}

        dense = field_types.get("knn_vector_768")
        byte = field_types.get("knn_vector_768_byte")
        assert dense is not None, "managed-schema.xml must define knn_vector_768"
        assert byte is not None, "managed-schema.xml must define knn_vector_768_byte"
        assert dense["class"] == "solr.DenseVectorField"
        assert byte["class"] == "solr.ScalarQuantizedDenseVectorField"
        assert_supported_solr10_scalar_bits(byte["bits"])
        for attrs in (dense, byte):
            assert "hnswMaxConnections" not in attrs
            assert "hnswBeamWidth" not in attrs
        assert byte["hnswM"] == "12"

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_security_fixture_keeps_health_unauthenticated(self) -> None:
        """Solr 10 E2E health probes depend on blockUnknown=false and open health."""
        security = _load_security_json()
        assert security.get("authentication", {}).get("blockUnknown") is False
        permissions = security.get("authorization", {}).get("permissions", [])
        roles = {permission["name"]: permission.get("role") for permission in permissions}
        assert roles.get("health") is None
        assert roles.get("metrics-read") is None

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_e2e_compose_keeps_fixture_stack_isolated(self) -> None:
        """The E2E override must remain safe for local runs against either Solr version."""
        compose = _load_yaml(E2E_COMPOSE_PATH)
        solr_search_env = _service_env(compose["services"]["solr-search"])
        assert solr_search_env["RATE_LIMIT_REQUESTS_PER_MINUTE"] == "0"
        assert solr_search_env["UPLOAD_RATE_LIMIT_REQUESTS_PER_MINUTE"] == "0"
        document_data = compose["volumes"]["document-data"]
        device = document_data["driver_opts"]["device"]
        assert device == "${E2E_LIBRARY_PATH:-/tmp/aithena-e2e-library}"


class TestPhase1ActivePreflight:
    """Issue #1355: Phase 1 checks that can run before Solr 10 fixtures exist."""

    @pytest.mark.e2e
    @pytest.mark.phase1
    @pytest.mark.solr10
    def test_phase1_solr10_auth_cli_syntax_is_preflighted(self) -> None:
        """Auth bootstrap syntax is statically verifiable after the #1676 merge."""
        scripts = [
            _solr_init_script(COMPOSE_PATH),
            _solr_init_script(COMPOSE_PROD_PATH),
            SOLR_INIT_SCRIPT_PATH.read_text(encoding="utf-8"),
        ]

        for script in scripts:
            assert "solr auth enable --type basicAuth" in script
            assert "--block-unknown false" in script
            assert "solr_major_version" in script
            assert "SOLR_VERSION" in script


class TestSolr10Bootstrap:
    """Issue #1340: runtime E2E scenarios gated until Solr 10 fixtures exist."""

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_solr10_docker_compose_bootstrap(self) -> None:
        """Scenario 1: E2E Health Check."""
        pytest.skip("Requires docker-compose up fixture implementation")

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_auth_bootstrap_solr10(self) -> None:
        """Scenario 2: Auth Bootstrap."""
        pytest.skip("Requires auth initialization fixture")

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_e2e_document_indexing_solr10(self) -> None:
        """Scenario 3: Document Indexing Pipeline."""
        pytest.skip("Requires document upload and indexing fixtures")

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_search_quality_regression_solr10(self) -> None:
        """Scenario 4: Search Quality Maintained."""
        pytest.skip("Requires search quality validator fixture")

    @pytest.mark.e2e
    @pytest.mark.solr10
    def test_admin_api_solr10(self) -> None:
        """Scenario 5: Admin API Compatibility."""
        pytest.skip("Requires admin API fixture")


class TestPhase1SolrUpgrade:
    """Issue #1355: runtime Phase 1 scenarios gated until fixtures exist."""

    @pytest.mark.e2e
    @pytest.mark.phase1
    @pytest.mark.solr10
    def test_phase1_fresh_install_solr10(self) -> None:
        pytest.skip("GATED: requires fresh Solr 10 docker-compose fixture")

    @pytest.mark.e2e
    @pytest.mark.phase1
    @pytest.mark.solr10
    def test_phase1_backup_restore_9_to_10(self) -> None:
        pytest.skip("GATED: requires Solr 9.7 backup fixture")

    @pytest.mark.e2e
    @pytest.mark.phase1
    @pytest.mark.solr10
    def test_phase1_full_reindex(self) -> None:
        pytest.skip("GATED: requires test corpus and reindex fixtures")

    @pytest.mark.e2e
    @pytest.mark.phase1
    @pytest.mark.solr10
    def test_phase1_hnsw_parameters(self) -> None:
        pytest.skip("GATED: static schema/HNSW preflight is active; runtime kNN fixture still required")

    @pytest.mark.e2e
    @pytest.mark.phase1
    @pytest.mark.solr10
    def test_phase1_solr_cli_syntax(self) -> None:
        pytest.skip("GATED: static auth CLI syntax preflight is active; runtime solr-init fixture still required")
