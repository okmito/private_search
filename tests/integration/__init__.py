"""Integration tests for PrivateSearch."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "privatesearch"))
sys.path.insert(0, str(ROOT / "apps"))
