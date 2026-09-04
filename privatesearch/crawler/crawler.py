"""Asynchronous web crawler."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

import httpx

from privatesearch.common.config import Settings, get_settings
from privatesearch.crawler.frontier import Frontier, FrontierEntry
from privatesearch.crawler.robots import RobotsPolicy
from privatesearch.document_processing.html import ExtractedDocument, extract_document
from privatesearch.document_processing.url_normalize import (
    is_blocked_host,
    normalize_url,
)

__all__ = [
    "CrawlConfig",
    "CrawledPage",
    "CrawlResult",
    "CrawlStats",
    "Crawler",
]


logger = logging.getLogger(__name__)


FetchFn = Callable[[str], Awaitable[tuple[int, str, dict[str, str]]]]
"""Custom fetcher signature returning ``(http_status, body, headers)``."""


@dataclass(slots=True)
class CrawlConfig:
    seed_urls: Sequence[str] = field(default_factory=list)
    allowed_domains: Sequence[str] = field(default_factory=list)
    max_depth: int = 2
    max_pages: int = 100
    delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    max_response_bytes: int = 5 * 1024 * 1024
    user_agent: str = "PrivateSearch/0.1"
    concurrency: int = 4
    respect_robots: bool = True

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> CrawlConfig:
        settings = settings or get_settings()
        return cls(
            seed_urls=list(settings.crawler_allowed_domains),
            allowed_domains=list(settings.crawler_allowed_domains),
            max_depth=settings.crawler_max_depth,
            max_pages=settings.crawler_max_pages,
            delay_seconds=settings.crawler_delay_seconds,
            timeout_seconds=settings.crawler_timeout_seconds,
            max_response_bytes=settings.crawler_max_response_bytes,
            user_agent=settings.crawler_user_agent,
        )


@dataclass(slots=True)
class CrawledPage:
    url: str
    canonical_url: str
    title: str
    description: str
    body: str
    headings: list[str]
    links: list[str]
    language: str | None
    published_at: str | None
    fetched_at: dt.datetime
    status: int
    depth: int

    def to_extracted(self) -> ExtractedDocument:
        return ExtractedDocument(
            url=self.url,
            canonical_url=self.canonical_url,
            title=self.title,
            description=self.description,
            body=self.body,
            headings=list(self.headings),
            links=list(self.links),
            language=self.language,
            published_at=self.published_at,
        )


@dataclass(slots=True)
class CrawlStats:
    started_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    finished_at: dt.datetime | None = None
    pages_fetched: int = 0
    pages_failed: int = 0
    pages_skipped: int = 0
    bytes_downloaded: int = 0

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or dt.datetime.now(dt.UTC)
        return (end - self.started_at).total_seconds()

    @property
    def pages_per_minute(self) -> float:
        elapsed = self.duration_seconds
        if elapsed <= 0:
            return 0.0
        return (self.pages_fetched / elapsed) * 60


@dataclass(slots=True)
class CrawlResult:
    pages: list[CrawledPage] = field(default_factory=list)
    stats: CrawlStats = field(default_factory=CrawlStats)
    errors: list[tuple[str, str]] = field(default_factory=list)


class Crawler:
    """BFS-based asynchronous web crawler.

    The crawler enforces SSRF protection by validating every URL with
    :func:`is_blocked_host` and by refusing to follow any URL whose hostname
    is not in the configured allowlist. ``robots.txt`` is consulted via
    :class:`RobotsPolicy`. Crawl delays are enforced per host.
    """

    def __init__(
        self,
        config: CrawlConfig,
        *,
        fetcher: FetchFn | None = None,
        client: httpx.AsyncClient | None = None,
        robots: RobotsPolicy | None = None,
    ) -> None:
        self.config = config
        self.frontier = Frontier()
        self.robots = robots or RobotsPolicy()
        self.robots.set_user_agent(config.user_agent)
        self._owns_client = client is None and fetcher is None
        self._client = client
        self._fetcher = fetcher or self._default_fetch
        self._last_request: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------
    async def run(self) -> CrawlResult:
        result = CrawlResult()
        if not self.config.seed_urls:
            logger.warning("Crawler has no seed URLs; returning empty result")
            result.stats.finished_at = dt.datetime.now(dt.UTC)
            return result

        allowed_hosts = {h.lower() for h in self.config.allowed_domains}
        for seed in self.config.seed_urls:
            normalized = normalize_url(seed)
            if normalized is None:
                continue
            if allowed_hosts and normalized.host not in allowed_hosts:
                logger.info("Skipping seed outside allowlist: %s", normalized.url)
                continue
            if is_blocked_host(normalized.host):
                logger.warning("Refusing to crawl blocked host: %s", normalized.host)
                continue
            self.frontier.push(normalized.url, depth=0)

        if self.config.respect_robots:
            await self._bootstrap_robots()

        semaphore = asyncio.Semaphore(max(1, self.config.concurrency))

        try:
            while self.frontier and result.stats.pages_fetched < self.config.max_pages:
                batch: list[FrontierEntry] = []
                while (
                    self.frontier
                    and len(batch) < max(1, self.config.concurrency)
                    and result.stats.pages_fetched + len(batch) < self.config.max_pages
                ):
                    entry = self.frontier.pop()
                    if entry is None:
                        break
                    batch.append(entry)
                if not batch:
                    break
                tasks = [
                    asyncio.create_task(
                        self._process_entry(entry, semaphore, result, allowed_hosts)
                    )
                    for entry in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if self._owns_client and self._client is not None:
                await self._client.aclose()

        result.stats.finished_at = dt.datetime.now(dt.UTC)
        return result

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------
    async def _process_entry(
        self,
        entry: FrontierEntry,
        semaphore: asyncio.Semaphore,
        result: CrawlResult,
        allowed_hosts: set[str],
    ) -> None:
        assert entry is not None
        async with semaphore:
            await self._enforce_delay(entry.url)
            decision = self.robots.can_fetch(entry.url) if self.config.respect_robots else None
            if decision is not None and not decision.allowed:
                result.stats.pages_skipped += 1
                result.errors.append((entry.url, "blocked by robots.txt"))
                return
            try:
                http_status, body, headers = await self._fetcher(entry.url)
            except Exception as exc:  # noqa: BLE001 - report any fetch error
                result.stats.pages_failed += 1
                result.errors.append((entry.url, str(exc)))
                return

            if http_status >= 400:
                result.stats.pages_failed += 1
                result.errors.append((entry.url, f"HTTP {http_status}"))
                return
            content_length = len(body.encode("utf-8", errors="ignore"))
            if content_length > self.config.max_response_bytes:
                result.stats.pages_failed += 1
                result.errors.append((entry.url, "Response too large"))
                return
            result.stats.bytes_downloaded += content_length

            extracted = extract_document(body, entry.url)
            if not extracted.body.strip() and not extracted.title:
                result.stats.pages_skipped += 1
                result.errors.append((entry.url, "Empty document"))
                return

            page = CrawledPage(
                url=extracted.url,
                canonical_url=extracted.canonical_url or extracted.url,
                title=extracted.title,
                description=extracted.description,
                body=extracted.body,
                headings=list(extracted.headings),
                links=list(extracted.links),
                language=extracted.language,
                published_at=extracted.published_at,
                fetched_at=dt.datetime.now(dt.UTC),
                status=http_status,
                depth=entry.priority,
            )
            result.pages.append(page)
            result.stats.pages_fetched += 1

            if entry.priority >= self.config.max_depth:
                return
            for link in extracted.links:
                normalized = normalize_url(link)
                if normalized is None:
                    continue
                if allowed_hosts and normalized.host not in allowed_hosts:
                    continue
                if is_blocked_host(normalized.host):
                    continue
                if normalized.url in self.frontier:
                    continue
                self.frontier.push(normalized.url, depth=entry.priority + 1)

    async def _enforce_delay(self, url: str) -> None:
        host = (self._client.base_url.host if self._client else None) or _host_of(url)
        if not host:
            return
        delay = self.robots.delay_for(host) or self.config.delay_seconds
        last = self._last_request.get(host, 0.0)
        now = time.monotonic()
        wait = delay - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request[host] = time.monotonic()

    async def _bootstrap_robots(self) -> None:
        hosts: set[str] = set()
        for entry_url in self.frontier:
            normalized = normalize_url(entry_url)
            if normalized:
                hosts.add(_host_of(normalized.url))
        for host in hosts:
            if not host:
                continue
            scheme = "https"
            robots_url = f"{scheme}://{host}/robots.txt"
            try:
                status, body, _ = await self._fetcher(robots_url)
            except Exception:  # noqa: BLE001 - ignore robots fetch errors
                continue
            if status == 200 and body:
                self.robots.load(robots_url, body)

    async def _default_fetch(self, url: str) -> tuple[int, str, dict[str, str]]:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=False,
            )
        response = await self._client.get(url, follow_redirects=False)
        text = response.text
        return response.status_code, text, dict(response.headers)


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").lower()
