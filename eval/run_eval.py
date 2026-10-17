"""Measure retrieval and answer quality on eval/questions.jsonl.

Usage:
    python -m eval.run_eval                     # full eval (retrieval + answers), a few minutes
    python -m eval.run_eval --retrieval-only    # only Hit@5 and MRR, no LLM, a few seconds
    python -m eval.run_eval --min-hit 0.8       # exit with code 1 if Hit@5 is below 0.8

Needs Qdrant (with the lectures indexed) and Ollama running.
"""

import argparse
import json
import sys
from pathlib import Path

from app.config import TOP_K
from app.rag.ask import ask
from app.rag.generate import NOT_COVERED
from app.rag.retrieve import retrieve

QUESTIONS_FILE = Path(__file__).parent / "questions.jsonl"


def load_questions(path: Path = QUESTIONS_FILE) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def normalize(text: str) -> str:
    """Lowercase, drop spaces and unify symbols, so "10 × 32 x 32" matches "10x32x32"."""
    text = text.lower()
    for dash in "–—−":
        text = text.replace(dash, "-")
    text = text.replace("×", "x").replace("*", "x")
    return "".join(text.split())


def first_hit_rank(retrieved_ids: list[str], expected: list[str]) -> int | None:
    """1-based rank of the first expected slide in the results, or None if none was found."""
    for rank, slide_id in enumerate(retrieved_ids, start=1):
        if slide_id in expected:
            return rank
    return None


def evaluate(questions: list[dict], retrieval_only: bool) -> tuple[dict, list[dict]]:
    """Run every question and return (metrics, per-question results)."""
    results = []
    for i, q in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] {q['question']}", file=sys.stderr)
        answerable = bool(q["expected_slides"])

        if retrieval_only:
            slides = retrieve(q["question"])
            answer, cited = None, []
        else:
            result = ask(q["question"])
            slides, answer = result["sources"], result["answer"]
            cited = [c["slide_id"] for c in result["citations"]]

        retrieved_ids = [s["slide_id"] for s in slides]
        results.append(
            {
                "question": q["question"],
                "answerable": answerable,
                "expected": q["expected_slides"],
                "retrieved": retrieved_ids,
                "rank": first_hit_rank(retrieved_ids, q["expected_slides"]) if answerable else None,
                "answer": answer,
                "refused": answer == NOT_COVERED,
                "cited": cited,
                "keywords_found": [k for k in q["must_mention"] if answer and normalize(k) in normalize(answer)],
                "must_mention": q["must_mention"],
            }
        )

    answerable = [r for r in results if r["answerable"]]
    metrics = {
        # Retrieval: did the right slide come back, and how high?
        "hit@k": sum(r["rank"] is not None for r in answerable) / len(answerable),
        "mrr": sum(1 / r["rank"] for r in answerable if r["rank"]) / len(answerable),
    }

    if not retrieval_only:
        answered = [r for r in answerable if not r["refused"]]
        all_cited = [c for r in answered for c in r["cited"]]
        unanswerable = [r for r in results if not r["answerable"]]
        metrics |= {
            # Share of cited slides that are among the expected ones.
            "citation_accuracy": (
                sum(c in r["expected"] for r in answered for c in r["cited"]) / len(all_cited) if all_cited else 0.0
            ),
            # Share of must_mention terms that appear in the answers.
            "keyword_coverage": (
                sum(len(r["keywords_found"]) for r in answered) / max(1, sum(len(r["must_mention"]) for r in answered))
            ),
            # Not-covered questions that were correctly refused.
            "refusal_accuracy": sum(r["refused"] for r in unanswerable) / len(unanswerable) if unanswerable else 0.0,
            # Covered questions that were wrongly refused.
            "false_refusal_rate": sum(r["refused"] for r in answerable) / len(answerable),
        }
    return metrics, results


def print_report(metrics: dict, results: list[dict]) -> None:
    misses = [r for r in results if r["answerable"] and r["rank"] is None]
    if misses:
        print(f"\nRetrieval misses (no expected slide in top {TOP_K}):")
        for r in misses:
            print(f"  - {r['question']}\n      expected {r['expected']}, got {r['retrieved']}")

    if any(r["answer"] is not None for r in results):
        wrong_refusals = [r for r in results if r["answerable"] and r["refused"]]
        not_refused = [r for r in results if not r["answerable"] and not r["refused"]]
        if wrong_refusals:
            print("\nWrongly refused (covered, but answered 'Not covered'):")
            for r in wrong_refusals:
                print(f"  - {r['question']}")
        if not_refused:
            print("\nShould have been refused:")
            for r in not_refused:
                print(f"  - {r['question']}\n      answer: {r['answer'][:120]}")

    print(f"\n{'Metric':<22}Value")
    print("-" * 30)
    for name, value in metrics.items():
        print(f"{name:<22}{value:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--retrieval-only", action="store_true", help="skip the LLM, only measure retrieval")
    parser.add_argument("--min-hit", type=float, default=0.8, help="fail if Hit@k is below this (default 0.8)")
    args = parser.parse_args()

    metrics, results = evaluate(load_questions(), retrieval_only=args.retrieval_only)
    print_report(metrics, results)

    if metrics["hit@k"] < args.min_hit:
        print(f"\nFAIL: Hit@{TOP_K} {metrics['hit@k']:.3f} is below the threshold {args.min_hit}")
        sys.exit(1)
    print(f"\nPASS: Hit@{TOP_K} {metrics['hit@k']:.3f} >= {args.min_hit}")


if __name__ == "__main__":
    main()
