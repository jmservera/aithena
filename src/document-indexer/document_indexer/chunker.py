from __future__ import annotations

import re


def _split_words(text: str) -> list[str]:
    """Split text into individual word tokens (whitespace-separated)."""
    return text.split()


def _find_sentence_ends(words: list[str]) -> list[int]:
    """Return sorted exclusive word indices where sentences end.

    A sentence boundary is placed after any word whose last character is
    ``'.'``, ``'!'``, or ``'?'``.  The total word count is always included
    as the final boundary so that trailing text without punctuation is not
    lost.
    """
    ends: list[int] = []
    for i, w in enumerate(words):
        if w and w[-1] in ".!?":
            ends.append(i + 1)
    if not ends or ends[-1] != len(words):
        ends.append(len(words))
    return ends


def _word_based_ranges(n: int, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """Return ``(start, end)`` word-index pairs using fixed-stride splitting."""
    ranges: list[tuple[int, int]] = []
    stride = max(1, chunk_size - overlap)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        ranges.append((start, end))
        if end == n:
            break
        start += stride
    return ranges


def _sentence_aware_ranges(
    words: list[str],
    chunk_size: int,
    overlap: int,
) -> list[tuple[int, int]]:
    """Return ``(start, end)`` word-index pairs with sentence-boundary snapping.

    * Chunks end at the **last** sentence boundary that fits within
      *chunk_size* words.  If no boundary exists (a single sentence is
      longer than *chunk_size*), the chunk ends at the word boundary and
      word-based overlap is applied for that transition.
    * Overlap is realised by starting the next chunk at a sentence boundary
      inside the previous chunk, chosen so that the repeated region is at
      most *overlap* words.
    """
    n = len(words)
    if n == 0:
        return []

    sent_ends = _find_sentence_ends(words)

    # A single boundary (the end-of-text sentinel) means no internal
    # sentence punctuation was found — fall back to word-based splitting.
    if len(sent_ends) <= 1:
        return _word_based_ranges(n, chunk_size, overlap)

    # Sentence start positions (each sentence starts where the previous ended).
    sent_starts = [0] + sent_ends[:-1]

    result: list[tuple[int, int]] = []
    start = 0

    while start < n:
        max_end = min(start + chunk_size, n)

        # Last sentence end that is > start and <= max_end.
        best_end: int | None = None
        for se in sent_ends:
            if se <= start:
                continue
            if se <= max_end:
                best_end = se
            else:
                break

        if best_end is None:
            # No sentence boundary within chunk_size — word-boundary fallback.
            best_end = max_end
            at_sentence = False
        else:
            at_sentence = True

        result.append((start, best_end))

        if best_end >= n:
            break

        # Advance *start* for the next chunk, applying overlap.
        if overlap > 0 and at_sentence:
            # Find the first sentence start >= (best_end - overlap) and < best_end.
            target = max(start + 1, best_end - overlap)
            next_start = best_end  # fallback when no boundary fits
            for ss in sent_starts:
                if ss < target:
                    continue
                if ss >= best_end:
                    break
                next_start = ss
                break
            start = next_start
        elif overlap > 0:
            # Inside a long sentence — use plain word-based overlap.
            start = max(start + 1, best_end - overlap)
        else:
            start = best_end

    return result


def chunk_text_with_pages(
    pages: list[tuple[int, str]],
    chunk_size: int = 90,
    overlap: int = 10,
) -> list[tuple[str, int, int]]:
    """Split page-aware text into overlapping sentence-aware chunks.

    Each input page is a ``(page_number, text)`` pair.  The function tracks
    which page every word originated from so that each output chunk carries
    ``page_start`` and ``page_end`` — the first and last page numbers covered
    by that chunk.

    Chunks prefer to end at sentence boundaries (delimited by ``'.'``,
    ``'!'``, or ``'?'``) while never exceeding *chunk_size* words.  When a
    single sentence is longer than *chunk_size*, the chunk falls back to a
    word-boundary split.

    Args:
        pages: Ordered list of ``(page_number, text)`` pairs.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of trailing words (approximately) to repeat from the
            previous chunk, snapped to the nearest sentence boundary when
            possible.

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

    ranges = _sentence_aware_ranges(all_words, chunk_size, overlap)

    result: list[tuple[str, int, int]] = []
    for s, e in ranges:
        chunk = " ".join(all_words[s:e])
        page_start = word_pages[s]
        page_end = word_pages[e - 1]
        result.append((chunk, page_start, page_end))

    return result


def chunk_text(text: str, chunk_size: int = 90, overlap: int = 10) -> list[str]:
    """Split *text* into overlapping sentence-aware chunks.

    Chunks prefer to end at sentence boundaries (delimited by ``'.'``,
    ``'!'``, or ``'?'``) while never exceeding *chunk_size* words.  When a
    single sentence is longer than *chunk_size*, the chunk falls back to a
    word-boundary split.

    The chunking is fully deterministic: given the same ``text``,
    ``chunk_size``, and ``overlap``, the output is always identical.

    Args:
        text: The full document text to split.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of trailing words (approximately) to repeat from the
            previous chunk, snapped to the nearest sentence boundary when
            possible.

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

    ranges = _sentence_aware_ranges(words, chunk_size, overlap)
    return [" ".join(words[s:e]) for s, e in ranges]
