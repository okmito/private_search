"""Unit tests for the inverted index."""

from __future__ import annotations

from pathlib import Path

import pytest

from privatesearch.indexing.inverted_index import InvertedIndex, Posting


def _build_index() -> InvertedIndex:
    index = InvertedIndex()
    index.add_document(
        1,
        text="machine learning is fun",
        title="Machine Learning",
        url="https://example.com/1",
    )
    index.add_document(
        2,
        text="deep learning uses neural networks",
        title="Deep Learning",
        url="https://example.com/2",
    )
    index.add_document(
        3,
        text="relational databases use SQL",
        title="Databases",
        url="https://example.com/3",
    )
    index.add_document(
        4,
        text="vector search uses embeddings and neural networks",
        title="Vector Search",
        url="https://example.com/4",
    )
    return index


def test_add_document_increases_document_count() -> None:
    index = _build_index()
    assert len(index) == 4
    assert index.stats.num_terms >= 8


def test_get_postings_returns_term_frequency_and_positions() -> None:
    index = _build_index()
    postings = index.get_postings("learning")
    assert {p.doc_id for p in postings} == {1, 2}
    for posting in postings:
        assert isinstance(posting, Posting)
        assert posting.term_frequency >= 1
        assert posting.positions == tuple(sorted(posting.positions))


def test_document_frequency_matches_postings_length() -> None:
    index = _build_index()
    assert index.document_frequency("learning") == 2
    assert index.document_frequency("missing") == 0


def test_remove_document_drops_postings_and_metadata() -> None:
    index = _build_index()
    index.remove_document(2)
    assert 2 not in index
    for posting in index.get_postings("learning"):
        assert posting.doc_id != 2


def test_duplicate_document_id_raises() -> None:
    index = InvertedIndex()
    index.add_document(1, text="foo bar")
    with pytest.raises(ValueError):
        index.add_document(1, text="baz qux")


def test_snapshot_round_trip(tmp_path: Path) -> None:
    original = _build_index()
    snapshot_path = original.save_snapshot(tmp_path / "snapshot.json")
    assert snapshot_path.exists()

    reloaded = InvertedIndex.load_snapshot(snapshot_path)
    assert reloaded.stats.num_documents == original.stats.num_documents
    assert reloaded.stats.num_terms == original.stats.num_terms
    assert reloaded.stats.avg_document_length == pytest.approx(
        original.stats.avg_document_length
    )

    for term in original.terms():
        assert [p.doc_id for p in reloaded.get_postings(term)] == [
            p.doc_id for p in original.get_postings(term)
        ]


def test_clear_empties_the_index() -> None:
    index = _build_index()
    index.clear()
    assert len(index) == 0
    assert index.stats.num_terms == 0
    assert index.terms() == []