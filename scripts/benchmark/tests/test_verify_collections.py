"""Tests for the collection verification logic.

All Solr calls are mocked — these tests validate the verification logic,
dimension checks, ID comparison, and report formatting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from verify_collections import (
    CollectionStatus,
    VerificationResult,
    format_report,
    get_doc_count,
    get_parent_ids,
    get_sample_embedding_dim,
    result_to_dict,
    verify_collections,
)

SOLR_URL = "http://localhost:8983"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_collection_status(
    collection: str = "books",
    total_docs: int = 100,
    parent_docs: int = 20,
    chunk_docs: int = 80,
    sample_embedding_dim: int | None = 512,
    parent_ids: list[str] | None = None,
    error: str | None = None,
) -> CollectionStatus:
    return CollectionStatus(
        collection=collection,
        total_docs=total_docs,
        parent_docs=parent_docs,
        chunk_docs=chunk_docs,
        sample_embedding_dim=sample_embedding_dim,
        parent_ids=parent_ids or [f"doc{i}" for i in range(parent_docs)],
        error=error,
    )


def _mock_solr_response(num_found: int, docs: list[dict] | None = None) -> dict:
    return {"response": {"numFound": num_found, "docs": docs or []}}


# ---------------------------------------------------------------------------
# get_doc_count
# ---------------------------------------------------------------------------


class TestGetDocCount:
    @patch("verify_collections.requests.get")
    def test_returns_count(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(42)
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        assert get_doc_count(SOLR_URL, "books") == 42

    @patch("verify_collections.requests.get")
    def test_passes_filter_query(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(10)
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        get_doc_count(SOLR_URL, "books", fq="-parent_id_s:[* TO *]")

        call_params = mock_get.call_args[1]["params"]
        assert call_params["fq"] == "-parent_id_s:[* TO *]"


# ---------------------------------------------------------------------------
# get_parent_ids
# ---------------------------------------------------------------------------


class TestGetParentIds:
    @patch("verify_collections.requests.get")
    def test_returns_ids(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(
            3, [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        ids = get_parent_ids(SOLR_URL, "books")
        assert ids == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# get_sample_embedding_dim
# ---------------------------------------------------------------------------


class TestGetSampleEmbeddingDim:
    @patch("verify_collections.requests.get")
    def test_returns_dimension(self, mock_get: MagicMock) -> None:
        embedding = [0.1] * 512
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(
            1, [{"id": "chunk1", "embedding_v": embedding}],
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        dim = get_sample_embedding_dim(SOLR_URL, "books")
        assert dim == 512

    @patch("verify_collections.requests.get")
    def test_returns_768_for_e5base(self, mock_get: MagicMock) -> None:
        embedding = [0.1] * 768
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(
            1, [{"id": "chunk1", "embedding_v": embedding}],
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        dim = get_sample_embedding_dim(SOLR_URL, "books_e5base")
        assert dim == 768

    @patch("verify_collections.requests.get")
    def test_returns_none_when_no_chunks(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(0, [])
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        dim = get_sample_embedding_dim(SOLR_URL, "books")
        assert dim is None

    @patch("verify_collections.requests.get")
    def test_returns_none_when_no_embedding_field(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_solr_response(1, [{"id": "chunk1"}])
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        dim = get_sample_embedding_dim(SOLR_URL, "books")
        assert dim is None


# ---------------------------------------------------------------------------
# verify_collections (integration with mocked Solr)
# ---------------------------------------------------------------------------


class TestVerifyCollections:
    @patch("verify_collections.inspect_collection")
    def test_all_checks_pass(self, mock_inspect: MagicMock) -> None:
        shared_ids = [f"doc{i}" for i in range(10)]
        mock_inspect.side_effect = [
            _make_collection_status(
                collection="books", parent_docs=10, chunk_docs=80,
                sample_embedding_dim=512, parent_ids=shared_ids,
            ),
            _make_collection_status(
                collection="books_e5base", parent_docs=10, chunk_docs=60,
                sample_embedding_dim=768, parent_ids=shared_ids,
            ),
        ]

        result = verify_collections(SOLR_URL)

        assert result.parent_count_match is True
        assert result.parent_ids_match is True
        assert result.baseline_dim_correct is True
        assert result.candidate_dim_correct is True
        assert result.all_checks_passed is True

    @patch("verify_collections.inspect_collection")
    def test_count_mismatch_detected(self, mock_inspect: MagicMock) -> None:
        mock_inspect.side_effect = [
            _make_collection_status(
                collection="books", parent_docs=10,
                parent_ids=[f"d{i}" for i in range(10)],
            ),
            _make_collection_status(
                collection="books_e5base", parent_docs=8,
                sample_embedding_dim=768, parent_ids=[f"d{i}" for i in range(8)],
            ),
        ]

        result = verify_collections(SOLR_URL)

        assert result.parent_count_match is False
        assert result.all_checks_passed is False

    @patch("verify_collections.inspect_collection")
    def test_missing_ids_detected(self, mock_inspect: MagicMock) -> None:
        mock_inspect.side_effect = [
            _make_collection_status(
                collection="books", parent_docs=3,
                parent_ids=["doc1", "doc2", "doc3"],
            ),
            _make_collection_status(
                collection="books_e5base", parent_docs=3,
                sample_embedding_dim=768,
                parent_ids=["doc1", "doc2", "doc4"],
            ),
        ]

        result = verify_collections(SOLR_URL)

        assert result.parent_ids_match is False
        assert result.missing_in_candidate == ["doc3"]
        assert result.missing_in_baseline == ["doc4"]

    @patch("verify_collections.inspect_collection")
    def test_wrong_dimensionality_detected(self, mock_inspect: MagicMock) -> None:
        shared_ids = ["doc1"]
        mock_inspect.side_effect = [
            _make_collection_status(
                collection="books", parent_docs=1, chunk_docs=5,
                sample_embedding_dim=768,  # wrong! should be 512
                parent_ids=shared_ids,
            ),
            _make_collection_status(
                collection="books_e5base", parent_docs=1, chunk_docs=5,
                sample_embedding_dim=512,  # wrong! should be 768
                parent_ids=shared_ids,
            ),
        ]

        result = verify_collections(SOLR_URL)

        assert result.baseline_dim_correct is False
        assert result.candidate_dim_correct is False
        assert result.all_checks_passed is False

    @patch("verify_collections.inspect_collection")
    def test_empty_collections_pass(self, mock_inspect: MagicMock) -> None:
        mock_inspect.side_effect = [
            _make_collection_status(
                collection="books", total_docs=0, parent_docs=0, chunk_docs=0,
                sample_embedding_dim=None, parent_ids=[],
            ),
            _make_collection_status(
                collection="books_e5base", total_docs=0, parent_docs=0, chunk_docs=0,
                sample_embedding_dim=None, parent_ids=[],
            ),
        ]

        result = verify_collections(SOLR_URL)

        assert result.parent_count_match is True
        assert result.parent_ids_match is True
        assert result.baseline_dim_correct is True  # no chunks → passes
        assert result.candidate_dim_correct is True
        assert result.all_checks_passed is True

    @patch("verify_collections.inspect_collection")
    def test_error_in_collection_does_not_crash(self, mock_inspect: MagicMock) -> None:
        mock_inspect.side_effect = [
            _make_collection_status(collection="books", error="Connection refused"),
            _make_collection_status(collection="books_e5base", sample_embedding_dim=768),
        ]

        result = verify_collections(SOLR_URL)

        assert result.all_checks_passed is False
        assert result.baseline is not None
        assert result.baseline.error == "Connection refused"


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_passing_report(self) -> None:
        result = VerificationResult(
            baseline=_make_collection_status(collection="books", sample_embedding_dim=512),
            candidate=_make_collection_status(collection="books_e5base", sample_embedding_dim=768),
            parent_count_match=True,
            parent_ids_match=True,
            baseline_dim_correct=True,
            candidate_dim_correct=True,
            all_checks_passed=True,
        )
        text = format_report(result)

        assert "ALL CHECKS PASSED" in text
        assert "books" in text
        assert "books_e5base" in text
        assert "512" in text
        assert "768" in text

    def test_failing_report_shows_discrepancies(self) -> None:
        result = VerificationResult(
            baseline=_make_collection_status(collection="books"),
            candidate=_make_collection_status(collection="books_e5base", sample_embedding_dim=768),
            parent_count_match=False,
            parent_ids_match=False,
            baseline_dim_correct=True,
            candidate_dim_correct=True,
            missing_in_candidate=["doc99"],
            all_checks_passed=False,
        )
        text = format_report(result)

        assert "SOME CHECKS FAILED" in text
        assert "doc99" in text

    def test_error_report(self) -> None:
        result = VerificationResult(
            baseline=_make_collection_status(collection="books", error="timeout"),
            candidate=None,
            all_checks_passed=False,
        )
        text = format_report(result)

        assert "timeout" in text
        assert "NOT AVAILABLE" in text

    def test_verbose_shows_all_ids(self) -> None:
        missing = [f"doc{i}" for i in range(20)]
        result = VerificationResult(
            baseline=_make_collection_status(collection="books"),
            candidate=_make_collection_status(collection="books_e5base", sample_embedding_dim=768),
            parent_count_match=False,
            parent_ids_match=False,
            baseline_dim_correct=True,
            candidate_dim_correct=True,
            missing_in_candidate=missing,
            all_checks_passed=False,
        )
        terse = format_report(result, verbose=False)
        verbose = format_report(result, verbose=True)

        assert "... and 10 more" in terse
        assert "... and 10 more" not in verbose
        assert "doc19" in verbose


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestResultToDict:
    def test_json_serializable(self) -> None:
        result = VerificationResult(
            baseline=_make_collection_status(collection="books"),
            candidate=_make_collection_status(collection="books_e5base", sample_embedding_dim=768),
            parent_count_match=True,
            parent_ids_match=True,
            baseline_dim_correct=True,
            candidate_dim_correct=True,
            all_checks_passed=True,
        )
        d = result_to_dict(result)
        serialized = json.dumps(d)
        assert "books" in serialized
        assert "books_e5base" in serialized

    def test_includes_all_fields(self) -> None:
        result = VerificationResult(
            baseline=_make_collection_status(collection="books"),
            candidate=_make_collection_status(collection="books_e5base", sample_embedding_dim=768),
            parent_count_match=True,
            parent_ids_match=False,
            baseline_dim_correct=True,
            candidate_dim_correct=True,
            missing_in_candidate=["doc5"],
            all_checks_passed=False,
        )
        d = result_to_dict(result)

        assert d["parent_count_match"] is True
        assert d["parent_ids_match"] is False
        assert d["missing_in_candidate"] == ["doc5"]
        assert d["baseline"]["collection"] == "books"
        assert d["candidate"]["collection"] == "books_e5base"
