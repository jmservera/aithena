from __future__ import annotations

import pytest
from document_indexer.chunker import chunk_text, chunk_text_with_pages


class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\t  ") == []

    def test_short_text_fits_in_single_chunk(self):
        text = "one two three"
        chunks = chunk_text(text, chunk_size=10, overlap=0)
        assert chunks == ["one two three"]

    def test_exact_chunk_size_produces_one_chunk(self):
        words = list("abcdefghij")  # 10 single-char words
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=10, overlap=0)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_text_split_into_multiple_chunks_no_overlap(self):
        words = [str(i) for i in range(10)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        # words 0-3, 4-7, 8-9
        assert len(chunks) == 3
        assert chunks[0] == "0 1 2 3"
        assert chunks[1] == "4 5 6 7"
        assert chunks[2] == "8 9"

    def test_overlap_repeats_words_at_chunk_boundaries(self):
        words = [str(i) for i in range(10)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=4, overlap=2)
        # stride = 4 - 2 = 2
        # chunk 0: words[0:4]  = "0 1 2 3"
        # chunk 1: words[2:6]  = "2 3 4 5"
        # chunk 2: words[4:8]  = "4 5 6 7"
        # chunk 3: words[6:10] = "6 7 8 9"
        assert chunks[0] == "0 1 2 3"
        assert chunks[1] == "2 3 4 5"
        assert chunks[-1] == "6 7 8 9"

    def test_overlap_words_appear_in_consecutive_chunks(self):
        text = "a b c d e f g h i j"
        chunks = chunk_text(text, chunk_size=4, overlap=1)
        # stride = 3
        # chunk 0: a b c d
        # chunk 1: d e f g
        # chunk 2: g h i j
        for prev, nxt in zip(chunks, chunks[1:], strict=False):
            prev_words = prev.split()
            nxt_words = nxt.split()
            assert prev_words[-1] == nxt_words[0]

    def test_output_is_deterministic(self):
        text = " ".join(["word"] * 100)
        assert chunk_text(text, 20, 5) == chunk_text(text, 20, 5)

    def test_normalises_internal_whitespace(self):
        text = "hello   world\nfoo\tbar"
        chunks = chunk_text(text, chunk_size=10, overlap=0)
        assert chunks == ["hello world foo bar"]

    def test_invalid_chunk_size_raises(self):
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text("some text", chunk_size=0)

    def test_negative_overlap_raises(self):
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("some text", chunk_size=10, overlap=-1)

    def test_overlap_equal_to_chunk_size_raises(self):
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("some text", chunk_size=5, overlap=5)

    def test_last_chunk_contains_remaining_words(self):
        words = [str(i) for i in range(7)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        all_words = " ".join(chunks).split()
        # All original words appear (no duplicates without overlap)
        assert all_words == words

    def test_single_word(self):
        chunks = chunk_text("hello", chunk_size=10, overlap=0)
        assert chunks == ["hello"]


class TestChunkTextWithPages:
    def test_empty_pages_returns_empty_list(self):
        assert chunk_text_with_pages([]) == []

    def test_pages_with_no_text_return_empty_list(self):
        assert chunk_text_with_pages([(1, "   "), (2, "\n\t")]) == []

    def test_single_page_short_text_fits_in_one_chunk(self):
        result = chunk_text_with_pages([(1, "one two three")], chunk_size=10, overlap=0)
        assert len(result) == 1
        chunk, page_start, page_end = result[0]
        assert chunk == "one two three"
        assert page_start == 1
        assert page_end == 1

    def test_single_page_chunk_tracks_correct_page_number(self):
        result = chunk_text_with_pages([(5, "word1 word2 word3")], chunk_size=10, overlap=0)
        _, page_start, page_end = result[0]
        assert page_start == 5
        assert page_end == 5

    def test_multi_page_single_chunk_spans_all_pages(self):
        pages = [(1, "alpha beta"), (2, "gamma delta")]
        result = chunk_text_with_pages(pages, chunk_size=10, overlap=0)
        assert len(result) == 1
        chunk, page_start, page_end = result[0]
        assert page_start == 1
        assert page_end == 2

    def test_chunk_spanning_two_pages_has_correct_page_range(self):
        # 4 words on page 1, 4 words on page 2; chunk_size=6 → first chunk spans both pages
        pages = [(1, "a b c d"), (2, "e f g h")]
        result = chunk_text_with_pages(pages, chunk_size=6, overlap=0)
        assert len(result) == 2
        _, page_start_0, page_end_0 = result[0]
        assert page_start_0 == 1
        assert page_end_0 == 2  # chunk includes words from page 2

    def test_chunk_confined_to_single_page_has_matching_start_and_end(self):
        # 4 words on page 1, 4 words on page 2; chunk_size=4 → each chunk stays on one page
        pages = [(1, "a b c d"), (2, "e f g h")]
        result = chunk_text_with_pages(pages, chunk_size=4, overlap=0)
        assert len(result) == 2
        _, s0, e0 = result[0]
        _, s1, e1 = result[1]
        assert s0 == 1 and e0 == 1
        assert s1 == 2 and e1 == 2

    def test_returns_tuples_of_text_page_start_page_end(self):
        pages = [(3, "hello world")]
        result = chunk_text_with_pages(pages, chunk_size=10, overlap=0)
        assert len(result) == 1
        chunk, page_start, page_end = result[0]
        assert isinstance(chunk, str)
        assert isinstance(page_start, int)
        assert isinstance(page_end, int)

    def test_chunk_text_matches_expected_words(self):
        pages = [(1, "the quick brown fox")]
        result = chunk_text_with_pages(pages, chunk_size=2, overlap=0)
        assert result[0][0] == "the quick"
        assert result[1][0] == "brown fox"

    def test_overlap_propagated_correctly(self):
        pages = [(1, "a b c d e f")]
        result = chunk_text_with_pages(pages, chunk_size=4, overlap=2)
        # stride=2: chunk0=words[0:4], chunk1=words[2:6]
        assert result[0][0] == "a b c d"
        assert result[1][0] == "c d e f"

    def test_invalid_chunk_size_raises(self):
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text_with_pages([(1, "text")], chunk_size=0)

    def test_negative_overlap_raises(self):
        with pytest.raises(ValueError, match="overlap"):
            chunk_text_with_pages([(1, "text")], chunk_size=10, overlap=-1)

    def test_overlap_equal_to_chunk_size_raises(self):
        with pytest.raises(ValueError, match="overlap"):
            chunk_text_with_pages([(1, "text")], chunk_size=5, overlap=5)

    def test_page_numbering_non_sequential(self):
        # Non-consecutive page numbers (e.g. sparse PDF) should still work
        pages = [(10, "alpha beta"), (20, "gamma delta")]
        result = chunk_text_with_pages(pages, chunk_size=2, overlap=0)
        _, s0, e0 = result[0]
        _, s1, e1 = result[1]
        assert s0 == 10 and e0 == 10
        assert s1 == 20 and e1 == 20
