"""Tests for PDF parsing: file names, header removal and build detection.

The PDFs are generated on the fly, so no lecture material is needed.
"""

from pathlib import Path

import pymupdf
import pytest

from app.ingest.parse_pdf import boilerplate_lines, is_build_of, lecture_number_from_filename, parse_pdf

HEADER = ["My Course 2025", "Lecture 3"]


def make_pdf(path: Path, pages: list[list[str]]) -> Path:
    """Write a PDF where each page contains the given lines."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        for i, line in enumerate(lines):
            page.insert_text((72, 72 + 20 * i), line)
    doc.save(path)
    return path


# --- lecture_number_from_filename -------------------------------------------


@pytest.mark.parametrize(
    "filename, expected",
    [("lecture04.pdf", 4), ("lecture_5.pdf", 5), ("L12-cnn.pdf", 12)],
)
def test_lecture_number_from_filename(filename, expected):
    assert lecture_number_from_filename(Path(filename)) == expected


def test_lecture_number_missing_raises():
    with pytest.raises(ValueError):
        lecture_number_from_filename(Path("intro.pdf"))


# --- boilerplate_lines --------------------------------------------------------


def test_boilerplate_finds_lines_on_most_slides():
    slides = [HEADER + [f"content {i}"] for i in range(6)]
    assert boilerplate_lines(slides) == set(HEADER)


def test_boilerplate_keeps_lines_on_few_slides():
    slides = [HEADER + ["Pooling"], HEADER + ["Pooling"]] + [HEADER + [f"other {i}"] for i in range(4)]
    assert "Pooling" not in boilerplate_lines(slides)


def test_boilerplate_needs_enough_slides():
    # With only 2 slides, "on most slides" means nothing.
    assert boilerplate_lines([HEADER, HEADER]) == set()


# --- is_build_of --------------------------------------------------------------


def test_build_is_detected():
    assert is_build_of(["Stride", "Input: 7x7"], ["Stride", "Input: 7x7", "Output: 3x3"])


def test_different_slides_are_not_builds():
    assert not is_build_of(["Pooling", "max"], ["Stride", "Input: 7x7"])


def test_empty_slide_is_not_a_build():
    assert not is_build_of([], ["anything"])


# --- parse_pdf (end to end on a generated PDF) -------------------------------


def test_parse_pdf_removes_header_and_builds(tmp_path):
    pages = [
        HEADER + ["Intro to CNNs"],
        HEADER + ["Stride", "Input: 7x7"],  # build of the next slide -> skipped
        HEADER + ["Stride", "Input: 7x7", "Output: 3x3"],
        HEADER + ["Pooling", "No learnable parameters"],
        HEADER + ["Intro to CNNs"],  # exact repeat of slide 1 -> skipped
        HEADER + ["Summary"],
    ]
    chunks = parse_pdf(make_pdf(tmp_path / "lecture_3.pdf", pages))

    assert [c["id"] for c in chunks] == ["L03-s1", "L03-s3", "L03-s4", "L03-s6"]
    assert all("My Course 2025" not in c["text"] for c in chunks)
    assert chunks[1] == {
        "id": "L03-s3",
        "lecture": "Lecture 3",
        "slide": 3,
        "text": "Stride\nInput: 7x7\nOutput: 3x3",
    }
