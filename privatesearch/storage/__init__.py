"""Database access layer for PrivateSearch."""

from privatesearch.storage.base import Base
from privatesearch.storage.engine import (
    DatabaseSession,
    close_engine,
    get_engine,
    get_session_factory,
    init_database,
    session_scope,
)
from privatesearch.storage.models import (
    CrawlEvent,
    CrawlJob,
    Document,
    DocumentLink,
    Domain,
    IndexMetadata,
)

__all__ = [
    "Base",
    "DatabaseSession",
    "close_engine",
    "get_engine",
    "get_session_factory",
    "init_database",
    "session_scope",
    "CrawlEvent",
    "CrawlJob",
    "Domain",
    "Document",
    "DocumentLink",
    "IndexMetadata",
]
