"""Unit tests for the robots.txt policy helper."""

from __future__ import annotations

from privatesearch.crawler.robots import RobotsPolicy


ROBOTS_BODY = """
User-agent: *
Disallow: /private/
Crawl-delay: 1.5

User-agent: PrivateSearch
Disallow: /api/
"""


def test_load_parses_disallow_and_delay() -> None:
    policy = RobotsPolicy()
    policy.load("https://example.com/robots.txt", ROBOTS_BODY)
    assert "example.com" in list(policy.hosts())
    assert policy.delay_for("example.com") == 1.5


def test_can_fetch_blocks_disallowed_path() -> None:
    policy = RobotsPolicy()
    policy.set_user_agent("*")  # Default block applies to ``*``
    policy.load("https://example.com/robots.txt", ROBOTS_BODY)
    decision = policy.can_fetch("https://example.com/private/file")
    assert decision.allowed is False


def test_can_fetch_allows_public_path() -> None:
    policy = RobotsPolicy()
    policy.load("https://example.com/robots.txt", ROBOTS_BODY)
    decision = policy.can_fetch("https://example.com/about")
    assert decision.allowed is True


def test_can_fetch_falls_back_to_allow_when_unknown_host() -> None:
    policy = RobotsPolicy()
    decision = policy.can_fetch("https://unknown.example.org/")
    assert decision.allowed is True
    assert decision.crawl_delay is None


def test_can_fetch_respects_user_agent_specific_rules() -> None:
    policy = RobotsPolicy()
    policy.set_user_agent("PrivateSearch")
    policy.load("https://example.com/robots.txt", ROBOTS_BODY)
    decision = policy.can_fetch("https://example.com/api/users")
    assert decision.allowed is False


def test_set_user_agent_is_noop_for_blank_value() -> None:
    policy = RobotsPolicy()
    previous = policy._user_agent
    policy.set_user_agent("")
    assert policy._user_agent == previous