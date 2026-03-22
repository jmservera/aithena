"""Tests for thumbnail generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from document_indexer.thumbnail import generate_thumbnail

# ---------------------------------------------------------------------------
# Helper: create a real 1-page PDF via PyMuPDF
# ---------------------------------------------------------------------------


def _make_pdf(path: Path, *, pages: int = 1, text: str = "Hello") -> Path:
    """Create a minimal valid PDF at *path* using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


class TestGenerateThumbnailSuccess:
    def test_creates_jpeg_file(self, tmp_path: Path):
        pdf = _make_pdf(tmp_path / "book.pdf")
        out = tmp_path / "book.pdf.thumb.jpg"

        result = generate_thumbnail(str(pdf), str(out))

        assert result is True
        assert out.exists()
        assert out.stat().st_size > 0

    def test_jpeg_header(self, tmp_path: Path):
        pdf = _make_pdf(tmp_path / "book.pdf")
        out = tmp_path / "book.pdf.thumb.jpg"

        generate_thumbnail(str(pdf), str(out))

        # JPEG files start with 0xFFD8
        data = out.read_bytes()
        assert data[:2] == b"\xff\xd8"

    def test_custom_dimensions(self, tmp_path: Path):
        pdf = _make_pdf(tmp_path / "book.pdf")
        out = tmp_path / "thumb.jpg"

        result = generate_thumbnail(str(pdf), str(out), width=100, height=140)

        assert result is True
        assert out.exists()

    def test_default_dimensions(self, tmp_path: Path):
        """Default width=200, height=280 produces a reasonably-sized image."""
        pdf = _make_pdf(tmp_path / "book.pdf")
        out = tmp_path / "thumb.jpg"

        generate_thumbnail(str(pdf), str(out))

        assert out.stat().st_size > 100  # not trivially small

    def test_multi_page_uses_first_page(self, tmp_path: Path):
        pdf = _make_pdf(tmp_path / "multi.pdf", pages=5, text="Page One")
        out = tmp_path / "thumb.jpg"

        result = generate_thumbnail(str(pdf), str(out))

        assert result is True
        assert out.exists()


# ---------------------------------------------------------------------------
# Failure / graceful degradation
# ---------------------------------------------------------------------------


class TestGenerateThumbnailFailure:
    def test_nonexistent_pdf_returns_false(self, tmp_path: Path):
        out = tmp_path / "thumb.jpg"

        result = generate_thumbnail("/no/such/file.pdf", str(out))

        assert result is False
        assert not out.exists()

    def test_corrupt_pdf_returns_false(self, tmp_path: Path):
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"this is not a pdf")
        out = tmp_path / "thumb.jpg"

        result = generate_thumbnail(str(corrupt), str(out))

        assert result is False

    def test_empty_file_returns_false(self, tmp_path: Path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        out = tmp_path / "thumb.jpg"

        result = generate_thumbnail(str(empty), str(out))

        assert result is False

    def test_zero_page_pdf_returns_false(self, tmp_path: Path):
        """A PDF with zero pages should return False."""
        out = tmp_path / "thumb.jpg"

        with patch("document_indexer.thumbnail.fitz") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.page_count = 0
            mock_fitz.open.return_value = mock_doc
            result = generate_thumbnail("/fake/zero.pdf", str(out))

        assert result is False

    def test_unwritable_output_returns_false(self, tmp_path: Path):
        pdf = _make_pdf(tmp_path / "book.pdf")
        # Path that can't be written (directory doesn't exist)
        out = "/no/such/dir/thumb.jpg"

        result = generate_thumbnail(str(pdf), out)

        assert result is False

    def test_logs_warning_on_failure(self, tmp_path: Path, caplog):
        out = tmp_path / "thumb.jpg"

        with caplog.at_level("WARNING"):
            generate_thumbnail("/no/such/file.pdf", str(out))

        assert any("Thumbnail generation failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Integration with index_document
# ---------------------------------------------------------------------------


class TestThumbnailIntegration:
    """Verify thumbnail generation is called during indexing and its result
    is included in the Solr document parameters."""

    @patch("document_indexer.__main__.generate_thumbnail", return_value=True)
    @patch("document_indexer.__main__.index_chunks", return_value=5)
    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.load_metadata_override", return_value=None)
    @patch("document_indexer.__main__.get_page_count", return_value=10)
    @patch("document_indexer.__main__.extract_metadata")
    @patch("requests.post")
    def test_thumbnail_url_in_solr_params(
        self,
        mock_post,
        mock_extract,
        mock_page_count,
        mock_override,
        mock_save_state,
        mock_index_chunks,
        mock_gen_thumb,
        tmp_path: Path,
    ):
        from document_indexer.__main__ import index_document

        pdf = tmp_path / "library" / "Author" / "Title.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4 fake")
        mock_extract.return_value = {
            "title": "Title",
            "author": "Author",
            "year": 2024,
            "category": "Fiction",
            "language": "en",
            "file_path": "library/Author/Title.pdf",
            "folder_path": "library/Author",
            "file_size": pdf.stat().st_size,
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        index_document(pdf)

        # Verify generate_thumbnail was called with pdf path and .thumb.jpg
        mock_gen_thumb.assert_called_once()
        call_args = mock_gen_thumb.call_args
        assert call_args[0][0] == str(pdf)
        assert call_args[0][1].endswith(".thumb.jpg")

        # Verify thumbnail_url_s was included in Solr params
        post_call = mock_post.call_args
        params = post_call.kwargs.get("params") or post_call[1].get("params")
        assert "literal.thumbnail_url_s" in params

    @patch("document_indexer.__main__.generate_thumbnail", return_value=False)
    @patch("document_indexer.__main__.index_chunks", return_value=5)
    @patch("document_indexer.__main__.save_state")
    @patch("document_indexer.__main__.load_metadata_override", return_value=None)
    @patch("document_indexer.__main__.get_page_count", return_value=10)
    @patch("document_indexer.__main__.extract_metadata")
    @patch("requests.post")
    def test_indexing_continues_when_thumbnail_fails(
        self,
        mock_post,
        mock_extract,
        mock_page_count,
        mock_override,
        mock_save_state,
        mock_index_chunks,
        mock_gen_thumb,
        tmp_path: Path,
    ):
        from document_indexer.__main__ import index_document

        pdf = tmp_path / "library" / "Author" / "Title.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4 fake")
        mock_extract.return_value = {
            "title": "Title",
            "author": "Author",
            "year": None,
            "category": None,
            "language": None,
            "file_path": "library/Author/Title.pdf",
            "folder_path": "library/Author",
            "file_size": pdf.stat().st_size,
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Should NOT raise — indexing continues even though thumbnail failed
        result = index_document(pdf)

        assert result is not None
        mock_index_chunks.assert_called_once()

        # thumbnail_url_s should NOT be in params when generation failed
        post_call = mock_post.call_args
        params = post_call.kwargs.get("params") or post_call[1].get("params")
        assert "literal.thumbnail_url_s" not in params
