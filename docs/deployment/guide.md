# Deployment

## Docker Compose (recommended)

```bash
docker compose up --build
# postgres  :5432  (pgvector/pgvector:pg16)
# api       :8000  (FastAPI, uvicorn)
# crawler   (one-shot: python -m apps.crawler --seed-urls https://example.com)
# frontend  :3000  (Next.js)
```

Environment (`.env`):

```
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql+asyncpg://privatesearch:changeme@postgres:5432/privatesearch
SEED_URLS=https://example.com
CRAWLER_ALLOWED_DOMAINS=example.com
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Local (no Docker)

Backend needs Python 3.11+; frontend needs Node 18+:

```bash
pip install -e ".[dev]"
# or: pip install -r requirements.txt  (if generated)

# SQLite fallback (no Postgres):
export DATABASE_URL=sqlite:///./data/privatesearch.sqlite
python -m apps.crawler --seed-urls https://example.com --max-pages 5
uvicorn apps.api.main:app --reload --port 8000

# Frontend:
cd apps/web && npm ci && npm run build && npm start
# or: npm run dev  (HMR)
```

## Windows

Use `python -m apps.crawler` and `npm.cmd` (PowerShell execution policy may block `npm` — use `npm.cmd` explicitly). `PYTHONPATH` handling for apps is encapsulated in `apps/crawler/__main__.py` and `conftest.py`.

## Rebuilding the Index

```
GET /api/v1/index/rebuild   → { "documents": N }
```

The API loads the `InvertedIndex` from storage at startup; `/index/rebuild` re-loads it without restarting.