"""Unit tests for URL normalisation and safety checks."""

from __future__ import annotations

import pytest

from privatesearch.document_processing.url_normalize import (
    is_blocked_host,
    is_safe_public_host,
    normalize_url,
    same_site,
)


def test_normalize_lowercases_scheme_and_host() -> None:
    result = normalize_url("HTTP://Example.COM/Path")
    assert result is not None
    assert result.scheme == "http"
    assert result.host == "example.com"
    assert result.url.startswith("http://example.com/Path")


def test_normalize_drops_default_port() -> None:
    result = normalize_url("https://example.com:443/x")
    assert result is not None
    assert result.port is None
    assert ":443" not in result.url


def test_normalize_preserves_explicit_port() -> None:
    result = normalize_url("https://example.com:8443/x")
    assert result is not None
    assert result.port == 8443
    assert ":8443" in result.url


def test_normalize_drops_fragment() -> None:
    result = normalize_url("https://example.com/page#section-2")
    assert result is not None
    assert "#" not in result.url


def test_normalize_strips_tracking_query_params() -> None:
    result = normalize_url("https://example.com/article?utm_source=x&page=2")
    assert result is not None
    assert "utm_source" not in result.url
    assert "page=2" in result.url


def test_normalize_resolves_relative_urls() -> None:
    result = normalize_url("/article/2", base="https://example.com/section/")
    assert result is not None
    assert result.url == "https://example.com/article/2"


def test_normalize_rejects_non_http_schemes() -> None:
    assert normalize_url("ftp://example.com/file") is None
    assert normalize_url("javascript:alert(1)") is None
    assert normalize_url("file:///etc/passwd") is None
    assert normalize_url("") is None


def test_normalize_keeps_query_parameters_sorted() -> None:
    result = normalize_url("https://example.com/?b=2&a=1")
    assert result is not None
    assert result.url.endswith("?a=1&b=2")


def test_is_blocked_host_blocks_localhost() -> None:
    assert is_blocked_host("localhost")
    assert is_blocked_host("127.0.0.1")
    assert is_blocked_host("::1")


def test_is_blocked_host_blocks_private_ips() -> None:
    assert is_blocked_host("10.0.0.5")
    assert is_blocked_host("192.168.1.1")
    assert is_blocked_host("169.254.169.254")


def test_is_safe_public_host_respects_allowlist() -> None:
    assert is_safe_public_host("example.com", allowed=["example.com", "example.org"])
    assert not is_safe_public_host("evil.example.com", allowed=["example.com"])


def test_same_site_compares_host_and_scheme() -> None:
    assert same_site("https://example.com/a", "https://example.com/b")
    assert not same_site("https://example.com/a", "http://example.com/a")
    assert not same_site("https://example.com/a", "https://other.com/a")


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.com/", True),
        ("http://Example.com", True),
        ("//example.com", False),  # protocol-relative is rejected
        ("http:///path", False),
    ],
)
def test_normalize_edge_cases(url: str, expected: bool) -> None:
    assert (normalize_url(url) is not None) == expected
