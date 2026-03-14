from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

EMBEDDINGS_TIMEOUT = 300


def get_embeddings(
    texts: list[str],
    host: str,
    port: int,
) -> list[list[float]]:
    """Request embeddings for *texts* from the embeddings-server.

    Args:
        texts: Non-empty list of strings to embed.
        host: Hostname of the embeddings-server.
        port: Port of the embeddings-server.

    Returns:
        A list of embedding vectors, one per input text, in the same order.

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

    embeddings = [item["embedding"] for item in data["data"]]
    if len(embeddings) != len(texts):
        raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)} from {url}")
    return embeddings
