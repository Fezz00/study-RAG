"""Build a prompt from retrieved slides and ask the chat model for an answer."""

import os

import ollama

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:4b")

_client = ollama.Client(host=OLLAMA_URL)

SYSTEM_PROMPT = "You are a helpful study assistant. Use the lecture slides below to answer the question."


def format_sources(slides: list[dict]) -> str:
    """Label every slide with its ID so the model can refer to it, e.g. [L05-s12]."""
    return "\n\n".join(f"[{slide['slide_id']}]\n{slide['text']}" for slide in slides)


def generate_answer(question: str, slides: list[dict]) -> str:
    user_message = f"Slides:\n\n{format_sources(slides)}\n\nQuestion: {question}"
    response = _client.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        think=False,  # Qwen3 can "think" before answering; off = faster
    )
    return response.message.content
