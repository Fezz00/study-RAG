"""Ask a question about the indexed lectures from the terminal.

Usage:
    python -m app.rag.ask "What is dropout?"
"""

import sys

from app.rag.generate import generate_answer
from app.rag.retrieve import retrieve


def ask(question: str, top_k: int = 5) -> dict:
    slides = retrieve(question, top_k=top_k)
    answer = generate_answer(question, slides)
    return {"answer": answer, "sources": slides}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python -m app.rag.ask "<question>"')
        sys.exit(1)

    result = ask(sys.argv[1])
    print(result["answer"])
    print("\nRetrieved slides:")
    for slide in result["sources"]:
        print(f"  {slide['slide_id']}  ({slide['lecture']}, slide {slide['slide']})  score={slide['score']:.3f}")
