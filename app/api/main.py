"""HTTP API for the study assistant.

Run:
    uvicorn app.api.main:app --reload
Then open http://localhost:8000/docs to try the endpoints in the browser.
"""

import time
from pathlib import Path

import ollama
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from qdrant_client import QdrantClient

from app.api.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    DocumentResponse,
    Lecture,
    OverviewResponse,
    QuizRequest,
    QuizResponse,
    Source,
)
from app.config import DATA_DIR, OLLAMA_URL, QDRANT_URL
from app.ingest.index import index_pdf
from app.metrics import REQUEST_SECONDS
from app.rag.ask import ask
from app.rag.overview import get_overview
from app.rag.quiz import make_quiz
from app.rag.retrieve import list_lectures

app = FastAPI(title="Lecture Study Assistant")

qdrant = QdrantClient(url=QDRANT_URL)


@app.middleware("http")
async def measure_requests(request: Request, call_next):
    """Time every request and record it with its endpoint and status code."""
    start = time.perf_counter()
    status = 500  # if the endpoint crashes, it counts as a server error
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # Use the route template ("/ask"), not the raw URL, so random URLs don't create endless labels.
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        REQUEST_SECONDS.labels(request.method, path, str(status)).observe(time.perf_counter() - start)


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """All metrics in Prometheus' text format; Prometheus reads this page every few seconds."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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


@app.get("/lectures", response_model=list[Lecture])
def lectures() -> list[Lecture]:
    """All indexed lectures with their number of slides."""
    return [Lecture(**lecture) for lecture in list_lectures()]


@app.get("/lectures/{number}/overview", response_model=OverviewResponse)
def lecture_overview(number: int, refresh: bool = False) -> OverviewResponse:
    """The main topics of a lecture with their slides. The first call takes a few minutes, then it is saved."""
    overview = get_overview(number, refresh=refresh)
    if overview is None:
        raise HTTPException(status_code=404, detail=f"Lecture {number} is not indexed.")
    return OverviewResponse(**overview)


@app.post("/quiz", response_model=QuizResponse)
def quiz(request: QuizRequest) -> QuizResponse:
    """Multiple-choice questions from random slides of a lecture, optionally only about a topic."""
    questions = make_quiz(request.lecture, count=request.count, topic=request.topic)
    if not questions:
        about = f" about '{request.topic}'" if request.topic else ""
        raise HTTPException(status_code=404, detail=f"No slides{about} found in Lecture {request.lecture}.")
    return QuizResponse(lecture=f"Lecture {request.lecture}", questions=questions)
