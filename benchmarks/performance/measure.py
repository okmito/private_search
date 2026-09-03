"""Measure search latency and indexing throughput.

The script generates a deterministic synthetic corpus of N documents, builds
the inverted index and measures:

* Indexing latency (seconds to add N documents)
* Search latency at the p50, p95 and p99 percentile
* Documents-per-second during indexing

The numbers are written to ``benchmarks/results/performance.json`` and
printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.retrieval.bm25 import BM25


def _generate_corpus(num_documents: int) -> list[tuple[int, str, str, str]]:
    vocabulary = [
        "machine", "learning", "deep", "neural", "networks", "databases",
        "relational", "sql", "tables", "python", "search", "engine",
        "privacy", "crawler", "index", "ranking", "bm25", "vector",
        "embedding", "hybrid", "fastapi", "nextjs", "typescript",
    ]
    documents = []
    for i in range(num_documents):
        body_tokens = [vocabulary[(i * j) % len(vocabulary)] for j in range(1, 12)]
        body = " ".join(body_tokens)
        title = f"Document {i}"
        url = f"https://example.com/d/{i}"
        documents.append((i, url, title, body))
    return documents


def measure_indexing(num_documents: int) -> dict[str, float]:
    corpus = _generate_corpus(num_documents)
    index = InvertedIndex()
    start = time.perf_counter()
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)
    duration = time.perf_counter() - start
    return {
        "documents": float(num_documents),
        "duration_seconds": duration,
        "documents_per_second": num_documents / duration if duration else 0.0,
    }


def measure_search(num_documents: int, num_queries: int) -> dict[str, float]:
    corpus = _generate_corpus(num_documents)
    index = InvertedIndex()
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)
    bm25 = BM25(index)

    queries = [f"machine {word}" for word in ["learning", "deep", "search"]]
    latencies: list[float] = []
    for i in range(num_queries):
        query = queries[i % len(queries)]
        start = time.perf_counter()
        bm25.score(query)
        latencies.append((time.perf_counter() - start) * 1000)
    latencies.sort()
    p50 = latencies[int(0.50 * (len(latencies) - 1))]
    p95 = latencies[int(0.95 * (len(latencies) - 1))]
    p99 = latencies[min(len(latencies) - 1, int(0.99 * (len(latencies) - 1)))]
    return {
        "documents": float(num_documents),
        "queries": float(num_queries),
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "average_ms": statistics.fmean(latencies),
        "queries_per_second": num_queries / (sum(latencies) / 1000) if latencies else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure indexing and search performance")
    parser.add_argument("--documents", type=int, default=1000)
    parser.add_argument("--queries", type=int, default=200)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "benchmarks" / "results" / "performance.json",
    )
    args = parser.parse_args(argv)

    indexing = measure_indexing(args.documents)
    search = measure_search(args.documents, args.queries)
    payload = {
        "indexing": indexing,
        "search": search,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Indexing")
    for key, value in indexing.items():
        print(f"  {key}: {value}")
    print("Search")
    for key, value in search.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())