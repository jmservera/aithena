from __future__ import annotations

import pytest

from document_indexer.chunker import chunk_text


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
        for prev, nxt in zip(chunks, chunks[1:]):
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
