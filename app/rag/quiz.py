"""Quiz mode: multiple-choice questions generated from the lecture slides.

Every question comes from exactly one slide, so it can always show where the answer is.
The model writes each question in a fixed JSON shape; the code then checks it and shuffles
the options (small models like to put the right answer first).

Small models sometimes mark a wrong option as correct, so every question is self-checked:
a second call gets the slide, the question and the shuffled options - but not the answer -
and must pick the answer itself. Only questions where both calls agree are kept.
Grading needs no model: the correct option is known, so the UI just compares.

Usage:
    python -m app.rag.quiz 5
    python -m app.rag.quiz 5 "pooling"
"""

import json
import random
import sys
import time
from collections.abc import Callable

import ollama
from pydantic import BaseModel, Field, ValidationError

from app.config import CHAT_MODEL, MIN_SCORE, OLLAMA_URL
from app.metrics import LLM_SECONDS
from app.rag.retrieve import lecture_slides, retrieve

_client = ollama.Client(host=OLLAMA_URL)

# Slides with less text (titles, pictures without a description) make poor questions.
MIN_CHARS = 200
# How many slides close to a topic are considered for a topic quiz.
TOPIC_SLIDES = 15

PROMPT = """You write exam questions for university students from ONE lecture slide.
Write one multiple-choice question that can be answered from the slide alone.
Give exactly 4 short options: one correct, three plausible but clearly wrong.
"answer" is the index (0-3) of the correct option. The explanation says in one sentence
why it is correct, using only the slide. Don't ask about dates, course organisation or layout."""

CHECK_PROMPT = """You get a lecture slide and a multiple-choice question about it.
Using ONLY the slide, give the index (0-3) of the correct option."""


class QuizQuestion(BaseModel):
    """The JSON shape the chat model must answer in."""

    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    answer: int = Field(ge=0, le=3)
    explanation: str


class CheckAnswer(BaseModel):
    answer: int = Field(ge=0, le=3)


def chat_json(system: str, user: str, shape: type[BaseModel]) -> dict:
    """Ask the chat model; the reply is forced into the JSON shape of the given model."""
    start = time.perf_counter()
    response = _client.chat(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format=shape.model_json_schema(),
        think=False,
    )
    LLM_SECONDS.observe(time.perf_counter() - start)
    return json.loads(response.message.content)


def candidate_slides(number: int, topic: str | None = None) -> list[dict]:
    """Slides with enough text: the whole lecture, or only the slides close to a topic."""
    if topic:
        # Same guardrail as /ask: slides below MIN_SCORE are unrelated to the topic.
        slides = [
            s
            for s in retrieve(topic, top_k=TOPIC_SLIDES)
            if s["lecture"] == f"Lecture {number}" and s["score"] >= MIN_SCORE
        ]
    else:
        slides = lecture_slides(number)
    return [slide for slide in slides if len(slide["text"]) >= MIN_CHARS]


def make_question(slide: dict, llm: Callable[..., dict], rng: random.Random) -> dict | None:
    """One checked question about the slide, or None if the model's question is unusable."""
    slide_text = f"[{slide['slide_id']}]\n{slide['text']}"
    try:
        question = QuizQuestion.model_validate(llm(PROMPT, slide_text, QuizQuestion))
    except ValidationError:
        return None

    options = [option.strip() for option in question.options]
    if not question.question.strip() or len({option.lower() for option in options}) < 4:
        return None  # empty question or the same option twice

    correct = options[question.answer]
    rng.shuffle(options)
    answer = options.index(correct)

    # Self-check without the answer key; disagreement means the question or its answer is unreliable.
    numbered = "\n".join(f"{i}. {option}" for i, option in enumerate(options))
    try:
        check = CheckAnswer.model_validate(
            llm(CHECK_PROMPT, f"Slide:\n{slide_text}\n\nQuestion: {question.question}\n{numbered}", CheckAnswer)
        )
    except ValidationError:
        return None
    if check.answer != answer:
        return None

    return {
        "question": question.question.strip(),
        "options": options,
        "answer": answer,
        "explanation": question.explanation.strip(),
        "slide_id": slide["slide_id"],
    }


def make_quiz(
    number: int,
    count: int = 5,
    topic: str | None = None,
    llm: Callable[..., dict] | None = None,
    seed: int | None = None,
) -> list[dict]:
    """Up to `count` questions, each from a different random slide. llm and seed are for tests."""
    llm = llm or chat_json
    rng = random.Random(seed)
    slides = candidate_slides(number, topic)
    rng.shuffle(slides)

    questions = []
    # About half of the questions fail the self-check, so try up to 3x as many slides - but no endless retries.
    for slide in slides[: 3 * count]:
        question = make_question(slide, llm, rng)
        if question:
            questions.append(question)
        if len(questions) == count:
            break
    return questions


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print('Usage: python -m app.rag.quiz <lecture-number> ["topic"]')
        sys.exit(1)

    quiz = make_quiz(int(sys.argv[1]), topic=sys.argv[2] if len(sys.argv) == 3 else None)
    if not quiz:
        print("No suitable slides found.")
        sys.exit(1)

    for i, q in enumerate(quiz, 1):
        print(f"{i}. {q['question']}  [{q['slide_id']}]")
        for letter, option in zip("ABCD", q["options"]):
            print(f"   {'*' if option == q['options'][q['answer']] else ' '} {letter}) {option}")
        print(f"   → {q['explanation']}\n")
