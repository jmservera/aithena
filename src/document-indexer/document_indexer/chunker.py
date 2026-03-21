from __future__ import annotations

import re


def _split_words(text: str) -> list[str]:
    """Split text into individual word tokens (whitespace-separated)."""
    return text.split()


def chunk_text_with_pages(
    pages: list[tuple[int, str]],
    chunk_size: int = 90,
    overlap: int = 10,
) -> list[tuple[str, int, int]]:
    """Split page-aware text into overlapping word-based chunks.

    Each input page is a ``(page_number, text)`` pair.  The function tracks
    which page every word originated from so that each output chunk carries
    ``page_start`` and ``page_end`` — the first and last page numbers covered
    by that chunk.

    Args:
        pages: Ordered list of ``(page_number, text)`` pairs.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of words to repeat at the start of each subsequent
            chunk to preserve cross-boundary context.

    Returns:
        An ordered list of ``(chunk_text, page_start, page_end)`` tuples.
        Returns an empty list when *pages* contains no printable words.

    Raises:
        ValueError: If *chunk_size* ≤ 0, *overlap* < 0, or *overlap* ≥ *chunk_size*.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    all_words: list[str] = []
    word_pages: list[int] = []

    for page_num, text in pages:
        normalised = re.sub(r"\s+", " ", text).strip()
        words = normalised.split()
        all_words.extend(words)
        word_pages.extend([page_num] * len(words))

    if not all_words:
        return []

    result: list[tuple[str, int, int]] = []
    stride = chunk_size - overlap
    start = 0

    while start < len(all_words):
        end = min(start + chunk_size, len(all_words))
        chunk = " ".join(all_words[start:end])
        page_start = word_pages[start]
        page_end = word_pages[end - 1]
        result.append((chunk, page_start, page_end))
        if end == len(all_words):
            break
        start += stride

    return result


def chunk_text(text: str, chunk_size: int = 90, overlap: int = 10) -> list[str]:
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
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

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
