"""Unit tests for the embedding-based semantic search."""

from __future__ import annotations

import pytest

from privatesearch.embeddings.base import cosine_similarity
from privatesearch.embeddings.tfidf import TFIDFEmbedding
from privatesearch.embeddings.vector_store import InMemoryVectorStore
from privatesearch.indexing.inverted_index import InvertedIndex
from privatesearch.retrieval.hybrid import HybridConfig, HybridSearch


def _corpus() -> list[tuple[int, str, str, str]]:
    return [
        (1, "https://example.com/a", "Apples", "apple apple apple fruit fresh"),
        (2, "https://example.com/b", "Bananas", "banana banana banana fruit yellow"),
        (3, "https://example.com/c", "Cars", "car engine vehicle wheels"),
    ]


def test_tfidf_fit_and_embed_produces_normalised_vectors() -> None:
    embedding = TFIDFEmbedding()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in _corpus()])
    vector = embedding.embed(1, "apple apple fruit")
    norm = sum(value * value for value in vector.values) ** 0.5
    assert 0.99 <= norm <= 1.01


def test_tfidf_embed_query_matches_relevant_document() -> None:
    embedding = TFIDFEmbedding()
    corpus = _corpus()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in corpus])
    for doc_id, _, _, body in corpus:
        embedding.embed(doc_id, body)
    query = embedding.embed_query("apple")
    vector = embedding.embed(1, "apple apple apple fruit fresh")
    score = cosine_similarity(query, vector)
    assert score > 0


def test_vector_store_search_returns_top_hits() -> None:
    embedding = TFIDFEmbedding()
    corpus = _corpus()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in corpus])
    store = InMemoryVectorStore()
    for doc_id, _, _, body in corpus:
        store.upsert(embedding.embed(doc_id, body))
    query = embedding.embed_query("apple fruit")
    top = store.search(query, limit=2)
    assert len(top) == 2
    assert top[0].score >= top[1].score
    # The most relevant doc should be the apple one.
    assert top[0].doc_id == 1


def test_hybrid_search_combines_bm25_and_semantic() -> None:
    index = InvertedIndex()
    corpus = _corpus()
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)

    embedding = TFIDFEmbedding()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in corpus])

    hybrid = HybridSearch(index, embedding, config=HybridConfig(bm25_weight=1.0, semantic_weight=1.0))
    hybrid.fit(corpus)

    hits = hybrid.search("apple fruit", limit=3)
    assert hits
    top = hits[0]
    assert top.doc_id == 1
    assert top.semantic_score > 0
    assert top.bm25_score > 0
    # Both components contribute to the final score.
    assert top.final_score > top.semantic_score


def test_hybrid_search_empty_query_returns_no_hits() -> None:
    index = InvertedIndex()
    corpus = _corpus()
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)
    embedding = TFIDFEmbedding()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in corpus])
    hybrid = HybridSearch(index, embedding)
    hybrid.fit(corpus)
    assert hybrid.search("", limit=5) == []


def test_hybrid_search_explanation_contains_components() -> None:
    index = InvertedIndex()
    corpus = _corpus()
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)
    embedding = TFIDFEmbedding()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in corpus])
    hybrid = HybridSearch(index, embedding)
    hybrid.fit(corpus)
    hits = hybrid.search("apple", limit=1)
    assert hits
    explanation = hits[0].explanation()
    assert {"final", "bm25", "semantic", "title"} == set(explanation.keys())


def test_hybrid_search_pagination() -> None:
    index = InvertedIndex()
    corpus = _corpus()
    for doc_id, url, title, body in corpus:
        index.add_document(doc_id, text=body, title=title, url=url)
    embedding = TFIDFEmbedding()
    embedding.fit([(doc_id, body) for doc_id, _, _, body in corpus])
    hybrid = HybridSearch(index, embedding)
    hybrid.fit(corpus)
    page1 = hybrid.search("fruit", limit=1, offset=0)
    page2 = hybrid.search("fruit", limit=1, offset=1)
    assert page1 and page2
    assert page1[0].doc_id != page2[0].doc_id