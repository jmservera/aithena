#!/usr/bin/env python3
"""
Fast corpus builder using Project Gutenberg text → PDF conversion.
Generates many small PDFs from public domain books.
Runs in parallel with the existing arXiv/HAL/SciELO/RACO downloads.
"""

import json
import logging
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests

CORPUS_ROOT = Path("/data/documents/benchmark-corpus")
TARGETS = {"en": 400, "fr": 400, "es": 400, "ca": 300}
MAX_PAGES = 6
WORDS_PER_CHUNK = 2000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def get_pdf_page_count(data: bytes) -> int:
    try:
        import io

        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(data))
        return len(reader.pages)
    except Exception:
        return -1


def count_saved(lang: str) -> int:
    return len(list((CORPUS_ROOT / lang).glob("*.pdf")))


def text_to_pdf(text: str, title: str = "Document") -> bytes | None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph(title[:100], styles["Title"]))
        story.append(Spacer(1, 0.5 * cm))

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            clean = para.replace("\n", " ").strip()
            if clean:
                story.append(Paragraph(clean, styles["Normal"]))
                story.append(Spacer(1, 0.2 * cm))

        doc.build(story)
        return buf.getvalue()
    except Exception as e:
        log.debug("PDF gen error: %s", e)
        return None


def fetch_gutenberg(book_id: int) -> tuple:
    """Download Gutenberg book. Returns (title, text) or (None, None)."""
    import re

    for suffix in ["-0.txt", ".txt", "-8.txt"]:
        url = f"https://www.gutenberg.org/files/{book_id}/{book_id}{suffix}"
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "aithena-benchmark/1.0"})
            if resp.status_code == 200 and len(resp.content) > 5000:
                text = resp.content.decode("utf-8", errors="replace")
                title_match = re.search(r"Title:\s*(.+)", text)
                title = title_match.group(1).strip() if title_match else f"Book {book_id}"
                start = text.find("*** START OF")
                end = text.find("*** END OF")
                if start != -1:
                    text = text[start + 100 :]
                if end != -1:
                    text = text[:end]
                return title, text
        except Exception:  # noqa: S110 — best-effort text extraction
            pass
    return None, None


def process_book(lang: str, book_id: int, target: int) -> int:
    """Download one book and generate PDF chunks. Returns new count."""
    if count_saved(lang) >= target:
        return count_saved(lang)

    title, text = fetch_gutenberg(book_id)
    if not text:
        log.debug("%s: book %d not found", lang, book_id)
        return count_saved(lang)

    words = text.split()
    log.info("%s: Book '%s' (%d words) → chunks", lang.upper(), title[:50], len(words))

    chunk_num = 0
    i = 0
    while i < len(words) and count_saved(lang) < target:
        chunk_words = words[i : i + WORDS_PER_CHUNK]
        if len(chunk_words) < 200:
            break
        chunk_text = " ".join(chunk_words)
        chunk_title = f"{title} — Part {chunk_num + 1}"

        filename = f"gutenberg_{book_id}_p{chunk_num:04d}.pdf"
        dest = CORPUS_ROOT / lang / filename

        if not dest.exists():
            pdf_data = text_to_pdf(chunk_text, title=chunk_title)
            if pdf_data:
                pages = get_pdf_page_count(pdf_data)
                if 1 <= pages <= MAX_PAGES:
                    dest.write_bytes(pdf_data)
                    log.info("%s: saved %s (%d pages, total=%d)", lang.upper(), filename, pages, count_saved(lang))
                else:
                    log.debug("%s: chunk %d has %d pages, skipping", lang, chunk_num, pages)

        i += WORDS_PER_CHUNK
        chunk_num += 1

    return count_saved(lang)


# Comprehensive book lists per language
BOOKS = {
    "en": [
        # Classic novels and texts — widely available
        1342,
        84,
        11,
        98,
        74,
        76,
        1661,
        2701,
        4300,
        5200,
        345,
        174,
        2554,
        1080,
        1260,
        1184,
        219,
        30,
        1998,
        203,
        768,
        1399,
        2591,
        16328,
        46,
        1232,
        7370,
        25344,
        7178,
        2148,
        3207,
        1952,
        2097,
        2600,
        2413,
        4517,
        514,
        766,
        1400,
        1322,
        244,
        580,
        786,
        161,
        158,
        120,
        730,
        863,
        36,
        105,
        113,
        159,
        160,
        164,
        23,
        41,
        43,
        45,
        47,
        55,
        67,
        73,
        79,
        808,
        818,
        820,
        821,
        823,
        824,
        826,
        829,
        830,
        833,
        844,
        845,
        852,
        855,
        883,
        910,
        921,
        928,
        932,
        935,
        943,
        946,
        949,
        951,
        957,
        963,
        968,
    ],
    "fr": [
        # French public domain works
        13951,
        17489,
        4650,
        14779,
        5097,
        3748,
        14286,
        17834,
        13846,
        15621,
        17235,
        3160,
        17154,
        16816,
        5765,
        3074,
        4122,
        7105,
        2982,
        16652,
        14523,
        7942,
        18585,
        17302,
        14672,
        10133,
        7399,
        2413,
        8129,
        11568,
        14280,
        13804,
        16715,
        17111,
        6592,
        11539,
        6593,
        6594,
        6595,
        6596,
        13852,
        13853,
        13854,
        13855,
        13856,
        13857,
        14022,
        14023,
        14024,
        14025,
        14026,
        14027,
        14028,
        14029,
        14030,
        14031,
        14032,
        14033,
        14034,
        14035,
        14036,
        14037,
        14038,
        14039,
        14040,
        14041,
        14042,
        14043,
        14044,
        14045,
        14046,
        14047,
        14048,
        14049,
        14050,
        14051,
        14052,
        14053,
        14054,
        14055,
    ],
    "es": [
        # Spanish public domain works
        2000,
        2033,
        2199,
        15130,
        14765,
        14981,
        15083,
        15136,
        14232,
        14441,
        14459,
        14588,
        14613,
        14678,
        14717,
        14741,
        14783,
        14793,
        14801,
        14888,
        14915,
        14934,
        15010,
        15016,
        15064,
        15078,
        15095,
        15105,
        15117,
        15133,
        16396,
        16397,
        16398,
        16399,
        16400,
        16401,
        16402,
        16403,
        16404,
        16405,
        14267,
        14268,
        14269,
        14270,
        14271,
        14272,
        14273,
        14274,
        14275,
        14276,
        14277,
        14278,
        14279,
        14281,
        14282,
        14283,
        14284,
        14285,
        14287,
        14288,
        14289,
        14290,
        14291,
        14292,
        14293,
        14294,
        14295,
        14296,
        14297,
        14298,
        14299,
        14300,
        14301,
        14302,
        14303,
        14304,
        14305,
        14306,
        14307,
        14308,
    ],
    "ca": [
        # Catalan works — fewer available, supplement with regional Spanish
        11561,
        14467,
        43363,
        43364,
        43365,
        43366,
        43367,
        43368,
        43369,
        43370,
        28371,
        28372,
        28373,
        28374,
        43371,
        43372,
        43373,
        43374,
        43375,
        43376,
        43377,
        43378,
        43379,
        43380,
        43381,
        43382,
        43383,
        43384,
        # Also try some general Romance IDs that may have CA content
        55989,
        55990,
        55991,
        55992,
        55993,
        55994,
        55995,
    ],
}


def write_manifest():
    stats = {lang: count_saved(lang) for lang in TARGETS}
    total_bytes = sum(f.stat().st_size for lang in TARGETS for f in (CORPUS_ROOT / lang).glob("*.pdf"))
    manifest = {
        "corpus_id": f"benchmark-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "total_documents": sum(stats.values()),
        "per_language": stats,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 2),
        "max_pages_per_doc": MAX_PAGES,
        "source": "gutenberg_fast",
    }
    (CORPUS_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    log.info("=== Fast Gutenberg Corpus Builder ===")
    log.info("Target: EN=%d FR=%d ES=%d CA=%d", *TARGETS.values())

    for lang in ["en", "fr", "es", "ca"]:
        target = TARGETS[lang]
        log.info("--- Language: %s (need %d more) ---", lang.upper(), max(0, target - count_saved(lang)))
        for book_id in BOOKS[lang]:
            if count_saved(lang) >= target:
                log.info("%s: reached target %d", lang.upper(), target)
                break
            process_book(lang, book_id, target)
            time.sleep(0.5)  # polite delay

    # Write final manifest
    manifest = write_manifest()
    log.info("=== DONE ===")
    log.info(
        "EN: %d  FR: %d  ES: %d  CA: %d  TOTAL: %d (%.1f MB)",
        manifest["per_language"]["en"],
        manifest["per_language"]["fr"],
        manifest["per_language"]["es"],
        manifest["per_language"]["ca"],
        manifest["total_documents"],
        manifest["total_mb"],
    )


if __name__ == "__main__":
    main()
