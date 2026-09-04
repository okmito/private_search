"""Seed demo documents so the search feels like a search engine immediately."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from privatesearch.crawler.crawler import CrawledPage  # noqa: E402
from privatesearch.indexing.pipeline import IndexingPipeline  # noqa: E402
from privatesearch.storage.engine import close_engine, init_database  # noqa: E402


def _demo_pages() -> list[CrawledPage]:
    base = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
    docs: list[tuple[str, str, str, str]] = [
        (
            "https://example.com/ml-intro",
            "Introduction to Machine Learning",
            "Machine learning is a field of computer science that gives computers "
            "the ability to learn without being explicitly programmed.",
        ),
        (
            "https://example.com/deep-learning",
            "Deep Learning Foundations",
            "Deep learning is a subset of machine learning that uses neural networks "
            "with many layers to model complex patterns.",
        ),
        (
            "https://example.com/transformers",
            "Transformers in NLP",
            "The transformer architecture underpins modern natural language processing models.",
        ),
        (
            "https://example.com/databases",
            "Relational Databases",
            "A relational database stores data in tables queried with SQL.",
        ),
        (
            "https://example.com/sql-tuning",
            "SQL Performance Tuning",
            "Indexing, statistics and query rewriting improve the performance of SQL workloads.",
        ),
        (
            "https://example.com/cooking",
            "Cooking Pasta",
            "Pasta recipes, Italian cuisine and beginner-friendly cooking guides.",
        ),
        (
            "https://example.com/python-intro",
            "Python for Data Science",
            "Python is widely used for data science thanks to numpy, pandas and scikit-learn.",
        ),
        (
            "https://example.com/vector-search",
            "Vector Search Primer",
            "Vector search embeds documents into a high-dimensional space and retrieves "
            "nearest neighbours based on similarity.",
        ),
        (
            "https://example.com/embeddings",
            "Embedding Models",
            "Embedding models project text into dense vectors that capture semantics.",
        ),
        (
            "https://example.com/ranking",
            "Learning to Rank",
            "Learning to rank trains a model to combine BM25 scores, link authority "
            "and freshness signals.",
        ),
        # Extra youtube/music docs so "youtube" has hits
        (
            "https://example.com/youtube-guide",
            "YouTube Creator Guide",
            "YouTube is a video platform for creators. This guide covers youtube channel "
            "growth, youtube analytics, and youtube monetization for music and education videos.",
        ),
        (
            "https://example.com/youtube-music",
            "YouTube Music Explained",
            "YouTube Music is a streaming service. Learn how youtube music recommends "
            "songs, youtube music playlists, and the difference between youtube and youtube music.",
        ),
        (
            "https://example.com/video-search",
            "Video Search on YouTube",
            "Searching youtube videos uses titles, descriptions and transcripts. "
            "YouTube search ranking combines watch time and relevance for video search.",
        ),
        (
            "https://example.com/music-theory",
            "Music Theory for Beginners",
            "Music theory covers scales, chords and rhythm for guitar covers and live performance.",
        ),
        (
            "https://example.com/privacy-search",
            "Private Search vs Tracking",
            "PrivateSearch avoids third-party analytics and cross-site tracking. Self-hosted "
            "search keeps queries private unlike ad-driven recommendations.",
        ),
        (
            "https://example.com/crawler",
            "Building a Web Crawler",
            "A web crawler respects robots.txt, crawl delays and domain allowlists. "
            "SSRF protection blocks private IPs and cloud metadata endpoints.",
        ),
        (
            "https://example.com/bm25",
            "BM25 Ranking Explained",
            "BM25 scores documents by term frequency, inverse document frequency and "
            "length normalization with parameters k1 and b.",
        ),
        (
            "https://example.com/fastapi",
            "FastAPI Search API",
            "FastAPI powers the PrivateSearch API with search, suggestions, health and stats endpoints.",
        ),
        (
            "https://example.com/nextjs",
            "Next.js Search UI",
            "The Next.js frontend provides a search box, highlighted snippets, pagination "
            "and dark/light theme without tracking.",
        ),
        (
            "https://example.com/hybrid",
            "Hybrid Search: BM25 + Vectors",
            "Hybrid search combines lexical BM25 and semantic vector similarity for diverse "
            "queries, evaluated with Precision, Recall, MRR and nDCG.",
        ),
    ]
    pages: list[CrawledPage] = []
    for url, title, body in docs:
        pages.append(
            CrawledPage(
                url=url,
                canonical_url=url,
                title=title,
                description=body[:120],
                body=body,
                headings=[title],
                links=[],
                language="en",
                published_at=None,
                fetched_at=base,
                status=200,
                depth=0,
            )
        )
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed PrivateSearch with demo documents")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the inverted index before seeding (DB rows are deduped by hash).",
    )
    args = parser.parse_args(argv)
    init_database()
    pipeline = IndexingPipeline()
    if args.reset:
        pipeline.index.clear()
    pages = _demo_pages()
    result = pipeline.index_pages(pages)
    # Reload from storage so stats are accurate even if duplicates were skipped
    count = pipeline.load_from_storage()
    print(
        f"Seeded {len(pages)} demo pages -> inserted={result.inserted} "
        f"updated={result.updated} duplicates={result.duplicates} failed={result.failed} "
        f"total_in_index={count} terms={pipeline.index.stats.num_terms}"
    )
    print(
        'Try: curl "http://localhost:8000/api/v1/search?q=youtube"  or search "youtube" in the UI'
    )
    close_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
