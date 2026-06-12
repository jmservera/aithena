#!/usr/bin/env python3
"""
Build a multilingual benchmark corpus of small PDFs for Solr benchmarking.

Target: ~1500 documents across EN/FR/ES/CA, each ≤6 pages.
Sources:
  - arXiv (EN): short CS/ML papers
  - HAL (FR): French open-access articles
  - SciELO (ES): Spanish open-access journals
  - RACO (CA): Catalan open-access journals
  - Project Gutenberg fallback: plain-text chunks → PDF via reportlab
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CORPUS_ROOT = Path("/data/documents/benchmark-corpus")
TARGETS = {"en": 400, "fr": 400, "es": 400, "ca": 300}
MAX_PAGES = 6
RATE_LIMIT_DELAY = 1.0  # seconds between requests
ARXIV_RATE_DELAY = 3.0  # arXiv asks for 3s between requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_dirs():
    for lang in TARGETS:
        (CORPUS_ROOT / lang).mkdir(parents=True, exist_ok=True)


def get_pdf_page_count(data: bytes) -> int:
    """Return page count from raw PDF bytes, or -1 on error."""
    try:
        import io

        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(data))
        return len(reader.pages)
    except Exception:
        return -1


def download(url: str, timeout: int = 30) -> bytes | None:
    """Download URL, return bytes or None on failure."""
    try:
        headers = {"User-Agent": "aithena-benchmark-corpus/1.0 (research use)"}
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
        log.debug("Bad response %s for %s", r.status_code, url)
    except Exception as e:
        log.debug("Download failed %s: %s", url, e)
    return None


def save_pdf(lang: str, name: str, data: bytes) -> bool:
    """Validate page count and save PDF. Returns True if saved."""
    pages = get_pdf_page_count(data)
    if pages < 1 or pages > MAX_PAGES:
        log.debug("Skipping %s: %d pages", name, pages)
        return False
    dest = CORPUS_ROOT / lang / name
    dest.write_bytes(data)
    return True


def count_saved(lang: str) -> int:
    return len(list((CORPUS_ROOT / lang).glob("*.pdf")))


# ---------------------------------------------------------------------------
# Source: arXiv (English)
# ---------------------------------------------------------------------------


def fetch_arxiv(target: int) -> int:
    """Fetch short CS/ML arXiv papers (English). Returns count saved."""
    log.info("=== arXiv (EN): target %d ===", target)
    saved = count_saved("en")
    if saved >= target:
        log.info("Already have %d EN docs, skipping arXiv", saved)
        return saved

    try:
        import arxiv
    except ImportError:
        log.warning("arxiv package not installed, skipping arXiv source")
        return saved

    # Search queries likely to return short papers
    queries = [
        "ti:survey cat:cs.CL",
        "ti:analysis cat:cs.IR",
        "ti:note cat:cs.LG",
        "ti:short cat:cs.AI",
        "ti:brief cat:stat.ML",
        "abstract cat:cs.CL",
        "cat:cs.IR",
        "cat:cs.CV comment:pages",
        "cat:cs.LG comment:pages",
        "cat:cs.NE",
        "cat:cs.DB",
        "cat:cs.SE",
    ]

    client = arxiv.Client(page_size=50, delay_seconds=ARXIV_RATE_DELAY, num_retries=3)

    for query in queries:
        if count_saved("en") >= target:
            break
        log.info("arXiv query: %s (have %d/%d)", query, count_saved("en"), target)
        search = arxiv.Search(query=query, max_results=100, sort_by=arxiv.SortCriterion.SubmittedDate)
        try:
            for result in client.results(search):
                if count_saved("en") >= target:
                    break
                # Filter: prefer papers with short page mention
                comment = (result.comment or "").lower()
                pages_match = re.search(r"(\d+)\s*page", comment)
                if pages_match:
                    n = int(pages_match.group(1))
                    if n > MAX_PAGES:
                        continue

                arxiv_id = result.entry_id.split("/")[-1]
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                safe_id = arxiv_id.replace("/", "_").replace(".", "_")
                filename = f"arxiv_{safe_id}.pdf"

                if (CORPUS_ROOT / "en" / filename).exists():
                    continue

                time.sleep(ARXIV_RATE_DELAY)
                data = download(pdf_url)
                if data:
                    if save_pdf("en", filename, data):
                        log.info("EN saved: %s (%d total)", filename, count_saved("en"))
                    else:
                        log.debug("EN skip (pages): %s", filename)
        except Exception as e:
            log.warning("arXiv query failed: %s", e)
            time.sleep(5)

    return count_saved("en")


# ---------------------------------------------------------------------------
# Source: HAL (French)
# ---------------------------------------------------------------------------


def fetch_hal(target: int) -> int:
    """Fetch French articles from HAL open archive."""
    log.info("=== HAL (FR): target %d ===", target)
    saved = count_saved("fr")
    if saved >= target:
        log.info("Already have %d FR docs, skipping HAL", saved)
        return saved

    base_url = "https://api.archives-ouvertes.fr/search/"
    rows = 50
    start = 0

    while count_saved("fr") < target:
        params = {
            "q": "*:*",
            "fq": "language_s:fr AND docType_s:ART AND fileMain_s:*",
            "fl": "halId_s,fileMain_s,title_s",
            "sort": "submittedDate_tdate desc",
            "rows": rows,
            "start": start,
            "wt": "json",
        }
        try:
            resp = requests.get(base_url, params=params, timeout=30,
                                headers={"User-Agent": "aithena-benchmark/1.0"})
            if resp.status_code != 200:
                log.warning("HAL API error %d", resp.status_code)
                break
            data = resp.json()
            docs = data.get("response", {}).get("docs", [])
            if not docs:
                log.info("HAL: no more results at start=%d", start)
                break

            for doc in docs:
                if count_saved("fr") >= target:
                    break
                pdf_url = doc.get("fileMain_s")
                hal_id = doc.get("halId_s", "unknown")
                if not pdf_url or not pdf_url.lower().endswith(".pdf"):
                    # Try constructing PDF URL from hal_id
                    pdf_url = f"https://hal.archives-ouvertes.fr/{hal_id}/document"

                filename = f"hal_{hal_id}.pdf"
                if (CORPUS_ROOT / "fr" / filename).exists():
                    continue

                time.sleep(RATE_LIMIT_DELAY)
                pdf_data = download(pdf_url)
                if pdf_data:
                    if save_pdf("fr", filename, pdf_data):
                        log.info("FR saved: %s (%d total)", filename, count_saved("fr"))
                    else:
                        log.debug("FR skip: %s", filename)

            start += rows
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            log.warning("HAL fetch error: %s", e)
            time.sleep(3)
            break

    return count_saved("fr")


# ---------------------------------------------------------------------------
# Source: SciELO (Spanish)
# ---------------------------------------------------------------------------


def fetch_scielo(target: int) -> int:
    """Fetch Spanish articles from SciELO."""
    log.info("=== SciELO (ES): target %d ===", target)
    saved = count_saved("es")
    if saved >= target:
        log.info("Already have %d ES docs, skipping SciELO", saved)
        return saved

    # SciELO SOLR API — search for Spanish articles
    base_url = "https://search.scielo.org/api/v1/search"
    rows = 50
    start = 1

    while count_saved("es") < target:
        params = {
            "q": "*",
            "lang": "es",
            "format": "json",
            "count": rows,
            "from": start,
            "output_lang": "es",
        }
        try:
            resp = requests.get(base_url, params=params, timeout=30,
                                headers={"User-Agent": "aithena-benchmark/1.0"})
            if resp.status_code != 200:
                log.warning("SciELO API error %d", resp.status_code)
                break
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                log.info("SciELO: no more results at from=%d", start)
                break

            for hit in hits:
                if count_saved("es") >= target:
                    break
                source = hit.get("_source", {})
                pid = source.get("id", "")
                if not pid:
                    continue

                # Build PDF URL from SciELO PID
                # Format: https://www.scielo.br/j/{journal}/a/{id}/?format=pdf
                # Or use the direct link
                links = source.get("links", [])
                pdf_url = None
                for lnk in links:
                    if isinstance(lnk, dict) and lnk.get("lang") == "es" and "pdf" in lnk.get("url", ""):
                        pdf_url = lnk["url"]
                        break
                if not pdf_url:
                    # Try to construct URL
                    clean_pid = pid.replace("/", "_")
                    pdf_url = f"https://www.scielo.org/pdf/{clean_pid}"

                filename = f"scielo_{pid.replace('/', '_').replace('.', '_')}.pdf"
                if (CORPUS_ROOT / "es" / filename).exists():
                    continue

                time.sleep(RATE_LIMIT_DELAY)
                pdf_data = download(pdf_url)
                if pdf_data:
                    if save_pdf("es", filename, pdf_data):
                        log.info("ES saved: %s (%d total)", filename, count_saved("es"))
                    else:
                        log.debug("ES skip: %s", filename)

            start += rows
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            log.warning("SciELO fetch error: %s", e)
            time.sleep(3)
            break

    return count_saved("es")


# ---------------------------------------------------------------------------
# Source: RACO (Catalan)
# ---------------------------------------------------------------------------


def fetch_raco(target: int) -> int:
    """Fetch Catalan articles from RACO (Revistes Catalanes amb Accés Obert)."""
    log.info("=== RACO (CA): target %d ===", target)
    saved = count_saved("ca")
    if saved >= target:
        log.info("Already have %d CA docs, skipping RACO", saved)
        return saved

    base_url = "https://raco.cat/index.php/raco/oai"
    # OAI-PMH endpoint
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "oai_dc",
        "set": "com:11001",  # Catalan language articles
    }

    try:
        resp = requests.get(base_url, params=params, timeout=30,
                            headers={"User-Agent": "aithena-benchmark/1.0"})
        if resp.status_code != 200:
            log.warning("RACO OAI error %d", resp.status_code)
            return saved

        # Parse OAI response for PDF links
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        ns = {
            "oai": "http://www.openarchives.org/OAI/2.0/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        }

        records = root.findall(".//oai:record", ns)
        log.info("RACO: found %d OAI records", len(records))

        for record in records:
            if count_saved("ca") >= target:
                break
            # Find identifier
            identifier = record.find(".//oai:identifier", ns)
            if identifier is None:
                continue
            rec_id = identifier.text or ""

            # Find resource links (PDF)
            metadata = record.find(".//oai_dc:dc", ns)
            if metadata is None:
                continue

            pdf_url = None
            for rel in metadata.findall("dc:relation", ns):
                if rel.text and (".pdf" in rel.text.lower() or "pdf" in rel.text.lower()):
                    pdf_url = rel.text
                    break
            if not pdf_url:
                for ident in metadata.findall("dc:identifier", ns):
                    if ident.text and "raco.cat" in ident.text and "/article/view/" in ident.text:
                        # Try to get PDF version
                        view_url = ident.text
                        article_id = view_url.rstrip("/").split("/")[-1]
                        pdf_url = view_url.replace("/article/view/", "/article/download/").rstrip("/") + "/pdf"
                        break

            if not pdf_url:
                continue

            safe_id = rec_id.replace(":", "_").replace("/", "_").replace(".", "_")
            filename = f"raco_{safe_id}.pdf"
            if (CORPUS_ROOT / "ca" / filename).exists():
                continue

            time.sleep(RATE_LIMIT_DELAY)
            pdf_data = download(pdf_url)
            if pdf_data:
                if save_pdf("ca", filename, pdf_data):
                    log.info("CA saved: %s (%d total)", filename, count_saved("ca"))
                else:
                    log.debug("CA skip: %s", filename)

    except Exception as e:
        log.warning("RACO fetch error: %s", e)

    return count_saved("ca")


# ---------------------------------------------------------------------------
# Fallback: Project Gutenberg → reportlab PDF
# ---------------------------------------------------------------------------


def text_to_pdf(text: str, title: str = "Document") -> bytes | None:
    """Convert text to PDF bytes using reportlab (max 6 pages)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from reportlab.platypus.flowables import PageBreak

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

        # Title
        story.append(Paragraph(title[:80], styles["Title"]))
        story.append(Spacer(1, 0.5 * cm))

        # Body — split into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            clean = para.replace("\n", " ").strip()
            if clean:
                story.append(Paragraph(clean, styles["Normal"]))
                story.append(Spacer(1, 0.3 * cm))

        doc.build(story)
        return buf.getvalue()
    except Exception as e:
        log.debug("reportlab error: %s", e)
        return None


def fetch_gutenberg_text(lang_code: str, book_id: int) -> tuple[str, str] | tuple[None, None]:
    """Download a Gutenberg plain text file. Returns (title, text) or (None, None)."""
    # Try UTF-8 first, then ISO-8859-1
    for suffix in ["-0.txt", ".txt", "-8.txt"]:
        url = f"https://www.gutenberg.org/files/{book_id}/{book_id}{suffix}"
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "aithena-benchmark/1.0"})
            if resp.status_code == 200 and len(resp.content) > 5000:
                text = resp.content.decode("utf-8", errors="replace")
                # Extract title from header
                title_match = re.search(r"Title:\s*(.+)", text)
                title = title_match.group(1).strip() if title_match else f"Gutenberg {book_id}"
                # Strip Gutenberg header/footer
                start = text.find("*** START OF")
                end = text.find("*** END OF")
                if start != -1:
                    text = text[start + 50 :]
                if end != -1:
                    text = text[:end]
                return title, text
        except Exception:
            pass
    return None, None


def chunk_text(text: str, words_per_chunk: int = 2000) -> list[str]:
    """Split text into chunks of ~N words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunk = " ".join(words[i : i + words_per_chunk])
        chunks.append(chunk)
    return chunks


# Gutenberg book IDs by language — short/medium texts, public domain
GUTENBERG_BOOKS = {
    "en": [
        11, 84, 1342, 1661, 2701, 74, 76, 98, 1400, 2600,
        345, 4300, 174, 1080, 2554, 5200, 2591, 16328, 46,
        1232, 7370, 25344, 7178, 2148, 3207, 1952, 2097,
        1260, 1184, 219, 30, 1998, 203, 768, 1399,
    ],
    "fr": [
        13951, 17489, 4650, 14779, 5097, 3748, 14286, 17834,
        13846, 15621, 17235, 3160, 17154, 16816, 5765, 3074,
        4122, 7105, 2982, 16652, 14523, 13846, 7942, 18585,
        17302, 14672, 10133, 5765, 14286, 7399,
    ],
    "es": [
        2000, 2033, 2199, 15130, 14765, 14981, 15083, 15136,
        14232, 14441, 14459, 14588, 14613, 14678, 14717, 14741,
        14783, 14793, 14801, 14888, 14915, 14934, 15010, 15016,
        15064, 15078, 15095, 15105, 15117, 15133,
    ],
    "ca": [
        # Catalan books are rarer on Gutenberg; use a mix
        11561, 14467, 43363, 43364, 43365, 43366, 43367,
        43368, 43369, 43370, 28371, 28372, 28373, 28374,
    ],
}


def fetch_gutenberg_fallback(lang: str, target: int) -> int:
    """Generate PDFs from Project Gutenberg texts for a given language."""
    log.info("=== Gutenberg fallback (%s): target %d ===", lang, target)
    saved = count_saved(lang)
    if saved >= target:
        return saved

    book_ids = GUTENBERG_BOOKS.get(lang, [])
    if not book_ids:
        return saved

    for book_id in book_ids:
        if count_saved(lang) >= target:
            break
        log.info("%s: Gutenberg book %d (have %d/%d)", lang.upper(), book_id, count_saved(lang), target)
        time.sleep(RATE_LIMIT_DELAY)
        title, text = fetch_gutenberg_text(lang, book_id)
        if not text:
            log.debug("Could not fetch Gutenberg book %d", book_id)
            continue

        chunks = chunk_text(text, words_per_chunk=2000)
        log.info("  Book '%s': %d chunks", title[:50], len(chunks))

        for i, chunk in enumerate(chunks):
            if count_saved(lang) >= target:
                break
            chunk_title = f"{title} (part {i + 1})"
            pdf_data = text_to_pdf(chunk, title=chunk_title)
            if pdf_data:
                # Verify page count
                pages = get_pdf_page_count(pdf_data)
                if 1 <= pages <= MAX_PAGES:
                    filename = f"gutenberg_{book_id}_part{i:03d}.pdf"
                    if not (CORPUS_ROOT / lang / filename).exists():
                        (CORPUS_ROOT / lang / filename).write_bytes(pdf_data)
                        log.info("%s saved: %s (%d pages, %d total)",
                                 lang.upper(), filename, pages, count_saved(lang))
                else:
                    log.debug("Chunk %d has %d pages, skipping", i, pages)

    return count_saved(lang)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def write_manifest(stats: dict):
    manifest = {
        "corpus_id": f"benchmark-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "total_documents": sum(stats.values()),
        "per_language": stats,
        "total_bytes": sum(
            f.stat().st_size
            for lang in TARGETS
            for f in (CORPUS_ROOT / lang).glob("*.pdf")
        ),
        "max_pages_per_doc": MAX_PAGES,
        "sources": ["arxiv", "hal", "scielo", "raco", "gutenberg"],
    }
    manifest_path = CORPUS_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.info("Manifest written: %s", manifest_path)
    return manifest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    log.info("Building benchmark corpus at %s", CORPUS_ROOT)
    ensure_dirs()

    # Install dependencies if missing
    try:
        import PyPDF2
    except ImportError:
        log.info("Installing PyPDF2...")
        os.system(f"{sys.executable} -m pip install PyPDF2 --quiet")
        import PyPDF2

    try:
        import reportlab
    except ImportError:
        log.info("Installing reportlab...")
        os.system(f"{sys.executable} -m pip install reportlab --quiet")

    try:
        import arxiv
    except ImportError:
        log.info("Installing arxiv...")
        os.system(f"{sys.executable} -m pip install arxiv --quiet")

    # Phase 1: Real PDF sources
    fetch_arxiv(TARGETS["en"])
    fetch_hal(TARGETS["fr"])
    fetch_scielo(TARGETS["es"])
    fetch_raco(TARGETS["ca"])

    # Phase 2: Gutenberg fallback for any language under target
    for lang, target in TARGETS.items():
        current = count_saved(lang)
        if current < target:
            log.info("%s: have %d/%d, using Gutenberg fallback", lang.upper(), current, target)
            fetch_gutenberg_fallback(lang, target)

    # Final stats
    stats = {lang: count_saved(lang) for lang in TARGETS}
    total = sum(stats.values())
    log.info("=" * 60)
    log.info("CORPUS BUILD COMPLETE")
    log.info("  EN: %d  FR: %d  ES: %d  CA: %d", stats["en"], stats["fr"], stats["es"], stats["ca"])
    log.info("  TOTAL: %d documents", total)

    manifest = write_manifest(stats)
    size_mb = manifest["total_bytes"] / (1024 * 1024)
    log.info("  SIZE: %.1f MB", size_mb)
    log.info("=" * 60)

    return stats


if __name__ == "__main__":
    main()
