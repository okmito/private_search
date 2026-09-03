"""Shared pytest fixtures for PrivateSearch tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect all writable paths to a temporary directory per test."""

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(data_dir / 'test.sqlite').as_posix()}")
    monkeypatch.setenv("PRIVATESEARCH_INDEX_STORAGE_PATH", (data_dir / "index").as_posix())
    monkeypatch.setenv("PRIVATESEARCH_SNAPSHOT_DIR", (data_dir / "snapshots").as_posix())
    monkeypatch.setenv("PRIVATESEARCH_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("PRIVATESEARCH_ENABLE_SEMANTIC_SEARCH", "false")
    # Make sure the cached settings module sees the overrides.
    from privatesearch.common import config as config_module

    config_module.get_settings.cache_clear()
    yield data_dir
    config_module.get_settings.cache_clear()


@pytest.fixture()
def sample_documents() -> list[tuple[int, str, str, str]]:
    """Tiny deterministic corpus used by several tests."""

    return [
        (
            1,
            "https://example.com/ml-intro",
            "Introduction to Machine Learning",
            "Machine learning is a field of computer science that gives computers "
            "the ability to learn without being explicitly programmed.",
        ),
        (
            2,
            "https://example.com/deep-learning",
            "Deep Learning Foundations",
            "Deep learning is a subset of machine learning that uses neural "
            "networks with many layers to model complex patterns.",
        ),
        (
            3,
            "https://example.com/databases",
            "Relational Databases Overview",
            "A relational database stores data in tables. SQL is the standard "
            "language used to query relational databases.",
        ),
        (
            4,
            "https://example.com/vectors",
            "Vector Search Primer",
            "Vector search embeds documents into a high dimensional space and "
            "retrieves nearest neighbours based on similarity.",
        ),
        (
            5,
            "https://example.com/python",
            "Python Programming",
            "Python is a popular programming language widely used for data "
            "science, web development and search engines.",
        ),
    ]