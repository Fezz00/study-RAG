"""Tests for the API layer, with the RAG pipeline replaced by a fake ("mock")."""

import pytest
from fastapi.testclient import TestClient

from app.api import main

client = TestClient(main.app)


def fake_ask(question: str) -> dict:
    slide = {"slide_id": "L05-s102", "lecture": "Lecture 5", "slide": 102, "text": "Max pooling ...", "score": 0.7}
    return {"answer": "Max pooling takes the maximum [L05-s102].", "citations": [slide], "sources": [slide]}


@pytest.fixture
def mocked_ask(monkeypatch):
    # Replace the real ask() so the test needs neither Ollama nor Qdrant.
    monkeypatch.setattr(main, "ask", fake_ask)


def test_ask_returns_answer_and_citations(mocked_ask):
    response = client.post("/ask", json={"question": "What is max pooling?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("Max pooling")
    assert body["citations"][0]["slide_id"] == "L05-s102"
    assert body["sources"] == [{"slide_id": "L05-s102", "score": 0.7}]


def test_ask_rejects_empty_question(mocked_ask):
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_ask_rejects_missing_question(mocked_ask):
    assert client.post("/ask", json={}).status_code == 422


def test_upload_rejects_non_pdf():
    response = client.post("/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
