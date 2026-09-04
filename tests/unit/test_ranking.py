"""Unit tests for the ranking pipeline."""

from __future__ import annotations

import math

from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.ranking.pipeline import (
    FreshnessSignal,
    QualitySignal,
    RankingConfig,
    RankingPipeline,
)


def _build_index() -> InvertedIndex:
    index = InvertedIndex()
    index.add_document(
        1,
        text="Machine learning is a field of computer science.",
        title="Machine Learning Introduction",
        url="https://example.com/articles/machine-learning-intro",
    )
    index.add_document(
        2,
        text="Relational databases store data in tables queried with SQL.",
        title="Databases 101",
        url="https://example.com/guides/databases",
    )
    index.add_document(
        3,
        text="Cooking recipes for beginners including pasta and pizza.",
        title="Cooking",
        url="https://example.com/cooking/recipes",
    )
    return index


def test_pipeline_returns_results_in_score_order() -> None:
    pipeline = RankingPipeline()
    hits = pipeline.rank("machine learning", index=_build_index(), limit=5)
    assert hits
    assert hits[0].doc_id == 1
    assert hits[0].bm25_score > 0
    assert hits[0].final_score > 0


def test_pipeline_exposes_signal_breakdown() -> None:
    pipeline = RankingPipeline()
    hits = pipeline.rank("machine", index=_build_index(), limit=3)
    assert hits
    top = hits[0]
    names = {signal.name for signal in top.signals}
    assert {"title", "url", "quality"}.issubset(names)
    explanation = pipeline.explain(top)
    assert "bm25" in explanation
    assert "title" in explanation


def test_exact_title_signal_boosts_matching_title() -> None:
    pipeline = RankingPipeline()
    index = _build_index()
    # Document 1's title contains both "machine" and "learning".
    hits = pipeline.rank("machine learning", index=index, limit=5)
    top = hits[0]
    title_signal = next(signal for signal in top.signals if signal.name == "title")
    assert title_signal.value == 1.0


def test_url_signal_matches_query_tokens() -> None:
    pipeline = RankingPipeline()
    index = _build_index()
    hits = pipeline.rank("machine learning", index=index, limit=5)
    top = hits[0]
    url_signal = next(signal for signal in top.signals if signal.name == "url")
    assert url_signal.value > 0


def test_bm25_only_config_disables_other_signals() -> None:
    config = RankingConfig.bm25_only()
    pipeline = RankingPipeline(config=config)
    hits = pipeline.rank("machine learning", index=_build_index(), limit=3)
    assert hits
    # All signals should have weight 0 in bm25-only mode.
    for hit in hits:
        for signal in hit.signals:
            assert signal.value == 0.0


def test_quality_signal_is_bounded_in_unit_interval() -> None:
    index = _build_index()
    signal = QualitySignal()
    from privatesearch.retrieval.bm25 import BM25

    bm25_hits = BM25(index).score_terms(["machine"])
    if bm25_hits:
        score = signal.compute(
            index=index,
            bm25_hit=bm25_hits[0],
            query_terms=["machine"],
            config=RankingConfig(),
        )
        assert 0.0 <= score.value <= 1.0


def test_freshness_signal_returns_neutral_default() -> None:
    signal = FreshnessSignal()
    index = _build_index()
    from privatesearch.retrieval.bm25 import BM25

    bm25_hits = BM25(index).score_terms(["machine"])
    score = signal.compute(
        index=index,
        bm25_hit=bm25_hits[0],
        query_terms=["machine"],
        config=RankingConfig(),
    )
    assert 0.0 <= score.value <= 1.0


def test_custom_signal_weights_change_ordering() -> None:
    index = _build_index()
    baseline = RankingPipeline(config=RankingConfig(title_weight=0.0, url_weight=0.0)).rank(
        "machine learning", index=index, limit=5
    )
    boosted = RankingPipeline(
        config=RankingConfig(title_weight=5.0, bm25_weight=0.0, url_weight=0.0)
    ).rank("machine learning", index=index, limit=5)
    if baseline and boosted:
        # When title weight is high, the doc with the best title wins.
        assert boosted[0].doc_id == 1


def test_ranking_pipeline_handles_empty_query() -> None:
    pipeline = RankingPipeline()
    assert pipeline.rank("", index=_build_index()) == []


def test_signal_score_serialization() -> None:
    index = _build_index()
    pipeline = RankingPipeline()
    hits = pipeline.rank("machine learning", index=index, limit=1)
    assert hits
    top = hits[0]
    payload = top.explanation()
    for key, value in payload.items():
        assert isinstance(key, str)
        assert isinstance(value, float)
        assert math.isfinite(value)


def test_explanation_keys_match_signal_names() -> None:
    """Explainable ranking must expose the same signals that contributed to the final score."""

    config = RankingConfig(
        bm25_weight=1.0,
        title_weight=2.0,
        url_weight=0.5,
        freshness_weight=0.0,
        quality_weight=1.5,
        enable_title=True,
        enable_url=True,
        enable_freshness=False,
        enable_quality=True,
    )
    pipeline = RankingPipeline(config=config)
    hits = pipeline.rank("machine learning", index=_build_index(), limit=3)
    assert hits
    top = hits[0]
    explanation = top.explanation()
    # Disabled signals should not appear in the explanation.
    assert "freshness" not in explanation
    assert "title" in explanation
    assert "url" in explanation
    assert "quality" in explanation
    assert "bm25" in explanation
    assert "final" in explanation
