"""Robots.txt policy parser and caching layer."""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

__all__ = ["RobotsPolicy", "RobotsDecision"]


@dataclass(frozen=True, slots=True)
class RobotsDecision:
    allowed: bool
    crawl_delay: float | None
    source_url: str | None = None


_LINE_RE = re.compile(r"^\s*(?P<field>[A-Za-z-]+)\s*:\s*(?P<value>.*?)\s*$")


class RobotsPolicy:
    """In-memory cache of robots.txt policies per host.

    The parser handles the subset of robots.txt directives actually used by
    a polite crawler: ``User-agent``, ``Disallow`` and ``Crawl-delay``. For
    every other directive the parser falls back to Python's
    :class:`urllib.robotparser.RobotFileParser`, which is fully standards
    compliant.
    """

    DEFAULT_USER_AGENT = "PrivateSearch"

    def __init__(self) -> None:
        self._parsers: dict[str, RobotFileParser] = {}
        self._delays: dict[str, float] = {}
        self._user_agent = self.DEFAULT_USER_AGENT

    def set_user_agent(self, user_agent: str) -> None:
        if user_agent:
            self._user_agent = user_agent

    @staticmethod
    def _host(url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    def load(self, url: str, body: str) -> None:
        """Parse the ``body`` of ``url`` (which must point at ``/robots.txt``)."""

        host = self._host(url)
        if not host:
            return
        parser = RobotFileParser(url=url)
        parser.parse(io.StringIO(body).readlines())
        self._parsers[host] = parser

        # ``RobotFileParser`` does not expose Crawl-delay, so we extract it
        # ourselves from the raw text.
        delay = self._extract_crawl_delay(body)
        if delay is not None:
            self._delays[host] = delay

    @staticmethod
    def _extract_crawl_delay(body: str) -> float | None:
        current_agents: list[str] = []
        delay: float | None = None
        for line in body.splitlines():
            match = _LINE_RE.match(line)
            if not match:
                continue
            field = match.group("field").lower()
            value = match.group("value")
            if field == "user-agent":
                current_agents = [value.lower()]
            elif field == "crawl-delay" and (
                "*" in current_agents or RobotsPolicy.DEFAULT_USER_AGENT.lower() in current_agents
            ):
                try:
                    delay = float(value)
                except ValueError:
                    delay = None
        return delay

    def can_fetch(self, url: str) -> RobotsDecision:
        host = self._host(url)
        parser = self._parsers.get(host)
        if parser is None:
            return RobotsDecision(allowed=True, crawl_delay=None)
        allowed = parser.can_fetch(self._user_agent, url)
        return RobotsDecision(
            allowed=bool(allowed),
            crawl_delay=self._delays.get(host),
        )

    def delay_for(self, host: str) -> float | None:
        return self._delays.get(host.lower())

    def hosts(self) -> Iterable[str]:
        return self._parsers.keys()
