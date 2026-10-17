"""All settings in one place.

Each value comes from an environment variable, with a default for local development.
Docker Compose (phase 2) and Kubernetes (phase 4) override them without code changes.
"""

import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:4b")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "slides")

TOP_K = int(os.getenv("TOP_K", "5"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.5"))

DATA_DIR = os.getenv("DATA_DIR", "data")
