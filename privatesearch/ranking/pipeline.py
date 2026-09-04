"""Modular ranking pipeline used by PrivateSearch.

Each signal contributes a non-negative :class:`SignalScore`. The pipeline
combines them with user-defined weights to produce the final score. The
weights can be tweaked without touching the signal implementations, and
every signal can be enabled/disabled individually.

The signals currently implemented are:

* :class:`ExactTitleSignal` – boosts documents whose title matches the query.
* :class:`UrlRelevanceSignal` – rewards URLs that contain query tokens.
* :class:`FreshnessSignal` – favours recently crawled documents.
* :class:`QualitySignal` – penalises very short or empty content.

PageRank is intentionally left out of the default pipeline. Implementing it
requires a separate offline link-analysis pass; the framework is in place
to plug it in once the data is available.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from privatesearch.document_processing.tokenizer import Tokenizer, default_tokenizer
from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.retrieval.bm25 import BM25, BM25Hit

__all__ = [
    "RankedHit",
    "RankingConfig",
    "RankingPipeline",
    "RankingSignal",
    "SignalScore",
]


@dataclass(frozen=True, slots=True)
class SignalScore:
    """A single signal contribution for a document."""

    name: str
    value: float
    raw: float | None = None

    def to_dict(self) -> dict[str, float]:
        payload: dict[str, float] = {"score": self.value}
        if self.raw is not None:
            payload["raw"] = float(self.raw)
        return payload


@dataclass(frozen=True, slots=True)
class RankedHit:
    """The combined ranking output for one document."""

    doc_id: int
    bm25_score: float
    final_score: float
    matched_terms: tuple[str, ...]
    signals: tuple[SignalScore, ...] = field(default_factory=tuple)

    def explanation(self) -> dict[str, float]:
        out: dict[str, float] = {"bm25": self.bm25_score, "final": self.final_score}
        for signal in self.signals:
            out[signal.name] = signal.value
        return out


class RankingSignal:
    """Abstract base class for ranking signals."""

    name = "signal"

    def compute(
        self,
        *,
        index: InvertedIndex,
        bm25_hit: BM25Hit,
        query_terms: Sequence[str],
        config: RankingConfig,
    ) -> SignalScore:
        raise NotImplementedError

    @staticmethod
    def _normalize(value: float, ceiling: float) -> float:
        if ceiling <= 0:
            return 0.0
        ratio = value / ceiling
        if ratio < 0:
            return 0.0
        if ratio > 1:
            return 1.0
        return ratio


@dataclass(slots=True)
class RankingConfig:
    """Weights and toggles for the ranking pipeline."""

    bm25_weight: float = 1.0
    title_weight: float = 1.5
    url_weight: float = 0.5
    freshness_weight: float = 0.3
    quality_weight: float = 0.3
    enable_title: bool = True
    enable_url: bool = True
    enable_freshness: bool = True
    enable_quality: bool = True

    @classmethod
    def balanced(cls) -> RankingConfig:
        return cls()

    @classmethod
    def bm25_only(cls) -> RankingConfig:
        config = cls()
        config.enable_title = False
        config.enable_url = False
        config.enable_freshness = False
        config.enable_quality = False
        return config

    def weights(self) -> dict[str, float]:
        return {
            "bm25": self.bm25_weight,
            "title": self.title_weight if self.enable_title else 0.0,
            "url": self.url_weight if self.enable_url else 0.0,
            "freshness": self.freshness_weight if self.enable_freshness else 0.0,
            "quality": self.quality_weight if self.enable_quality else 0.0,
        }


class RankingPipeline:
    """Combines BM25 with the configured signals."""

    def __init__(
        self,
        signals: Iterable[RankingSignal] | None = None,
        config: RankingConfig | None = None,
        tokenizer: Tokenizer | None = None,
    ) -> None:
        self.config = config or RankingConfig()
        self.tokenizer: Tokenizer = tokenizer or default_tokenizer()
        self.signals: list[RankingSignal] = (
            list(signals) if signals is not None else _default_signals(self.tokenizer)
        )

    def rank(
        self,
        query: str,
        *,
        index: InvertedIndex,
        limit: int = 10,
        offset: int = 0,
    ) -> list[RankedHit]:
        if limit <= 0:
            return []
        tokens = self.tokenizer.tokenize(query)
        if not tokens:
            return []
        bm25 = BM25(index, tokenizer=self.tokenizer)
        hits = bm25.score_terms(tokens)
        weights = self.config.weights()
        ranked: list[RankedHit] = []
        for hit in hits:
            signals: list[SignalScore] = []
            for signal in self.signals:
                if weights.get(signal.name, 0.0) == 0.0:
                    continue
                signals.append(
                    signal.compute(
                        index=index,
                        bm25_hit=hit,
                        query_terms=tokens,
                        config=self.config,
                    )
                )
            weighted = sum(signal.value * weights.get(signal.name, 0.0) for signal in signals)
            bm25_weighted = hit.score * weights.get("bm25", 0.0)
            ranked.append(
                RankedHit(
                    doc_id=hit.doc_id,
                    bm25_score=hit.score,
                    final_score=bm25_weighted + weighted,
                    matched_terms=hit.matched_terms,
                    signals=tuple(signals),
                )
            )
        ranked.sort(key=lambda hit: (-hit.final_score, hit.doc_id))
        return ranked[offset : offset + limit]

    def explain(self, hit: RankedHit) -> dict[str, float]:
        return hit.explanation()


def _default_signals(tokenizer: Tokenizer) -> list[RankingSignal]:
    return [
        ExactTitleSignal(tokenizer),
        UrlRelevanceSignal(tokenizer),
        FreshnessSignal(),
        QualitySignal(),
    ]


# ----------------------------------------------------------------------
# Built-in signals.
# ----------------------------------------------------------------------


@dataclass(slots=True)
class ExactTitleSignal(RankingSignal):
    """Boosts documents whose title contains every query term."""

    name = "title"
    tokenizer: Tokenizer = field(default_factory=default_tokenizer)

    def compute(  # type: ignore[override]
        self,
        *,
        index: InvertedIndex,
        bm25_hit: BM25Hit,
        query_terms: Sequence[str],
        config: RankingConfig,
    ) -> SignalScore:
        field = index.document(bm25_hit.doc_id)
        if field is None or not field.title:
            return SignalScore(name=self.name, value=0.0)
        title_tokens = {token.term for token in self.tokenizer.stream(field.title)}
        if not query_terms:
            return SignalScore(name=self.name, value=0.0)
        matched = sum(1 for term in query_terms if term in title_tokens)
        score = matched / len(query_terms)
        return SignalScore(name=self.name, value=score, raw=float(matched))


@dataclass(slots=True)
class UrlRelevanceSignal(RankingSignal):
    """Rewards URLs that contain query tokens in their path or hostname."""

    name = "url"
    tokenizer: Tokenizer = field(default_factory=default_tokenizer)

    def compute(  # type: ignore[override]
        self,
        *,
        index: InvertedIndex,
        bm25_hit: BM25Hit,
        query_terms: Sequence[str],
        config: RankingConfig,
    ) -> SignalScore:
        field = index.document(bm25_hit.doc_id)
        if field is None or not field.url:
            return SignalScore(name=self.name, value=0.0)
        lowered = field.url.lower()
        matched = sum(1 for term in query_terms if term and term in lowered)
        if not query_terms:
            return SignalScore(name=self.name, value=0.0)
        score = matched / len(query_terms)
        return SignalScore(name=self.name, value=score, raw=float(matched))


@dataclass(slots=True)
class FreshnessSignal(RankingSignal):
    """Decays the contribution of documents that have not been refreshed.

    The signal is intentionally simple: documents crawled in the last
    seven days get a full contribution, older documents decay linearly to
    zero over one year.
    """

    name = "freshness"

    def compute(  # type: ignore[override]
        self,
        *,
        index: InvertedIndex,
        bm25_hit: BM25Hit,
        query_terms: Sequence[str],
        config: RankingConfig,
    ) -> SignalScore:
        field = index.document(bm25_hit.doc_id)
        if field is None:
            return SignalScore(name=self.name, value=0.0)
        # We do not store the last crawl timestamp inside the in-memory
        # index yet, so we fall back to a neutral contribution of 0.5.
        # Once the storage layer is queried for the timestamp the formula
        # below should be used:
        #   age_days = (now - last_crawled).days
        #   decay = max(0.0, 1 - age_days / 365)
        #   return SignalScore(name=self.name, value=decay, raw=age_days)
        return SignalScore(name=self.name, value=0.5, raw=0.0)


@dataclass(slots=True)
class QualitySignal(RankingSignal):
    """Penalises documents with unusually short or empty bodies."""

    name = "quality"

    def compute(  # type: ignore[override]
        self,
        *,
        index: InvertedIndex,
        bm25_hit: BM25Hit,
        query_terms: Sequence[str],
        config: RankingConfig,
    ) -> SignalScore:
        stats = index.stats
        field = index.document(bm25_hit.doc_id)
        if field is None or stats.num_documents == 0:
            return SignalScore(name=self.name, value=0.5)
        if field.doc_length <= 0:
            return SignalScore(name=self.name, value=0.0)
        # Soft reward based on length percentile.
        avg_dl = stats.avg_document_length or 1.0
        ratio = field.doc_length / avg_dl
        # Map ratio in [0.2, 3.0] to [0.0, 1.0] using a smooth function.
        norm = 1 / (1 + math.exp(-(ratio - 1)))
        return SignalScore(name=self.name, value=norm, raw=field.doc_length)
