"""Tests for the lecture overview (map-reduce summary), with a fake chat model instead of a real one."""

from fastapi.testclient import TestClient

from app.api import main
from app.rag import overview
from app.rag.overview import BATCH_SIZE, MAP_PROMPT, summarize


def make_slides(count: int) -> list[dict]:
    return [
        {"slide_id": f"L05-s{n}", "lecture": "Lecture 5", "slide": n, "text": f"Slide {n} text"}
        for n in range(1, count + 1)
    ]


class FakeChatModel:
    """Answers like the real model would, and remembers every prompt it got."""

    def __init__(self):
        self.calls = []

    def __call__(self, system: str, user: str) -> dict:
        self.calls.append(system)
        if system == MAP_PROMPT:
            # One topic per batch, citing the first slide of the batch and one made-up ID.
            first = user.split("[")[1].split("]")[0]
            return {"topics": [{"title": f"Part from {first}", "summary": "...", "slides": [first, "L05-s999"]}]}
        # Reduce: merge everything into two topics, listed in the wrong order on purpose.
        return {
            "topics": [
                {"title": "Pooling", "summary": "...", "slides": ["L05-s16"]},
                {"title": "Convolution", "summary": "...", "slides": ["L05-s1", "L05-s1"]},
                {"title": "Invented", "summary": "...", "slides": ["L09-s1"]},
            ]
        }


def test_one_batch_needs_no_merge_step():
    llm = FakeChatModel()
    topics = summarize(make_slides(BATCH_SIZE), llm=llm)

    assert llm.calls == [MAP_PROMPT]
    assert topics == [{"title": "Part from L05-s1", "summary": "...", "slides": ["L05-s1"]}]  # L05-s999 removed


def test_many_slides_are_summarized_in_batches_then_merged():
    llm = FakeChatModel()
    topics = summarize(make_slides(2 * BATCH_SIZE + 1), llm=llm)  # 3 batches

    assert llm.calls.count(MAP_PROMPT) == 3
    assert len(llm.calls) == 4  # plus one merge step
    assert [t["title"] for t in topics] == ["Convolution", "Pooling"]  # lecture order; "Invented" dropped
    assert topics[0]["slides"] == ["L05-s1"]  # duplicate ID removed


def test_overview_is_saved_and_reused(tmp_path, monkeypatch):
    llm = FakeChatModel()
    monkeypatch.setattr(overview, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(overview, "lecture_slides", lambda number: make_slides(3))
    monkeypatch.setattr(overview, "chat_json", llm)

    first = overview.get_overview(5)
    second = overview.get_overview(5)

    assert first == second == {"lecture": "Lecture 5", "slides": 3, "topics": first["topics"]}
    assert (tmp_path / "overviews" / "L05.json").exists()
    assert len(llm.calls) == 1  # the second call read the file instead of asking the model

    overview.get_overview(5, refresh=True)
    assert len(llm.calls) == 2


def test_lecture_that_is_not_indexed_has_no_overview(tmp_path, monkeypatch):
    monkeypatch.setattr(overview, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(overview, "lecture_slides", lambda number: [])
    assert overview.get_overview(7) is None


client = TestClient(main.app)


def test_api_overview(monkeypatch):
    topics = [{"title": "Pooling", "summary": "Max pooling keeps the largest value.", "slides": ["L05-s102"]}]
    monkeypatch.setattr(
        main, "get_overview", lambda number, refresh: {"lecture": "Lecture 5", "slides": 101, "topics": topics}
    )

    response = client.get("/lectures/5/overview")
    assert response.status_code == 200
    assert response.json()["topics"] == topics


def test_api_overview_of_unknown_lecture_is_404(monkeypatch):
    monkeypatch.setattr(main, "get_overview", lambda number, refresh: None)
    assert client.get("/lectures/7/overview").status_code == 404


def test_api_lists_lectures(monkeypatch):
    monkeypatch.setattr(main, "list_lectures", lambda: [{"number": 5, "lecture": "Lecture 5", "slides": 101}])
    assert client.get("/lectures").json() == [{"number": 5, "lecture": "Lecture 5", "slides": 101}]
