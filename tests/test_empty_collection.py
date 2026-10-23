"""Regression tests for issue #24: asking before any lecture is indexed used to return 500."""

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.api import main
from app.rag import ask as ask_module
from app.rag import retrieve as retrieve_module


class EmptyQdrant:
    """A fake Qdrant client where no collection exists yet."""

    def collection_exists(self, name):
        return False

    def query_points(self, **kwargs):
        raise AssertionError("must not query a collection that doesn't exist")


def no_embedding(texts):
    raise AssertionError("must not embed the question when nothing is indexed")


def test_retrieve_returns_nothing_without_collection(monkeypatch):
    monkeypatch.setattr(retrieve_module, "_client", EmptyQdrant())
    monkeypatch.setattr(retrieve_module, "embed_texts", no_embedding)
    assert retrieve_module.retrieve("What is max pooling?") == []


def test_ask_says_no_lectures_and_counts_it(monkeypatch):
    monkeypatch.setattr(ask_module, "retrieve", lambda question, top_k: [])
    before = REGISTRY.get_sample_value("rag_answers_total", {"outcome": "no_lectures"}) or 0.0

    result = ask_module.ask("What is max pooling?")

    assert result == {"answer": ask_module.NO_LECTURES, "citations": [], "sources": []}
    assert REGISTRY.get_sample_value("rag_answers_total", {"outcome": "no_lectures"}) == before + 1


def test_api_returns_200_with_message(monkeypatch):
    # The exact situation from the issue: a real /ask request against an empty database.
    monkeypatch.setattr(retrieve_module, "_client", EmptyQdrant())
    monkeypatch.setattr(retrieve_module, "embed_texts", no_embedding)

    response = TestClient(main.app).post("/ask", json={"question": "What is max pooling?"})

    assert response.status_code == 200
    assert response.json()["answer"] == ask_module.NO_LECTURES
