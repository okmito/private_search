"""Helpers for computing content hashes used in deduplication."""

from __future__ import annotations

import hashlib

__all__ = ["content_hash", "content_fingerprint"]


def content_fingerprint(text: str) -> str:
    """Return a normalised, lower-cased representation used for near-duplicate detection."""

    if not text:
        return ""
    # Lowercase, collapse whitespace and remove the most common stop words to
    # produce a stable fingerprint that survives light re-formatting.
    lowered = text.lower()
    cleaned: list[str] = []
    for token in lowered.split():
        if not token:
            continue
        if token in {"the", "a", "an", "and", "or", "of", "to", "is", "in"}:
            continue
        cleaned.append(token.strip(".,;:!?\"'()[]{}"))
    return " ".join(filter(None, cleaned))


def content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of the normalised content fingerprint."""

    return hashlib.sha256(content_fingerprint(text).encode("utf-8")).hexdigest()
