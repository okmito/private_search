"""Unit tests for the SQLAlchemy storage layer."""

from __future__ import annotations

import pytest

from privatesearch.storage import repository as repo
from privatesearch.storage.engine import (
    close_engine,
    get_engine,
    init_database,
    session_scope,
)


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "storage.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    close_engine()
    init_database()
    yield
    close_engine()


def test_init_database_creates_tables() -> None:
    engine = get_engine()
    tables = set(engine.table_names()) if hasattr(engine, "table_names") else None
    if tables is None:
        # SQLAlchemy >= 2: use reflection
        from sqlalchemy import inspect

        tables = set(inspect(engine).get_table_names())
    assert "documents" in tables
    assert "domains" in tables
    assert "crawl_jobs" in tables
    assert "crawl_events" in tables
    assert "index_metadata" in tables


def test_add_document_and_lookup_by_doc_id() -> None:
    with session_scope() as session:
        doc = repo.add_document(
            session,
            doc_id=1,
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            title="Title",
            description="Desc",
            body="body",
            content_hash="abc123",
            links=[("https://example.com/related", "related")],
        )
        session.flush()
        assert doc.id is not None

    with session_scope() as session:
        loaded = repo.get_document_by_doc_id(session, 1)
        assert loaded is not None
        assert loaded.title == "Title"
        assert loaded.body == "body"
        assert loaded.content_hash == "abc123"


def test_add_document_replaces_existing() -> None:
    with session_scope() as session:
        repo.add_document(
            session,
            doc_id=1,
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            title="First",
            description="",
            body="",
            content_hash="hash1",
        )

    with session_scope() as session:
        repo.add_document(
            session,
            doc_id=1,
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            title="Second",
            description="",
            body="",
            content_hash="hash2",
        )

    with session_scope() as session:
        loaded = repo.get_document_by_doc_id(session, 1)
        assert loaded.title == "Second"
        assert loaded.content_hash == "hash2"


def test_get_or_assign_doc_id_is_stable() -> None:
    with session_scope() as session:
        first = repo.get_or_assign_doc_id(session, "https://example.com/article")
        assert first == 1
    with session_scope() as session:
        repo.add_document(
            session,
            doc_id=first,
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            title="",
            description="",
            body="",
            content_hash="h",
        )
    with session_scope() as session:
        again = repo.get_or_assign_doc_id(session, "https://example.com/article")
        assert again == first


def test_document_exists_by_hash() -> None:
    with session_scope() as session:
        repo.add_document(
            session,
            doc_id=1,
            url="https://example.com/a",
            canonical_url="https://example.com/a",
            title="",
            description="",
            body="",
            content_hash="hash-xyz",
        )
    with session_scope() as session:
        assert repo.document_exists_by_hash(session, "hash-xyz")
        assert not repo.document_exists_by_hash(session, "missing")


def test_add_document_records_links() -> None:
    with session_scope() as session:
        doc = repo.add_document(
            session,
            doc_id=1,
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            title="",
            description="",
            body="",
            content_hash="h",
            links=[("https://example.com/a", "A"), ("https://example.com/b", "B")],
        )
        session.flush()
        assert len(doc.links) == 2
    with session_scope() as session:
        loaded = repo.get_document_by_doc_id(session, 1)
        urls = {link.target_url for link in loaded.links}
        assert urls == {"https://example.com/a", "https://example.com/b"}


def test_create_crawl_job_records_progress() -> None:
    with session_scope() as session:
        job = repo.create_crawl_job(
            session,
            name="seed",
            seed_urls=["https://example.com"],
            allowed_domains=["example.com"],
            max_depth=2,
            max_pages=10,
            delay_seconds=0.5,
        )
        session.flush()
        repo.add_crawl_event(
            session,
            job=job,
            url="https://example.com",
            status="success",
            http_status=200,
        )
        repo.finish_crawl_job(session, job, pages_crawled=1, pages_failed=0)
    with session_scope() as session:
        from sqlalchemy import select

        from privatesearch.storage.models import CrawlJob

        jobs = session.execute(select(CrawlJob)).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].pages_crawled == 1
        assert jobs[0].status == "completed"
        assert jobs[0].finished_at is not None