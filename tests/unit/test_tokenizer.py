"""Unit tests for the tokenizer."""

from __future__ import annotations

from privatesearch.document_processing.tokenizer import EnglishTokenizer, default_tokenizer


def test_lowercases_and_strips_punctuation() -> None:
    tokens = default_tokenizer().tokenize("Machine Learning, ROCKS!! 42 times.")
    assert tokens == ["machine", "learning", "rocks", "42", "times"]


def test_removes_stop_words() -> None:
    tokens = default_tokenizer().tokenize("The quick brown fox is a fox")
    # ``the``, ``is`` and ``a`` are stop words.
    assert "the" not in tokens
    assert "is" not in tokens
    assert "a" not in tokens
    assert "fox" in tokens


def test_handles_html_entities_and_unicode() -> None:
    tokens = default_tokenizer().tokenize("Caf&eacute; &amp; Na&iuml;ve — voilà!")
    assert "café" in tokens
    assert "naïve" in tokens
    assert "voilà" in tokens


def test_filters_short_tokens() -> None:
    tokenizer = EnglishTokenizer(min_token_length=3)
    tokens = tokenizer.tokenize("a be cat dog")
    assert tokens == ["cat", "dog"]


def test_stream_returns_positions() -> None:
    stream = default_tokenizer().stream("machine learning machine")
    terms = [token.term for token in stream]
    positions = [token.position for token in stream]
    assert terms == ["machine", "learning", "machine"]
    assert positions[0] < positions[1] < positions[2]


def test_case_sensitivity_is_controllable() -> None:
    tokenizer = EnglishTokenizer(lowercase=False)
    assert tokenizer.tokenize("Machine Learning") == ["Machine", "Learning"]


def test_empty_input_returns_empty_list() -> None:
    assert default_tokenizer().tokenize("") == []
    assert default_tokenizer().tokenize("!!! ???") == []
