"""Tests for the rerank_service module."""

from __future__ import annotations

import pytest
from rerank_service import (
    build_chunk_vector_params,
    cosine_rerank,
    cosine_similarity,
    extract_grouped_vectors,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero(self):
        assert cosine_similarity([0.0], [0.0]) == 0.0


class TestCosineRerank:
    def test_ranks_by_similarity(self):
        query = [1.0, 0.0, 0.0]
        docs = [
            ("doc_far", [0.0, 1.0, 0.0]),
            ("doc_close", [0.9, 0.1, 0.0]),
            ("doc_exact", [1.0, 0.0, 0.0]),
        ]
        result = cosine_rerank(query, docs)
        ids = [doc_id for doc_id, _ in result]
        assert ids[0] == "doc_exact"
        assert ids[1] == "doc_close"
        assert ids[2] == "doc_far"

    def test_empty_docs(self):
        assert cosine_rerank([1.0, 0.0], []) == []

    def test_single_doc(self):
        result = cosine_rerank([1.0], [("only", [1.0])])
        assert len(result) == 1
        assert result[0][0] == "only"
        assert result[0][1] == pytest.approx(1.0)


class TestBuildChunkVectorParams:
    def test_basic(self):
        params = build_chunk_vector_params(["book1", "book2"], "embedding_v")
        assert "parent_id_s" in params["q"]
        assert "book1" in params["q"]
        assert "book2" in params["q"]
        assert params["fl"] == "parent_id_s,embedding_v"
        assert params["group"] == "true"
        assert params["group.field"] == "parent_id_s"
        assert params["group.limit"] == "1"
        assert params["rows"] == 2

    def test_single_parent(self):
        params = build_chunk_vector_params(["single"], "embedding_byte_v")
        assert params["fl"] == "parent_id_s,embedding_byte_v"
        assert params["rows"] == 1


class TestExtractGroupedVectors:
    def test_extracts_vectors(self):
        response = {
            "grouped": {
                "parent_id_s": {
                    "groups": [
                        {
                            "groupValue": "book1",
                            "doclist": {"docs": [{"parent_id_s": "book1", "embedding_v": [0.1, 0.2, 0.3]}]},
                        },
                        {
                            "groupValue": "book2",
                            "doclist": {"docs": [{"parent_id_s": "book2", "embedding_v": [0.4, 0.5, 0.6]}]},
                        },
                    ]
                }
            }
        }
        result = extract_grouped_vectors(response, "embedding_v")
        assert "book1" in result
        assert "book2" in result
        assert result["book1"] == [0.1, 0.2, 0.3]

    def test_skips_missing_vectors(self):
        response = {
            "grouped": {
                "parent_id_s": {
                    "groups": [
                        {
                            "groupValue": "book1",
                            "doclist": {"docs": [{"parent_id_s": "book1"}]},
                        },
                    ]
                }
            }
        }
        result = extract_grouped_vectors(response, "embedding_v")
        assert result == {}

    def test_empty_response(self):
        result = extract_grouped_vectors({}, "embedding_v")
        assert result == {}

    def test_skips_null_group_value(self):
        response = {
            "grouped": {
                "parent_id_s": {
                    "groups": [
                        {
                            "groupValue": None,
                            "doclist": {"docs": [{"embedding_v": [0.1]}]},
                        },
                    ]
                }
            }
        }
        result = extract_grouped_vectors(response, "embedding_v")
        assert result == {}
