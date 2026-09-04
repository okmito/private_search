"""Crawler worker entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from privatesearch.common.config import get_settings
from privatesearch.crawler.crawler import CrawlConfig, Crawler
from privatesearch.indexing.pipeline import IndexingPipeline


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PrivateSearch crawler")
    parser.add_argument(
        "--seed-urls",
        nargs="+",
        help="One or more URLs to start crawling from.",
    )
    parser.add_argument(
        "--allowed-domains",
        nargs="+",
        help="Restrict crawling to these hosts. Defaults to the host of each seed.",
    )
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional JSON file with crawler configuration overrides.",
    )
    parser.add_argument(
        "--print-stats",
        action="store_true",
        help="Print the crawl statistics as JSON to stdout at the end.",
    )
    return parser.parse_args(argv)


def _apply_overrides(args: argparse.Namespace) -> CrawlConfig:
    settings = get_settings()
    config = CrawlConfig.from_settings(settings)
    if args.max_depth is not None:
        config.max_depth = args.max_depth
    if args.max_pages is not None:
        config.max_pages = args.max_pages
    if args.delay is not None:
        config.delay_seconds = args.delay
    if args.allowed_domains:
        config.allowed_domains = args.allowed_domains
    if args.config:
        overrides = json.loads(args.config.read_text(encoding="utf-8"))
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    if args.seed_urls:
        config.seed_urls = args.seed_urls
    if not config.allowed_domains:
        config.allowed_domains = sorted(
            {
                (urlparse(url).hostname or "").lower()
                for url in config.seed_urls
                if urlparse(url).hostname
            }
        )
    return config


async def _run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = _apply_overrides(args)
    if not config.seed_urls:
        print("No seed URLs provided. Use --seed-urls or SEED_URLS env var.", file=sys.stderr)
        return 1
    crawler = Crawler(config)
    crawl_result = await crawler.run()
    pipeline = IndexingPipeline()
    indexing = pipeline.index_crawl_result(crawl_result)
    if indexing.failed:
        logging.warning("Indexing had %s failed documents", indexing.failed)
    if args.print_stats:
        payload = {
            "crawl": {
                "pages_fetched": crawl_result.stats.pages_fetched,
                "pages_failed": crawl_result.stats.pages_failed,
                "pages_skipped": crawl_result.stats.pages_skipped,
                "bytes_downloaded": crawl_result.stats.bytes_downloaded,
                "duration_seconds": crawl_result.stats.duration_seconds,
            },
            "indexing": {
                "inserted": indexing.inserted,
                "updated": indexing.updated,
                "duplicates": indexing.duplicates,
                "failed": indexing.failed,
            },
            "errors": crawl_result.errors[:20],
        }
        print(json.dumps(payload, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_run(_parse_args(list(argv) if argv is not None else None)))


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
