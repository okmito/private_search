"""Snippet generation for search results."""

from __future__ import annotations

from dataclasses import dataclass

from privatesearch.document_processing.tokenizer import Tokenizer, default_tokenizer
from privatesearch.indexing.inverted_index import InvertedIndex

__all__ = ["Snippet", "build_snippet"]


@dataclass(frozen=True, slots=True)
class Snippet:
    """A highlighted snippet extracted from a document body."""

    text: str
    highlighted: str
    matched_positions: tuple[int, ...]

    def to_html(self) -> str:
        return f'<span class="snippet">{self.highlighted}</span>'


def _find_positions(text: str, term: str) -> list[int]:
    """Return character offsets where ``term`` occurs in ``text``."""

    if not term:
        return []
    positions: list[int] = []
    start = 0
    lower = text.lower()
    needle = term.lower()
    while True:
        idx = lower.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + max(len(needle), 1)
    return positions


def build_snippet(
    text: str,
    *,
    query_terms: list[str],
    tokenizer: Tokenizer | None = None,
    max_length: int = 240,
    highlight_open: str = "<mark>",
    highlight_close: str = "</mark>",
) -> Snippet:
    """Return a snippet around the earliest occurrence of any ``query_terms``."""

    if not text:
        return Snippet(text="", highlighted="", matched_positions=())

    matched_positions = sorted({pos for term in query_terms for pos in _find_positions(text, term)})
    start = 0
    end = len(text)
    if matched_positions:
        first = matched_positions[0]
        half = max_length // 2
        start = max(0, first - half)
        end = min(len(text), start + max_length)
        start = max(0, end - max_length)
    snippet_text = text[start:end]

    if start > 0:
        snippet_text = "..." + snippet_text
    if end < len(text):
        snippet_text = snippet_text + "..."

    # Build the highlighted version by walking through positions inside the
    # extracted window only.
    window_text = text[start:end]
    lower_terms = sorted({term.lower() for term in query_terms if term})
    if not lower_terms:
        return Snippet(text=snippet_text, highlighted=snippet_text, matched_positions=tuple(matched_positions))

    # Replace occurrences of the matched terms inside the window text.
    highlighted_chunks: list[str] = []
    cursor = 0
    lower_window = window_text.lower()
    boundary = len(window_text)
    while cursor < boundary:
        next_match: tuple[int, str] | None = None
        for term in lower_terms:
            idx = lower_window.find(term, cursor)
            if idx == -1:
                continue
            if next_match is None or idx < next_match[0]:
                next_match = (idx, term)
        if next_match is None:
            highlighted_chunks.append(window_text[cursor:])
            break
        idx, term = next_match
        highlighted_chunks.append(window_text[cursor:idx])
        highlighted_chunks.append(highlight_open)
        highlighted_chunks.append(window_text[idx : idx + len(term)])
        highlighted_chunks.append(highlight_close)
        cursor = idx + len(term)
    highlighted_window = "".join(highlighted_chunks)

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return Snippet(
        text=snippet_text,
        highlighted=f"{prefix}{highlighted_window}{suffix}",
        matched_positions=tuple(matched_positions),
    )


def collect_matched_positions(index: InvertedIndex, doc_id: int, terms: list[str]) -> list[int]:
    """Aggregate every token position in ``doc_id`` that matches any of ``terms``."""

    positions: list[int] = []
    for term in terms:
        for posting in index.get_postings(term):
            if posting.doc_id == doc_id:
                positions.extend(posting.positions)
    return sorted(positions)