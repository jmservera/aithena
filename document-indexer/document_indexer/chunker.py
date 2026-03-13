from __future__ import annotations

import re


def _split_words(text: str) -> list[str]:
    """Split text into individual word tokens (whitespace-separated)."""
    return text.split()


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Split *text* into overlapping word-based chunks.

    The chunking is fully deterministic: given the same ``text``,
    ``chunk_size``, and ``overlap``, the output is always identical.

    Args:
        text: The full document text to split.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of words to repeat at the start of each subsequent
            chunk to preserve cross-boundary context.

    Returns:
        An ordered list of non-empty chunk strings.  Returns an empty list
        when *text* contains no printable words.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )

    # Collapse all whitespace so chunks are reproducible regardless of the
    # original line-ending style.
    normalised = re.sub(r"\s+", " ", text).strip()
    words = _split_words(normalised)

    if not words:
        return []

    chunks: list[str] = []
    stride = chunk_size - overlap
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += stride

    return chunks
