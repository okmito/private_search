"""Indexing pipeline connecting storage and search."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from privatesearch.crawler.crawler import CrawledPage, CrawlResult
from privatesearch.document_processing.hashing import content_hash
from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.storage import repository as repo
from privatesearch.storage.engine import init_database, session_scope

__all__ = [
    "IndexingResult",
    "IndexingPipeline",
    "SearchService",
]


@dataclass(slots=True)
class IndexingResult:
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    failed: int = 0

    @property
    def total_processed(self) -> int:
        return self.inserted + self.updated + self.duplicates + self.failed


class IndexingPipeline:
    """Coordinates storage and the in-memory inverted index."""

    def __init__(self, index: InvertedIndex | None = None) -> None:
        self.index = index or InvertedIndex()

    def index_pages(self, pages: Iterable[CrawledPage]) -> IndexingResult:
        # Ensure the database schema exists before touching the repository.
        init_database()
        result = IndexingResult()
        for page in pages:
            try:
                self._index_one(page, result)
            except Exception as exc:  # noqa: BLE001 - never let a single page abort the pipeline
                import logging

                logging.getLogger(__name__).exception("Failed to index page %s: %s", page.url, exc)
                result.failed += 1
        return result

    def index_crawl_result(self, crawl: CrawlResult) -> IndexingResult:
        return self.index_pages(crawl.pages)

    def load_from_storage(self) -> int:
        """Rebuild the in-memory index from the database."""

        self.index.clear()
        with session_scope() as session:
            documents = repo.all_documents(session)
        for document in documents:
            self.index.add_document(
                document.doc_id,
                text=document.body or "",
                title=document.title or "",
                url=document.canonical_url or document.url or "",
            )
        return len(documents)

    def _index_one(self, page: CrawledPage, result: IndexingResult) -> None:
        canonical = page.canonical_url or page.url
        digest = content_hash(page.body or "")

        with session_scope() as session:
            existing = repo.get_document_by_url(session, canonical)
            doc_id = (
                existing.doc_id
                if existing is not None
                else repo.get_or_assign_doc_id(session, canonical)
            )
            if existing is None:
                repo.add_document(
                    session,
                    doc_id=doc_id,
                    url=page.url,
                    canonical_url=canonical,
                    title=page.title,
                    description=page.description,
                    body=page.body,
                    content_hash=digest,
                    language=page.language,
                    links=[(link, "") for link in page.links],
                )
                result.inserted += 1
            else:
                if existing.content_hash == digest and existing.title == page.title:
                    result.duplicates += 1
                    return
                repo.add_document(
                    session,
                    doc_id=existing.doc_id,
                    url=page.url,
                    canonical_url=canonical,
                    title=page.title,
                    description=page.description,
                    body=page.body,
                    content_hash=digest,
                    language=page.language,
                    links=[(link, "") for link in page.links],
                )
                result.updated += 1

        # Keep the in-memory index in sync.
        if self.index.document(doc_id) is not None:
            self.index.remove_document(doc_id)
        self.index.add_document(
            doc_id,
            text=page.body or "",
            title=page.title or "",
            url=canonical,
        )

    def save_snapshot(self, path: str | Path) -> Path:
        return self.index.save_snapshot(path)

    def load_snapshot(self, path: str | Path) -> InvertedIndex:
        self.index = InvertedIndex.load_snapshot(path)
        return self.index


@dataclass
class SearchService:
    """Glue object exposing search through the inverted index and storage."""

    index: InvertedIndex
    pipeline: IndexingPipeline | None = None

    def rebuild(self) -> int:
        pipeline = self.pipeline or IndexingPipeline(self.index)
        self.pipeline = pipeline
        return pipeline.load_from_storage()

    def search(self, query: str, *, limit: int = 10, offset: int = 0) -> list[dict[str, object]]:
        from privatesearch.retrieval.retriever import Retriever
        from privatesearch.retrieval.snippets import build_snippet

        retriever = Retriever(self.index)
        results = retriever.search(query, limit=limit, offset=offset, documents=None)
        payload: list[dict[str, object]] = []
        for result in results:
            doc_field = self.index.document(result.doc_id)
            body = doc_field.title if doc_field else ""
            snippet = build_snippet(
                body,
                query_terms=list(result.matched_terms),
                tokenizer=retriever.tokenizer,
                max_length=retriever.snippet_max_length,
            )
            payload.append(
                {
                    "doc_id": result.doc_id,
                    "score": result.score,
                    "title": result.title,
                    "url": result.url,
                    "snippet": snippet.text,
                    "highlighted": snippet.highlighted,
                }
            )
        return payload
