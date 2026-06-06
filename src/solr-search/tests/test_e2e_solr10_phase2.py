"""E2E tests for Solr 10 Phase 2: Standalone mode and vector quantization.

This module provides concrete test scenarios for:
- Issue #1356: Test Phase 2 (standalone mode, vector quantization, search tuning)

Scenarios cover standalone mode startup and workload, vector quantization memory
reduction, quantization search quality maintenance, and efSearchScaleFactor tuning.
"""

from __future__ import annotations

import importlib
import xml.etree.ElementTree as ET  # nosec B405
from pathlib import Path
from typing import Any

import pytest
import yaml
from solr10_gates import assert_supported_solr10_scalar_bits

from search_service import build_knn_params

pytestmark = [pytest.mark.e2e, pytest.mark.phase2, pytest.mark.solr10]

REPO_ROOT = Path(__file__).resolve().parents[3]
MANAGED_SCHEMA_PATH = REPO_ROOT / "src" / "solr" / "books" / "managed-schema.xml"
SINGLE_NODE_COMPOSE_PATH = REPO_ROOT / "docker" / "compose.single-node.yml"
PROD_COMPOSE_PATH = REPO_ROOT / "docker" / "compose.prod.yml"


class ComposeSafeLoader(yaml.SafeLoader):
    """YAML loader scoped to compose files that use Docker's !override tag."""


def _construct_override(loader: ComposeSafeLoader, node: yaml.Node) -> Any:
    return loader.construct_mapping(node)


ComposeSafeLoader.add_constructor("!override", _construct_override)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        loader = ComposeSafeLoader(fh)
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()
    assert isinstance(data, dict), f"{path} must parse as a YAML mapping"
    return data


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


def _reload_config(monkeypatch: pytest.MonkeyPatch, **env: str):
    import config

    for key in ("VECTOR_QUANTIZATION", "KNN_FIELD", "BOOK_EMBEDDING_FIELD"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config)


class TestPhase2ActivePreflight:
    """Issue #1356 checks that can run before #1670/#1344 land."""

    def test_phase2_single_node_overlay_status_is_explicit(self) -> None:
        """The available single-node overlay is active but still ZooKeeper-backed."""
        compose = _load_yaml(SINGLE_NODE_COMPOSE_PATH)
        services = compose["services"]

        assert services["zoo1"]["environment"]["ZOO_STANDALONE_ENABLED"] == "true"
        assert services["solr"]["environment"]["ZK_HOST"] == "zoo1:2181"
        assert services["solr-init"]["environment"]["SOLR_EXPECTED_NODES"] == "1"
        solr_search_env = _service_env(services["solr-search"])
        assert solr_search_env.get("ZOOKEEPER_HOSTS") == "zoo1:2181"
        assert "zoo1" in services["solr"]["depends_on"]

    def test_phase2_single_node_overlay_keeps_only_one_active_solr_node(self) -> None:
        """Single-node mode must route all Solr workload to the primary SolrCloud node."""
        compose = _load_yaml(SINGLE_NODE_COMPOSE_PATH)
        services = compose["services"]

        assert services["zoo2"]["profiles"] == ["distributed-only"]
        assert services["zoo3"]["profiles"] == ["distributed-only"]
        assert services["solr2"]["profiles"] == ["distributed-only"]
        assert services["solr3"]["profiles"] == ["distributed-only"]
        assert set(services["solr-init"]["depends_on"]) == {"solr"}
        assert services["solr-init"]["environment"]["SOLR_NUM_SHARDS"] == "${SOLR_NUM_SHARDS:-1}"
        assert services["solr-init"]["environment"]["SOLR_REPLICATION_FACTOR"] == "${SOLR_REPLICATION_FACTOR:-1}"

    def test_phase2_production_solrcloud_overseer_disabled_is_wired(self) -> None:
        """Production SolrCloud must keep 3 nodes while disabling the legacy Overseer queue."""
        compose = _load_yaml(PROD_COMPOSE_PATH)
        services = compose["services"]

        for service_name in ("zoo1", "zoo2", "zoo3", "solr", "solr2", "solr3"):
            assert service_name in services
            assert "distributed-only" not in services[service_name].get("profiles", [])

        for service_name in ("solr", "solr2", "solr3"):
            env = _service_env(services[service_name])
            assert "-Dsolr.cloud.overseer.enabled=${SOLR_CLOUD_OVERSEER_ENABLED:-false}" in env["SOLR_OPTS"]
            assert env["ZK_HOST"] == "zoo1:2181,zoo2:2181,zoo3:2181"

    def test_phase2_int8_schema_and_app_config_are_wired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quantization wiring can be validated without executing Solr benchmarks."""
        schema = ET.parse(MANAGED_SCHEMA_PATH).getroot()  # nosec B314
        field_types = {field_type.attrib.get("name"): field_type.attrib for field_type in schema.findall("fieldType")}
        byte_vector = field_types.get("knn_vector_768_byte")

        assert byte_vector is not None, "managed-schema.xml must define knn_vector_768_byte"
        assert byte_vector["class"] == "solr.ScalarQuantizedDenseVectorField"
        assert_supported_solr10_scalar_bits(byte_vector["bits"])
        assert byte_vector["hnswM"] == "12"

        config = _reload_config(monkeypatch, VECTOR_QUANTIZATION="int8")
        assert config.settings.vector_quantization == "int8"
        assert config.settings.knn_field == "embedding_byte_v"
        assert config.settings.book_embedding_field == "embedding_byte_v"

    def test_phase2_int8_vector_storage_estimate_meets_memory_reduction_gate(self) -> None:
        """Schema-level int8 storage should meet the Phase 2 ≥3.5× memory-reduction gate."""
        schema = ET.parse(MANAGED_SCHEMA_PATH).getroot()  # nosec B314
        field_types = {field_type.attrib.get("name"): field_type.attrib for field_type in schema.findall("fieldType")}
        float_vector = field_types["knn_vector_768"]
        byte_vector = field_types["knn_vector_768_byte"]

        assert int(float_vector["vectorDimension"]) == int(byte_vector["vectorDimension"]) == 768
        assert_supported_solr10_scalar_bits(byte_vector["bits"])

        float32_bytes_per_vector = int(float_vector["vectorDimension"]) * 4
        signed_byte_bytes_per_vector = int(byte_vector["vectorDimension"])
        assert float32_bytes_per_vector / signed_byte_bytes_per_vector >= 3.5

    @pytest.mark.parametrize("scale_factor", [2.0, 5.0])
    def test_phase2_efsearch_scale_factor_changes_solr_knn_query(self, scale_factor: float) -> None:
        """The Solr 10 efSearchScaleFactor tuning parameter must reach the kNN local params."""
        default_params = build_knn_params([0.5], top_k=10, knn_field="embedding_v")
        tuned_params = build_knn_params(
            [0.5],
            top_k=10,
            knn_field="embedding_v",
            ef_search_scale_factor=scale_factor,
        )

        assert "efSearchScaleFactor" not in default_params["q"]
        assert f"efSearchScaleFactor={scale_factor:g}" in tuned_params["q"]
        assert tuned_params["rows"] == 10


class TestPhase2StandaloneMode:
    """Issue #1356: Test Phase 2 (Standalone Mode & Quantization)."""

    @pytest.mark.e2e
    @pytest.mark.phase2
    def test_phase2_standalone_startup(self) -> None:
        """Scenario 1: Standalone Mode Startup.

        Verify Solr 10 standalone mode starts without ZooKeeper.

        Acceptance Criteria:
        - [ ] Solr starts in standalone mode
        - [ ] No ZK connection errors
        - [ ] Collection creation works in standalone mode
        - [ ] Health checks pass
        """
        pytest.skip("GATED: only single-node ZooKeeper overlay exists; true standalone Solr 10 fixture required")

    @pytest.mark.e2e
    @pytest.mark.phase2
    def test_phase2_standalone_full_workload(self) -> None:
        """Scenario 2: Standalone Full Workload.

        Verify standalone mode handles all operations.

        Acceptance Criteria:
        - [ ] All indexing operations succeed
        - [ ] All search operations return correct results
        - [ ] Admin operations work (backup, restore, collection status)
        - [ ] No ZK-related errors in logs
        - [ ] Performance acceptable (latency <= standalone baseline)
        """
        pytest.skip("GATED: requires standalone indexing and search fixtures")


class TestPhase2VectorQuantization:
    """Vector quantization (int8) testing."""

    @pytest.mark.e2e
    @pytest.mark.phase2
    def test_phase2_quantization_memory_reduction(self) -> None:
        """Scenario 3: Vector Quantization Memory Reduction.

        Verify int8 quantization reduces memory ~4× (3GB → ~750MB).

        Precondition: Must have baseline memory usage from float32.

        Acceptance Criteria:
        - [ ] Memory usage reduced by ≥ 3.5× (minimum acceptable)
        - [ ] Int8 encoding applied to all vectors
        - [ ] No out-of-memory errors during reindex
        - [ ] Solr index integrity verified (no corruption)
        """
        pytest.skip("GATED: requires #1344/#1670 quantization runtime plus memory profiler")

    @pytest.mark.e2e
    @pytest.mark.phase2
    def test_phase2_quantization_search_quality(self) -> None:
        """Scenario 4: Quantization Search Quality (int8 vs float32).

        Verify int8 quantization maintains ≥95% cosine similarity recall.

        Requires: float32 baseline search results from Phase 1.

        Acceptance Criteria:
        - [ ] Top-1 precision = 100% (best match must be correct)
        - [ ] Recall@10 ≥ 95% (at least 9 of top-10 match float32)
        - [ ] No quality loss below acceptable threshold
        """
        pytest.skip("GATED: requires #1344/#1670 quantization index and search quality validator")

    @pytest.mark.e2e
    @pytest.mark.phase2
    def test_phase2_efsearch_scale_factor(self) -> None:
        """Scenario 5: efSearchScaleFactor Parameter.

        Verify efSearchScaleFactor controls search speed/quality tradeoff.

        efSearchScaleFactor: multiplier for HNSW graph traversal depth.
        - Lower = faster but less accurate
        - Higher = slower but more accurate

        Acceptance Criteria:
        - [ ] efSearchScaleFactor=1: fastest (baseline)
        - [ ] efSearchScaleFactor=2: ~20% slower, ≤2% quality loss
        - [ ] efSearchScaleFactor=5: ~50% slower, ≤1% quality loss
        - [ ] Parameter correctly affects search behavior
        """
        pytest.skip("GATED: requires efSearchScaleFactor query fixture and latency profiler")
