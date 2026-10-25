"""Tests for quiz mode, with a fake chat model instead of a real one."""

import random

from fastapi.testclient import TestClient

from app.api import main
from app.rag import quiz
from app.rag.quiz import CHECK_PROMPT, MIN_CHARS, PROMPT, make_question, make_quiz

SLIDE = {"slide_id": "L05-s124", "lecture": "Lecture 5", "slide": 124, "text": "Pooling layer. Number of parameters: 0"}
GOOD = {
    "question": "How many parameters does a pooling layer have?",
    "options": ["0", "2", "F * F", "One per channel"],
    "answer": 0,
    "explanation": "The slide says: Number of parameters: 0.",
}


class FakeChatModel:
    """Writes the given question; as checker it picks the right option (honest) or the first wrong one."""

    def __init__(self, question=GOOD, honest_checker=True):
        self.question, self.honest_checker, self.calls = question, honest_checker, []

    def __call__(self, system: str, user: str, shape) -> dict:
        self.calls.append(system)
        if system == PROMPT:
            return self.question
        assert system == CHECK_PROMPT
        assert "answer" not in user.lower()  # the checker never sees the answer key
        options = [line.split(". ", 1)[1] for line in user.splitlines() if line[:3] in ("0. ", "1. ", "2. ", "3. ")]
        right = options.index("0")
        return {"answer": right if self.honest_checker else (right + 1) % 4}


def test_checked_question_points_to_the_right_option():
    question = make_question(SLIDE, FakeChatModel(), random.Random(1))
    assert question["options"][question["answer"]] == "0"
    assert question["slide_id"] == "L05-s124"
    assert sorted(question["options"]) == sorted(GOOD["options"])


def test_options_are_shuffled():
    positions = {make_question(SLIDE, FakeChatModel(), random.Random(seed))["answer"] for seed in range(20)}
    assert len(positions) > 1  # the model always puts the right answer first, the quiz doesn't


def test_question_is_dropped_when_the_self_check_disagrees():
    assert make_question(SLIDE, FakeChatModel(honest_checker=False), random.Random(1)) is None


def test_unusable_questions_are_dropped_before_the_check():
    for broken in (
        {**GOOD, "options": ["0", "2", "4"]},  # only 3 options
        {**GOOD, "options": ["0", "2", "2", "4"]},  # the same option twice
        {**GOOD, "answer": 7},  # no such option
        {**GOOD, "question": " "},  # no question
    ):
        llm = FakeChatModel(question=broken)
        assert make_question(SLIDE, llm, random.Random(1)) is None
        assert CHECK_PROMPT not in llm.calls  # no wasted second call


def test_candidate_slides(monkeypatch):
    long, short = "x" * MIN_CHARS, "Title only"
    slides = [{"slide_id": f"L05-s{n}", "lecture": "Lecture 5", "text": text} for n, text in enumerate([long, short])]
    monkeypatch.setattr(quiz, "lecture_slides", lambda number: slides)
    monkeypatch.setattr(
        quiz,
        "retrieve",
        lambda topic, top_k: [
            {"slide_id": "L05-s1", "lecture": "Lecture 5", "text": long, "score": 0.7},
            {"slide_id": "L05-s2", "lecture": "Lecture 5", "text": long, "score": 0.3},  # unrelated to the topic
            {"slide_id": "L06-s1", "lecture": "Lecture 6", "text": long, "score": 0.8},  # other lecture
        ],
    )

    assert [s["slide_id"] for s in quiz.candidate_slides(5)] == ["L05-s0"]  # too-short slide skipped
    assert [s["slide_id"] for s in quiz.candidate_slides(5, topic="pooling")] == ["L05-s1"]


def test_quiz_stops_at_count_and_does_not_retry_forever(monkeypatch):
    slides = [{**SLIDE, "slide_id": f"L05-s{n}"} for n in range(30)]
    monkeypatch.setattr(quiz, "candidate_slides", lambda number, topic: list(slides))

    assert len(make_quiz(5, count=3, llm=FakeChatModel(), seed=0)) == 3

    always_wrong = FakeChatModel(honest_checker=False)
    assert make_quiz(5, count=3, llm=always_wrong, seed=0) == []
    assert always_wrong.calls.count(PROMPT) == 9  # at most 3x count slides are tried


client = TestClient(main.app)


def test_api_quiz(monkeypatch):
    question = {**GOOD, "slide_id": "L05-s124"}
    monkeypatch.setattr(main, "make_quiz", lambda number, count, topic: [question])

    response = client.post("/quiz", json={"lecture": 5, "topic": "pooling"})
    assert response.status_code == 200
    assert response.json() == {"lecture": "Lecture 5", "questions": [question]}


def test_api_quiz_without_slides_is_404(monkeypatch):
    monkeypatch.setattr(main, "make_quiz", lambda number, count, topic: [])
    response = client.post("/quiz", json={"lecture": 5, "topic": "cooking"})
    assert response.status_code == 404
    assert "cooking" in response.json()["detail"]


def test_api_quiz_limits_the_number_of_questions():
    assert client.post("/quiz", json={"lecture": 5, "count": 50}).status_code == 422
