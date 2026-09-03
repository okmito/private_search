"""Unit tests for snippet generation and the high-level retriever."""

from __future__ import annotations

from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.retrieval.retriever import Retriever
from privatesearch.retrieval.snippets import build_snippet


def _index_with_corpus() -> tuple[InvertedIndex, list[tuple[int, str, str, str]]]:
    index = InvertedIndex()
    corpus = [
        (
            1,
            "https://example.com/ml-intro",
            "Introduction to Machine Learning",
            "Machine learning is a field of computer science that gives computers "
            "the ability to learn without being explicitly programmed.",
        ),
        (
            2,
            "https://example.com/deep-learning",
            "Deep Learning Foundations",
            "Deep learning is a subset of machine learning that uses neural "
            "networks with many layers to model complex patterns.",
        ),
        (
            3,
            "https://example.com/databases",
            "Relational Databases Overview",
            "A relational database stores data in tables. SQL is the standard "
            "language used to query relational databases.",
        ),
    ]
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)
    return index, corpus


def test_retriever_search_paginates_results() -> None:
    index, corpus = _index_with_corpus()
    retriever = Retriever(index)

    first_page = retriever.search("machine learning", limit=1, offset=0, documents=corpus)
    second_page = retriever.search("machine learning", limit=1, offset=1, documents=corpus)

    assert len(first_page) == 1
    assert len(second_page) == 1
    assert first_page[0].doc_id != second_page[0].doc_id
    assert first_page[0].score >= second_page[0].score


def test_retriever_search_returns_metadata() -> None:
    index, corpus = _index_with_corpus()
    retriever = Retriever(index)
    results = retriever.search("machine", limit=5, documents=corpus)
    assert results
    top = results[0]
    assert top.url
    assert top.title
    assert "machine" in top.snippet.text.lower() or "machine" in top.snippet.highlighted.lower()


def test_retriever_search_empty_query_returns_no_results() -> None:
    index, corpus = _index_with_corpus()
    retriever = Retriever(index)
    assert retriever.search("", documents=corpus) == []
    assert retriever.search("   ???  ", documents=corpus) == []


def test_retriever_count_matches_results() -> None:
    index, corpus = _index_with_corpus()
    retriever = Retriever(index)
    assert retriever.count("machine learning") == len(
        retriever.search("machine learning", limit=100, documents=corpus)
    )


def test_snippet_highlight_wraps_matched_terms() -> None:
    text = (
        "Machine learning is a field of computer science that gives computers "
        "the ability to learn without being explicitly programmed."
    )
    snippet = build_snippet(text, query_terms=["machine", "learning"])
    # The snippet must wrap the matched terms. The original casing of the
    # source text is preserved, so we compare case-insensitively.
    highlighted_lower = snippet.highlighted.lower()
    assert "<mark>machine</mark>" in highlighted_lower
    assert "<mark>learning</mark>" in highlighted_lower


def test_snippet_respects_max_length() -> None:
    text = "machine learning " * 100
    snippet = build_snippet(text, query_terms=["machine"], max_length=80)
    assert len(snippet.text) <= 80 + 6  # Allow for ellipsis prefix/suffix.


def test_snippet_handles_missing_terms() -> None:
    snippet = build_snippet("no matches here", query_terms=["machine"])
    assert snippet.highlighted == "no matches here"
    assert snippet.matched_positions == ()