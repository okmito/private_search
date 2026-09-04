"""TF-IDF embedding implementation (no external ML dependencies)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from privatesearch.document_processing.tokenizer import Tokenizer, default_tokenizer
from privatesearch.embeddings.base import EmbeddingModel, EmbeddingVector


class TFIDFEmbedding(EmbeddingModel):
    """Classic TF-IDF embedding with L2 normalisation.

    The implementation is intentionally minimal: it builds a vocabulary from
    the documents passed to :meth:`fit`, computes IDF weights and projects
    documents into a sparse (but stored as dense) vector space. The model is
    a good fallback for environments that cannot run a neural embedding
    model.
    """

    name = "tfidf"

    def __init__(self, tokenizer: Tokenizer | None = None) -> None:
        self.tokenizer: Tokenizer = tokenizer or default_tokenizer()
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._fitted = False

    @property
    def dimension(self) -> int:
        return len(self._vocab)

    def fit(self, documents: Sequence[tuple[int, str]]) -> None:
        df: dict[str, int] = {}
        for _, text in documents:
            seen: set[str] = set()
            for token in self.tokenizer.stream(text):
                if token.term in seen:
                    continue
                seen.add(token.term)
                df[token.term] = df.get(token.term, 0) + 1

        vocab = sorted(df.keys())
        self._vocab = {term: index for index, term in enumerate(vocab)}
        n = max(1, len(documents))
        self._idf = [math.log((n + 1) / (df[term] + 1)) + 1 for term in vocab]
        self._fitted = True

    def embed(self, doc_id: int, text: str) -> EmbeddingVector:
        if not self._fitted:
            raise RuntimeError("TFIDFEmbedding.fit must be called before embed")
        counts = self._term_counts(text)
        vector = [0.0] * len(self._vocab)
        for term, count in counts.items():
            index = self._vocab.get(term)
            if index is None:
                continue
            vector[index] = (1.0 + math.log(count)) * self._idf[index]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return EmbeddingVector(doc_id=doc_id, values=[value / norm for value in vector])

    def embed_query(self, query: str) -> EmbeddingVector:
        return self.embed(doc_id=-1, text=query)

    def _term_counts(self, text: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for token in self.tokenizer.stream(text):
            counts[token.term] = counts.get(token.term, 0) + 1
        return counts
