"""Tests for the eval helpers, so the metrics themselves can be trusted."""

import json

from eval.run_eval import QUESTIONS_FILE, first_hit_rank, normalize


def test_normalize_ignores_spaces_case_and_symbols():
    assert normalize("10 × 32 x 32") == "10x32x32"
    assert normalize("W – K + 1") == "w-k+1"


def test_first_hit_rank():
    assert first_hit_rank(["a", "b", "c"], ["c"]) == 3
    assert first_hit_rank(["a", "b"], ["x"]) is None


def test_questions_file_is_valid():
    rows = [json.loads(line) for line in QUESTIONS_FILE.read_text().splitlines() if line.strip()]
    assert len(rows) >= 30
    for row in rows:
        assert set(row) == {"question", "expected_slides", "must_mention"}
        assert row["question"].strip()
