"""High-level repository helpers built on top of SQLAlchemy."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from privatesearch.storage.engine import session_scope
from privatesearch.storage.models import (
    CrawlEvent,
    CrawlJob,
    Document,
    DocumentLink,
    Domain,
    IndexMetadata,
)


def _normalize_url(url: str) -> str:
    return url.strip()


def upsert_domain(session: Session, host: str, *, allowed: bool = True) -> Domain:
    host = host.lower()
    domain = session.execute(select(Domain).where(Domain.host == host)).scalar_one_or_none()
    if domain is None:
        domain = Domain(host=host, allowed=allowed)
        session.add(domain)
        session.flush()
    else:
        domain.allowed = allowed
    return domain


def get_domain(session: Session, host: str) -> Domain | None:
    return session.execute(select(Domain).where(Domain.host == host.lower())).scalar_one_or_none()


def get_or_assign_doc_id(session: Session, canonical_url: str) -> int:
    """Return the next ``doc_id`` for the given canonical URL.

    The function deliberately returns a stable integer even when no document
    has been written yet. The caller is responsible for using the returned
    identifier to create a :class:`Document` row.
    """

    canonical_url = _normalize_url(canonical_url)
    existing = session.execute(
        select(Document.doc_id).where(Document.canonical_url == canonical_url)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    highest = session.execute(select(Document.doc_id).order_by(Document.doc_id.desc())).first()
    return (highest[0] + 1) if highest else 1


def add_document(
    session: Session,
    *,
    doc_id: int,
    url: str,
    canonical_url: str,
    title: str,
    description: str,
    body: str,
    content_hash: str,
    language: str | None = None,
    links: Sequence[tuple[str, str]] | None = None,
    crawl_status: str = "fresh",
    last_crawled_at: dt.datetime | None = None,
) -> Document:
    """Insert or replace a document row."""

    url = _normalize_url(url)
    canonical_url = _normalize_url(canonical_url)
    host = ""
    if "://" in canonical_url:
        host = canonical_url.split("://", 1)[1].split("/", 1)[0].lower()

    domain_id: int | None = None
    if host:
        domain = upsert_domain(session, host)
        domain_id = domain.id

    existing = session.execute(
        select(Document).where(Document.canonical_url == canonical_url)
    ).scalar_one_or_none()

    timestamp = last_crawled_at or dt.datetime.now(dt.UTC)
    body_length = len(body)
    title_length = len(title)

    if existing is None:
        document = Document(
            doc_id=doc_id,
            url=url,
            canonical_url=canonical_url,
            domain_id=domain_id,
            title=title,
            description=description,
            body=body,
            content_hash=content_hash,
            language=language,
            title_length=title_length,
            body_length=body_length,
            crawl_status=crawl_status,
            last_crawled_at=timestamp,
        )
        session.add(document)
        session.flush()
    else:
        existing.doc_id = doc_id
        existing.url = url
        existing.domain_id = domain_id
        existing.title = title
        existing.description = description
        existing.body = body
        existing.content_hash = content_hash
        existing.language = language
        existing.title_length = title_length
        existing.body_length = body_length
        existing.crawl_status = crawl_status
        existing.last_crawled_at = timestamp
        document = existing

    if links:
        _replace_links(session, document, links)
    return document


def _replace_links(session: Session, document: Document, links: Iterable[tuple[str, str]]) -> None:
    session.query(DocumentLink).filter(DocumentLink.document_id == document.id).delete()
    seen: set[str] = set()
    for target_url, anchor_text in links:
        target_url = _normalize_url(target_url)
        if not target_url or target_url in seen:
            continue
        seen.add(target_url)
        session.add(
            DocumentLink(
                document_id=document.id,
                target_url=target_url,
                anchor_text=anchor_text[:500] if anchor_text else "",
            )
        )


def get_document_by_doc_id(session: Session, doc_id: int) -> Document | None:
    return session.execute(select(Document).where(Document.doc_id == doc_id)).scalar_one_or_none()


def get_document_by_url(session: Session, url: str) -> Document | None:
    return session.execute(
        select(Document).where(Document.canonical_url == url)
    ).scalar_one_or_none()


def document_exists_by_hash(session: Session, content_hash: str) -> bool:
    return (
        session.execute(select(Document.id).where(Document.content_hash == content_hash)).first()
        is not None
    )


def all_documents(session: Session, *, limit: int | None = None) -> list[Document]:
    stmt = select(Document).order_by(Document.doc_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars())


def count_documents(session: Session) -> int:
    return int(session.execute(select(Document.id)).all().__len__())


def create_crawl_job(
    session: Session,
    *,
    name: str,
    seed_urls: Iterable[str],
    allowed_domains: Iterable[str],
    max_depth: int,
    max_pages: int,
    delay_seconds: float,
) -> CrawlJob:
    job = CrawlJob(
        name=name,
        seed_urls="\n".join(seed_urls),
        allowed_domains="\n".join(allowed_domains),
        max_depth=max_depth,
        max_pages=max_pages,
        delay_seconds=delay_seconds,
    )
    session.add(job)
    session.flush()
    return job


def finish_crawl_job(
    session: Session,
    job: CrawlJob,
    *,
    pages_crawled: int,
    pages_failed: int,
    status: str = "completed",
) -> None:
    job.pages_crawled = pages_crawled
    job.pages_failed = pages_failed
    job.status = status
    job.finished_at = dt.datetime.now(dt.UTC)


def add_crawl_event(
    session: Session,
    *,
    job: CrawlJob,
    url: str,
    status: str,
    http_status: int | None = None,
    error: str | None = None,
) -> None:
    session.add(
        CrawlEvent(
            job_id=job.id,
            url=url,
            status=status,
            http_status=http_status,
            error=error,
        )
    )


def record_index_metadata(
    session: Session,
    *,
    snapshot_name: str,
    documents: int,
    terms: int,
    avg_document_length: float,
    path: str,
) -> IndexMetadata:
    existing = session.execute(
        select(IndexMetadata).where(IndexMetadata.snapshot_name == snapshot_name)
    ).scalar_one_or_none()
    if existing is None:
        metadata = IndexMetadata(
            snapshot_name=snapshot_name,
            documents=documents,
            terms=terms,
            avg_document_length=avg_document_length,
            path=path,
        )
        session.add(metadata)
        session.flush()
        return metadata
    existing.documents = documents
    existing.terms = terms
    existing.avg_document_length = avg_document_length
    existing.path = path
    return existing


def with_session(func):  # type: ignore[no-untyped-def]
    """Decorator that wraps a function in :func:`session_scope`."""

    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        with session_scope() as session:
            return func(session, *args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
