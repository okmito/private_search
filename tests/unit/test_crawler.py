"""Unit tests for the asynchronous crawler."""

from __future__ import annotations

from typing import Awaitable, Callable

import pytest

from privatesearch.crawler.crawler import CrawlConfig, Crawler
from privatesearch.crawler.robots import RobotsPolicy

pytestmark = pytest.mark.asyncio


FetchCallable = Callable[[str], Awaitable[tuple[int, str, dict[str, str]]]]


class FakeRobotsServer:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.robots_bodies: dict[str, str] = {}

    def __call__(self, url: str) -> Awaitable[tuple[int, str, dict[str, str]]]:
        async def _run() -> tuple[int, str, dict[str, str]]:
            self.calls.append(url)
            if url.endswith("/robots.txt"):
                body = self.robots_bodies.get(url, "")
                return 200, body, {"content-type": "text/plain"}
            if "/page" in url:
                body = (
                    "<html><head><title>Example</title></head>"
                    "<body><h1>Welcome</h1>"
                    "<p>This is the example page.</p>"
                    "<a href='/related'>related</a></body></html>"
                )
                return 200, body, {"content-type": "text/html"}
            if "/related" in url:
                return 200, "<html><body>Related</body></html>", {"content-type": "text/html"}
            if "/private" in url:
                return 403, "Forbidden", {"content-type": "text/plain"}
            return 404, "Not Found", {"content-type": "text/plain"}

        return _run()


@pytest.fixture
def fake_fetcher() -> FakeRobotsServer:
    return FakeRobotsServer()


async def test_crawler_fetches_seed_and_follows_links(fake_fetcher: FakeRobotsServer) -> None:
    config = CrawlConfig(
        seed_urls=["https://example.com/page"],
        allowed_domains=["example.com"],
        max_depth=2,
        max_pages=10,
        delay_seconds=0.0,
        concurrency=2,
    )
    crawler = Crawler(config, fetcher=fake_fetcher)
    result = await crawler.run()

    urls = {page.url for page in result.pages}
    assert "https://example.com/page" in urls
    assert "https://example.com/related" in urls
    assert result.stats.pages_failed == 0


async def test_crawler_skips_blocked_paths_in_robots(fake_fetcher: FakeRobotsServer) -> None:
    fake_fetcher.robots_bodies["https://example.com/robots.txt"] = (
        "User-agent: *\nDisallow: /private\n"
    )
    config = CrawlConfig(
        seed_urls=["https://example.com/page"],
        allowed_domains=["example.com"],
        max_depth=2,
        max_pages=10,
        delay_seconds=0.0,
        respect_robots=True,
    )
    crawler = Crawler(config, fetcher=fake_fetcher)
    result = await crawler.run()

    # Even though /private is a seed it must be skipped by the policy.
    fetched_urls = {page.url for page in result.pages}
    assert not any("/private" in url for url in fetched_urls)


async def test_crawler_respects_allowlist(fake_fetcher: FakeRobotsServer) -> None:
    config = CrawlConfig(
        seed_urls=["https://example.com/page"],
        allowed_domains=["other.com"],
        max_depth=2,
        max_pages=10,
        delay_seconds=0.0,
    )
    crawler = Crawler(config, fetcher=fake_fetcher)
    result = await crawler.run()
    assert result.pages == []
    # Even the robots.txt fetch should not have been issued.
    assert all(not url.startswith("https://example.com") for url in fake_fetcher.calls)


async def test_crawler_records_404_errors(fake_fetcher: FakeRobotsServer) -> None:
    config = CrawlConfig(
        seed_urls=["https://example.com/missing"],
        allowed_domains=["example.com"],
        max_depth=0,
        max_pages=5,
        delay_seconds=0.0,
    )
    crawler = Crawler(config, fetcher=fake_fetcher)
    result = await crawler.run()
    assert result.stats.pages_failed >= 1
    assert any("404" in error for _url, error in result.errors)


async def test_crawler_records_stats(fake_fetcher: FakeRobotsServer) -> None:
    config = CrawlConfig(
        seed_urls=["https://example.com/page"],
        allowed_domains=["example.com"],
        max_depth=2,
        max_pages=10,
        delay_seconds=0.0,
    )
    crawler = Crawler(config, fetcher=fake_fetcher)
    result = await crawler.run()
    assert result.stats.duration_seconds >= 0
    assert result.stats.pages_fetched >= 1
    assert result.stats.bytes_downloaded > 0