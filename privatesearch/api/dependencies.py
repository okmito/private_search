"""Runtime dependencies and shared services for the FastAPI layer."""

from __future__ import annotations

from privatesearch.common.config import Settings, get_settings
from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.indexing.pipeline import IndexingPipeline, SearchService
from privatesearch.storage.engine import init_database


class SearchServiceHolder:
    """Container that lazily constructs the :class:`SearchService`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._service: SearchService | None = None

    @property
    def service(self) -> SearchService:
        if self._service is None:
            init_database()
            pipeline = IndexingPipeline()
            pipeline.load_from_storage()
            self._service = SearchService(index=pipeline.index, pipeline=pipeline)
        return self._service

    def rebuild(self) -> int:
        init_database()
        pipeline = IndexingPipeline()
        pipeline.load_from_storage()
        self._service = SearchService(index=pipeline.index, pipeline=pipeline)
        return self._service.pipeline.index.stats.num_documents if self._service.pipeline else 0


_holder: SearchServiceHolder | None = None


def get_search_service() -> SearchService:
    global _holder
    if _holder is None:
        _holder = SearchServiceHolder()
    return _holder.service


def get_holder() -> SearchServiceHolder:
    global _holder
    if _holder is None:
        _holder = SearchServiceHolder()
    return _holder


def reset_for_tests() -> None:  # pragma: no cover - test helper
    global _holder
    _holder = None