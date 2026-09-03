"""Tokenizer for converting text into normalized tokens.

The tokenizer is intentionally simple and dependency-light. It handles:

* Unicode normalization via ``unicodedata``
* HTML entity unescaping (named, decimal and hex)
* Case folding
* Stop word removal
* Short/long token filtering
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass

__all__ = ["EnglishTokenizer", "Tokenizer", "TokenStream", "default_tokenizer"]


_DEFAULT_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "he",
        "her",
        "his",
        "i",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "she",
        "that",
        "the",
        "they",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "you",
        "your",
    }
)


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True)
class TokenStream:
    """A token with its position inside the source document."""

    term: str
    position: int


class Tokenizer(ABC):
    """Abstract interface for tokenizers."""

    @abstractmethod
    def tokenize(self, text: str) -> list[str]:
        """Return the list of terms for ``text``."""

    @abstractmethod
    def stream(self, text: str) -> list[TokenStream]:
        """Return tokens with positions for ``text``."""


def _basic_clean(text: str) -> str:
    if not text:
        return ""
    # 1. Unicode normalization (compatibility decomposition then recomposition
    #    into composed form so accents and ligatures are canonical).
    text = unicodedata.normalize("NFKC", text)
    # 2. Unescape HTML entities (named, decimal and hex).
    text = _html.unescape(text)
    return text


class EnglishTokenizer(Tokenizer):
    """Lowercase, punctuation-split tokenizer with optional stop words."""

    def __init__(
        self,
        *,
        lowercase: bool = True,
        stop_words: frozenset[str] | None = _DEFAULT_STOP_WORDS,
        min_token_length: int = 2,
        max_token_length: int = 40,
    ) -> None:
        self.lowercase = lowercase
        self.stop_words = stop_words
        self.min_token_length = min_token_length
        self.max_token_length = max_token_length

    def tokenize(self, text: str) -> list[str]:
        return [token.term for token in self.stream(text)]

    def stream(self, text: str) -> list[TokenStream]:
        cleaned = _basic_clean(text)
        tokens: list[TokenStream] = []
        for match in _TOKEN_RE.finditer(cleaned):
            raw = match.group(0)
            term = raw.lower() if self.lowercase else raw
            if len(term) < self.min_token_length or len(term) > self.max_token_length:
                continue
            if self.stop_words and term in self.stop_words:
                continue
            tokens.append(TokenStream(term=term, position=match.start()))
        return tokens


_default_tokenizer = EnglishTokenizer()


def default_tokenizer() -> EnglishTokenizer:
    """Return the process-wide default tokenizer instance."""

    return _default_tokenizer