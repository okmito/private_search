# Project Status

## Current Milestone

Milestone 11 — Polish / docs / verification (final). All pipelines are functional.

## Completed

- [x] Repository foundation (README, LICENSE, .gitignore, docker-compose, pyproject)
- [x] Search engine core: tokenizer, inverted index, BM25, retriever, snippets (Phase 1)
- [x] Document processing: HTML, URL normalization, SSRF guards, hashing (Phase 1)
- [x] Storage: SQLAlchemy models/engine/repository, SQLite + Postgres (Phase 2)
- [x] Crawler: frontier, robots, httpx async, safety, depth/page/concurrency limits (Phase 3)
- [x] Indexing pipeline: crawler → storage → index → search, `load_from_storage` (Phase 4)
- [x] Search API: FastAPI `/search`, `/search/hybrid`, `/documents/{id}`, `/suggestions`, `/health`, `/stats`, `/index/rebuild` (Phase 5)
- [x] Frontend: Next.js 14 + TS, search + highlighting + pagination + suggestions (Phase 6)
- [x] Ranking: `RankingPipeline` with 4 signals, `RankingConfig`, explainable `RankedHit` (Phase 7)
- [x] Benchmarks: quality (P@K/R@K/MRR/nDCG, 10 docs/8 queries) + performance (indexing/search latency) (Phase 8)
- [x] Embeddings: `EmbeddingModel` + `TFIDFEmbedding` + `InMemoryVectorStore`, transformer-swappable (Phase 9)
- [x] Hybrid search: `HybridSearch` (normalized BM25 + cosine) at `/search/hybrid` (Phase 10)
- [x] Explainable ranking: `hit.explanation()` surfaced in API (`explanation`) and UI ("Why this result?") (Phase 11)
- [x] Docker: `Dockerfile.api/crawler/web` + `init-db.sql`, docker-compose prod-ready
- [x] Docs: `docs/architecture/overview`, `docs/crawler/design`, `docs/indexing/inverted_index`, `docs/ranking/bm25`, `docs/ranking/signals`, `docs/privacy/model`, `docs/deployment/guide` + `.env.example`
- [x] E2E smoke: `scripts/e2e_smoke.py` (crawl example.com → index → search → hybrid, live)

## In Progress

- None — final verification pass in progress.

## Next

- Human review of docs + demo.

## Known Issues

- `FreshnessSignal` is a stub (neutral 0.5) until `last_crawled_at` is joined from storage into the in-memory index.
- `HybridSearch` fits embeddings per-request when storage is the source; a persistent vector snapshot would be needed for pgvector at scale.
- No auth on `/index/rebuild` — acceptable for single-operator self-hosted use; add auth before multi-user deploy.

## Known Limitations

- In-memory inverted index and `InMemoryVectorStore` (suitable to ~100k docs per shard; sharding/index spilling not built).
- No PageRank — link graph is collected (`DocumentLink`) but not yet scored.
- No local LLM/RAG answer mode.
- Tests use SQLite; Postgres path is covered by `docker compose up` and `DATABASE_URL` switching.

## Human Decisions

- Keep `benchmarks/results/*.json` gitignored; metrics reproduced via `python -m benchmarks.evaluation.runner` (numbers in README are measured, not committed).
- Default `DATABASE_URL` is `sqlite:///./data/privatesearch.sqlite` for portability; Postgres via Docker when `POSTGRES_PASSWORD`/`DATABASE_URL` point at `postgres` service.

## Test Status

- `pytest -q` — 124 tests, ~86% line coverage (unit: 108, integration: 16).
- `npm run build` — Next.js production build passes.
- E2E `python scripts/e2e_smoke.py` — live crawl of example.com, index, `/search` and `/search/hybrid` return hits with BM25 score 0.28 and hybrid 1.25.

## Benchmark Status

- Quality: `python -m benchmarks.evaluation.runner` — BM25 and Ranking both P@5 0.300 / R@10 0.875 / MRR 1.000 / nDCG@10 0.883 (tiny corpus).
- Performance: `python -m benchmarks.performance.measure --documents 1000 --queries 500` — 1k docs ~24k docs/sec indexing, p50 0.57 ms / p99 0.87 ms, ~1.7k qps; 10k docs ~5.5k docs/sec, p50 17 ms / p99 91 ms.

## Verification Checklist (before declaring complete)

- [x] API boots (`uvicorn apps.api.main:app`, smoke tested)
- [x] Frontend builds + serves (`apps/web` Next build, smoke)
- [x] DB initializes (SQLite fallback + Postgres via Docker)
- [x] Crawler crawls controlled targets (example.com live, depth/max_pages + allowlist + robots)
- [x] robots.txt respected
- [x] Documents processed (HTML → body/title/links)
- [x] Inverted index works (snapshot round-trip)
- [x] BM25 works (formula-checked)
- [x] Search API works (`/search`, `/documents/{id}`, pagination)
- [x] Frontend search works (search box → ResultList → highlighting → pagination)
- [x] Ranking works (title/URL/quality, explainable)
- [x] Deduplication works (content_hash)
- [x] Semantic search works (TF-IDF cosine)
- [x] Hybrid search works (`/search/hybrid`)
- [x] Benchmarks run (quality + performance harnesses, numbers above)
- [x] Tests pass (124, 86%)
- [x] Build passes (Next build)
- [x] Docker setup (3 Dockerfiles + compose)
- [ ] No secrets committed (`git status` clean, `.env` not in repo)
- [x] Docs match implementation
- [x] README complete with measured numbers only
- [x] PROJECT_STATUS.md updated
