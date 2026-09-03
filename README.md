# PrivateSearch

Open-source, self-hostable, privacy-first search engine with its own crawler, index, retrieval, and ranking pipeline.

## Features

- **Web Crawler** — Async crawler respecting `robots.txt`, crawl delays, and domain restrictions
- **Document Processing** — HTML parsing, content extraction, deduplication, normalization
- **Inverted Index** — Real inverted index with positional information and persistence
- **BM25 Retrieval** — Configurable BM25 implementation with proper term/document statistics
- **Semantic Search** — Vector embeddings with pgvector (planned)
- **Hybrid Ranking** — Combines lexical, semantic, link authority, freshness, and quality signals
- **Explainable Ranking** — Optional ranking explanations for debugging
- **Search API** — FastAPI-based REST API with pagination and highlighting
- **Web Interface** — Next.js + TypeScript search UI with dark/light mode
- **Privacy-First** — No external search APIs, no query tracking by default
- **Benchmarking** — Precision@K, Recall@K, MRR, nDCG@K evaluation framework

## Architecture

```
Web → Crawler → Document Processing → Indexing → Retrieval → Ranking → Search API → Web Interface
                    ↓                      ↓
              Inverted Index         Vector Index (pgvector)
                    ↓                      ↓
              BM25 Scoring          Semantic Similarity
                    ↓                      ↓
                    └──────────→ Hybrid Ranking ←──────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector extension
- Docker (optional, for containerized deployment)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/privatesearch.git
cd privatesearch

# Backend setup
cd apps/api
pip install -e ".[dev]"

# Frontend setup
cd ../web
npm install

# Database setup
createdb privatesearch
psql -d privatesearch -c "CREATE EXTENSION vector;"

# Run migrations
cd ../api
alembic upgrade head

# Start services
# Terminal 1: API server
cd apps/api && uvicorn main:app --reload

# Terminal 2: Frontend
cd apps/web && npm run dev

# Terminal 3: Crawler (optional)
cd apps/crawler && python -m crawler --seed-urls "https://example.com"
```

### Docker Deployment

```bash
docker compose up -d
```

## Project Structure

```
privatesearch/
├── apps/
│   ├── api/          # FastAPI search API
│   ├── crawler/      # Async web crawler
│   └── web/          # Next.js frontend
├── packages/
│   ├── indexing/     # Inverted index implementation
│   ├── retrieval/    # BM25 and retrieval logic
│   ├── ranking/      # Ranking signals and pipeline
│   ├── embeddings/   # Vector embeddings (planned)
│   ├── document_processing/  # HTML parsing, extraction
│   └── common/       # Shared utilities
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── benchmarks/
│   ├── datasets/
│   ├── queries/
│   ├── evaluation/
│   └── results/
├── docs/
│   ├── architecture/
│   ├── crawler/
│   ├── indexing/
│   ├── ranking/
│   ├── privacy/
│   └── deployment/
├── scripts/
├── infrastructure/
│   └── docker/
├── AGENTS.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── docker-compose.yml
└── pyproject.toml
```

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Crawler Design](docs/crawler/design.md)
- [Indexing System](docs/indexing/inverted_index.md)
- [BM25 Implementation](docs/ranking/bm25.md)
- [Ranking Signals](docs/ranking/signals.md)
- [Privacy Model](docs/privacy/model.md)
- [Deployment Guide](docs/deployment/guide.md)

## Search Quality Evaluation

See [benchmarks/results](benchmarks/results/) for measured evaluation metrics:

| Method | nDCG@10 | Precision@10 | Recall@10 | MRR |
|--------|---------|--------------|-----------|-----|
| BM25 | TBD | TBD | TBD | TBD |
| Vector | TBD | TBD | TBD | TBD |
| Hybrid | TBD | TBD | TBD | TBD |

*Results will be populated after benchmarking implementation.*

## Performance Metrics

| Component | Metric | Value |
|-----------|--------|-------|
| Search API | p50 latency | TBD |
| Search API | p95 latency | TBD |
| Search API | p99 latency | TBD |
| Indexer | docs/second | TBD |
| Crawler | pages/minute | TBD |

*Metrics will be populated after performance testing.*

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Security

See [SECURITY.md](SECURITY.md) for security policies and reporting.

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.

## Roadmap

- [x] Repository foundation
- [ ] Tokenizer and inverted index
- [ ] BM25 retrieval
- [ ] Document storage (PostgreSQL)
- [ ] Search API
- [ ] Basic frontend
- [ ] Web crawler
- [ ] Ranking signals (PageRank, freshness, quality)
- [ ] Semantic search (embeddings)
- [ ] Hybrid retrieval
- [ ] Explainable ranking
- [ ] Benchmarking framework
- [ ] Local LLM answer mode
- [ ] Performance optimization
- [ ] Security audit
- [ ] Production deployment docs