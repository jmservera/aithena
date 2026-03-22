from __future__ import annotations

import pytest

from document_indexer.chunker import chunk_text, chunk_text_with_pages

# ---------------------------------------------------------------------------
# Original word-based tests (backward compatibility)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Sentence-boundary awareness tests
# ---------------------------------------------------------------------------


class TestSentenceBoundaryChunking:
    """Tests for the sentence-aware splitting introduced in #812."""

    def test_chunks_end_at_sentence_boundaries(self):
        text = "The cat sat. The dog ran. The bird flew."
        # 3 sentences of 3 words each = 9 words.
        # chunk_size=7 can fit at most 2 sentences (6 words).
        chunks = chunk_text(text, chunk_size=7, overlap=0)
        assert chunks[0] == "The cat sat. The dog ran."
        assert chunks[1] == "The bird flew."

    def test_sentence_boundary_chunks_never_exceed_chunk_size(self):
        text = (
            "First sentence here. Second sentence here. "
            "Third sentence here. Fourth sentence here."
        )
        for cs in (5, 8, 10, 15):
            chunks = chunk_text(text, chunk_size=cs, overlap=0)
            for chunk in chunks:
                assert len(chunk.split()) <= cs, (
                    f"chunk_size={cs}: chunk has {len(chunk.split())} words"
                )

    def test_chunks_may_be_shorter_to_respect_sentences(self):
        # "Hello world." = 2 words, "How are you today?" = 4 words.
        # chunk_size=5 can fit sentence 1 (2 words), then sentence 2 would
        # push to 6 words → flush at 2 words (shorter than 5).
        text = "Hello world. How are you today?"
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        assert chunks[0] == "Hello world."
        assert chunks[1] == "How are you today?"

    def test_sentence_overlap_includes_previous_sentence(self):
        # 4 sentences of 3 words each.
        text = "The cat sat. The dog ran. The bird flew. The fish swam."
        # chunk_size=7, overlap=4 → overlap budget can include one
        # 3-word sentence from the previous chunk.
        chunks = chunk_text(text, chunk_size=7, overlap=4)
        # chunk 0: "The cat sat. The dog ran." (6 words, ends at sentence)
        # chunk 1 overlaps previous → starts at "The dog ran."
        assert chunks[0] == "The cat sat. The dog ran."
        assert "The dog ran." in chunks[1]

    def test_no_overlap_when_sentence_exceeds_overlap_budget(self):
        # Two 5-word sentences, overlap=3.  The trailing sentence of
        # chunk 0 is 5 words — larger than the overlap budget → no overlap.
        text = "One two three four five. Six seven eight nine ten."
        chunks = chunk_text(text, chunk_size=6, overlap=3)
        assert chunks[0] == "One two three four five."
        assert chunks[1] == "Six seven eight nine ten."

    def test_long_sentence_falls_back_to_word_split(self):
        # A single sentence of 10 words with chunk_size=4.
        text = "This is a very long sentence that keeps going on."
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        for chunk in chunks:
            assert len(chunk.split()) <= 4
        # All words are present.
        all_words = []
        for c in chunks:
            all_words.extend(c.split())
        assert " ".join(all_words) == text

    def test_long_sentence_word_based_overlap(self):
        # Within a long sentence (no sentence boundaries), word-based
        # overlap should still apply.
        text = "One two three four five six seven eight nine ten."
        chunks = chunk_text(text, chunk_size=5, overlap=2)
        # First chunk: words[0:5] = "One two three four five"
        # Next start: max(1, 5-2) = 3 → words[3:8]
        assert chunks[0] == "One two three four five"
        assert chunks[1] == "four five six seven eight"

    def test_single_sentence_uses_word_based_fallback(self):
        text = "The quick brown fox jumps over the lazy dog."
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        # Single sentence → word-based splitting.
        assert chunks[0] == "The quick brown fox"
        assert chunks[1] == "jumps over the lazy"
        assert chunks[2] == "dog."

    def test_no_sentence_boundaries_uses_word_based(self):
        # Bullet-point style text without sentence-ending punctuation.
        text = "item one item two item three item four"
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        assert chunks == ["item one item two", "item three item four"]

    def test_mixed_long_and_short_sentences(self):
        text = (
            "Short one. "
            "This is a much longer sentence that exceeds the chunk size easily. "
            "Tiny."
        )
        chunks = chunk_text(text, chunk_size=6, overlap=0)
        # "Short one." (2 words) fits in a chunk.
        # Next sentence is 12 words → word-based fallback.
        # "Tiny." (1 word) fits in a chunk.
        for chunk in chunks:
            assert len(chunk.split()) <= 6
        # First and last sentences appear intact somewhere.
        assert chunks[0] == "Short one."
        assert chunks[-1].endswith("Tiny.")

    def test_exclamation_mark_is_sentence_boundary(self):
        text = "Watch out! The bridge is collapsing."
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        assert chunks[0] == "Watch out!"
        assert chunks[1] == "The bridge is collapsing."

    def test_question_mark_is_sentence_boundary(self):
        text = "Is it raining? I forgot my umbrella."
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        assert chunks[0] == "Is it raining?"
        assert chunks[1] == "I forgot my umbrella."

    def test_multiple_punctuation_types(self):
        text = "Hello! How are you? I am fine."
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        # "Hello!" (1) + "How are you?" (3) = 4 words → fits.
        # "I am fine." (3) → next chunk.
        assert chunks[0] == "Hello! How are you?"
        assert chunks[1] == "I am fine."

    def test_cjk_text_without_ascii_punctuation(self):
        # CJK text without ASCII sentence enders falls back to word-based.
        # Chinese characters without spaces are treated as single "words".
        text = "你好世界 这是测试 中文分词 示例文本"
        chunks = chunk_text(text, chunk_size=2, overlap=0)
        assert chunks == ["你好世界 这是测试", "中文分词 示例文本"]

    def test_arabic_text_without_ascii_punctuation(self):
        text = "مرحبا بالعالم هذا اختبار"
        chunks = chunk_text(text, chunk_size=2, overlap=0)
        assert chunks == ["مرحبا بالعالم", "هذا اختبار"]

    def test_cjk_text_with_ascii_punctuation(self):
        text = "你好世界. 这是测试. 中文."
        # Each "sentence" is 1 word; chunk_size=2 fits 2 sentences per chunk.
        chunks = chunk_text(text, chunk_size=2, overlap=0)
        assert chunks[0] == "你好世界. 这是测试."
        assert chunks[1] == "中文."
        # With chunk_size=1, each sentence becomes its own chunk.
        chunks = chunk_text(text, chunk_size=1, overlap=0)
        assert chunks == ["你好世界.", "这是测试.", "中文."]

    def test_deterministic_with_sentence_boundaries(self):
        text = "Alpha bravo. Charlie delta. Echo foxtrot."
        a = chunk_text(text, chunk_size=4, overlap=1)
        b = chunk_text(text, chunk_size=4, overlap=1)
        assert a == b

    def test_all_words_preserved_no_overlap(self):
        text = "First sentence. Second one. Third here. Last one."
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        reconstructed = " ".join(chunks)
        assert reconstructed == text

    def test_overlap_zero_produces_no_repeated_words(self):
        text = "The cat sat. The dog ran. The bird flew."
        chunks = chunk_text(text, chunk_size=7, overlap=0)
        all_words = []
        for c in chunks:
            all_words.extend(c.split())
        original_words = text.split()
        assert all_words == original_words


class TestSentenceBoundaryWithPages:
    """Sentence-aware tests for ``chunk_text_with_pages``."""

    def test_sentence_boundary_respected_across_pages(self):
        pages = [(1, "Hello world."), (2, "How are you? Fine thanks.")]
        result = chunk_text_with_pages(pages, chunk_size=5, overlap=0)
        # "Hello world." (2) + "How are you?" (3) = 5 → fits in one chunk.
        assert result[0][0] == "Hello world. How are you?"
        assert result[0][1] == 1  # page_start
        assert result[0][2] == 2  # page_end

    def test_page_tracking_with_sentence_split(self):
        pages = [
            (1, "The cat sat."),
            (2, "The dog ran."),
            (3, "The bird flew."),
        ]
        result = chunk_text_with_pages(pages, chunk_size=4, overlap=0)
        # Each sentence is 3 words; chunk_size=4 fits one sentence per chunk.
        assert len(result) == 3
        assert result[0] == ("The cat sat.", 1, 1)
        assert result[1] == ("The dog ran.", 2, 2)
        assert result[2] == ("The bird flew.", 3, 3)

    def test_sentence_overlap_with_pages(self):
        pages = [
            (1, "Alpha bravo."),
            (2, "Charlie delta."),
            (3, "Echo foxtrot."),
        ]
        # chunk_size=5, overlap=3 → overlap can include trailing 2-word sentence.
        result = chunk_text_with_pages(pages, chunk_size=5, overlap=3)
        assert result[0][0] == "Alpha bravo. Charlie delta."
        # Second chunk should overlap with "Charlie delta."
        assert "Charlie delta." in result[1][0]

    def test_long_sentence_word_split_preserves_pages(self):
        pages = [(1, "a b c d e f g h")]
        result = chunk_text_with_pages(pages, chunk_size=3, overlap=0)
        for chunk_text_val, ps, pe in result:
            assert len(chunk_text_val.split()) <= 3
            assert ps == 1
            assert pe == 1

    def test_no_chunk_exceeds_chunk_size_with_pages(self):
        pages = [
            (1, "The quick brown fox jumps."),
            (2, "Over the lazy dog."),
            (3, "A second paragraph starts here."),
        ]
        for cs in (4, 6, 8, 10):
            result = chunk_text_with_pages(pages, chunk_size=cs, overlap=0)
            for text, _, _ in result:
                assert len(text.split()) <= cs


# ---------------------------------------------------------------------------
# Wave 1 — Additional chunker edge cases (#813)
# ---------------------------------------------------------------------------


class TestChunkerEdgeCases:
    """Extra edge-case coverage for the sentence-boundary chunker."""

    def test_default_chunk_size_is_90_words(self):
        """90-word default: text of exactly 90 words produces one chunk."""
        text = " ".join(f"word{i}" for i in range(90))
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert len(chunks[0].split()) == 90

    def test_default_chunk_size_splits_at_91_words(self):
        """91 words with 90-word default should produce two chunks."""
        text = " ".join(f"w{i}" for i in range(91))
        chunks = chunk_text(text)
        assert len(chunks) == 2

    def test_tabs_and_newlines_normalised(self):
        """Tabs, newlines, and multiple spaces are collapsed to single spaces."""
        text = "Hello\tworld.\nHow\n\nare  you?"
        chunks = chunk_text(text, chunk_size=10, overlap=0)
        assert chunks == ["Hello world. How are you?"]

    def test_abbreviation_is_false_positive_boundary(self):
        """Abbreviations ending in period (e.g. 'Dr.') trigger boundary detection.

        This is a known limitation of the simple '.!?' heuristic — document it.
        """
        text = "Dr. Smith went to the store. He bought milk."
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        # "Dr." counts as a sentence boundary, so the first chunk should be "Dr."
        # rather than grouping with "Smith went to the store."
        # Verify chunks are valid (all words present, no exceeds chunk_size).
        all_words = []
        for c in chunks:
            words = c.split()
            assert len(words) <= 5
            all_words.extend(words)
        assert " ".join(all_words) == text

    def test_trailing_whitespace_only_text(self):
        """Text with content followed by trailing whitespace."""
        text = "Hello world.   \n\n  "
        chunks = chunk_text(text, chunk_size=10, overlap=0)
        assert chunks == ["Hello world."]

    def test_single_period_sentence(self):
        """Edge case: a 'sentence' that is just a period."""
        text = ". . ."
        chunks = chunk_text(text, chunk_size=2, overlap=0)
        assert len(chunks) >= 1
        all_words = []
        for c in chunks:
            all_words.extend(c.split())
        assert all_words == [".", ".", "."]


class TestChunkerWithPagesEdgeCases:
    """Extra page-tracking edge cases."""

    def test_single_word_per_page(self):
        """Each page has exactly one word — chunks span multiple pages."""
        pages = [(i, f"word{i}") for i in range(1, 6)]
        result = chunk_text_with_pages(pages, chunk_size=2, overlap=0)
        assert result[0] == ("word1 word2", 1, 2)
        assert result[1] == ("word3 word4", 3, 4)
        assert result[2] == ("word5", 5, 5)

    def test_empty_page_in_middle(self):
        """An empty page between content pages should not break chunking."""
        pages = [(1, "Hello world."), (2, ""), (3, "Goodbye world.")]
        result = chunk_text_with_pages(pages, chunk_size=10, overlap=0)
        assert len(result) == 1
        assert result[0] == ("Hello world. Goodbye world.", 1, 3)
