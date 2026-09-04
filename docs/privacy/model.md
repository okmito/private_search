# Privacy Model

PrivateSearch never requires Google/Bing/third-party search APIs. The default data flow is:

```
User → PrivateSearch API (self-hosted) → Inverted Index / PostgreSQL → Results
```

- Queries are not forwarded to any external service. External calls are limited to the crawler fetching sites the operator configured via `seed_urls`.
- No raw query logging by default. The API logs do not store the query string; the placeholder `scripts/e2e_smoke.py` and tests use an SQLite DB with no analytics.
- No analytics, no advertising. There is no telemetry endpoint.

If an embedding provider or other external service is proposed, it must be called out explicitly and approved (see `AGENTS.md` privacy gate).