# Architecture Overview

PrivateSearch is a self-hostable search engine. The pipeline is entirely local: no query is proxied to Google/Bing, no analytics is collected by default.

```
Web → Crawler → HTML Processor → Document Store → Inverted Index → BM25 → Ranking → Search API → Web UI
                                   ↕                    ↕           ↕
                              PostgreSQL         Snapshot JSON   Hybrid (TF-IDF)
```

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Tokenizer | Implemented | `privatesearch/document_processing/tokenizer.py` |
| URL normalization + SSRF guard | Implemented | `privatesearch/document_processing/url_normalize.py` |
| HTML extraction | Implemented | `privatesearch/document_processing/html.py` |
| Inverted index (in-memory + snapshot) | Implemented | `privatesearch/indexing/` |
| BM25 (k1, b configurable) | Implemented | `privatesearch/retrieval/bm25.py` |
| Snippet + highlighting | Implemented | `privatesearch/retrieval/snippets.py` |
| PostgreSQL (SQLAlchemy, SQLite fallback) | Implemented | `privatesearch/storage/` |
| Async crawler + robots + frontier | Implemented | `privatesearch/crawler/` |
| Indexing pipeline | Implemented | `privatesearch/indexing/pipeline.py` |
| TF-IDF embeddings + vector store | Implemented | `privatesearch/embeddings/` |
| Hybrid search | Implemented | `privatesearch/retrieval/hybrid.py` |
| Ranking pipeline (title/URL/freshness/quality) | Implemented | `privatesearch/ranking/` |
| FastAPI search API | Implemented | `privatesearch/api/` + `apps/api/` |
| Next.js frontend | Implemented | `apps/web/` |
| Evaluation harness | Implemented | `benchmarks/evaluation/` |

## Data Flow

1. **Crawl.** `CrawlConfig → Frontier → Crawler (httpx async, semaphore-bounded BFS) → ExtractedDocument`.
2. **Store.** `Document` row written via `storage/repository.py`; content-hash deduplication.
3. **Index.** `IndexingPipeline.index_crawl_result` rebuilds the `InvertedIndex` and writes a snapshot JSON (`IndexSnapshot`).
4. **Search.** `GET /api/v1/search?q=...` loads the index from storage, runs `Retriever` (BM25) or `HybridSearch` (BM25+TF-IDF cosine), generates snippets.
5. **Frontend.** Next.js UI at `apps/web` proxies `/api/*` to the API via `next.config.mjs` rewrites.

## Persistence

- In-memory inverted index with `save_snapshot`/`load_snapshot` (JSON). Loaded from storage on API startup via `SearchServiceHolder`.
- `DATABASE_URL` selects the backend: `postgresql+asyncpg://...` for production, `sqlite:////...` when Postgres is unavailable (test/dev).

## Security Boundary

The crawler is the security-sensitive component: see `docs/crawler/design.md` and `SECURITY.md`. All outbound fetches pass `is_blocked_host` checks (private IP, localhost, cloud metadata endpoint).