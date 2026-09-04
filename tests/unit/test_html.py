"""Unit tests for HTML extraction."""

from __future__ import annotations

from privatesearch.document_processing.html import extract_document

HTML = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>  Original Title  </title>
    <meta name="description" content="A short summary of the article.">
    <link rel="canonical" href="https://example.com/canonical">
  </head>
  <body>
    <nav>Skip this navigation</nav>
    <main>
      <h1>Headline</h1>
      <h2>Subhead</h2>
      <p>Machine learning is <strong>fun</strong> and useful.</p>
      <p>Read more on <a href="/related">related content</a>.</p>
      <script>alert('nope')</script>
    </main>
  </body>
</html>
"""


def test_extract_title_strips_whitespace() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert document.title == "Original Title"


def test_extract_description_from_meta() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert document.description == "A short summary of the article."


def test_extract_canonical_resolves_against_base() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert document.canonical_url == "https://example.com/canonical"


def test_extract_main_text_excludes_navigation_and_scripts() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert "Skip this navigation" not in document.body
    assert "alert" not in document.body
    assert "Machine learning" in document.body


def test_extract_headings_collects_h1_to_h3() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert "Headline" in document.headings
    assert "Subhead" in document.headings


def test_extract_links_resolves_relative_urls() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert "https://example.com/related" in document.links


def test_extract_handles_empty_html() -> None:
    document = extract_document("", "https://example.com/x")
    assert document.title == ""
    assert document.body == ""
    assert document.links == []


def test_extract_detects_language() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert document.language == "en"


def test_extract_uses_canonical_url_when_present() -> None:
    document = extract_document(HTML, "https://example.com/article")
    assert document.canonical_url == "https://example.com/canonical"
