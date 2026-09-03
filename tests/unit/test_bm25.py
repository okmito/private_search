"""Unit tests for the BM25 retrieval implementation."""

from __future__ import annotations

import math

import pytest

from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.retrieval.bm25 import BM25


def _fixture_index() -> InvertedIndex:
    index = InvertedIndex()
    index.add_document(
        1,
        text="machine learning is fun",
        title="Machine Learning",
    )
    index.add_document(
        2,
        text="deep learning uses neural networks",
        title="Deep Learning",
    )
    index.add_document(
        3,
        text="relational databases use SQL",
        title="Databases",
    )
    index.add_document(
        4,
        text="vector search uses embeddings and neural networks",
        title="Vector Search",
    )
    return index


def test_bm25_returns_empty_for_empty_query() -> None:
    bm25 = BM25(_fixture_index())
    assert bm25.score("") == []
    assert bm25.score("   !!!  ") == []


def test_bm25_ranks_more_relevant_documents_higher() -> None:
    bm25 = BM25(_fixture_index())
    hits = bm25.score("learning")
    assert len(hits) == 2
    assert hits[0].doc_id == 1  # shorter document wins.
    assert hits[0].score > hits[1].score


def test_bm25_score_matches_textbook_formula() -> None:
    index = _fixture_index()
    bm25 = BM25(index, k1=1.2, b=0.75)
    hits = bm25.score("learning")
    n = index.stats.num_documents  # 4
    df = 2
    avg_dl = index.stats.avg_document_length

    idf = math.log(((n - df + 0.5) / (df + 0.5)) + 1.0)
    dl_doc1 = index.document_length(1)
    dl_doc2 = index.document_length(2)
    expected_doc1 = idf * (
        (1 * (1.2 + 1))
        / (1 + 1.2 * (1 - 0.75 + 0.75 * (dl_doc1 / avg_dl)))
    )
    expected_doc2 = idf * (
        (1 * (1.2 + 1))
        / (1 + 1.2 * (1 - 0.75 + 0.75 * (dl_doc2 / avg_dl)))
    )
    scores = {hit.doc_id: hit.score for hit in hits}
    assert scores[1] == pytest.approx(expected_doc1, rel=1e-6)
    assert scores[2] == pytest.approx(expected_doc2, rel=1e-6)


def test_bm25_idf_stays_non_negative() -> None:
    index = _fixture_index()
    # ``uses`` occurs in 2 of 4 documents, still positive IDF.
    bm25 = BM25(index)
    hits = bm25.score("uses")
    assert hits
    assert all(hit.score > 0 for hit in hits)


def test_bm25_term_frequency_saturation() -> None:
    index = InvertedIndex()
    # Both documents contain "machine" once. The second document also
    # repeats it many extra times so we can observe the BM25 saturation
    # curve. Lengths are balanced to remove length normalisation from the
    # comparison.
    filler = "alpha beta gamma delta epsilon zeta eta iota kappa"
    index.add_document(1, text=filler + " machine")
    index.add_document(2, text=filler + " machine " + " ".join(["machine"] * 50))
    bm25 = BM25(index, k1=1.2, b=0.75)
    hits = bm25.score_terms(["machine"])
    by_doc = {hit.doc_id: hit for hit in hits}
    once_hit = by_doc[1]
    repeated_hit = by_doc[2]
    # The document that repeats the term many times should still rank higher
    # but the additional benefit must plateau thanks to term frequency
    # saturation.
    assert repeated_hit.score > once_hit.score
    assert repeated_hit.score < once_hit.score * 10


def test_bm25_is_deterministic() -> None:
    bm25 = BM25(_fixture_index())
    first = bm25.score("machine learning")
    second = bm25.score("machine learning")
    assert first == second


def test_bm25_validates_parameters() -> None:
    index = _fixture_index()
    with pytest.raises(ValueError):
        BM25(index, k1=-1)
    with pytest.raises(ValueError):
        BM25(index, b=2)


def test_bm25_handles_repeated_query_terms() -> None:
    index = _fixture_index()
    bm25 = BM25(index)
    # Repeated terms must not be double-counted - each unique term should
    # contribute exactly once per document.
    single = {h.doc_id: h.score for h in bm25.score("learning")}
    repeated = {h.doc_id: h.score for h in bm25.score("learning learning learning")}
    assert set(single) == set(repeated)
    for doc_id in single:
        assert single[doc_id] == pytest.approx(repeated[doc_id])


def test_bm25_filters_zero_score_documents() -> None:
    bm25 = BM25(_fixture_index())
    hits = bm25.score("zzznotavailableterm")
    assert hits == []