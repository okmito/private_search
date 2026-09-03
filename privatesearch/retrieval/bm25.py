"""BM25 retrieval implementation.

This module implements the Okapi BM25 ranking function described in
Robertson, S. and Zaragoza, H., *The Probabilistic Relevance Framework: BM25
and Beyond*, 2009.

The implementation here is intentionally explicit. Each score is the
classical sum over query terms of the IDF-weighted, length-normalised
saturation function. The two free parameters ``k1`` and ``b`` are exposed
as constructor arguments and match the textbook interpretation:

* ``k1`` controls how quickly the contribution of repeated occurrences of a
  term saturates. Typical values lie in the range ``1.2`` to ``2.0``.
* ``b`` controls the strength of document-length normalisation. ``0`` disables
  the normalisation; ``1`` uses the full document length.

The IDF term uses the smoothed ``log((N - n + 0.5) / (n + 0.5) + 1)`` form
to remain non-negative even for terms that occur in more than half of the
documents in the collection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from privatesearch.document_processing.tokenizer import Tokenizer, default_tokenizer
from privatesearch.indexing.inverted_index import InvertedIndex

__all__ = ["BM25", "BM25Hit"]


@dataclass(frozen=True, slots=True)
class BM25Hit:
    """A single BM25-ranked result."""

    doc_id: int
    score: float
    matched_terms: tuple[str, ...]

    @property
    def document_id(self) -> int:
        return self.doc_id


class BM25:
    """Okapi BM25 scorer over an :class:`InvertedIndex`."""

    def __init__(
        self,
        index: InvertedIndex,
        *,
        k1: float = 1.2,
        b: float = 0.75,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        if k1 < 0:
            raise ValueError("k1 must be non-negative")
        if not 0 <= b <= 1:
            raise ValueError("b must be in [0, 1]")
        self.index = index
        self.k1 = k1
        self.b = b
        self.tokenizer: Tokenizer = tokenizer or index.tokenizer or default_tokenizer()

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------
    def score(self, query: str) -> list[BM25Hit]:
        """Score every document that matches at least one query term.

        The result is sorted by descending score. Documents with a score of
        zero (because no query term occurs in them) are omitted so the caller
        can rely on the returned list as a ranked candidate set.
        """

        tokens = self.tokenizer.tokenize(query)
        if not tokens:
            return []
        return self.score_terms(tokens)

    def score_terms(self, query_terms: list[str]) -> list[BM25Hit]:
        if not query_terms:
            return []
        stats = self.index.stats
        if stats.num_documents == 0:
            return []

        n = stats.num_documents
        avg_dl = stats.avg_document_length or 1.0

        # Per the BM25 definition the contribution of a term is computed once
        # per *unique* query term; repeating a term in the query does not
        # double-count its contribution.
        unique_terms = sorted(set(query_terms))

        scores: dict[int, float] = {}
        matched: dict[int, set[str]] = {}

        for term in unique_terms:
            postings = self.index.get_postings(term)
            df = len(postings)
            if df == 0:
                continue
            idf = math.log(((n - df + 0.5) / (df + 0.5)) + 1.0)
            for posting in postings:
                dl = self.index.document_length(posting.doc_id) or 1
                tf = posting.term_frequency
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * (dl / avg_dl)
                )
                contribution = idf * (numerator / denominator)
                scores[posting.doc_id] = scores.get(posting.doc_id, 0.0) + contribution
                matched.setdefault(posting.doc_id, set()).add(term)

        hits = [
            BM25Hit(
                doc_id=doc_id,
                score=score,
                matched_terms=tuple(sorted(matched.get(doc_id, set()))),
            )
            for doc_id, score in scores.items()
            if score > 0
        ]
        hits.sort(key=lambda hit: (-hit.score, hit.doc_id))
        return hits