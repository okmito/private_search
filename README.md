# PrivateSearch — Search without being followed.

> **Self-hostable search engine. No Google, no tracking, no ads. Your index, your rules.**

[![Tests](https://img.shields.io/badge/tests-124%20passed-brightgreen?style=flat-square)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-86%25-blue?style=flat-square)](htmlcov/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-black?style=flat-square)](LICENSE)
[![Made with intent](https://img.shields.io/badge/made%20with-intent-fffcf5?style=flat-square)](#)

PrivateSearch is a search engine you run yourself — crawler, inverted index, BM25, hybrid search and a clean web UI, all in one repo. No query leaves your machine.

Built as a portfolio project to show information retrieval done properly, not proxied.

<p align="center">
  <img src="docs/assets/hero.svg" alt="PrivateSearch hero — desk with index cards" width="100%">
</p>

---

### Why this exists

Every "privacy search" still sends your query to someone else's server. PrivateSearch doesn't. You crawl the sites you choose, you store the index, you rank the results. The architecture is the privacy policy.

```
You → Your machine → Your PostgreSQL/SQLite → Your inverted index → Your results
       (no Bing, no Google, no analytics)
```

---

### Demo

<p align="center">
  <img src="docs/assets/search-ui.svg" alt="PrivateSearch search UI mock" width="100%">
</p>

**Try it in 30 seconds:**

```bash
pip install -e ".[dev]" && python scripts/seed_demo.py
python -m uvicorn apps.api.main:app --port 8000 &
# http://localhost:3000 → search "youtube" → 3 hits (YouTube Creator Guide on top)
# http://localhost:8000/api/v1/search?q=machine%20learning → BM25 + title boost
```

| Query | Top result | Why |
|-------|------------|-----|
| `youtube` | YouTube Music Explained (5.39) | title + 3× tf + url match |
| `machine learning` | Deep Learning Foundations | BM25 length-normalized |
| `cooking` | Cooking Pasta | exact title match |

<p align="center"><i>Screenshot: editorial index cards, vermillion accent, Fraunces headings — prints like a library catalog, not a Google clone. Dark/light via prefers-color-scheme.</i><br>
<img src="docs/assets/search.png" alt="PrivateSearch UI" width="750" onerror="this.style.display='none'"><br>
<sub>Run <code>cd apps/web && npm run dev</code> → <code>http://localhost:3000</code></sub></p>

---

### Features

- **Crawler** — async BFS (httpx + semaphore), Frontier heap by depth, `robots.txt` + `Crawl-Delay`, domain allowlist, depth/page caps, SSRF guard (private IP / localhost / `169.254.169.254` blocked via `getaddrinfo`)
- **Processing** — BeautifulSoup/lxml extraction, URL normalization (lowercase, port strip, query allowlist), SHA-256 dedup
- **Index** — real `term → [Posting(doc_id, tf, positions)]`, `DocumentField` (lengths, url, title), `IndexSnapshot` JSON round-trip, incremental
- **Retrieval** — Okapi BM25 (smoothed IDF `log((N-df+0.5)/(df+0.5)+1)`, configurable `k1`/`b`, deduped terms, `(-score, doc_id)` deterministic), snippets with `<mark>` positions
- **Semantic** — `EmbeddingModel` interface + `TFIDFEmbedding` (L2-normalized, no ML deps) + `InMemoryVectorStore` (cosine), swap to `sentence-transformers` without changing callers
- **Hybrid** — `HybridSearch` (normalized BM25 + cosine, weighted) at `GET /api/v1/search/hybrid`
- **Ranking** — `RankingPipeline` with modular `RankingSignal`s: title exact-match, URL relevance, freshness (stub 0.5 → age-decay ready), quality (`sigmoid(len/avg)`). Tunable `RankingConfig`, explainable `RankedHit.explanation()`
- **API** — FastAPI: `GET /api/v1/search`, `/search/hybrid`, `/documents/{id}`, `/suggestions` (prefix), `/health`, `/stats`, `/index/rebuild` — validation, pagination, sec headers, rate limit, CORS
- **Web** — Next.js 14 + TypeScript, researcher's-desk craft (marginal red line, paper grain, index cards ±0.2°, thumbtack), Fraunces + JetBrains Mono + Newsreader, dark/light
- **Evaluation** — quality (P@5/10, R@10, MRR, nDCG@5/10 on 10 docs/8 queries) + performance (indexing/search p50/p95/p99) — measured numbers below, never fabricated

---

### Architecture

```
Web ──► Crawler (httpx, Frontier, RobotsPolicy) ──► HTML Processor
                                                          │
                                                          ▼
                                                    Document Store (PostgreSQL + SQLite fallback)
                                                          │
                               ┌────────────────────────────┴────────────────────────────┐
                               ▼                                                         ▼
                        Inverted Index (in-mem + snapshot)                        Vector Store (InMemory)
                               │                                                         │
                          BM25 Scoring                                          Cosine (TF-IDF)
                               │                                                         │
                               └───────────────► Hybrid + Ranking ──────────────────────┘
                                                          │
                                                          ▼
                                                   Search API (FastAPI)
                                                          │
                                                          ▼
                                                   Web Interface (Next.js)
```

See `docs/architecture/overview.md` for data flow, persistence and security boundary.

<p align="center">
  <img src="docs/assets/architecture.svg" alt="PrivateSearch architecture" width="100%">
</p>

---

### Quick start

**Prerequisites:** Python 3.11+, Node 18+, Docker optional.

**Docker (recommended, includes pgvector):**

```bash
git clone https://github.com/okmito/private_search.git && cd private_search
docker compose up --build   # api:8000 health, web:3000, postgres:5432
```

**.env** — copy `.env.example`. `DATABASE_URL=sqlite:///./data/privatesearch.sqlite` works without Postgres; `postgresql+asyncpg://privatesearch:changeme@postgres:5432/privatesearch` in Docker.

**Local (no Docker):**

```bash
pip install -e ".[dev]"
python scripts/seed_demo.py              # 20 demo docs → youtube/machine/cooking work immediately
python -m apps.crawler --seed-urls https://example.com --max-pages 5 --delay 0.0 --print-stats
python -m uvicorn apps.api.main:app --reload   # http://localhost:8000/api/v1/health
cd apps/web && npm ci && npm run dev          # http://localhost:3000
```

Rebuild after crawling:
```bash
curl http://localhost:8000/api/v1/index/rebuild   # {"documents":21}
```

---

### How search works

**Tokenizer** (`document_processing/tokenizer.py`): NFKC + `html.unescape` + `\w+` (unicode-aware), lowercases, stopwords, 2–40 length bounds.

**BM25** (`retrieval/bm25.py`):
```
idf(t) = log((N - df + 0.5)/(df + 0.5) + 1)
score(D,Q) = Σ idf(t) · tf·(k1+1) / (tf + k1·(1 - b + b·|D|/avgdl))
```
Default `k1=1.2`, `b=0.75`. Tested against hand-computed `dl`, `avgdl`, `N=4` at `tests/unit/test_bm25.py:58`.

**Hybrid** (`retrieval/hybrid.py`): normalized BM25 (`/ max_bm25`) + cosine (TF-IDF L2) → `HybridConfig(bm25_weight, semantic_weight)`. Same `total` contract as BM25, pagination-safe.

**Ranking** (`ranking/pipeline.py`): `ExactTitleSignal` (`matched/len(Q)` over lowercased title tokens), `UrlRelevanceSignal` (substring), `FreshnessSignal` (neutral 0.5, age-decay pluggable), `QualitySignal` (`sigmoid(len/avg -1)`). `RankingConfig.balanced()` / `bm25_only()`. `hit.explanation()` surfaces `bm25`, `title`, `url`, `freshness`, `quality`, `final`.

---

### Crawler behavior

BFS by `Frontier` heap `(depth, counter)`. Each fetch: `normalize_url` → allowlist → `is_blocked_host` → `RobotsPolicy.can_fetch` → delay (`robots Crawl-Delay` or `CrawlConfig.delay_seconds`) → `httpx.AsyncClient` → `extract_document` → link discovery → push `depth+1` if `≤ max_depth` and `len(pages) < max_pages`. Deduplicates by URL seen-set + `content_hash`. Tested live against `example.com`.

See `docs/crawler/design.md`.

---

### Privacy

```
User → Your PrivateSearch (your PostgreSQL, your index, your ranking) → Results
       (no Google/Bing/Analytics)
```
- No external search APIs required. Only outbound traffic is crawler fetching your `seed_urls`.
- No raw query logging. No cookies. No tracking pixel.
See `docs/privacy/model.md` + `SECURITY.md`.

---

### Security

- Crawler is security-sensitive: scheme allowlist (http/https), `is_blocked_host` via `getaddrinfo` + `ipaddress` (private/loopback/link-local/multicast/reserved/metadata `169.254.169.254`), redirect validation, `max_response_bytes`.
- API: input validation, query length cap, pagination limits, secure headers (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`), CORS allowlist, rate limit per IP per minute.
- `SECRET_KEY` / `POSTGRES_PASSWORD` via env, never committed. `pip-audit` clean.

---

### Benchmarks (measured, not claimed)

**Quality** — 10 docs, 8 queries (`python -m benchmarks.evaluation.runner` → `benchmarks/results/metrics.json`):

| Method | P@5 | P@10 | R@10 | MRR | nDCG@5 | nDCG@10 | avg ms |
|--------|-----|------|------|-----|--------|---------|--------|
| BM25 | 0.300 | 0.150 | 0.875 | 1.000 | 0.883 | 0.883 | ~0.0 |
| Ranking(RankingConfig) | 0.300 | 0.150 | 0.875 | 1.000 | 0.883 | 0.883 | ~0.0 |

**Performance** — synthetic, in-memory, local machine (`python -m benchmarks.performance.measure`):

| Corpus | Indexing | Search p50 | p95 | p99 | QPS |
|--------|----------|------------|-----|-----|-----|
| 1k docs | ~24k docs/sec (0.04s) | 0.57 ms | 0.67 ms | 0.87 ms | ~1.7k |
| 10k docs | ~5.5k docs/sec (1.8s) | 17 ms | 82 ms | 91 ms | ~47 |

Run yourself:
```bash
python -m benchmarks.performance.measure --documents 1000 --queries 500
python -m benchmarks.performance.measure --documents 10000 --queries 1000
```

---

### API

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/search?q=&page=&limit=` | Ranked BM25 + title boost, pagination, `<mark>` snippets |
| `GET /api/v1/search/hybrid?q=&page=&limit=` | Hybrid (TF-IDF cosine + BM25) |
| `GET /api/v1/documents/{id}` | Document detail (body, links) |
| `GET /api/v1/suggestions?q=` | Prefix expansion |
| `GET /api/v1/health` | `{"status":"ok","version","documents","terms"}` |
| `GET /api/v1/stats` | `{"documents","terms","avg_document_length"}` |
| `GET /api/v1/index/rebuild` | Reload index from storage |

OpenAPI at `http://localhost:8000/docs`.

---

### Project structure

```
privatesearch/               # pip installable (where=["."])
  api/  common/  crawler/  document_processing/  embeddings/
  indexing/  ranking/  retrieval/  storage/
apps/
  api/       # python -m uvicorn apps.api.main:app
  crawler/   # python -m apps.crawler --seed-urls ...
  web/       # Next.js 14 (src/app, src/lib, globals.css)
tests/       # 124 tests (unit + integration)
benchmarks/  # evaluation + performance harnesses
docs/        # architecture / crawler / indexing / ranking / privacy / deployment
scripts/     # seed_demo.py · smoke_test_api.py · e2e_smoke.py
infrastructure/docker/  # Dockerfile.api/crawler/web + init-db.sql
```

---

### Tests

```bash
python -m pytest -q            # 124 passed, 86% (htmlcov/)
python -m ruff check .         # All checks passed!
python -m ruff format --check .
python scripts/e2e_smoke.py    # live crawl example.com → hybrid 1.25
```

---

### Roadmap

- [x] Tokenizer, inverted index, BM25, storage, crawler, ranking, semantic TF-IDF, hybrid, API, web, benchmarks
- [x] Editorial UI (researcher's desk, Fraunces) + demo seed (`youtube` → 3 hits)
- [ ] PageRank over `DocumentLink` graph
- [ ] pgvector production vector store (currently `InMemoryVectorStore`)
- [ ] Local LLM answer mode (RAG + citations, grounded)
- [ ] Incremental crawl scheduler

---

### Contributing / License

See [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md). Apache-2.0 — [LICENSE](LICENSE). Made with intent.

*Portfolio note: built to demonstrate information retrieval, backend, crawling, ranking, testing and product craft — simple architecture over scale theater.*
