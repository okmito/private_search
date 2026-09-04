"""Tests for the FastAPI search API."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "privatesearch"))

from privatesearch.api.app import create_app  # noqa: E402
from privatesearch.api.dependencies import reset_for_tests  # noqa: E402
from privatesearch.crawler.crawler import CrawledPage  # noqa: E402
from privatesearch.indexing.pipeline import IndexingPipeline  # noqa: E402
from privatesearch.storage.engine import close_engine, init_database  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "api.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("PRIVATESEARCH_LOG_LEVEL", "WARNING")
    close_engine()
    init_database()
    reset_for_tests()
    yield
    close_engine()
    reset_for_tests()


@pytest.fixture
def client():
    return TestClient(create_app())


def _pages():
    base = __import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    return [
        CrawledPage(
            url="https://example.com/ml",
            canonical_url="https://example.com/ml",
            title="Machine Learning Primer",
            description="Introduction to machine learning.",
            body="Machine learning is a field of computer science that learns from data. "
            "It uses algorithms and neural networks to make predictions.",
            headings=["Machine Learning"],
            links=[],
            language="en",
            published_at=None,
            fetched_at=base,
            status=200,
            depth=0,
        ),
        CrawledPage(
            url="https://example.com/db",
            canonical_url="https://example.com/db",
            title="Databases 101",
            description="Introduction to relational databases.",
            body="A relational database organises data in tables queried with SQL.",
            headings=["Databases"],
            links=[],
            language="en",
            published_at=None,
            fetched_at=base,
            status=200,
            depth=0,
        ),
    ]


@pytest.fixture
def seeded_index():
    pipeline = IndexingPipeline()
    pipeline.index_pages(_pages())
    return pipeline


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_stats_endpoint(client):
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    body = response.json()
    assert "documents" in body
    assert "terms" in body


def test_search_endpoint_returns_results(client, seeded_index):
    response = client.get("/api/v1/search", params={"q": "machine learning"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "machine learning"
    assert payload["total"] >= 1
    assert payload["results"]
    assert payload["results"][0]["title"]


def test_search_endpoint_paginates(client, seeded_index):
    # Add a second document containing "machine" so pagination has work to do.
    import datetime as dt

    extra_page = CrawledPage(
        url="https://example.com/ml-advanced",
        canonical_url="https://example.com/ml-advanced",
        title="Advanced Machine Learning",
        description="Advanced topics in machine learning.",
        body="Machine learning advanced techniques include ensembles and deep nets.",
        headings=[],
        links=[],
        language="en",
        published_at=None,
        fetched_at=dt.datetime.now(dt.UTC),
        status=200,
        depth=0,
    )
    seeded_index.index_pages([extra_page])

    first = client.get(
        "/api/v1/search",
        params={"q": "machine", "page": 1, "limit": 1},
    )
    second = client.get(
        "/api/v1/search",
        params={"q": "machine", "page": 2, "limit": 1},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["results"][0]["doc_id"] != second.json()["results"][0]["doc_id"]


def test_search_endpoint_rejects_blank_query(client):
    response = client.get("/api/v1/search", params={"q": "   "})
    assert response.status_code == 400


def test_search_endpoint_validates_pagination(client):
    response = client.get("/api/v1/search", params={"q": "hello", "limit": 0})
    assert response.status_code == 422


def test_search_endpoint_validates_limit(client):
    response = client.get("/api/v1/search", params={"q": "hello", "limit": 1000})
    assert response.status_code == 422


def test_suggestions_endpoint(client, seeded_index):
    response = client.get("/api/v1/suggestions", params={"q": "mach"})
    assert response.status_code == 200
    payload = response.json()
    assert "suggestions" in payload
    # The seeded corpus contains "machine" so the prefix expansion should
    # return at least one suggestion that includes it.
    assert any("machine" in s for s in payload["suggestions"])


def test_document_endpoint_returns_metadata(client, seeded_index):
    response = client.get("/api/v1/documents/1")
    assert response.status_code == 200
    body = response.json()
    assert body["title"]
    assert body["canonical_url"]


def test_document_endpoint_returns_404_for_missing(client):
    response = client.get("/api/v1/documents/9999")
    assert response.status_code == 404


def test_health_response_includes_security_headers(client):
    response = client.get("/api/v1/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
