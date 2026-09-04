# Crawler Design

## Responsibilities

- BFS URL frontier (`crawler/frontier.py`) with depth priority and seen-set deduplication.
- Async fetching via `httpx.AsyncClient`, bounded by `CrawlConfig.concurrency` (semaphore) and `delay_seconds` (per-host sleep).
- `robots.txt` parsing (`crawler/robots.py`): per-host `RobotFileParser` cache, `Crawl-Delay` extraction, `can_fetch` gate before every fetch and during frontier expansion.
- HTML extraction (`document_processing/html.py`): BeautifulSoup/lxml, strip `script/style/noscript/iframe`, extract title/description/headings/body/links/language with canonical URL resolution.
- Safety (`document_processing/url_normalize.py`): scheme allowlist (http/https), hostname normalization, default-port stripping, query-parameter allowlist, same for redirect targets, `is_blocked_host` via `getaddrinfo` + `ipaddress` checks.

## SSRF Protection

`is_blocked_host(host)` rejects:

- `localhost`, `127.0.0.0/8`, `::1`, link-local, multicast, unspecified, reserved.
- Private ranges `10/8`, `172.16/12`, `192.168/16`.
- Cloud metadata `169.254.169.254`.
- Any hostname that fails DNS (`getaddrinfo` error) is treated as blocked.

The allowlist (`allowed_domains`) is an additional gate enforced at seed and at link discovery.

## Frontier

`Frontier` is a heap keyed by `(depth, insertion_counter)`. `pop` discards the URL from the seen set so it can be re-queued only by link discovery (already-seen links are not re-pushed by `Crawler._process_entry`).

## Tests

- `test_frontier.py` — deduplication, BFS order.
- `test_robots.py` — disallow, allow, crawl-delay, unknown host, per-user-agent rules.
- `test_crawler.py` — mocked fetcher: BFS expansion to depth, robots skip, allowlist enforcement, 404 handling, max_pages limit.
- E2E `test_pipeline.py` and `scripts/e2e_smoke.py` wire crawler → storage → index → search.