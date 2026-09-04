"""In-memory vector store used to look up nearest neighbours."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass

from privatesearch.embeddings.base import EmbeddingVector, cosine_similarity

__all__ = ["VectorHit", "InMemoryVectorStore"]


@dataclass(frozen=True, slots=True)
class VectorHit:
    doc_id: int
    score: float


class InMemoryVectorStore:
    """A trivial vector store that keeps vectors in memory.

    For the V1 portfolio this is sufficient: the brute-force scan runs in
    ``O(N * dim)`` which is fine for the project's 10k–100k document scale.
    A real vector database (or pgvector) can replace this class later
    without changing the rest of the code base.
    """

    def __init__(self) -> None:
        self._vectors: dict[int, EmbeddingVector] = {}

    def __len__(self) -> int:
        return len(self._vectors)

    def upsert(self, vector: EmbeddingVector) -> None:
        self._vectors[vector.doc_id] = vector

    def remove(self, doc_id: int) -> None:
        self._vectors.pop(doc_id, None)

    def get(self, doc_id: int) -> EmbeddingVector | None:
        return self._vectors.get(doc_id)

    def search(self, query: EmbeddingVector, *, limit: int = 10) -> list[VectorHit]:
        if limit <= 0 or not self._vectors:
            return []
        scored = [
            (cosine_similarity(query, vector), vector.doc_id)
            for vector in self._vectors.values()
            if vector.doc_id != query.doc_id
        ]
        if not scored:
            return []
        # ``nsmallest`` returns ascending order so we negate the score.
        top = heapq.nlargest(limit, scored, key=lambda item: item[0])
        return [VectorHit(doc_id=doc_id, score=score) for score, doc_id in top]

    def all_vectors(self) -> Iterable[EmbeddingVector]:
        return self._vectors.values()
