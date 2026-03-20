"""
Tests for the synthetic test data generator.

Validates deterministic output, file format correctness, and CLI arguments.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from generate_test_data import (
    BATCH_PRESETS,
    DEFAULT_SEED,
    SUPPORTED_TYPES,
    _make_faker,
    build_parser,
    generate_documents,
    generate_title,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """Provide a temporary output directory for generated files."""
    out = tmp_path / "test_output"
    out.mkdir()
    return out


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Verify that the same seed produces identical output."""

    def test_same_seed_produces_identical_pdfs(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "run_a"
        dir_b = tmp_path / "run_b"

        files_a = generate_documents(count=3, doc_type="pdf", seed=42, pages_per_doc=2, output_dir=dir_a)
        files_b = generate_documents(count=3, doc_type="pdf", seed=42, pages_per_doc=2, output_dir=dir_b)

        assert len(files_a) == len(files_b) == 3
        for fa, fb in zip(files_a, files_b, strict=True):
            assert fa.read_bytes() == fb.read_bytes(), f"Files differ: {fa.name}"

    def test_same_seed_produces_identical_epubs(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "run_a"
        dir_b = tmp_path / "run_b"

        files_a = generate_documents(count=3, doc_type="epub", seed=42, pages_per_doc=2, output_dir=dir_a)
        files_b = generate_documents(count=3, doc_type="epub", seed=42, pages_per_doc=2, output_dir=dir_b)

        assert len(files_a) == len(files_b) == 3
        for fa, fb in zip(files_a, files_b, strict=True):
            assert fa.read_bytes() == fb.read_bytes(), f"Files differ: {fa.name}"

    def test_different_seeds_produce_different_output(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "seed_1"
        dir_b = tmp_path / "seed_2"

        files_a = generate_documents(count=1, doc_type="pdf", seed=1, pages_per_doc=2, output_dir=dir_a)
        files_b = generate_documents(count=1, doc_type="pdf", seed=99, pages_per_doc=2, output_dir=dir_b)

        assert files_a[0].read_bytes() != files_b[0].read_bytes()

    def test_faker_titles_are_deterministic(self) -> None:
        fake1 = _make_faker(42)
        titles1 = [generate_title(fake1) for _ in range(5)]

        fake2 = _make_faker(42)
        titles2 = [generate_title(fake2) for _ in range(5)]

        assert titles1 == titles2


# ---------------------------------------------------------------------------
# Document type validation
# ---------------------------------------------------------------------------


class TestDocumentTypes:
    """Verify each document type generates valid files."""

    def test_pdf_generates_valid_file(self, tmp_output: Path) -> None:
        files = generate_documents(count=1, doc_type="pdf", seed=DEFAULT_SEED, pages_per_doc=3, output_dir=tmp_output)
        assert len(files) == 1
        path = files[0]
        assert path.exists()
        assert path.suffix == ".pdf"
        assert path.stat().st_size > 0
        # PDF files start with %PDF
        content = path.read_bytes()
        assert content[:5] == b"%PDF-"

    def test_pdf_ocr_generates_valid_file(self, tmp_output: Path) -> None:
        files = generate_documents(
            count=1, doc_type="pdf-ocr", seed=DEFAULT_SEED, pages_per_doc=3, output_dir=tmp_output
        )
        assert len(files) == 1
        path = files[0]
        assert path.exists()
        assert path.suffix == ".pdf"
        assert path.stat().st_size > 0
        content = path.read_bytes()
        assert content[:5] == b"%PDF-"

    def test_epub_generates_valid_file(self, tmp_output: Path) -> None:
        files = generate_documents(
            count=1, doc_type="epub", seed=DEFAULT_SEED, pages_per_doc=3, output_dir=tmp_output
        )
        assert len(files) == 1
        path = files[0]
        assert path.exists()
        assert path.suffix == ".epub"
        assert path.stat().st_size > 0
        # EPUB files are ZIP archives (PK magic bytes)
        content = path.read_bytes()
        assert content[:2] == b"PK"

    def test_unsupported_type_raises(self, tmp_output: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported document type"):
            generate_documents(count=1, doc_type="docx", seed=DEFAULT_SEED, output_dir=tmp_output)

    def test_all_supported_types_generate(self, tmp_output: Path) -> None:
        for doc_type in SUPPORTED_TYPES:
            files = generate_documents(
                count=1, doc_type=doc_type, seed=DEFAULT_SEED, pages_per_doc=2, output_dir=tmp_output / doc_type
            )
            assert len(files) == 1
            assert files[0].exists()


# ---------------------------------------------------------------------------
# Count and batch tests
# ---------------------------------------------------------------------------


class TestCounts:
    """Verify correct number of files are generated."""

    def test_generates_requested_count(self, tmp_output: Path) -> None:
        files = generate_documents(count=7, doc_type="pdf", seed=DEFAULT_SEED, pages_per_doc=1, output_dir=tmp_output)
        assert len(files) == 7
        assert all(f.exists() for f in files)

    def test_zero_count_generates_nothing(self, tmp_output: Path) -> None:
        files = generate_documents(count=0, doc_type="pdf", seed=DEFAULT_SEED, output_dir=tmp_output)
        assert files == []

    def test_batch_presets_are_defined(self) -> None:
        assert "small" in BATCH_PRESETS
        assert "medium" in BATCH_PRESETS
        assert "large" in BATCH_PRESETS
        assert BATCH_PRESETS["small"]["count"] == 50
        assert BATCH_PRESETS["medium"]["count"] == 500
        assert BATCH_PRESETS["large"]["count"] == 2000


# ---------------------------------------------------------------------------
# CLI argument tests
# ---------------------------------------------------------------------------


class TestCLI:
    """Verify CLI argument parsing and execution."""

    def test_parser_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.doc_type == "pdf"
        assert args.seed == DEFAULT_SEED
        assert args.count is None
        assert args.batch is None

    def test_parser_with_all_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--count", "10", "--type", "epub", "--seed", "99", "--pages", "5"])
        assert args.count == 10
        assert args.doc_type == "epub"
        assert args.seed == 99
        assert args.pages == 5

    def test_parser_batch_preset(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--batch", "small"])
        assert args.batch == "small"

    def test_main_generates_files(self, tmp_output: Path) -> None:
        main(["--count", "3", "--type", "pdf", "--seed", "42", "--pages", "2", "--output", str(tmp_output)])
        generated = list(tmp_output.glob("*.pdf"))
        assert len(generated) == 3

    def test_main_batch_preset(self, tmp_output: Path) -> None:
        # Use small batch but override count to keep test fast
        main(["--batch", "small", "--count", "2", "--type", "epub", "--output", str(tmp_output)])
        generated = list(tmp_output.glob("*.epub"))
        assert len(generated) == 2

    def test_cli_subprocess(self, tmp_output: Path) -> None:
        """Run the generator as a subprocess to validate the CLI entry point."""
        script = Path(__file__).resolve().parent / "generate_test_data.py"
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(script), "--count", "2", "--type", "pdf", "--seed", "42", "--output", str(tmp_output)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "Generated 2 files" in result.stdout
        generated = list(tmp_output.glob("*.pdf"))
        assert len(generated) == 2


# ---------------------------------------------------------------------------
# Output directory tests
# ---------------------------------------------------------------------------


class TestOutputDirectory:
    """Verify output directory handling."""

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        files = generate_documents(count=1, doc_type="pdf", seed=DEFAULT_SEED, pages_per_doc=1, output_dir=nested)
        assert nested.is_dir()
        assert len(files) == 1

    def test_files_use_sequential_naming(self, tmp_output: Path) -> None:
        files = generate_documents(count=3, doc_type="pdf", seed=DEFAULT_SEED, pages_per_doc=1, output_dir=tmp_output)
        names = [f.name for f in files]
        assert names == ["doc_00000.pdf", "doc_00001.pdf", "doc_00002.pdf"]
