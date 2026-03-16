#!/usr/bin/env python3
"""Generate sample PDF fixtures for integration and E2E runs."""

from __future__ import annotations

import sys
from pathlib import Path


DEFAULT_OUTPUT_DIR = "/tmp/aithena-e2e-library"


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 12 Tf", "72 720 Td"]
    first_line, *remaining_lines = lines or [""]
    commands.append(f"({_escape_pdf_text(first_line)}) Tj")
    for line in remaining_lines:
        commands.append(f"0 -18 Td ({_escape_pdf_text(line)}) Tj")
    commands.append("ET")

    stream_body = "\n".join(commands).encode("latin-1")
    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R"
            b" /MediaBox [0 0 612 792]"
            b" /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (
            b"4 0 obj\n<< /Length "
            + str(len(stream_body)).encode()
            + b" >>\nstream\n"
            + stream_body
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    header = b"%PDF-1.4\n"
    body = b""
    offsets: list[int] = []
    offset = len(header)
    for obj in objects:
        offsets.append(offset)
        body += obj
        offset += len(obj)

    xref_offset = len(header) + len(body)
    xref = b"xref\n" + f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for obj_offset in offsets:
        xref += f"{obj_offset:010d} 00000 n \n".encode()

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return header + body + xref + trailer


def _write_doc(output_dir: Path, relative_path: str, lines: list[str]) -> None:
    pdf_path = output_dir / relative_path
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(_build_pdf(lines))
    print(f"Created {pdf_path}")


def main(argv: list[str]) -> int:
    output_dir = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    docs: dict[str, list[str]] = {
        "Ada Lovelace/Ada Lovelace - Analytical Engine Notes (1843).pdf": [
            "Analytical Engine Notes",
            "Sample PDF fixture for aithena integration tests.",
            "Author: Ada Lovelace",
            "Year: 1843",
        ],
        "Miguel de Cervantes/Miguel de Cervantes - Don Quixote Sampler (1605).pdf": [
            "Don Quixote Sampler",
            "This public-domain inspired fixture exercises PDF indexing.",
            "Author: Miguel de Cervantes",
            "Year: 1605",
        ],
        "Project Gutenberg/Project Gutenberg - Library Smoke Test (2024).pdf": [
            "Library Smoke Test",
            "Small generated PDF for CI and GitHub Actions volume checks.",
            "Source: Generated locally by e2e/create-sample-docs.py",
        ],
    }

    for relative_path, lines in docs.items():
        _write_doc(output_dir, relative_path, lines)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
