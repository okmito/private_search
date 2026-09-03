"""Tests for the search quality benchmarking framework."""

from __future__ import annotations

import math

from benchmarks.evaluation.runner import (
    BenchmarkCorpus,
    BenchmarkQuery,
    BenchmarkRunner,
    evaluate,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_precision_at_k_basic() -> None:
    assert precision_at_k([1, 2, 3], [1, 2], 2) == 1.0
    assert precision_at_k([3, 4, 1], [1, 2], 3) == 1 / 3
    assert precision_at_k([], [1, 2], 5) == 0.0


def test_recall_at_k_basic() -> None:
    assert recall_at_k([1, 2, 3], [1, 2, 3], 3) == 1.0
    assert recall_at_k([1], [1, 2, 3], 5) == 1 / 3


def test_ndcg_at_k_perfect_ranking() -> None:
    predicted = [1, 2, 3]
    relevant = [1, 2, 3]
    assert math.isclose(ndcg_at_k(predicted, relevant, 3), 1.0, rel_tol=1e-9)


def test_ndcg_at_k_zero_relevant() -> None:
    assert ndcg_at_k([1, 2, 3], [], 3) == 0.0


def test_evaluate_returns_results_for_all_methods() -> None:
    corpus = BenchmarkCorpus(
        name="tiny",
        documents=[
            (1, "https://example.com/a", "Apple Pie", "apple pie recipe sugar flour"),
            (2, "https://example.com/b", "Banana Bread", "banana bread recipe sugar"),
            (3, "https://example.com/c", "Cherry Jam", "cherry jam sugar fruit"),
        ],
    )
    queries = [
        BenchmarkQuery(query="apple pie", relevant=(1,)),
        BenchmarkQuery(query="banana", relevant=(2,)),
    ]
    results = evaluate(corpus, queries)
    assert len(results) >= 2
    methods = {result.method for result in results}
    assert "BM25" in methods
    assert any("Ranking" in method for method in methods)


def test_runner_produces_expected_metrics() -> None:
    corpus = BenchmarkCorpus(
        name="tiny",
        documents=[
            (1, "https://example.com/a", "Apple Pie", "apple pie recipe"),
            (2, "https://example.com/b", "Banana Bread", "banana bread recipe"),
        ],
    )
    queries = [BenchmarkQuery(query="apple", relevant=(1,))]
    runner = BenchmarkRunner(corpus, queries)
    bm25_result = runner.evaluate_bm25(k=5)
    assert bm25_result.precision_at_5 >= 0.0
    assert bm25_result.precision_at_5 <= 1.0
    assert bm25_result.recall_at_10 >= 0.0
    assert bm25_result.ndcg_at_10 >= 0.0
    # The first result for "apple" must be the apple document.
    assert bm25_result.mrr >= 0.5