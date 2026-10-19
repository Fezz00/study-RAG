"""Tests for the RAG logic that doesn't need Ollama or Qdrant."""

from app.ingest.index import point_id
from app.rag.ask import validate_citations
from app.rag.generate import format_sources

SLIDES = [
    {"slide_id": "L05-s102", "lecture": "Lecture 5", "slide": 102, "text": "Max pooling ..."},
    {"slide_id": "L05-s103", "lecture": "Lecture 5", "slide": 103, "text": "Pooling summary ..."},
]


# --- validate_citations ---------------------------------------------------------


def test_valid_citations_are_kept():
    answer, cited = validate_citations("Max pooling takes the maximum [L05-s102].", SLIDES)
    assert answer == "Max pooling takes the maximum [L05-s102]."
    assert [s["slide_id"] for s in cited] == ["L05-s102"]


def test_invented_citations_are_removed():
    answer, cited = validate_citations("Pooling has no parameters [L05-s999] [L05-s103].", SLIDES)
    assert "[L05-s999]" not in answer
    assert "[L05-s103]" in answer
    assert [s["slide_id"] for s in cited] == ["L05-s103"]


def test_repeated_citation_is_listed_once():
    _, cited = validate_citations("A [L05-s102]. B [L05-s102].", SLIDES)
    assert [s["slide_id"] for s in cited] == ["L05-s102"]


def test_no_citations():
    _, cited = validate_citations("An answer without any source.", SLIDES)
    assert cited == []


def test_other_brackets_are_untouched():
    answer, _ = validate_citations("A [3x3] filter [L05-s102].", SLIDES)
    assert "[3x3]" in answer


# --- point_id ---------------------------------------------------------------------


def test_point_id_is_stable():
    # Same slide -> same ID, so re-indexing overwrites instead of duplicating.
    assert point_id("L05-s12") == point_id("L05-s12")


def test_point_id_differs_per_slide():
    assert point_id("L05-s12") != point_id("L05-s13")


# --- format_sources ---------------------------------------------------------------


def test_format_sources_labels_every_slide():
    text = format_sources(SLIDES)
    assert "[L05-s102]\nMax pooling ..." in text
    assert "[L05-s103]\nPooling summary ..." in text
