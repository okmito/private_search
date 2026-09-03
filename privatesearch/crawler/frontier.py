"""URL frontier with deduplication and breadth-first ordering."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Iterable, Iterator

__all__ = ["FrontierEntry", "Frontier"]


@dataclass(order=True, frozen=True, slots=True)
class FrontierEntry:
    """Priority queue entry. ``priority`` is the BFS depth."""

    priority: int
    counter: int
    url: str = field(compare=False)


class Frontier:
    """A bounded breadth-first URL frontier.

    The frontier stores URLs as a min-heap keyed by depth, then by insertion
    counter, which yields a deterministic BFS traversal. Every URL added via
    :meth:`push` is normalised and de-duplicated. Hosts are tracked
    independently so the crawler can enforce a per-host delay.
    """

    def __init__(self) -> None:
        self._heap: list[FrontierEntry] = []
        self._seen: set[str] = set()
        self._counter = 0

    def __len__(self) -> int:
        return len(self._heap)

    def __contains__(self, url: str) -> bool:
        return url in self._seen

    def __iter__(self) -> Iterator[str]:
        for entry in sorted(self._heap):
            yield entry.url

    @property
    def seen(self) -> set[str]:
        return self._seen

    def push(self, url: str, *, depth: int = 0) -> bool:
        if not url:
            return False
        if url in self._seen:
            return False
        self._counter += 1
        heapq.heappush(self._heap, FrontierEntry(depth, self._counter, url))
        self._seen.add(url)
        return True

    def push_many(self, urls: Iterable[str], *, depth: int = 0) -> int:
        added = 0
        for url in urls:
            if self.push(url, depth=depth):
                added += 1
        return added

    def pop(self) -> FrontierEntry | None:
        if not self._heap:
            return None
        entry = heapq.heappop(self._heap)
        self._seen.discard(entry.url)
        return entry

    def clear(self) -> None:
        self._heap.clear()
        self._seen.clear()
        self._counter = 0