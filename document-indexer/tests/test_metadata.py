from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REQUIRED_METADATA_KEYS

REAL_LIBRARY_CASES = [
    pytest.param(
        "amades/Auca dels costums de Barcelona amades.pdf",
        {
            "title": "Auca dels costums de Barcelona",
            "author": "Amades",
            "year": None,
            "category": None,
        },
        id="real-amades-author-folder",
    ),
    pytest.param(
        "amades/costumari 1 1 -3 OCR.pdf",
        {
            "title": "costumari 1 1 -3 OCR",
            "author": "Amades",
            "year": None,
            "category": None,
        },
        id="real-amades-irregular-numeric",
    ),
    pytest.param(
        "balearics/ESTUDIS_BALEARICS_01.pdf",
        {
            "title": "ESTUDIS BALEARICS 01",
            "author": "Unknown",
            "year": None,
            "category": "Balearics",
        },
        id="real-balearics-series-folder",
    ),
    pytest.param(
        "bsal/Bolletí societat arqueologica luliana 1885 - 1886.pdf",
        {
            "title": "Bolletí societat arqueologica luliana 1885 - 1886",
            "author": "Unknown",
            "year": None,
            "category": "BSAL",
        },
        id="real-bsal-year-range",
    ),
]


def assert_metadata_shape(metadata: dict, file_path: Path, base_path: Path) -> None:
    assert REQUIRED_METADATA_KEYS.issubset(metadata.keys())
    assert metadata["file_path"] == file_path.relative_to(base_path).as_posix()

    folder_path = file_path.parent.relative_to(base_path).as_posix()
    assert metadata["folder_path"] == ("" if folder_path == "." else folder_path)
    assert metadata["file_size"] == file_path.stat().st_size


def assert_metadata_values(metadata: dict, **expected: object) -> None:
    for key, value in expected.items():
        assert metadata[key] == value


def test_extract_metadata_parses_author_directory_pattern(make_document, extract_metadata_func):
    file_path, base_path = make_document(
        "Gabriel García Márquez/Cien años de soledad.pdf",
        b"abc123",
    )

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title="Cien años de soledad",
        author="Gabriel García Márquez",
        year=None,
        category=None,
    )


def test_extract_metadata_parses_author_title_year_filename_pattern(make_document, extract_metadata_func):
    file_path, base_path = make_document(
        "Mercè Rodoreda - La plaça del Diamant (1962).pdf",
        b"root-file",
    )

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert metadata["folder_path"] == ""
    assert_metadata_values(
        metadata,
        title="La plaça del Diamant",
        author="Mercè Rodoreda",
        year=1962,
        category=None,
    )


def test_extract_metadata_parses_category_author_title_pattern(make_document, extract_metadata_func):
    file_path, base_path = make_document(
        "Novel·la/Víctor Català/Solitud.pdf",
        b"category-author-title",
    )

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title="Solitud",
        author="Víctor Català",
        year=None,
        category="Novel·la",
    )


def test_extract_metadata_parses_category_filename_pattern(make_document, extract_metadata_func):
    file_path, base_path = make_document(
        "Poesia/Federico García Lorca - Romancero gitano (1928).pdf",
        b"category-filename",
    )

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title="Romancero gitano",
        author="Federico García Lorca",
        year=1928,
        category="Poesia",
    )


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    [
        pytest.param(
            "François Villon - L'été à Sóller (1984).pdf",
            {
                "title": "L'été à Sóller",
                "author": "François Villon",
                "year": 1984,
                "category": None,
            },
            id="special-characters-author-title-year",
        ),
        pytest.param(
            "Mercè Rodoreda - Jardí vora el mar.pdf",
            {
                "title": "Jardí vora el mar",
                "author": "Mercè Rodoreda",
                "year": None,
                "category": None,
            },
            id="missing-year",
        ),
        pytest.param(
            "Émile Zola/La curée.txt",
            {
                "title": "La curée",
                "author": "Émile Zola",
                "year": None,
                "category": None,
            },
            id="non-pdf",
        ),
    ],
)
def test_extract_metadata_handles_unicode_and_non_pdf_paths(
    make_document, extract_metadata_func, relative_path, expected
):
    file_path, base_path = make_document(relative_path, "olé".encode())

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(metadata, **expected)


def test_extract_metadata_keeps_very_long_titles_intact(make_document, extract_metadata_func):
    long_title = "Crònica" * 25
    file_path, base_path = make_document(f"Arxiu/{long_title}.pdf", b"long-title")

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title=long_title,
        author="Arxiu",
        year=None,
        category=None,
    )


def test_extract_metadata_falls_back_for_root_level_unknown_pattern(make_document, extract_metadata_func):
    file_path, base_path = make_document("scan_0042_final copy.pdf", b"fallback-root")

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title="scan_0042_final copy",
        author="Unknown",
        year=None,
        category=None,
    )


def test_extract_metadata_handles_nested_deep_paths_conservatively(make_document, extract_metadata_func):
    file_path, base_path = make_document(
        "Archive/Scans/1901/Cançó de bressol.pdf",
        b"deep-path",
    )

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title="Cançó de bressol",
        author="Unknown",
        year=None,
        category="Archive",
    )


def test_extract_metadata_uses_filename_fallback_for_unknown_patterns(make_document, extract_metadata_func):
    file_path, base_path = make_document(
        "Collected_Works__Vol_7__draft copy.pdf",
        b"fallback-filename",
    )

    metadata = extract_metadata_func(str(file_path), base_path=str(base_path))

    assert_metadata_shape(metadata, file_path, base_path)
    assert_metadata_values(
        metadata,
        title="Collected_Works__Vol_7__draft copy",
        author="Unknown",
        year=None,
        category=None,
    )


@pytest.mark.skipif(
    not Path("/home/jmservera/booklibrary").exists(),
    reason="Real library paths are only available on the maintainer machine.",
)
@pytest.mark.parametrize(("relative_path", "expected"), REAL_LIBRARY_CASES)
def test_extract_metadata_matches_real_library_patterns(
    extract_metadata_func, booklibrary_root, relative_path, expected
):
    file_path = booklibrary_root / relative_path
    assert file_path.exists(), f"Expected scanned library fixture to exist: {file_path}"

    metadata = extract_metadata_func(str(file_path), base_path=str(booklibrary_root))

    assert_metadata_shape(metadata, file_path, booklibrary_root)
    assert_metadata_values(metadata, **expected)
