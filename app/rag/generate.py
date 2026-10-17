"""Build a prompt from retrieved slides and ask the chat model for an answer."""

import ollama

from app.config import CHAT_MODEL, OLLAMA_URL

_client = ollama.Client(host=OLLAMA_URL)

NOT_COVERED = "Not covered in the slides."

SYSTEM_PROMPT = f"""You are a study assistant for university lecture slides.

Rules:
1. Answer ONLY with information from the slides you are given. Never use outside knowledge.
2. After every sentence, cite the slide it comes from with its ID in square brackets, e.g. [L05-s12].
3. Only cite IDs that appear in the slides you are given.
4. If the slides do not contain the answer, reply with exactly: {NOT_COVERED}
5. Keep the answer short and clear."""


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
    # Some Qwen3 builds still write their reasoning, ending with "</think>". Keep only the answer.
    return response.message.content.split("</think>")[-1].strip()
