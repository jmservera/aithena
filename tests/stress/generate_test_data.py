#!/usr/bin/env python3
"""
Synthetic test data generator for Aithena stress tests.

Produces deterministic PDF and EPUB files using seeded random generation
so that stress test runs are reproducible.

Usage:
    python generate_test_data.py --count 50 --type pdf --seed 42
    python generate_test_data.py --count 500 --type epub --output /tmp/test_data
    python generate_test_data.py --batch medium

Batch presets:
    small   –  50 docs, ~10 pages each  (~500 total pages)
    medium  – 500 docs, ~10 pages each  (~5K total pages)
    large   – 2000 docs, ~10 pages each (~20K total pages)
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from faker import Faker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "test_data"
DEFAULT_SEED = 42
DEFAULT_PAGES_PER_DOC = 10

BATCH_PRESETS: dict[str, dict] = {
    "small": {"count": 50, "pages": 10},
    "medium": {"count": 500, "pages": 10},
    "large": {"count": 2000, "pages": 10},
}

SUPPORTED_TYPES = ("pdf", "pdf-ocr", "epub")


# ---------------------------------------------------------------------------
# Text generation helpers
# ---------------------------------------------------------------------------


def _make_faker(seed: int) -> Faker:
    """Return a seeded Faker instance for deterministic output."""
    fake = Faker()
    Faker.seed(seed)
    random.seed(seed)
    return fake


def generate_title(fake: Faker) -> str:
    """Generate a realistic book title."""
    patterns = [
        lambda: f"The {fake.word().title()} of {fake.word().title()}",
        lambda: f"{fake.word().title()} and {fake.word().title()}",
        lambda: f"A {fake.word().title()} {fake.word().title()}",
        lambda: fake.sentence(nb_words=4).rstrip("."),
    ]
    return random.choice(patterns)()  # noqa: S311


def generate_author(fake: Faker) -> str:
    """Generate a realistic author name."""
    return fake.name()


def generate_page_text(fake: Faker, min_paragraphs: int = 3, max_paragraphs: int = 6) -> str:
    """Generate realistic page content with multiple paragraphs."""
    n = random.randint(min_paragraphs, max_paragraphs)  # noqa: S311
    return "\n\n".join(fake.paragraph(nb_sentences=random.randint(4, 8)) for _ in range(n))  # noqa: S311


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


def generate_pdf(
    output_path: Path,
    *,
    title: str,
    author: str,
    fake: Faker,
    num_pages: int = DEFAULT_PAGES_PER_DOC,
    ocr_style: bool = False,
) -> Path:
    """
    Generate a PDF file with realistic text content.

    When *ocr_style* is True the text is rendered in a monospace font at a
    slightly larger size to mimic OCR-scanned documents.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    font_family = "Courier" if ocr_style else "Helvetica"
    body_size = 11 if ocr_style else 10

    pdf.set_title(title)
    pdf.set_author(author)

    # Title page
    pdf.add_page()
    pdf.set_font(font_family, "B", 24)
    pdf.cell(0, 60, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(font_family, "I", 16)
    pdf.cell(0, 10, f"by {author}", new_x="LMARGIN", new_y="NEXT", align="C")

    # Content pages
    for page_num in range(1, num_pages):
        pdf.add_page()
        chapter_title = f"Chapter {page_num}: {fake.sentence(nb_words=3).rstrip('.')}"
        pdf.set_font(font_family, "B", 14)
        pdf.cell(0, 10, chapter_title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font(font_family, "", body_size)

        text = generate_page_text(fake)
        # fpdf2 multi_cell handles wrapping
        pdf.multi_cell(0, 5, text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# EPUB generation
# ---------------------------------------------------------------------------


def generate_epub(
    output_path: Path,
    *,
    title: str,
    author: str,
    fake: Faker,
    num_pages: int = DEFAULT_PAGES_PER_DOC,
) -> Path:
    """Generate an EPUB file with realistic text content."""
    from ebooklib import epub

    book = epub.EpubBook()

    book.set_identifier(f"aithena-stress-{fake.uuid4()}")
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    chapters = []
    for i in range(1, num_pages + 1):
        chapter_title = f"Chapter {i}: {fake.sentence(nb_words=3).rstrip('.')}"
        ch = epub.EpubHtml(title=chapter_title, file_name=f"chap_{i:04d}.xhtml", lang="en")

        paragraphs = generate_page_text(fake)
        html_body = "".join(f"<p>{p.strip()}</p>" for p in paragraphs.split("\n\n") if p.strip())
        ch.content = f"<html><body><h1>{chapter_title}</h1>{html_body}</body></html>"
        book.add_item(ch)
        chapters.append(ch)

    book.toc = [(epub.Section("Contents"), chapters)]

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = ["nav", *chapters]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book, {})
    return output_path


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def generate_documents(
    *,
    count: int,
    doc_type: str,
    seed: int = DEFAULT_SEED,
    pages_per_doc: int = DEFAULT_PAGES_PER_DOC,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """
    Generate *count* synthetic documents of the given type.

    Returns a list of paths to the generated files.
    """
    if doc_type not in SUPPORTED_TYPES:
        msg = f"Unsupported document type: {doc_type!r}. Choose from {SUPPORTED_TYPES}"
        raise ValueError(msg)

    fake = _make_faker(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for i in range(count):
        title = generate_title(fake)
        author = generate_author(fake)
        safe_name = f"doc_{i:05d}"

        if doc_type == "pdf":
            path = output_dir / f"{safe_name}.pdf"
            generate_pdf(path, title=title, author=author, fake=fake, num_pages=pages_per_doc)
        elif doc_type == "pdf-ocr":
            path = output_dir / f"{safe_name}.pdf"
            generate_pdf(path, title=title, author=author, fake=fake, num_pages=pages_per_doc, ocr_style=True)
        elif doc_type == "epub":
            path = output_dir / f"{safe_name}.epub"
            generate_epub(path, title=title, author=author, fake=fake, num_pages=pages_per_doc)

        generated.append(path)

    return generated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic test documents for Aithena stress tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of documents to generate (overrides --batch count)",
    )
    parser.add_argument(
        "--type",
        dest="doc_type",
        choices=SUPPORTED_TYPES,
        default="pdf",
        help="Document type to generate (default: pdf)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for deterministic output (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help=f"Pages per document (default: {DEFAULT_PAGES_PER_DOC})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--batch",
        choices=BATCH_PRESETS.keys(),
        default=None,
        help="Use a preset batch size (small/medium/large)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve count and pages from batch preset or explicit args
    if args.batch:
        preset = BATCH_PRESETS[args.batch]
        count = args.count if args.count is not None else preset["count"]
        pages = args.pages if args.pages is not None else preset["pages"]
    else:
        count = args.count if args.count is not None else 50
        pages = args.pages if args.pages is not None else DEFAULT_PAGES_PER_DOC

    print(f"Generating {count} {args.doc_type} documents ({pages} pages each) with seed={args.seed}")
    print(f"Output directory: {args.output}")

    files = generate_documents(
        count=count,
        doc_type=args.doc_type,
        seed=args.seed,
        pages_per_doc=pages,
        output_dir=args.output,
    )

    total_pages = count * pages
    print(f"Generated {len(files)} files (~{total_pages} total pages)")
    for f in files[:5]:
        print(f"  {f}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")


if __name__ == "__main__":
    main()
