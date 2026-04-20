"""Solr 9/10 compatibility layer.

Provides version-aware parameter names, field type definitions, and helpers
so the search service can work with both Solr 9.7 and Solr 10 during the
migration window.

Version detection order:
  1. ``SOLR_VERSION`` environment variable (``"9"`` or ``"10"``)
  2. Solr admin API ``/admin/info/system`` response
  3. Default: ``"9"``

See ``docs/migration/solr-compat-layer.md`` for full details.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_cached_version: int | None = None

# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------


def detect_solr_version(
    solr_url: str | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 5.0,
) -> int:
    """Detect the Solr major version.

    Checks ``SOLR_VERSION`` env var first, then queries the Solr admin API.
    Returns ``9`` or ``10``.
    """
    env_val = os.environ.get("SOLR_VERSION", "").strip()
    if env_val in ("9", "10"):
        logger.info("Solr version from SOLR_VERSION env var: %s", env_val)
        return int(env_val)

    if solr_url:
        try:
            import requests  # noqa: PLC0415

            url = f"{solr_url.rstrip('/')}/admin/info/system"
            resp = requests.get(url, auth=auth, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            spec_version = data.get("lucene", {}).get("solr-spec-version", "")
            major = int(spec_version.split(".")[0]) if spec_version else 9
            if major in (9, 10):
                logger.info("Solr version from API: %s (spec: %s)", major, spec_version)
                return major
        except Exception:
            logger.warning("Failed to detect Solr version via API, defaulting to 9", exc_info=True)

    logger.info("Solr version defaulting to 9")
    return 9


def get_solr_version(
    solr_url: str | None = None,
    auth: tuple[str, str] | None = None,
) -> int:
    """Return the cached Solr major version, detecting on first call."""
    global _cached_version  # noqa: PLW0603
    if _cached_version is None:
        _cached_version = detect_solr_version(solr_url=solr_url, auth=auth)
    return _cached_version


def is_solr_10(
    solr_url: str | None = None,
    auth: tuple[str, str] | None = None,
) -> bool:
    """Return True if the detected Solr version is 10."""
    return get_solr_version(solr_url=solr_url, auth=auth) >= 10


def reset_cached_version() -> None:
    """Clear the cached version (useful for testing)."""
    global _cached_version  # noqa: PLW0603
    _cached_version = None


# ---------------------------------------------------------------------------
# HNSW parameters
# ---------------------------------------------------------------------------

# Solr 9: hnswMaxConnections / hnswBeamWidth
# Solr 10: maxConnections / beamWidth
_HNSW_PARAM_MAP: dict[int, dict[str, str]] = {
    9: {"max_connections": "hnswMaxConnections", "beam_width": "hnswBeamWidth"},
    10: {"max_connections": "maxConnections", "beam_width": "beamWidth"},
}


def hnsw_params(
    max_connections: int = 16,
    beam_width: int = 100,
    solr_url: str | None = None,
    auth: tuple[str, str] | None = None,
) -> dict[str, int]:
    """Return HNSW configuration parameters with version-appropriate names.

    Args:
        max_connections: Maximum number of connections per node (default: 16).
        beam_width: Beam width for index construction (default: 100).

    Returns:
        Dict mapping the correct Solr parameter names to their values,
        e.g. ``{"hnswMaxConnections": 16, "hnswBeamWidth": 100}`` for Solr 9.
    """
    version = get_solr_version(solr_url=solr_url, auth=auth)
    names = _HNSW_PARAM_MAP.get(version, _HNSW_PARAM_MAP[9])
    return {
        names["max_connections"]: max_connections,
        names["beam_width"]: beam_width,
    }


# ---------------------------------------------------------------------------
# Dense vector field type definition
# ---------------------------------------------------------------------------


def dense_vector_field_type(
    name: str = "knn_vector_768",
    vector_dimension: int = 768,
    similarity_function: str = "cosine",
    knn_algorithm: str = "hnsw",
    hnsw_max_connections: int | None = None,
    hnsw_beam_width: int | None = None,
    solr_url: str | None = None,
    auth: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """Build a Solr DenseVectorField type definition dict.

    Returns a dict suitable for use with the Solr Schema API
    ``add-field-type`` command, with HNSW parameter names adjusted
    for the detected Solr version.

    When ``hnsw_max_connections`` and ``hnsw_beam_width`` are ``None``,
    HNSW tuning parameters are omitted (Solr uses its own defaults).
    """
    field_type: dict[str, Any] = {
        "name": name,
        "class": "solr.DenseVectorField",
        "vectorDimension": vector_dimension,
        "similarityFunction": similarity_function,
        "knnAlgorithm": knn_algorithm,
    }

    if hnsw_max_connections is not None or hnsw_beam_width is not None:
        hp = hnsw_params(
            max_connections=hnsw_max_connections or 16,
            beam_width=hnsw_beam_width or 100,
            solr_url=solr_url,
            auth=auth,
        )
        field_type.update(hp)

    return field_type
