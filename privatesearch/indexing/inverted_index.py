"""In-memory inverted index with optional snapshot persistence.

The data structure used here is the classical inverted index: a dictionary
mapping each term to a sorted list of postings. Each posting stores the
document id, the term frequency inside that document and the token positions
needed for phrase queries and snippet generation.

Although the index is in-memory, it can serialise itself to a JSON snapshot
file via :meth:`InvertedIndex.save_snapshot`. Loading a snapshot returns the
same statistics and behaves identically to a freshly built index, which is
sufficient for the V1 portfolio goals (10k–100k documents per shard).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from privatesearch.document_processing.tokenizer import Tokenizer, default_tokenizer

__all__ = ["InvertedIndex", "Posting", "PostingList", "IndexStats", "IndexSnapshot"]


@dataclass(frozen=True, slots=True)
class Posting:
    """A single (document, term-frequency, positions) tuple."""

    doc_id: int
    term_frequency: int
    positions: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "tf": self.term_frequency,
            "positions": list(self.positions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Posting:
        return cls(
            doc_id=int(data["doc_id"]),
            term_frequency=int(data["tf"]),
            positions=tuple(int(p) for p in data["positions"]),  # type: ignore[arg-type]
        )


PostingList = list[Posting]


@dataclass(slots=True)
class DocumentField:
    """Per-document field lengths used for BM25 normalisation."""

    doc_id: int
    doc_length: int
    title_length: int = 0
    url: str = ""
    title: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "doc_length": self.doc_length,
            "title_length": self.title_length,
            "url": self.url,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DocumentField:
        return cls(
            doc_id=int(data["doc_id"]),
            doc_length=int(data["doc_length"]),
            title_length=int(data.get("title_length", 0)),
            url=str(data.get("url", "")),
            title=str(data.get("title", "")),
        )


@dataclass(slots=True)
class IndexStats:
    """Global statistics about an :class:`InvertedIndex`."""

    num_documents: int = 0
    num_terms: int = 0
    total_postings: int = 0
    avg_document_length: float = 0.0
    total_document_length: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "num_documents": self.num_documents,
            "num_terms": self.num_terms,
            "total_postings": self.total_postings,
            "avg_document_length": self.avg_document_length,
            "total_document_length": self.total_document_length,
        }


@dataclass
class IndexSnapshot:
    """Serializable representation of the inverted index."""

    stats: IndexStats
    postings: dict[str, list[dict[str, object]]]
    documents: list[dict[str, object]]

    def to_json(self) -> str:
        return json.dumps(
            {
                "stats": self.stats.to_dict(),
                "postings": self.postings,
                "documents": self.documents,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str) -> IndexSnapshot:
        data = json.loads(raw)
        return cls(
            stats=IndexStats(**data["stats"]),  # type: ignore[arg-type]
            postings=data["postings"],
            documents=data["documents"],
        )


class InvertedIndex:
    """A simple in-memory inverted index.

    The implementation is purposely small and deterministic. It is meant to
    demonstrate the core data structure of a search engine rather than be
    production-scale. All public methods are safe to call from multiple
    threads as long as the caller serialises updates.
    """

    def __init__(self, tokenizer: Tokenizer | None = None) -> None:
        self._tokenizer: Tokenizer = tokenizer or default_tokenizer()
        self._postings: dict[str, PostingList] = {}
        self._documents: dict[int, DocumentField] = {}
        self._stats = IndexStats()

    # ------------------------------------------------------------------
    # Properties used by the retriever / BM25 implementation.
    # ------------------------------------------------------------------
    @property
    def tokenizer(self) -> Tokenizer:
        return self._tokenizer

    @property
    def stats(self) -> IndexStats:
        return self._stats

    def __len__(self) -> int:
        return self._stats.num_documents

    def __contains__(self, doc_id: int) -> bool:
        return doc_id in self._documents

    def document(self, doc_id: int) -> DocumentField | None:
        return self._documents.get(doc_id)

    def document_length(self, doc_id: int) -> int:
        field = self._documents.get(doc_id)
        return field.doc_length if field is not None else 0

    def document_frequency(self, term: str) -> int:
        posting_list = self._postings.get(term)
        return len(posting_list) if posting_list else 0

    def get_postings(self, term: str) -> PostingList:
        return list(self._postings.get(term, ()))

    def iter_terms(self) -> Iterable[str]:
        return self._postings.keys()

    def terms(self) -> list[str]:
        return sorted(self._postings.keys())

    def all_documents(self) -> Iterator[DocumentField]:
        return iter(self._documents.values())

    # ------------------------------------------------------------------
    # Indexing API.
    # ------------------------------------------------------------------
    def add_document(
        self,
        doc_id: int,
        *,
        text: str,
        title: str = "",
        url: str = "",
    ) -> None:
        """Tokenise and insert ``text`` into the index under ``doc_id``."""

        if doc_id in self._documents:
            raise ValueError(f"Document {doc_id} already indexed")

        body_tokens = self._tokenizer.stream(text)
        title_tokens = self._tokenizer.stream(title) if title else []
        positions: dict[str, list[int]] = {}

        for token in body_tokens:
            positions.setdefault(token.term, []).append(token.position)

        for term, term_positions in positions.items():
            posting = Posting(
                doc_id=doc_id,
                term_frequency=len(term_positions),
                positions=tuple(term_positions),
            )
            self._postings.setdefault(term, []).append(posting)

        self._documents[doc_id] = DocumentField(
            doc_id=doc_id,
            doc_length=len(body_tokens),
            title_length=len(title_tokens),
            url=url,
            title=title,
        )
        self._refresh_stats()

    def remove_document(self, doc_id: int) -> None:
        if doc_id not in self._documents:
            return
        for term in list(self._postings.keys()):
            postings = self._postings[term]
            remaining = [p for p in postings if p.doc_id != doc_id]
            if remaining:
                self._postings[term] = remaining
            else:
                del self._postings[term]
        del self._documents[doc_id]
        self._refresh_stats()

    def clear(self) -> None:
        self._postings.clear()
        self._documents.clear()
        self._stats = IndexStats()

    # ------------------------------------------------------------------
    # Snapshot persistence.
    # ------------------------------------------------------------------
    def snapshot(self) -> IndexSnapshot:
        postings_payload: dict[str, list[dict[str, object]]] = {}
        for term, postings in self._postings.items():
            postings_payload[term] = [p.to_dict() for p in postings]
        documents_payload = [doc.to_dict() for doc in self._documents.values()]
        return IndexSnapshot(
            stats=self._stats,
            postings=postings_payload,
            documents=documents_payload,
        )

    def save_snapshot(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.snapshot().to_json(), encoding="utf-8")
        return path

    @classmethod
    def load_snapshot(cls, path: str | Path, tokenizer: Tokenizer | None = None) -> InvertedIndex:
        path = Path(path)
        snapshot = IndexSnapshot.from_json(path.read_text(encoding="utf-8"))
        index = cls(tokenizer=tokenizer)
        for doc_payload in snapshot.documents:
            field = DocumentField.from_dict(doc_payload)
            index._documents[field.doc_id] = field  # noqa: SLF001 - restoration
        for term, postings_payload in snapshot.postings.items():
            index._postings[term] = [Posting.from_dict(p) for p in postings_payload]
        index._stats = snapshot.stats
        return index

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------
    def _refresh_stats(self) -> None:
        total_postings = sum(len(p) for p in self._postings.values())
        total_length = sum(d.doc_length for d in self._documents.values())
        num_documents = len(self._documents)
        avg_length = (total_length / num_documents) if num_documents else 0.0
        self._stats = IndexStats(
            num_documents=num_documents,
            num_terms=len(self._postings),
            total_postings=total_postings,
            avg_document_length=avg_length,
            total_document_length=total_length,
        )
