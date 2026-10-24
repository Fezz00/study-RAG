"""Tests for describing slide images (issue #2), with a fake vision model instead of a real one."""

from pathlib import Path

import pymupdf

from app.ingest.parse_pdf import parse_pdf

HEADER = ["My Course 2025", "Lecture 3"]
IMAGE = "image"  # marker: put a small picture on this page


def make_pdf(path: Path, pages: list[list[str]]) -> Path:
    """Write a PDF; a page whose lines include IMAGE also gets a small red picture."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        for i, line in enumerate(line for line in lines if line != IMAGE):
            page.insert_text((72, 72 + 20 * i), line)
        if IMAGE in lines:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
            pixmap.set_rect(pixmap.irect, (255, 0, 0))
            page.insert_image(pymupdf.Rect(100, 300, 200, 400), pixmap=pixmap)
    doc.save(path)
    return path


PAGES = [
    HEADER + ["Intro to CNNs"],
    HEADER + [IMAGE],  # only a picture (after the header is removed)
    HEADER + ["Pooling", IMAGE],  # text and a picture
    HEADER + ["Stride"],
    HEADER + ["Padding"],
    HEADER + ["Summary"],
]


class FakeVisionModel:
    """Stands in for the vision model and remembers how often it was asked."""

    def __init__(self):
        self.calls = 0

    def __call__(self, png: bytes) -> str:
        assert png.startswith(b"\x89PNG")  # it really gets a PNG image of the slide
        self.calls += 1
        return "A 4x4 grid is reduced to 2x2 by max pooling."


def test_without_vision_model_image_only_slides_are_skipped(tmp_path):
    chunks = parse_pdf(make_pdf(tmp_path / "lecture_3.pdf", PAGES))
    assert [c["slide"] for c in chunks] == [1, 3, 4, 5, 6]
    assert all("[Figure]" not in c["text"] for c in chunks)


def test_vision_model_describes_slides_with_images(tmp_path):
    vision = FakeVisionModel()
    chunks = parse_pdf(make_pdf(tmp_path / "lecture_3.pdf", PAGES), describe=vision)
    by_slide = {c["slide"]: c["text"] for c in chunks}

    assert sorted(by_slide) == [1, 2, 3, 4, 5, 6]  # the image-only slide 2 is kept now
    assert by_slide[2] == "[Figure] A 4x4 grid is reduced to 2x2 by max pooling."
    assert by_slide[3] == "Pooling\n[Figure] A 4x4 grid is reduced to 2x2 by max pooling."
    assert "[Figure]" not in by_slide[1]  # slides without pictures are left alone
    assert vision.calls == 2  # only slides with pictures are sent to the (slow) model


def test_skipped_slides_are_not_described(tmp_path):
    pages = [HEADER + ["Stride", IMAGE], HEADER + ["Stride", "Output: 3x3"]] + PAGES[3:] + [HEADER + ["End"]]
    vision = FakeVisionModel()
    chunks = parse_pdf(make_pdf(tmp_path / "lecture_3.pdf", pages), describe=vision)

    assert 1 not in [c["slide"] for c in chunks]  # slide 1 is a build of slide 2
    assert vision.calls == 0  # so its picture was never sent to the model
