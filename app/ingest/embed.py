"""Turn texts into embedding vectors with a local Ollama model."""

import ollama

from app.config import EMBED_MODEL, OLLAMA_URL

_client = ollama.Client(host=OLLAMA_URL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one vector per text, in the same order."""
    response = _client.embed(model=EMBED_MODEL, input=texts)
    return response.embeddings
