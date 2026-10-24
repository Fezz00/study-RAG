"""Describe slide images (diagrams, charts, figures) in words with a local vision model.

The description is added to the slide text, so retrieval can find slides whose content
is mainly a picture. Enabled by setting VISION_MODEL to a vision-capable Ollama model.
"""

import ollama

from app.config import OLLAMA_URL, VISION_MODEL

_client = ollama.Client(host=OLLAMA_URL)

PROMPT = (
    "This is a slide from a university lecture. Describe its figures, diagrams, charts and formulas "
    "in 2-4 short factual sentences. Include numbers, labels and names you can read. "
    "Don't describe layout, colors or decoration, and don't add knowledge that isn't shown."
)


def describe_slide(png: bytes) -> str:
    """Return a short text description of a slide image."""
    response = _client.chat(
        model=VISION_MODEL,
        messages=[{"role": "user", "content": PROMPT, "images": [png]}],
    )
    return response.message.content.strip()
