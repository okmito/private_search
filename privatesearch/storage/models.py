"""SQLAlchemy models describing documents, crawl jobs and links."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from privatesearch.storage.base import Base

# SQLite uses INTEGER for autoincrement while PostgreSQL uses BIGINT.
BigInt = BigInteger().with_variant(Integer, "sqlite")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    allowed: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    documents: Mapped[list[Document]] = relationship(back_populates="domain")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    body_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    last_crawled_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    crawl_status: Mapped[str] = mapped_column(String(32), default="fresh", nullable=False)

    domain: Mapped[Domain | None] = relationship(back_populates="documents")
    links: Mapped[list[DocumentLink]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_documents_domain_status", "domain_id", "crawl_status"),)


class DocumentLink(Base):
    __tablename__ = "document_links"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    anchor_text: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="links")

    __table_args__ = (
        UniqueConstraint("document_id", "target_url", name="uq_document_link"),
        Index("ix_document_links_target", "target_url"),
    )


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    seed_urls: Mapped[str] = mapped_column(Text, nullable=False, default="")
    allowed_domains: Mapped[str] = mapped_column(Text, nullable=False, default="")
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    delay_seconds: Mapped[float] = mapped_column(nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class CrawlEvent(Base):
    __tablename__ = "crawl_events"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class IndexMetadata(Base):
    __tablename__ = "index_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_document_length: Mapped[float] = mapped_column(nullable=False, default=0.0)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
