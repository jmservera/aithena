"""First-page PDF thumbnail generation using PyMuPDF."""

from __future__ import annotations

import logging

import fitz

logger = logging.getLogger(__name__)


def generate_thumbnail(
    pdf_path: str,
    output_path: str,
    width: int = 200,
    height: int = 280,
) -> bool:
    """Render the first page of a PDF as a JPEG thumbnail.

    Args:
        pdf_path: Path to the source PDF file.
        output_path: Destination path for the JPEG thumbnail.
        width: Target thumbnail width in pixels.
        height: Target thumbnail height in pixels.

    Returns:
        ``True`` on success, ``False`` on failure (graceful — never raises).
    """
    try:
        doc = fitz.open(pdf_path)
        try:
            if doc.page_count == 0:
                logger.warning("PDF has no pages: %s", pdf_path)
                return False

            page = doc.load_page(0)
            page_rect = page.rect

            # Scale to fit within width×height while preserving aspect ratio
            scale_x = width / page_rect.width
            scale_y = height / page_rect.height
            scale = min(scale_x, scale_y)

            matrix = fitz.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=matrix)
            pixmap.save(output_path, output="jpeg")
        finally:
            doc.close()
    except Exception as exc:
        logger.warning(
            "Thumbnail generation failed for %s: %s",
            pdf_path,
            exc,
        )
        return False

    logger.info("Generated thumbnail: %s", output_path)
    return True
