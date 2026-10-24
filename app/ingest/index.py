"""Parse a lecture PDF, embed every slide and store it in Qdrant.

Usage:
    python -m app.ingest.index data/lecture04.pdf
"""

import sys
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import QDRANT_COLLECTION as COLLECTION
from app.config import QDRANT_URL, VISION_MODEL
from app.ingest.describe import describe_slide
from app.ingest.embed import embed_texts
from app.ingest.parse_pdf import parse_pdf


def point_id(slide_id: str) -> str:
    """Qdrant only accepts integers or UUIDs as IDs, so derive a UUID from 'L04-s12'.

    The same slide always gets the same UUID, so re-indexing a lecture
    overwrites its slides instead of adding duplicates.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, slide_id))


def index_pdf(pdf_path: str, client: QdrantClient) -> int:
    """Index one PDF and return how many slides were stored."""
    # Fail fast: check that Qdrant answers before the slow parsing/vision step, not after it.
    client.get_collections()

    # With a vision model configured, slide images are described in words and indexed too.
    chunks = parse_pdf(pdf_path, describe=describe_slide if VISION_MODEL else None)
    if not chunks:
        return 0

    vectors = embed_texts([chunk["text"] for chunk in chunks])

    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
        )
    else:
        # Re-indexing replaces the whole lecture, so slides that are now skipped don't linger.
        client.delete(
            collection_name=COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="lecture", match=MatchValue(value=chunks[0]["lecture"]))])
            ),
        )

    points = [
        PointStruct(
            id=point_id(chunk["id"]),
            vector=vector,
            payload={
                "slide_id": chunk["id"],
                "lecture": chunk["lecture"],
                "slide": chunk["slide"],
                "text": chunk["text"],
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=COLLECTION, points=points)
    return len(points)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.ingest.index <path-to-pdf>")
        sys.exit(1)

    client = QdrantClient(url=QDRANT_URL)
    count = index_pdf(sys.argv[1], client)
    print(f"Indexed {count} slides into collection '{COLLECTION}'")
