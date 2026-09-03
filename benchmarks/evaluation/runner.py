"""Search quality evaluation framework.

Implements Precision@K, Recall@K, MRR and nDCG@K and provides a CLI to
run them against a real corpus. The framework is deliberately small and
does not pretend to ship labelled datasets: the bundled corpus is
synthetic but deterministic so the numbers are easy to reproduce.

The numerical results are written to ``benchmarks/results/metrics.json``,
which the README references.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.indexing.pipeline import IndexingPipeline
from privatesearch.ranking.pipeline import RankingConfig, RankingPipeline
from privatesearch.retrieval.bm25 import BM25
from privatesearch.retrieval.retriever import Retriever

__all__ = [
    "BenchmarkCorpus",
    "BenchmarkQuery",
    "BenchmarkResult",
    "BenchmarkRunner",
    "evaluate",
]


# ----------------------------------------------------------------------
# Dataset types.
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BenchmarkCorpus:
    """A deterministic mini-corpus used for evaluation."""

    name: str
    documents: list[tuple[int, str, str, str]]  # (doc_id, url, title, body)

    def to_index(self) -> InvertedIndex:
        index = InvertedIndex()
        for doc_id, url, title, body in self.documents:
            index.add_document(doc_id, text=body, title=title, url=url)
        return index


@dataclass(frozen=True, slots=True)
class BenchmarkQuery:
    """One query with its graded relevance judgements."""

    query: str
    relevant: tuple[int, ...] = field(default_factory=tuple)
    irrelevant: tuple[int, ...] = field(default_factory=tuple)


# ----------------------------------------------------------------------
# Metrics.
# ----------------------------------------------------------------------


def precision_at_k(predicted: Sequence[int], relevant: Sequence[int], k: int) -> float:
    if k <= 0 or not predicted:
        return 0.0
    top_k = list(predicted[:k])
    if not relevant:
        return 0.0
    hits = sum(1 for doc_id in top_k if doc_id in set(relevant))
    return hits / k


def recall_at_k(predicted: Sequence[int], relevant: Sequence[int], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = list(predicted[:k])
    hits = sum(1 for doc_id in top_k if doc_id in set(relevant))
    return hits / len(relevant)


def mean_reciprocal_rank(
    queries: Iterable[tuple[Sequence[int], Sequence[int]]],
) -> float:
    total = 0.0
    count = 0
    for predicted, relevant in queries:
        relevant_set = set(relevant)
        for rank, doc_id in enumerate(predicted, start=1):
            if doc_id in relevant_set:
                total += 1.0 / rank
                break
        count += 1
    return total / count if count else 0.0


def dcg_at_k(predicted: Sequence[int], relevant: Sequence[int], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = list(predicted[:k])
    score = 0.0
    for rank, doc_id in enumerate(top_k, start=1):
        if doc_id in set(relevant):
            score += 1.0 / math.log2(rank + 1)
    return score


def ndcg_at_k(predicted: Sequence[int], relevant: Sequence[int], k: int) -> float:
    if not relevant:
        return 0.0
    ideal = sorted(relevant, key=lambda _: 0, reverse=True)
    ideal_dcg = dcg_at_k(ideal, relevant, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(predicted, relevant, k) / ideal_dcg


# ----------------------------------------------------------------------
# Runner.
# ----------------------------------------------------------------------


@dataclass(slots=True)
class BenchmarkResult:
    method: str
    precision_at_5: float
    precision_at_10: float
    recall_at_10: float
    mrr: float
    ndcg_at_5: float
    ndcg_at_10: float
    average_latency_ms: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "method": self.method,
            "precision_at_5": self.precision_at_5,
            "precision_at_10": self.precision_at_10,
            "recall_at_10": self.recall_at_10,
            "mrr": self.mrr,
            "ndcg_at_5": self.ndcg_at_5,
            "ndcg_at_10": self.ndcg_at_10,
            "average_latency_ms": self.average_latency_ms,
        }


class BenchmarkRunner:
    """Runs an evaluation harness against a :class:`BenchmarkCorpus`."""

    def __init__(
        self,
        corpus: BenchmarkCorpus,
        queries: Sequence[BenchmarkQuery],
    ) -> None:
        self.corpus = corpus
        self.queries = list(queries)
        self._index = corpus.to_index()

    @property
    def index(self) -> InvertedIndex:
        return self._index

    # ------------------------------------------------------------------
    # Methods evaluated.
    # ------------------------------------------------------------------
    def evaluate_bm25(self, k: int = 10) -> BenchmarkResult:
        bm25 = BM25(self._index)
        return self._evaluate(
            name="BM25",
            k=k,
            ranker=lambda query: [hit.doc_id for hit in bm25.score_terms(query)],
        )

    def evaluate_bm25_retriever(self, k: int = 10) -> BenchmarkResult:
        retriever = Retriever(self._index)

        def _rank(query: list[str]) -> list[int]:
            if not query:
                return []
            hits = retriever.bm25.score_terms(query)
            return [hit.doc_id for hit in hits[:k]]

        return self._evaluate(
            name="BM25+snippets",
            k=k,
            ranker=_rank,
        )

    def evaluate_ranking(self, config: RankingConfig | None = None, k: int = 10) -> BenchmarkResult:
        pipeline = RankingPipeline(config=config or RankingConfig())

        def _rank(query: list[str]) -> list[int]:
            if not query:
                return []
            hits = pipeline.rank(" ".join(query), index=self._index, limit=k)
            return [hit.doc_id for hit in hits]

        name = "Ranking"
        if config is not None:
            name = f"Ranking[{type(config).__name__}]"
        return self._evaluate(name=name, k=k, ranker=_rank)

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------
    def _evaluate(
        self,
        *,
        name: str,
        k: int,
        ranker,
    ) -> BenchmarkResult:
        precisions_5: list[float] = []
        precisions_10: list[float] = []
        recalls_10: list[float] = []
        mrr_pairs: list[tuple[Sequence[int], Sequence[int]]] = []
        ndcgs_5: list[float] = []
        ndcgs_10: list[float] = []
        latencies_ms: list[float] = []

        tokenizer = self._index.tokenizer
        for item in self.queries:
            tokens = tokenizer.tokenize(item.query)
            start = time.perf_counter()
            predicted = list(ranker(tokens))
            latencies_ms.append((time.perf_counter() - start) * 1000)
            precisions_5.append(precision_at_k(predicted, item.relevant, 5))
            precisions_10.append(precision_at_k(predicted, item.relevant, 10))
            recalls_10.append(recall_at_k(predicted, item.relevant, 10))
            mrr_pairs.append((predicted, item.relevant))
            ndcgs_5.append(ndcg_at_k(predicted, item.relevant, 5))
            ndcgs_10.append(ndcg_at_k(predicted, item.relevant, 10))

        return BenchmarkResult(
            method=name,
            precision_at_5=statistics.fmean(precisions_5) if precisions_5 else 0.0,
            precision_at_10=statistics.fmean(precisions_10) if precisions_10 else 0.0,
            recall_at_10=statistics.fmean(recalls_10) if recalls_10 else 0.0,
            mrr=mean_reciprocal_rank(mrr_pairs),
            ndcg_at_5=statistics.fmean(ndcgs_5) if ndcgs_5 else 0.0,
            ndcg_at_10=statistics.fmean(ndcgs_10) if ndcgs_10 else 0.0,
            average_latency_ms=statistics.fmean(latencies_ms) if latencies_ms else 0.0,
        )


def bm25_score_terms(retriever: Retriever, tokens: list[str], limit: int):
    """Return up to ``limit`` BM25 hits using the retriever's BM25 scorer."""

    return retriever.bm25.score_terms(tokens)[:limit]


def evaluate(
    corpus: BenchmarkCorpus,
    queries: Sequence[BenchmarkQuery],
    *,
    methods: Sequence[str] | None = None,
    k: int = 10,
) -> list[BenchmarkResult]:
    """Run the configured evaluation methods and return the results.

    The ``methods`` argument accepts ``"bm25"``, ``"bm25_retriever"`` and
    ``"ranking"``. The default is to run every method.
    """

    runner = BenchmarkRunner(corpus, queries)
    selected = set(methods) if methods else {"bm25", "ranking"}
    results: list[BenchmarkResult] = []
    if "bm25" in selected:
        results.append(runner.evaluate_bm25(k=k))
    if "bm25_retriever" in selected:
        results.append(runner.evaluate_bm25_retriever(k=k))
    if "ranking" in selected:
        results.append(runner.evaluate_ranking(k=k))
    return results


# ----------------------------------------------------------------------
# CLI.
# ----------------------------------------------------------------------


def _build_default_corpus() -> BenchmarkCorpus:
    documents = [
        (
            1,
            "https://example.com/ml-intro",
            "Introduction to Machine Learning",
            "Machine learning is a field of computer science that gives computers the ability "
            "to learn without being explicitly programmed.",
        ),
        (
            2,
            "https://example.com/deep-learning",
            "Deep Learning Foundations",
            "Deep learning is a subset of machine learning that uses neural networks with "
            "many layers to model complex patterns.",
        ),
        (
            3,
            "https://example.com/transformers",
            "Transformers in NLP",
            "The transformer architecture underpins modern natural language processing models.",
        ),
        (
            4,
            "https://example.com/databases",
            "Relational Databases",
            "A relational database stores data in tables queried with SQL.",
        ),
        (
            5,
            "https://example.com/sql-tuning",
            "SQL Performance Tuning",
            "Indexing, statistics and query rewriting improve the performance of SQL workloads.",
        ),
        (
            6,
            "https://example.com/cooking",
            "Cooking Pasta",
            "Pasta recipes, Italian cuisine and beginner-friendly cooking guides.",
        ),
        (
            7,
            "https://example.com/python-intro",
            "Python for Data Science",
            "Python is widely used for data science thanks to numpy, pandas and scikit-learn.",
        ),
        (
            8,
            "https://example.com/vector-search",
            "Vector Search Primer",
            "Vector search embeds documents into a high-dimensional space and retrieves nearest "
            "neighbours based on similarity.",
        ),
        (
            9,
            "https://example.com/embeddings",
            "Embedding Models",
            "Embedding models project text into dense vectors that capture semantics.",
        ),
        (
            10,
            "https://example.com/ranking",
            "Learning to Rank",
            "Learning to rank trains a model to combine BM25 scores, link authority and "
            "freshness signals.",
        ),
    ]
    return BenchmarkCorpus(name="default", documents=documents)


def _build_default_queries() -> list[BenchmarkQuery]:
    return [
        BenchmarkQuery(
            query="machine learning",
            relevant=(1, 2),
            irrelevant=(4, 6),
        ),
        BenchmarkQuery(
            query="deep learning neural networks",
            relevant=(2, 1),
        ),
        BenchmarkQuery(
            query="transformer nlp",
            relevant=(3, 9),
        ),
        BenchmarkQuery(
            query="sql database",
            relevant=(4, 5),
        ),
        BenchmarkQuery(
            query="vector embeddings",
            relevant=(8, 9),
        ),
        BenchmarkQuery(
            query="cooking pasta",
            relevant=(6,),
        ),
        BenchmarkQuery(
            query="python data science",
            relevant=(7, 1),
        ),
        BenchmarkQuery(
            query="learning to rank",
            relevant=(10,),
        ),
    ]


def _format_results(results: Iterable[BenchmarkResult]) -> str:
    lines = ["method            P@5    P@10   R@10   MRR    nDCG@5 nDCG@10  avg ms"]
    for result in results:
        lines.append(
            f"{result.method:<16} "
            f"{result.precision_at_5:>5.3f} "
            f"{result.precision_at_10:>5.3f} "
            f"{result.recall_at_10:>5.3f} "
            f"{result.mrr:>5.3f} "
            f"{result.ndcg_at_5:>5.3f}  "
            f"{result.ndcg_at_10:>5.3f}  "
            f"{result.average_latency_ms:>6.1f}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PrivateSearch quality benchmarks")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "benchmarks" / "results" / "metrics.json",
        help="Path to write the JSON metrics file.",
    )
    args = parser.parse_args(argv)

    corpus = _build_default_corpus()
    queries = _build_default_queries()
    results = evaluate(corpus, queries)
    payload = {
        "corpus": corpus.name,
        "num_queries": len(queries),
        "results": [result.to_dict() for result in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(_format_results(results))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())