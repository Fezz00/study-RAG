"""HTTP API for the study assistant.

Run:
    uvicorn app.api.main:app --reload
Then open http://localhost:8000/docs to try the endpoints in the browser.
"""

from pathlib import Path

import ollama
from fastapi import FastAPI, HTTPException, UploadFile
from qdrant_client import QdrantClient

from app.api.schemas import AskRequest, AskResponse, Citation, DocumentResponse, Source
from app.config import DATA_DIR, OLLAMA_URL, QDRANT_URL
from app.ingest.index import index_pdf
from app.rag.ask import ask

app = FastAPI(title="Lecture Study Assistant")

qdrant = QdrantClient(url=QDRANT_URL)


# Plain "def" (not "async def"): our Qdrant and Ollama calls are blocking,
# so FastAPI runs these functions in a thread pool and the server stays responsive.


@app.get("/health")
def health() -> dict:
    """Check that the API can reach Qdrant and Ollama."""
    status = {"api": "ok"}

    try:
        qdrant.get_collections()
        status["qdrant"] = "ok"
    except Exception:
        status["qdrant"] = "unreachable"

    try:
        ollama.Client(host=OLLAMA_URL).list()
        status["ollama"] = "ok"
    except Exception:
        status["ollama"] = "unreachable"

    if "unreachable" in status.values():
        raise HTTPException(status_code=503, detail=status)
    return status


@app.post("/documents", response_model=DocumentResponse)
def upload_document(file: UploadFile) -> DocumentResponse:
    """Upload a lecture PDF, save it to data/ and index its slides."""
    # Only keep the bare file name, so a name like "../../x.pdf" can't escape data/.
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    path = Path(DATA_DIR) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file.file.read())

    try:
        count = index_pdf(str(path), qdrant)
    except ValueError as error:  # e.g. no lecture number in the file name
        raise HTTPException(status_code=400, detail=str(error))

    return DocumentResponse(filename=filename, slides_indexed=count)


@app.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    """Answer a question from the indexed slides, with citations."""
    result = ask(request.question)
    return AskResponse(
        answer=result["answer"],
        citations=[Citation(**slide) for slide in result["citations"]],
        sources=[Source(slide_id=s["slide_id"], score=s["score"]) for s in result["sources"]],
    )
