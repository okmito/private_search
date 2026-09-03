"""High-level search retriever used by the API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from privatesearch.document_processing.tokenizer import Tokenizer, default_tokenizer
from privatesearch.indexing.inverted_index import DocumentField, InvertedIndex
from privatesearch.retrieval.bm25 import BM25
from privatesearch.retrieval.snippets import Snippet, build_snippet

__all__ = ["Retriever", "SearchResult"]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single search result returned to the API/frontend."""

    doc_id: int
    score: float
    url: str
    title: str
    snippet: Snippet
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    document_length: int = 0


class Retriever:
    """Thin wrapper that ties together the index, BM25 scorer and snippets."""

    def __init__(
        self,
        index: InvertedIndex,
        *,
        k1: float = 1.2,
        b: float = 0.75,
        tokenizer: Tokenizer | None = None,
        snippet_max_length: int = 240,
    ) -> None:
        self.index = index
        self.bm25 = BM25(index, k1=k1, b=b, tokenizer=tokenizer)
        self.tokenizer: Tokenizer = tokenizer or default_tokenizer()
        self.snippet_max_length = snippet_max_length

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        documents: Sequence[tuple[int, str, str, str]] | None = None,
    ) -> list[SearchResult]:
        """Run BM25 for ``query`` and return up to ``limit`` results.

        ``documents`` is an optional iterable of ``(doc_id, url, title,
        body)`` tuples used to render the snippet and metadata. When
        ``documents`` is omitted the retriever falls back to whatever the
        index already knows about each document.
        """

        if limit <= 0:
            return []
        if offset < 0:
            raise ValueError("offset must be non-negative")

        tokens = self.tokenizer.tokenize(query)
        if not tokens:
            return []
        hits = self.bm25.score_terms(tokens)
        page = hits[offset : offset + limit]
        if not page:
            return []

        lookup: dict[int, tuple[str, str, str]] = {}
        if documents is not None:
            for doc_id, url, title, body in documents:
                lookup[int(doc_id)] = (url, title, body)

        results: list[SearchResult] = []
        for hit in page:
            doc_field = self.index.document(hit.doc_id)
            url, title, body = self._resolve_document(hit.doc_id, doc_field, lookup)
            snippet = build_snippet(
                body,
                query_terms=list(hit.matched_terms),
                tokenizer=self.tokenizer,
                max_length=self.snippet_max_length,
            )
            results.append(
                SearchResult(
                    doc_id=hit.doc_id,
                    score=hit.score,
                    url=url,
                    title=title,
                    snippet=snippet,
                    matched_terms=hit.matched_terms,
                    document_length=doc_field.doc_length if doc_field else len(body.split()),
                )
            )
        return results

    def count(self, query: str) -> int:
        if not self.tokenizer.tokenize(query):
            return 0
        return len(self.bm25.score_terms(self.tokenizer.tokenize(query)))

    @staticmethod
    def _resolve_document(
        doc_id: int,
        doc_field: DocumentField | None,
        lookup: dict[int, tuple[str, str, str]],
    ) -> tuple[str, str, str]:
        if doc_id in lookup:
            url, title, body = lookup[doc_id]
            return url, title, body
        if doc_field is not None:
            return doc_field.url, doc_field.title, ""
        return "", "", ""