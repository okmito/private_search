"""Unit tests for the URL frontier."""

from __future__ import annotations

from privatesearch.crawler.frontier import Frontier


def test_frontier_deduplicates_urls() -> None:
    frontier = Frontier()
    assert frontier.push("https://example.com/a")
    assert not frontier.push("https://example.com/a")
    assert "https://example.com/a" in frontier


def test_frontier_pops_in_bfs_order() -> None:
    frontier = Frontier()
    frontier.push("https://example.com/root", depth=0)
    frontier.push("https://example.com/child-a", depth=1)
    frontier.push("https://example.com/child-b", depth=1)
    frontier.push("https://example.com/grand", depth=2)

    assert frontier.pop().url == "https://example.com/root"
    # Same depth: order follows insertion.
    next_two = [frontier.pop().url, frontier.pop().url]
    assert next_two == [
        "https://example.com/child-a",
        "https://example.com/child-b",
    ]
    assert frontier.pop().url == "https://example.com/grand"
    assert frontier.pop() is None


def test_frontier_releases_seen_on_pop() -> None:
    frontier = Frontier()
    frontier.push("https://example.com/a")
    assert "https://example.com/a" in frontier
    frontier.pop()
    # After popping, the URL is no longer considered "seen" so it can be
    # re-queued if the caller wants to.
    assert "https://example.com/a" not in frontier


def test_frontier_push_many_returns_count() -> None:
    frontier = Frontier()
    added = frontier.push_many(
        ["https://example.com/a", "https://example.com/a", "https://example.com/b"],
        depth=1,
    )
    assert added == 2
    assert len(frontier) == 2
