"""Find the slides most similar to a question."""

from qdrant_client import QdrantClient

from app.config import QDRANT_COLLECTION as COLLECTION
from app.config import QDRANT_URL, TOP_K
from app.ingest.embed import embed_texts

_client = QdrantClient(url=QDRANT_URL)


def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    """Embed the question and return the top_k closest slides, best first.

    Each result is the slide's payload plus its similarity score.
    """
    query_vector = embed_texts([question])[0]
    response = _client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=top_k,
    )
    return [{**point.payload, "score": point.score} for point in response.points]
