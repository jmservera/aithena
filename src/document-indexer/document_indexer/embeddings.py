from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

EMBEDDINGS_TIMEOUT = 300

# Default Solr field name when the server does not include field_name
_DEFAULT_FIELD = "embedding"


@dataclass
class EmbeddingResult:
    """An embedding vector together with its target Solr field name."""

    vector: list[float]
    field_name: str = _DEFAULT_FIELD


def get_embeddings(
    texts: list[str],
    host: str,
    port: int,
) -> list[EmbeddingResult]:
    """Request embeddings for *texts* from the embeddings-server.

    Args:
        texts: Non-empty list of strings to embed.
        host: Hostname of the embeddings-server.
        port: Port of the embeddings-server.

    Returns:
        A list of :class:`EmbeddingResult` objects, one per input text,
        in the same order.

    Raises:
        requests.HTTPError: If the server returns a non-2xx response.
        ValueError: If the server returns fewer embeddings than inputs.
    """
    url = f"http://{host}:{port}/v1/embeddings/"
    response = requests.post(
        url,
        json={"input": texts},
        timeout=EMBEDDINGS_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    results = [
        EmbeddingResult(
            vector=item["embedding"],
            field_name=item.get("field_name", _DEFAULT_FIELD),
        )
        for item in data["data"]
    ]
    if len(results) != len(texts):
        raise ValueError(f"Expected {len(texts)} embeddings, got {len(results)} from {url}")
    return results
