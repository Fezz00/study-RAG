"""Parse a lecture PDF into one chunk per slide.

Each chunk keeps the lecture name and slide number so that answers
can later cite e.g. "Lecture 4, slide 12".

Usage:
    python -m app.ingest.parse_pdf data/lecture04.pdf
"""

import re
import sys
from pathlib import Path

import pymupdf


def lecture_number_from_filename(pdf_path: Path) -> int:
    """Take the first number in the file name, e.g. 'lecture04.pdf' -> 4."""
    match = re.search(r"\d+", pdf_path.stem)
    if match is None:
        raise ValueError(
            f"No lecture number in file name '{pdf_path.name}'. "
            "Rename it like 'lecture04.pdf' or pass lecture_number."
        )
    return int(match.group())


def parse_pdf(pdf_path: str | Path, lecture_number: int | None = None) -> list[dict]:
    """Return one chunk per slide (page) of the PDF.

    Slides without any text (e.g. only an image) are skipped.
    """
    pdf_path = Path(pdf_path)
    if lecture_number is None:
        lecture_number = lecture_number_from_filename(pdf_path)

    chunks = []
    with pymupdf.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text().strip()
            if not text:
                continue

            slide_number = page_index + 1  # pages are 0-based, slides start at 1
            chunks.append(
                {
                    "id": f"L{lecture_number:02d}-s{slide_number}",
                    "lecture": f"Lecture {lecture_number}",
                    "slide": slide_number,
                    "text": text,
                }
            )
    return chunks


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.ingest.parse_pdf <path-to-pdf>")
        sys.exit(1)

    chunks = parse_pdf(sys.argv[1])
    print(f"Parsed {len(chunks)} slides with text\n")
    for chunk in chunks[:3]:
        print(f"--- {chunk['id']} ({chunk['lecture']}, slide {chunk['slide']}) ---")
        print(chunk["text"][:300])
        print()
