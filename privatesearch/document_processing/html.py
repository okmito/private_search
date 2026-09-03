"""HTML processing utilities used by the crawler."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from privatesearch.document_processing.url_normalize import NormalizedUrl, normalize_url

__all__ = ["ExtractedDocument", "extract_document"]


@dataclass(slots=True)
class ExtractedDocument:
    """Result of parsing an HTML response."""

    url: str
    canonical_url: str | None
    title: str
    description: str
    body: str
    headings: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    language: str | None = None
    published_at: str | None = None

    def to_metadata(self) -> dict[str, object]:
        return {
            "url": self.url,
            "canonical_url": self.canonical_url or self.url,
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "published_at": self.published_at,
            "headings": list(self.headings),
        }


_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _extract_meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if isinstance(tag, Tag):
        content = tag.get("content")
        if isinstance(content, str):
            return content.strip()
    return None


def _extract_property(soup: BeautifulSoup, property_name: str) -> str | None:
    tag = soup.find("meta", attrs={"property": property_name})
    if isinstance(tag, Tag):
        content = tag.get("content")
        if isinstance(content, str):
            return content.strip()
    return None


def _extract_canonical(soup: BeautifulSoup, page_url: str) -> str | None:
    tag = soup.find("link", attrs={"rel": "canonical"})
    if isinstance(tag, Tag):
        href = tag.get("href")
        if isinstance(href, str):
            normalized = normalize_url(href, base=page_url)
            if normalized is not None:
                return normalized.url
    return None


def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return _collapse_whitespace(soup.title.string)
    og_title = _extract_property(soup, "og:title")
    if og_title:
        return _collapse_whitespace(og_title)
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        return _collapse_whitespace(h1.get_text(" ", strip=True))
    return ""


def _extract_headings(soup: BeautifulSoup) -> list[str]:
    headings: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        if isinstance(tag, Tag):
            text = _collapse_whitespace(tag.get_text(" ", strip=True))
            if text:
                headings.append(text)
    return headings


def _extract_main_text(soup: BeautifulSoup) -> str:
    for selector in ("main", "article", "[role=main]"):
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            return _collapse_whitespace(node.get_text(" ", strip=True))
    body = soup.body
    if isinstance(body, Tag):
        return _collapse_whitespace(body.get_text(" ", strip=True))
    return _collapse_whitespace(soup.get_text(" ", strip=True))


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        normalized = normalize_url(href, base=base_url)
        if normalized is None:
            continue
        if normalized.url in seen:
            continue
        seen.add(normalized.url)
        links.append(normalized.url)
    return links


def extract_document(html: str, url: str) -> ExtractedDocument:
    """Parse ``html`` and return an :class:`ExtractedDocument`.

    The parser strips ``script``/``style``/``noscript`` blocks before
    extracting the main text. It is deliberately conservative: it returns an
    empty body rather than raising when the markup is malformed.
    """

    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "template"]):
        tag.decompose()

    canonical = _extract_canonical(soup, url) or url
    normalized_url = normalize_url(url) or NormalizedUrl(
        url=url,
        scheme="http",
        host="",
        port=None,
        path="/",
        is_canonical=False,
    )
    title = _extract_title(soup)
    description = (
        _extract_meta(soup, "description")
        or _extract_property(soup, "og:description")
        or ""
    )
    body = _extract_main_text(soup)
    headings = _extract_headings(soup)
    links = _extract_links(soup, normalized_url.url)
    language = soup.html.get("lang") if soup.html else None
    published_at = _extract_meta(soup, "article:published_time") or _extract_property(
        soup, "article:published_time"
    )
    return ExtractedDocument(
        url=normalized_url.url,
        canonical_url=canonical,
        title=_collapse_whitespace(title),
        description=_collapse_whitespace(description),
        body=body,
        headings=headings,
        links=links,
        language=language,
        published_at=published_at,
    )