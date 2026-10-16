"""Turn texts into embedding vectors with a local Ollama model."""

import os

import ollama

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

_client = ollama.Client(host=OLLAMA_URL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one vector per text, in the same order."""
    response = _client.embed(model=EMBED_MODEL, input=texts)
    return response.embeddings
