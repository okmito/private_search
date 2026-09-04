"""Common embedding interface."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence

__all__ = ["EmbeddingModel", "EmbeddingVector", "cosine_similarity"]


class EmbeddingVector:
    """A dense numeric vector with optional metadata."""

    __slots__ = ("values", "doc_id")

    def __init__(self, doc_id: int, values: Sequence[float]) -> None:
        self.doc_id = doc_id
        self.values = tuple(float(value) for value in values)

    def __len__(self) -> int:
        return len(self.values)

    def __iter__(self):
        return iter(self.values)


class EmbeddingModel(ABC):
    """Abstract embedding model interface."""

    name: str = "embedding"

    @abstractmethod
    def fit(self, documents: Sequence[tuple[int, str]]) -> None:
        """Fit any parameters the model needs from the training corpus."""

    @abstractmethod
    def embed(self, doc_id: int, text: str) -> EmbeddingVector:
        """Embed a single document."""

    @abstractmethod
    def embed_query(self, query: str) -> EmbeddingVector:
        """Embed a search query."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""


def cosine_similarity(a: EmbeddingVector, b: EmbeddingVector) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimension mismatch")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a.values, b.values):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
