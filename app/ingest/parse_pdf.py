"""Parse a lecture PDF into one chunk per slide.

Each chunk keeps the lecture name and slide number so that answers
can later cite e.g. "Lecture 4, slide 12".

Two clean-up steps make retrieval better:
- Header/footer lines that repeat on most slides (course name, date) are removed.
- Progressive "build" slides (the same slide shown again with one more line) are
  skipped, so only the most complete version is indexed.

Usage:
    python -m app.ingest.parse_pdf data/lecture04.pdf
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

# A line that appears on more than this share of slides is a header or footer.
BOILERPLATE_SHARE = 0.5
# Below this many slides we can't tell headers from real content.
MIN_SLIDES_FOR_BOILERPLATE = 5
# A slide whose lines are (almost) all on the next slide is an earlier build of it.
BUILD_OVERLAP = 0.9


def lecture_number_from_filename(pdf_path: Path) -> int:
    """Take the first number in the file name, e.g. 'lecture04.pdf' -> 4."""
    match = re.search(r"\d+", pdf_path.stem)
    if match is None:
        raise ValueError(
            f"No lecture number in file name '{pdf_path.name}'. "
            "Rename it like 'lecture04.pdf' or pass lecture_number."
        )
    return int(match.group())


def boilerplate_lines(slides: list[list[str]]) -> set[str]:
    """Lines that appear on more than half of the slides, e.g. the course name."""
    if len(slides) < MIN_SLIDES_FOR_BOILERPLATE:
        return set()
    counts = Counter(line for lines in slides for line in set(lines))
    return {line for line, n in counts.items() if n > BOILERPLATE_SHARE * len(slides)}


def is_build_of(lines: list[str], next_lines: list[str]) -> bool:
    """True if (almost) every line of this slide also appears on the next slide."""
    if not lines:
        return False
    next_set = set(next_lines)
    return sum(line in next_set for line in lines) / len(lines) >= BUILD_OVERLAP


def parse_pdf(pdf_path: str | Path, lecture_number: int | None = None) -> list[dict]:
    """Return one chunk per slide (page) of the PDF.

    Slides without text after clean-up, earlier builds of the next slide and exact
    repeats of an earlier slide are skipped.
    """
    pdf_path = Path(pdf_path)
    if lecture_number is None:
        lecture_number = lecture_number_from_filename(pdf_path)

    with pymupdf.open(pdf_path) as doc:
        raw = [[line.strip() for line in page.get_text().splitlines() if line.strip()] for page in doc]

    boilerplate = boilerplate_lines(raw)
    slides = []
    for page_index, lines in enumerate(raw):
        slide_number = page_index + 1  # pages are 0-based, slides start at 1
        # Drop the header/footer and the printed slide number.
        slides.append([line for line in lines if line not in boilerplate and line != str(slide_number)])

    chunks = []
    seen_texts = set()
    for page_index, lines in enumerate(slides):
        text = "\n".join(lines)
        next_lines = slides[page_index + 1] if page_index + 1 < len(slides) else []
        if not text or text in seen_texts or is_build_of(lines, next_lines):
            continue
        seen_texts.add(text)

        slide_number = page_index + 1
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
