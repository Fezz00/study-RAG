"""Read slides from Qdrant: the closest slides to a question, or all slides of a lecture."""

from collections import Counter

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.config import QDRANT_COLLECTION as COLLECTION
from app.config import QDRANT_URL, TOP_K
from app.ingest.embed import embed_texts

_client = QdrantClient(url=QDRANT_URL)


def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    """Embed the question and return the top_k closest slides, best first.

    Each result is the slide's payload plus its similarity score.
    Returns an empty list if no lecture has been indexed yet (the collection doesn't exist).
    """
    if not _client.collection_exists(COLLECTION):
        return []

    query_vector = embed_texts([question])[0]
    response = _client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=top_k,
    )
    return [{**point.payload, "score": point.score} for point in response.points]


def _scroll(scroll_filter: Filter | None = None, fields: list[str] | bool = True) -> list[dict]:
    """Payloads of all points matching the filter. Scroll returns one page per call, so loop until the end."""
    payloads, offset = [], None
    while True:
        points, offset = _client.scroll(
            COLLECTION, scroll_filter=scroll_filter, limit=256, offset=offset, with_payload=fields
        )
        payloads += [point.payload for point in points]
        if offset is None:
            return payloads


def list_lectures() -> list[dict]:
    """Every indexed lecture with its slide count, e.g. [{"number": 5, "lecture": "Lecture 5", "slides": 101}]."""
    if not _client.collection_exists(COLLECTION):
        return []
    counts = Counter(payload["lecture"] for payload in _scroll(fields=["lecture"]))
    lectures = [{"number": int(name.split()[-1]), "lecture": name, "slides": n} for name, n in counts.items()]
    return sorted(lectures, key=lambda lecture: lecture["number"])


def lecture_slides(number: int) -> list[dict]:
    """All slides of one lecture in slide order - a filter, not a similarity search."""
    if not _client.collection_exists(COLLECTION):
        return []
    only_this_lecture = Filter(must=[FieldCondition(key="lecture", match=MatchValue(value=f"Lecture {number}"))])
    return sorted(_scroll(only_this_lecture), key=lambda slide: slide["slide"])
