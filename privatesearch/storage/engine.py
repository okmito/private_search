"""Engine/session helpers for SQLAlchemy."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from privatesearch.common.config import get_settings
from privatesearch.storage.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _configure_sqlite(engine: Engine) -> None:
    """Enable foreign keys and WAL mode for SQLite (test-friendly defaults)."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # SQLAlchemy accepts forms ``sqlite:///relative/path`` and
        # ``sqlite:////absolute/path``. Strip the scheme and normalise the
        # leading slashes so we can detect whether we have an absolute path.
        stripped = url[len("sqlite:///") :]
        if stripped.startswith("/"):
            path = "/" + stripped.lstrip("/")
        else:
            path = stripped
        if path and path != ":memory:":
            from pathlib import Path

            db_file = Path(path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        _configure_sqlite(engine)
    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


def close_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_database() -> None:
    """Create every table declared on :class:`Base`."""

    engine = get_engine()
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error."""

    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Type alias for use in helper signatures.
DatabaseSession = Session
