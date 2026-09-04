# PrivateSearch

Open-source, self-hostable, privacy-first search engine with its own crawler, inverted index, BM25 retrieval, hybrid search, ranking pipeline, evaluation harness, and web UI.

## Features

- **Web Crawler** — Async BFS crawler (httpx), respects `robots.txt` + `Crawl-Delay`, domain allowlist, depth/page limits, SSRF guard.
- **Document Processing** — HTML (BeautifulSoup/lxml), content extraction, URL normalization, content-hash deduplication.
- **Inverted Index** — Real `term → [Posting(doc_id, tf, positions)]` with `DocumentField` metadata, JSON snapshot persistence, incremental updates.
- **BM25 Retrieval** — Okapi BM25 with configurable `k1`, `b`, smoothed IDF, deterministic ranking — tested against the textbook formula.
- **Semantic Search** — Pluggable `EmbeddingModel`; default TF-IDF + cosine (no ML deps), `InMemoryVectorStore`, swappable to transformer embeddings.
- **Hybrid Search** — `HybridSearch` (normalized BM25 + cosine) at `GET /api/v1/search/hybrid`.
- **Ranking Pipeline** — `RankingPipeline` with modular signals: exact title match, URL relevance, freshness, content quality (`RankingConfig` weights/toggles), explainable `RankedHit`.
- **Search API** — FastAPI, `GET /api/v1/search`, `/api/v1/search/hybrid`, `/documents/{id}`, `/suggestions`, `/health`, `/stats`, `/index/rebuild`; validation, pagination, secure headers, rate limit, CORS.
- **Web Interface** — Next.js 14 + TypeScript, search box, snippets with `<mark>` highlighting, pagination, suggestions, loading/error/empty states, dark/light (prefers-color-scheme).
- **Privacy-First** — No external search APIs, no query tracking, no analytics.
- **Benchmarking** — `benchmarks/evaluation` (P@K, R@K, MRR, nDCG@K) + `benchmarks/performance` (indexing/search latency). Measured numbers below.

## Architecture

```
Web → Crawler → Document Processing → Indexing → Retrieval → Ranking → Search API → Web Interface
                    ↓                      ↓
              Inverted Index         Vector Store (InMemoryVectorStore, pgvector-ready)
                    ↓                      ↓
              BM25 Scoring          Cosine (TF-IDF)
                    ↓                      ↓
                    └──────────→ Hybrid Ranking ←──────────┘
```

See `docs/architecture/overview.md`.

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
# api       http://localhost:8000   (health at /api/v1/health)
# frontend  http://localhost:3000
# postgres  :5432  (pgvector/pgvector:pg16, init at infrastructure/docker/init-db.sql)
```

### Local (no Docker, SQLite fallback)

```bash
pip install -e ".[dev]"
python -m apps.crawler --seed-urls https://example.com --max-pages 5 --delay 0.0 --print-stats

# API
uvicorn apps.api.main:app --reload   # http://localhost:8000
# or: python -m uvicorn apps.api.main:app --reload

# Frontend
cd apps/web && npm ci && npm run build && npm start   # http://localhost:3000
# dev: npm run dev
```

Env: see `.env.example`. `DATABASE_URL=sqlite:///./data/privatesearch.sqlite` works without Postgres; `postgresql+asyncpg://...` is used in Docker.

### Rebuild index

```bash
curl http://localhost:8000/api/v1/index/rebuild
```

## Project Structure

```
privatesearch/                  # installable package (pyproject.toml: where=["."])
  api/                          # FastAPI (app, schemas, dependencies)
  common/                       # Settings (pydantic-settings, env)
  crawler/                      # Frontier, RobotsPolicy, Crawler (httpx async)
  document_processing/          # tokenizer, url_normalize, html, hashing
  embeddings/                   # EmbeddingModel, TFIDFEmbedding, VectorStore
  indexing/                     # InvertedIndex, pipeline (storage ↔ index)
  ranking/                      # RankingPipeline + signals
  retrieval/                    # BM25, Retriever, HybridSearch, snippets
  storage/                      # SQLAlchemy models/engine/repository
apps/
  api/                          # uvicorn entry: apps.api.main:app (thin re-export)
  crawler/                      # CLI: python -m apps.crawler --seed-urls ...
  web/                          # Next.js 14 app (src/app, src/lib)
tests/
  unit/  integration/
benchmarks/
  evaluation/  performance/  results/
docs/
  architecture/  crawler/  indexing/  ranking/  privacy/  deployment/
scripts/
  smoke_test_api.py  e2e_smoke.py
infrastructure/docker/
  Dockerfile.api  Dockerfile.crawler  Dockerfile.web  init-db.sql
```

## Documentation

- [Architecture](docs/architecture/overview.md)
- [Crawler](docs/crawler/design.md)
- [Indexing](docs/indexing/inverted_index.md)
- [BM25](docs/ranking/bm25.md) · [Ranking signals](docs/ranking/signals.md)
- [Privacy](docs/privacy/model.md) · [Deployment](docs/deployment/guide.md)

## Search Quality Evaluation

Corpus: 10 docs, 8 queries (`benchmarks/evaluation/runner.py`). Run:

```bash
python -m benchmarks.evaluation.runner  # writes benchmarks/results/metrics.json
```

| Method | P@5 | P@10 | R@10 | MRR | nDCG@5 | nDCG@10 | avg ms |
|--------|-----|------|------|-----|--------|---------|--------|
| BM25 | 0.300 | 0.150 | 0.875 | 1.000 | 0.883 | 0.883 | ~0.0 |
| Ranking(RankingConfig) | 0.300 | 0.150 | 0.875 | 1.000 | 0.883 | 0.883 | ~0.0 |

## Performance

Synthetic corpus, local machine, in-memory index:

```bash
python -m benchmarks.performance.measure --documents 1000 --queries 500
# 1k docs:  indexing ~24k docs/sec,  search p50 0.57 ms  p95 0.67 ms  p99 0.87 ms  (~1.7k qps)
# 10k docs: indexing ~5.5k docs/sec, search p50 17 ms    p95 82 ms    p99 91 ms   (~47 qps)
```

```bash
python -m benchmarks.performance.measure --documents 10000 --queries 1000
```

Raw JSON at `benchmarks/results/performance.json` (1000-doc run shown above).

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/search?q=&page=&limit=` | BM25 search, pagination, snippets + highlighting |
| `GET /api/v1/search/hybrid?q=&page=&limit=` | Hybrid (TF-IDF cosine + BM25) |
| `GET /api/v1/documents/{id}` | Document detail |
| `GET /api/v1/suggestions?q=` | Prefix suggestions |
| `GET /api/v1/health` | `{"status":"ok","version","documents","terms"}` |
| `GET /api/v1/stats` | Index stats |
| `GET /api/v1/index/rebuild` | Rebuild index from storage |

## Tests

```bash
pytest -q
# 124 tests, ~86% coverage
python scripts/e2e_smoke.py   # crawl → index → search → hybrid (hits example.com live)
```

## Contributing / Security / License

- [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [LICENSE](LICENSE) (Apache-2.0)

## Roadmap

- [x] Tokenizer and inverted index
- [x] BM25 retrieval
- [x] Document storage (PostgreSQL/SQLAlchemy, SQLite fallback)
- [x] Search API
- [x] Frontend
- [x] Web crawler
- [x] Ranking signals (title, URL, freshness, quality)
- [x] Semantic search (pluggable TF-IDF; transformer swap-ready)
- [x] Hybrid retrieval
- [x] Explainable ranking
- [x] Benchmarking (quality + performance harnesses)
- [ ] Local LLM answer mode (RAG + citations, planned)
- [ ] PageRank over crawl link graph
- [ ] pgvector production vector store (InMemoryVectorStore is default)