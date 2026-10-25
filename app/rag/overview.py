"""Summarize a whole lecture into its main topics, each with the slides it comes from.

/ask only sees the 5 slides closest to a question, but an overview needs every slide.
A lecture is ~10k tokens, too much for one prompt, so it is done in two steps ("map-reduce"):
1. map:    every batch of BATCH_SIZE slides is summarized into a few topics
2. reduce: the topics of all batches are merged into the main topics of the lecture

Generating takes a few minutes, so the result is saved in data/overviews/
and deleted again when the lecture is re-indexed.

Usage:
    python -m app.rag.overview 5
"""

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

import ollama
from pydantic import BaseModel

from app.config import CHAT_MODEL, DATA_DIR, OLLAMA_URL
from app.metrics import LLM_SECONDS
from app.rag.generate import format_sources
from app.rag.retrieve import lecture_slides

_client = ollama.Client(host=OLLAMA_URL)

BATCH_SIZE = 15
# Room for a batch of slides plus the answer; Ollama's default context (4096 tokens) is too small.
CONTEXT_TOKENS = 8192

MAP_PROMPT = """You summarize university lecture slides.
Group the slides you are given into 1-4 topics. For each topic write a short title,
a 1-2 sentence summary using ONLY information from the slides, and the IDs of the
slides it comes from, e.g. ["L05-s12", "L05-s13"]. Only use IDs that appear in the slides."""

REDUCE_PROMPT = """You get the topics of consecutive parts of one lecture, in order.
Merge them into 4-8 main topics of the whole lecture, in lecture order. Combine topics
about the same thing and keep all their slide IDs. Use ONLY the information given."""


class Topic(BaseModel):
    title: str
    summary: str
    slides: list[str]


class Topics(BaseModel):
    """The JSON shape the chat model must answer in."""

    topics: list[Topic]


def chat_json(system: str, user: str) -> dict:
    """Ask the chat model; its reply is forced into the Topics JSON shape."""
    start = time.perf_counter()
    response = _client.chat(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format=Topics.model_json_schema(),  # structured output: Ollama only lets the model write matching JSON
        think=False,
        options={"num_ctx": CONTEXT_TOKENS},
    )
    LLM_SECONDS.observe(time.perf_counter() - start)
    return json.loads(response.message.content)


def slide_number(slide_id: str) -> int:
    return int(slide_id.split("-s")[1])  # "L05-s12" -> 12


def clean_topics(raw: dict, known_ids: set[str]) -> list[dict]:
    """Drop slide IDs the model made up, and topics left without any real slide."""
    topics = []
    for topic in Topics.model_validate(raw).topics:
        slides = list(dict.fromkeys(s for s in topic.slides if s in known_ids))  # remove duplicates, keep order
        if slides:
            topics.append({"title": topic.title, "summary": topic.summary, "slides": sorted(slides, key=slide_number)})
    return sorted(topics, key=lambda topic: slide_number(topic["slides"][0]))


def summarize(slides: list[dict], llm: Callable[[str, str], dict] | None = None) -> list[dict]:
    """Map-reduce the slides into topics. llm can be replaced, e.g. by a fake in tests."""
    llm = llm or chat_json
    known_ids = {slide["slide_id"] for slide in slides}
    batches = [slides[i : i + BATCH_SIZE] for i in range(0, len(slides), BATCH_SIZE)]

    partial = []
    for batch in batches:
        partial += clean_topics(llm(MAP_PROMPT, f"Slides:\n\n{format_sources(batch)}"), known_ids)
    if len(batches) == 1:
        return partial  # nothing to merge
    return clean_topics(llm(REDUCE_PROMPT, f"Topics:\n\n{json.dumps(partial, indent=1)}"), known_ids)


def overview_path(number: int) -> Path:
    return Path(DATA_DIR) / "overviews" / f"L{number:02d}.json"


def get_overview(number: int, refresh: bool = False) -> dict | None:
    """The saved overview of a lecture, or a newly generated one. None if the lecture isn't indexed."""
    path = overview_path(number)
    if path.exists() and not refresh:
        return json.loads(path.read_text())

    slides = lecture_slides(number)
    if not slides:
        return None

    overview = {"lecture": f"Lecture {number}", "slides": len(slides), "topics": summarize(slides)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overview, indent=2))
    return overview


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.rag.overview <lecture-number>")
        sys.exit(1)

    overview = get_overview(int(sys.argv[1]))
    if overview is None:
        print(f"Lecture {sys.argv[1]} is not indexed.")
        sys.exit(1)

    print(f"{overview['lecture']} ({overview['slides']} slides)\n")
    for topic in overview["topics"]:
        print(f"## {topic['title']}  [{', '.join(topic['slides'])}]")
        print(f"{topic['summary']}\n")
