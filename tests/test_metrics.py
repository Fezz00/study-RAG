"""Tests for the Prometheus metrics, with Qdrant and the LLM replaced by fakes."""

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.api import main
from app.rag import ask as ask_module

client = TestClient(main.app)

SLIDE = {"slide_id": "L05-s102", "lecture": "Lecture 5", "slide": 102, "text": "Max pooling ...", "score": 0.7}


def count(outcome: str) -> float:
    """Current value of rag_answers_total for one outcome (0 if never counted)."""
    return REGISTRY.get_sample_value("rag_answers_total", {"outcome": outcome}) or 0.0


def test_metrics_endpoint_lists_our_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    for name in ["http_request_duration_seconds", "llm_generation_seconds", "retrieval_top_score", "rag_answers"]:
        assert name in response.text


def test_requests_are_recorded_by_route_template():
    client.post("/ask", json={"question": ""})  # rejected with 422, but still measured
    assert REGISTRY.get_sample_value(
        "http_request_duration_seconds_count", {"method": "POST", "path": "/ask", "status": "422"}
    )


def test_answer_is_counted(monkeypatch):
    monkeypatch.setattr(ask_module, "retrieve", lambda question, top_k: [SLIDE])
    monkeypatch.setattr(ask_module, "generate_answer", lambda question, slides: "It takes the max [L05-s102].")
    before = count("answered")
    ask_module.ask("What is max pooling?")
    assert count("answered") == before + 1


def test_low_score_refusal_is_counted(monkeypatch):
    monkeypatch.setattr(ask_module, "retrieve", lambda question, top_k: [{**SLIDE, "score": 0.2}])
    before = count("refused_low_score")
    ask_module.ask("What is the capital of France?")
    assert count("refused_low_score") == before + 1


def test_missing_citation_is_counted(monkeypatch):
    monkeypatch.setattr(ask_module, "retrieve", lambda question, top_k: [SLIDE])
    monkeypatch.setattr(ask_module, "generate_answer", lambda question, slides: "An answer without a source.")
    before = count("refused_no_citation")
    result = ask_module.ask("What is max pooling?")
    assert result["answer"] == "Not covered in the slides."
    assert count("refused_no_citation") == before + 1
