"""Integration tests for the crawling/indexing pipeline."""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable

import pytest

from privatesearch.crawler.crawler import CrawlConfig, CrawledPage, Crawler
from privatesearch.indexing.pipeline import IndexingPipeline, SearchService
from privatesearch.storage.engine import close_engine, init_database

FetchCallable = Callable[[str], Awaitable[tuple[int, str, dict[str, str]]]]


def _fake_pages() -> list[CrawledPage]:
    base = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    return [
        CrawledPage(
            url="https://example.com/intro",
            canonical_url="https://example.com/intro",
            title="Machine Learning Introduction",
            description="An overview of machine learning.",
            body="Machine learning is fun. Deep learning uses neural networks.",
            headings=["Machine Learning Introduction"],
            links=["https://example.com/deep", "https://example.com/related"],
            language="en",
            published_at=None,
            fetched_at=base,
            status=200,
            depth=0,
        ),
        CrawledPage(
            url="https://example.com/deep",
            canonical_url="https://example.com/deep",
            title="Deep Learning Deep Dive",
            description="A primer on deep learning.",
            body="Deep learning is a subset of machine learning using neural networks.",
            headings=["Deep Learning Deep Dive"],
            links=[],
            language="en",
            published_at=None,
            fetched_at=base,
            status=200,
            depth=1,
        ),
        CrawledPage(
            url="https://example.com/databases",
            canonical_url="https://example.com/databases",
            title="Relational Databases",
            description="Overview of relational databases and SQL.",
            body="A relational database organises data in tables queried with SQL.",
            headings=["Relational Databases"],
            links=[],
            language="en",
            published_at=None,
            fetched_at=base,
            status=200,
            depth=0,
        ),
    ]


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "integration.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    close_engine()
    init_database()
    yield
    close_engine()


async def test_crawler_pipeline_indexes_pages() -> None:
    pages = _fake_pages()
    await _run_crawler_pipeline(pages)


@pytest.mark.asyncio
async def test_crawler_pipeline_follows_links() -> None:
    # The fetcher is dynamic: it serves the four crawled pages.
    pages = _fake_pages()

    class DynamicFetcher:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def __call__(self, url: str):
            self.calls.append(url)
            if url.endswith("/robots.txt"):
                return 200, "User-agent: *\nDisallow: /private\n", {}
            for page in pages:
                if page.url == url:
                    return 200, _page_html(page), {"content-type": "text/html"}
            return 404, "Not Found", {}

    fetcher = DynamicFetcher()
    config = CrawlConfig(
        seed_urls=[pages[0].url],
        allowed_domains=["example.com"],
        max_depth=2,
        max_pages=10,
        delay_seconds=0.0,
    )
    crawler = Crawler(config, fetcher=fetcher)
    crawl_result = await crawler.run()

    fetched_urls = {page.url for page in crawl_result.pages}
    assert fetched_urls == {
        "https://example.com/deep",
        "https://example.com/intro",
    }

    pipeline = IndexingPipeline()
    indexing = pipeline.index_crawl_result(crawl_result)
    assert indexing.inserted == 2

    service = SearchService(index=pipeline.index, pipeline=pipeline)
    results = service.search("machine learning", limit=5)
    assert any("machine" in r["url"] or "deep" in r["url"] for r in results)


async def _run_crawler_pipeline(pages: list[CrawledPage]) -> None:
    class FakeFetcher:
        def __init__(self, pages: list[CrawledPage]) -> None:
            self.pages = pages
            self.calls: list[str] = []

        async def __call__(self, url: str):
            self.calls.append(url)
            for page in self.pages:
                if page.url == url or page.url == url.rstrip("/"):
                    return 200, _page_html(page), {"content-type": "text/html"}
            if url.endswith("/robots.txt"):
                return 200, "User-agent: *\nDisallow: /private\n", {}
            return 404, "Not Found", {}

    fetcher = FakeFetcher(pages)
    config = CrawlConfig(
        seed_urls=[pages[0].url],
        allowed_domains=["example.com"],
        max_depth=2,
        max_pages=10,
        delay_seconds=0.0,
    )
    crawler = Crawler(config, fetcher=fetcher)
    crawl_result = await crawler.run()

    pipeline = IndexingPipeline()
    indexing = pipeline.index_crawl_result(crawl_result)

    assert indexing.inserted >= 2
    assert pipeline.index.stats.num_documents >= 2

    service = SearchService(index=pipeline.index, pipeline=pipeline)
    results = service.search("machine learning", limit=5)
    assert results
    top = results[0]
    assert top["score"] > 0
    assert top["url"]


def _page_html(page: CrawledPage) -> str:
    return (
        f"<html><head><title>{page.title}</title></head>"
        f"<body><h1>{page.title}</h1><p>{page.body}</p>"
        + "".join(f'<a href="{link}">link</a>' for link in page.links)
        + "</body></html>"
    )


def test_indexing_pipeline_handles_duplicates() -> None:
    pages = _fake_pages()
    pipeline = IndexingPipeline()
    first = pipeline.index_pages(pages)
    second = pipeline.index_pages(pages)

    assert first.inserted == 3
    assert first.duplicates == 0
    assert second.inserted == 0
    assert second.duplicates == 3


def test_indexing_pipeline_persists_to_storage() -> None:
    pages = _fake_pages()
    pipeline = IndexingPipeline()
    pipeline.index_pages(pages)

    # Reload from storage into a fresh index and ensure the documents match.
    reloaded = IndexingPipeline()
    count = reloaded.load_from_storage()
    assert count == 3

    # Verify the documents rows in storage.
    from privatesearch.storage.engine import session_scope
    from privatesearch.storage.repository import get_document_by_doc_id

    with session_scope() as session:
        docs = [get_document_by_doc_id(session, i + 1) for i in range(3)]
        assert all(doc is not None for doc in docs)
        titles = {doc.title for doc in docs if doc is not None}
        assert "Machine Learning Introduction" in titles


def test_indexing_pipeline_updates_existing_documents() -> None:
    pipeline = IndexingPipeline()
    page = _fake_pages()[0]
    pipeline.index_pages([page])

    updated_page = CrawledPage(
        url=page.url,
        canonical_url=page.canonical_url,
        title=page.title,
        description="A refreshed description.",
        body=page.body + " Additional updated content.",
        headings=page.headings,
        links=page.links,
        language=page.language,
        published_at=page.published_at,
        fetched_at=dt.datetime.now(dt.UTC),
        status=page.status,
        depth=page.depth,
    )
    result = pipeline.index_pages([updated_page])
    assert result.updated == 1
    assert result.duplicates == 0
