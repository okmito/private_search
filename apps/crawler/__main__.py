"""Local entry point for the crawler worker."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

from apps.crawler.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())