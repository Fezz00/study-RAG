"""Ask a question about the indexed lectures from the terminal.

Usage:
    python -m app.rag.ask "What is dropout?"
"""

import os
import re
import sys

from app.rag.generate import NOT_COVERED, generate_answer
from app.rag.retrieve import retrieve

# Below this similarity the best slide is clearly unrelated, so we skip the LLM.
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.5"))

CITATION_PATTERN = re.compile(r"L\d+-s\d+")


def validate_citations(answer: str, slides: list[dict]) -> tuple[str, list[dict]]:
    """Keep only citations of slides we actually retrieved.

    Small models sometimes invent slide IDs, so any ID that was not retrieved
    is removed from the answer text. Returns the cleaned answer and the cited slides.
    """
    retrieved = {slide["slide_id"]: slide for slide in slides}

    cited_ids = []
    for slide_id in CITATION_PATTERN.findall(answer):
        if slide_id in retrieved and slide_id not in cited_ids:
            cited_ids.append(slide_id)

    cleaned = re.sub(
        r"\[(L\d+-s\d+)\]",
        lambda m: m.group(0) if m.group(1) in retrieved else "",
        answer,
    )
    return cleaned.strip(), [retrieved[slide_id] for slide_id in cited_ids]


def ask(question: str, top_k: int = 5) -> dict:
    slides = retrieve(question, top_k=top_k)

    # Layer 1: nothing similar enough was found -> don't even ask the LLM.
    if not slides or slides[0]["score"] < MIN_SCORE:
        return {"answer": NOT_COVERED, "citations": [], "sources": slides}

    # Layer 2: the strict prompt tells the model to cite or say NOT_COVERED.
    answer = generate_answer(question, slides)
    if NOT_COVERED in answer:
        return {"answer": NOT_COVERED, "citations": [], "sources": slides}

    # Layer 3: check the citations in code instead of trusting the model.
    answer, citations = validate_citations(answer, slides)
    if not citations:
        answer = NOT_COVERED

    return {"answer": answer, "citations": citations, "sources": slides}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python -m app.rag.ask "<question>"')
        sys.exit(1)

    result = ask(sys.argv[1])
    print(result["answer"])

    if result["citations"]:
        print("\nSources:")
        for slide in result["citations"]:
            print(f"  {slide['lecture']}, slide {slide['slide']}")

    print("\nRetrieved slides:")
    for slide in result["sources"]:
        print(f"  {slide['slide_id']}  score={slide['score']:.3f}")
