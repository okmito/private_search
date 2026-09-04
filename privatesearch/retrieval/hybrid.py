"""Hybrid search that combines lexical (BM25) and semantic scores."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from privatesearch.embeddings.base import EmbeddingModel
from privatesearch.embeddings.vector_store import InMemoryVectorStore, VectorHit
from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.retrieval.bm25 import BM25

__all__ = ["HybridConfig", "HybridHit", "HybridSearch"]


@dataclass(slots=True)
class HybridConfig:
    bm25_weight: float = 1.0
    semantic_weight: float = 0.5
    title_weight: float = 0.0
    enable_title: bool = False

    def weights(self) -> dict[str, float]:
        return {
            "bm25": self.bm25_weight,
            "semantic": self.semantic_weight,
            "title": self.title_weight if self.enable_title else 0.0,
        }


@dataclass(frozen=True, slots=True)
class HybridHit:
    doc_id: int
    final_score: float
    bm25_score: float
    semantic_score: float
    title_score: float
    matched_terms: tuple[str, ...]

    def explanation(self) -> dict[str, float]:
        return {
            "final": self.final_score,
            "bm25": self.bm25_score,
            "semantic": self.semantic_score,
            "title": self.title_score,
        }


class HybridSearch:
    """Combine BM25 hits with semantic similarity scores.

    The implementation linearly combines the two scores using configurable
    weights. The BM25 score is normalised by the maximum BM25 score in the
    candidate list; the semantic score is the cosine similarity returned by
    the embedding model. This means the absolute values of the two scores
    live in similar ranges (``[0, 1]``) so the weights are easier to reason
    about.
    """

    def __init__(
        self,
        index: InvertedIndex,
        embedding: EmbeddingModel,
        vector_store: InMemoryVectorStore | None = None,
        config: HybridConfig | None = None,
    ) -> None:
        self.index = index
        self.embedding = embedding
        self.vector_store = vector_store or InMemoryVectorStore()
        self.config = config or HybridConfig()
        self._bm25 = BM25(index)

    def fit(self, documents: Iterable[tuple[int, str, str, str]]) -> None:
        """Re-fit the embedding model and rebuild the vector store.

        ``documents`` is an iterable of ``(doc_id, url, title, body)``
        tuples. The body is what gets embedded; the other fields are
        ignored by the embedding model itself but they make the API
        symmetric with the indexing pipeline.
        """

        corpus = [(doc_id, body) for doc_id, _, _, body in documents]
        self.embedding.fit(corpus)
        for doc_id, _, _, body in documents:
            self.vector_store.upsert(self.embedding.embed(doc_id, body))

    def search(self, query: str, *, limit: int = 10, offset: int = 0) -> list[HybridHit]:
        if limit <= 0 or offset < 0:
            return []
        tokens = self.index.tokenizer.tokenize(query)
        if not tokens and not query.strip():
            return []

        bm25_hits = self._bm25.score_terms(tokens)
        bm25_lookup = {hit.doc_id: hit for hit in bm25_hits}
        semantic_query = self.embedding.embed_query(query) if query.strip() else None
        semantic_hits: list[VectorHit] = (
            self.vector_store.search(semantic_query, limit=max(limit * 4, 50))
            if semantic_query is not None
            else []
        )
        semantic_lookup = {hit.doc_id: hit.score for hit in semantic_hits}

        candidate_ids = set(bm25_lookup) | set(semantic_lookup)
        if not candidate_ids:
            return []

        max_bm25 = max((hit.score for hit in bm25_hits), default=1.0) or 1.0
        weights = self.config.weights()

        scored: list[HybridHit] = []
        for doc_id in candidate_ids:
            bm25_hit = bm25_lookup.get(doc_id)
            bm25_norm = (bm25_hit.score / max_bm25) if bm25_hit else 0.0
            semantic = semantic_lookup.get(doc_id, 0.0)
            title_score = self._title_score(doc_id, tokens)
            final = (
                bm25_norm * weights["bm25"]
                + semantic * weights["semantic"]
                + title_score * weights["title"]
            )
            scored.append(
                HybridHit(
                    doc_id=doc_id,
                    final_score=final,
                    bm25_score=bm25_norm,
                    semantic_score=semantic,
                    title_score=title_score,
                    matched_terms=bm25_hit.matched_terms if bm25_hit else (),
                )
            )
        scored.sort(key=lambda hit: (-hit.final_score, hit.doc_id))
        return scored[offset : offset + limit]

    def _title_score(self, doc_id: int, tokens: Sequence[str]) -> float:
        if not tokens or not self.config.enable_title:
            return 0.0
        doc = self.index.document(doc_id)
        if doc is None or not doc.title:
            return 0.0
        title_tokens = {token.term for token in self.index.tokenizer.stream(doc.title)}
        if not title_tokens:
            return 0.0
        return sum(1 for term in tokens if term in title_tokens) / len(tokens)
