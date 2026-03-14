from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

YEAR_PATTERN = re.compile(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)")
AUTHOR_TITLE_YEAR_PATTERN = re.compile(r"^(?P<author>.+?)\s+-\s+(?P<title>.+?)\s+\((?P<year>1[5-9]\d{2}|20\d{2})\)$")
AUTHOR_TITLE_PATTERN = re.compile(r"^(?P<author>.+?)\s+-\s+(?P<title>.+)$")
YEAR_RANGE_PATTERN = re.compile(r"(?P<start>1[5-9]\d{2}|20\d{2})\s*-\s*(?P<end>1[5-9]\d{2}|20\d{2})")


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    collapsed = re.sub(r"[^a-z0-9]+", " ", ascii_text.lower())
    return re.sub(r"\s+", " ", collapsed).strip()


def clean_text(text: str) -> str:
    cleaned = re.sub(r"[_]+", " ", text).strip()
    return re.sub(r"\s+", " ", cleaned)


def display_segment(segment: str) -> str:
    cleaned = clean_text(segment)
    if cleaned.islower():
        return " ".join(word.capitalize() for word in cleaned.split())
    return cleaned


def display_category_segment(segment: str) -> str:
    if segment.islower() and segment.isalpha() and len(segment) <= 4:
        return segment.upper()
    return display_segment(segment)


def extract_year(text: str) -> int | None:
    if YEAR_RANGE_PATTERN.search(text):
        return None
    match = YEAR_PATTERN.search(text)
    return int(match.group(1)) if match else None


def strip_author_from_title(title: str, author: str | None) -> str:
    if not author:
        return title.strip()

    normalized_author = normalize(author)
    normalized_title = normalize(title)
    if not normalized_author or normalized_author == normalized_title:
        return clean_text(title)

    author_tokens = normalized_author.split()
    title_tokens = normalized_title.split()
    if title_tokens[-len(author_tokens) :] == author_tokens:
        raw_tokens = clean_text(title).split()
        return " ".join(raw_tokens[: -len(author_tokens)]).strip(" -") or clean_text(title)
    if title_tokens[: len(author_tokens)] == author_tokens:
        raw_tokens = clean_text(title).split()
        return " ".join(raw_tokens[len(author_tokens) :]).strip(" -") or clean_text(title)
    return clean_text(title)


def looks_like_category(folder_name: str, stem: str) -> bool:
    normalized_folder = normalize(folder_name)
    if not normalized_folder:
        return False
    normalized_stem = normalize(stem)

    if YEAR_RANGE_PATTERN.search(stem):
        return True
    if (stem.isupper() or "_" in stem) and normalized_folder in normalized_stem:
        return True
    return normalized_folder.endswith("ics") and normalized_folder in normalized_stem


def is_year_fragment(text: str) -> bool:
    candidate = clean_text(text)
    return bool(
        re.fullmatch(
            r"(1[5-9]\d{2}|20\d{2})(\s*-\s*(1[5-9]\d{2}|20\d{2}))?",
            candidate,
        )
    )


def extract_metadata(file_path: str, base_path: str = "/data/documents/") -> dict[str, Any]:
    path = Path(file_path)
    base = Path(base_path)

    try:
        relative_path = path.relative_to(base)
    except ValueError:
        try:
            relative_path = path.resolve(strict=False).relative_to(base.resolve(strict=False))
        except ValueError:
            relative_path = Path(path.name)

    stem = path.stem
    fallback_title = stem.strip()
    folder_parts = relative_path.parent.parts if relative_path.parent != Path(".") else ()

    title = fallback_title
    author: str | None = None
    year = None
    category: str | None = None

    author_title_year = AUTHOR_TITLE_YEAR_PATTERN.match(stem)
    author_title = AUTHOR_TITLE_PATTERN.match(stem)

    if author_title_year:
        author = clean_text(author_title_year.group("author"))
        title = clean_text(author_title_year.group("title"))
        year = int(author_title_year.group("year"))
    elif author_title and not is_year_fragment(author_title.group("title")):
        author = clean_text(author_title.group("author"))
        title = clean_text(author_title.group("title"))
        year = extract_year(title)
    else:
        year = extract_year(stem)

    if len(folder_parts) == 2:
        category = display_category_segment(folder_parts[0])
        author = author or display_segment(folder_parts[1])
    elif len(folder_parts) > 2:
        category = display_category_segment(folder_parts[0])
    elif len(folder_parts) == 1:
        folder_name = folder_parts[0]
        if author:
            category = display_category_segment(folder_name)
        elif looks_like_category(folder_name, stem):
            category = display_category_segment(folder_name)
            title = clean_text(stem)
        else:
            author = display_segment(folder_name)

    title = strip_author_from_title(title, author)

    if not author:
        author = "Unknown"

    file_size = path.stat().st_size if path.exists() else 0
    folder_path = "" if relative_path.parent == Path(".") else relative_path.parent.as_posix()

    return {
        "title": title or fallback_title,
        "author": author,
        "year": year,
        "category": category,
        "file_path": relative_path.as_posix(),
        "folder_path": folder_path,
        "file_size": file_size,
    }
