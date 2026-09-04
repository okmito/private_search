# Ranking Signals

Each signal in `ranking/pipeline.py` maps to a `[0, 1]` `SignalScore`.

| Signal | Heuristic | Implemented |
|--------|-----------|-------------|
| Exact title match | `matched_query_terms / len(query)` over lowercased title tokens | Yes |
| URL relevance | `matched_query_terms / len(query)` over lowercased URL | Yes |
| Freshness | Neutral `0.5` today; design reserves age decay `1 - age/365` once `last_crawled_at` is joined from storage | Yes (stub) |
| Content quality | `sigmoid(doc_len/avgdl - 1)` in `[0,1]` | Yes |
| PageRank | Deferred — requires link-graph pass; framework leaves a `RankingSignal` slot | Planned |

Hybrid search (`retrieval/hybrid.py`) is orthogonal: `HybridSearch` normalizes BM25 by `max_bm25` and cosine (TF-IDF) by 1, then weights (`bm25_weight`, `semantic_weight`, `title_weight`).

Benchmarks compare `BM25` vs `Ranking(RankingConfig)` under `benchmarks/evaluation/runner.py` (P@5, P@10, R@10, MRR, nDCG@5, nDCG@10). See `benchmarks/results/metrics.json` after `python -m benchmarks.evaluation.runner`.