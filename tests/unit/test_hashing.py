"""Unit tests for content hashing utilities."""

from __future__ import annotations

from privatesearch.document_processing.hashing import content_fingerprint, content_hash


def test_fingerprint_is_stable_across_whitespace() -> None:
    a = content_fingerprint("Hello   World")
    b = content_fingerprint("Hello World")
    c = content_fingerprint("hello world")
    assert a == b == c


def test_fingerprint_is_case_insensitive() -> None:
    assert content_fingerprint("HELLO world") == content_fingerprint("hello WORLD")


def test_fingerprint_drops_common_stop_words() -> None:
    fp = content_fingerprint("The quick brown fox of the year")
    # ``the`` and ``of`` are filtered out
    assert "the" not in fp.split()
    assert "of" not in fp.split()
    assert "quick" in fp.split()


def test_content_hash_changes_when_text_changes() -> None:
    assert content_hash("hello world") != content_hash("hello universe")


def test_content_hash_is_stable_for_equivalent_content() -> None:
    assert content_hash("Hello WORLD") == content_hash("hello world")


def test_content_hash_returns_hex_string_of_expected_length() -> None:
    digest = content_hash("anything")
    assert len(digest) == 64
    int(digest, 16)
