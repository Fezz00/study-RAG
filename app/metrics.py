"""Prometheus metrics: numbers the API collects about itself, shown at /metrics.

Counter   = a number that only goes up (e.g. answers so far); Prometheus computes rates from it.
Histogram = sorts each measurement into buckets (e.g. "under 2 s"), so dashboards can show
            averages and percentiles ("95% of answers are faster than X").
"""

from prometheus_client import Counter, Histogram

REQUEST_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Time to handle an HTTP request",
    ["method", "path", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

LLM_SECONDS = Histogram(
    "llm_generation_seconds",
    "Time the chat model needs to write an answer",
    buckets=(0.5, 1, 2, 3, 5, 10, 20, 60, 120),
)

LLM_TOKENS_PER_SECOND = Histogram(
    "llm_tokens_per_second",
    "Generation speed of the chat model",
    buckets=(5, 10, 20, 30, 40, 60, 80, 120, 200),
)

RETRIEVAL_TOP_SCORE = Histogram(
    "retrieval_top_score",
    "Similarity of the best retrieved slide for a question",
    buckets=(0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

ANSWERS = Counter(
    "rag_answers",  # exported as rag_answers_total
    "Questions handled, by outcome",
    ["outcome"],  # answered | refused_low_score | refused_by_model | refused_no_citation
)
