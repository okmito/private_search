"""Embedding-based semantic search.

This package provides a pluggable :class:`EmbeddingModel` interface and a
lightweight default implementation based on term-frequency / inverse
document-frequency vectors. The default does not require any external
machine-learning libraries and is suitable for environments where
sentence-transformers or larger models cannot be downloaded.

When ``sentence-transformers`` is available a real transformer-based
embedding can be plugged in by implementing :class:`EmbeddingModel`.
"""

from privatesearch.embeddings.base import (
    EmbeddingModel,
    EmbeddingVector,
    cosine_similarity,
)
from privatesearch.embeddings.tfidf import TFIDFEmbedding
from privatesearch.embeddings.vector_store import InMemoryVectorStore, VectorHit

__all__ = [
    "EmbeddingModel",
    "EmbeddingVector",
    "cosine_similarity",
    "TFIDFEmbedding",
    "InMemoryVectorStore",
    "VectorHit",
]
