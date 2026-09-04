"""Pytest configuration shared across the project."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "privatesearch"
APPS_DIR = ROOT / "apps"

for path in (PACKAGES_DIR, APPS_DIR):
    path_str = path.as_posix()
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import os  # noqa: E402

# Force a deterministic, isolated working directory for tests.
TEST_DATA_DIR = ROOT / "data" / "test"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(TEST_DATA_DIR / 'test.sqlite').as_posix()}")
os.environ.setdefault("PRIVATESEARCH_INDEX_STORAGE_PATH", (TEST_DATA_DIR / "index").as_posix())
os.environ.setdefault("PRIVATESEARCH_SNAPSHOT_DIR", (TEST_DATA_DIR / "snapshots").as_posix())
os.environ.setdefault("PRIVATESEARCH_LOG_LEVEL", "WARNING")
os.environ.setdefault("PRIVATESEARCH_ENABLE_SEMANTIC_SEARCH", "false")
