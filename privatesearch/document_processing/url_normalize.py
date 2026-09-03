"""URL normalisation, validation and SSRF guards."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import ParseResult, parse_qs, urlencode, urljoin, urlparse, urlunparse

__all__ = [
    "NormalizedUrl",
    "is_blocked_host",
    "is_safe_public_host",
    "normalize_url",
    "resolve_host",
    "same_site",
]


_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    """Result of URL normalisation."""

    url: str
    scheme: str
    host: str
    port: int | None
    path: str
    is_canonical: bool

    @property
    def netloc(self) -> str:
        if self.port and ((self.scheme == "http" and self.port != 80)
                          or (self.scheme == "https" and self.port != 443)):
            return f"{self.host}:{self.port}"
        return self.host


def _strip_default_port(parsed: ParseResult) -> int | None:
    if parsed.port is None:
        return None
    if parsed.scheme == "http" and parsed.port == 80:
        return None
    if parsed.scheme == "https" and parsed.port == 443:
        return None
    return parsed.port


def _filter_query(query: str) -> str:
    if not query:
        return ""
    items = parse_qs(query, keep_blank_values=False)
    filtered = {
        key: sorted(values)
        for key, values in items.items()
        if key.lower() not in _TRACKING_PARAMS
    }
    # ``urlencode`` with a sorted dict produces a deterministic ordering.
    sorted_items = sorted(filtered.items())
    return urlencode(sorted_items, doseq=True)


def normalize_url(url: str, *, base: str | None = None) -> NormalizedUrl | None:
    """Return a normalised URL or ``None`` when the URL is unusable.

    Normalisation performs the following transformations:

    * Resolves relative URLs against ``base`` when provided.
    * Lower-cases scheme and host.
    * Drops the default port (``80`` for ``http``, ``443`` for ``https``).
    * Removes the URL fragment.
    * Removes common tracking query parameters.
    * Collapses consecutive slashes in the path.
    * Sorts query parameters alphabetically.
    """

    if not url:
        return None
    try:
        if base:
            joined = urljoin(base, url)
        else:
            joined = url
        parsed = urlparse(joined)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    if not host:
        return None

    path = parsed.path or "/"
    # Collapse repeated slashes inside the path (but preserve the leading one).
    while "//" in path:
        path = path.replace("//", "/")
    query = _filter_query(parsed.query)
    port = _strip_default_port(parsed)
    canonical = urlunparse(
        (
            parsed.scheme.lower(),
            host if port is None else f"{host}:{port}",
            path,
            "",
            query,
            "",
        )
    )
    return NormalizedUrl(
        url=canonical,
        scheme=parsed.scheme.lower(),
        host=host,
        port=port,
        path=path,
        is_canonical=True,
    )


def is_blocked_host(host: str) -> bool:
    """Return ``True`` if ``host`` resolves to a non-public address."""

    if not host:
        return True
    lowered = host.lower()
    if lowered in {"localhost", "ip6-localhost", "ip6-loopback"}:
        return True
    if lowered.endswith(".local") or lowered.endswith(".internal"):
        return True
    try:
        info = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return True
    for entry in info:
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return True
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            return True
        # Cloud metadata endpoints
        if str(ip) in {"169.254.169.254", "fd00:ec2::254"}:
            return True
    return False


def is_safe_public_host(host: str, allowed: Iterable[str] | None = None) -> bool:
    """Return ``True`` when the host can be safely fetched."""

    if is_blocked_host(host):
        return False
    if allowed:
        allowed_hosts = {h.lower() for h in allowed}
        return host.lower() in allowed_hosts
    return True


def resolve_host(host: str) -> list[str]:
    """Return a sorted list of IP addresses for ``host`` (best-effort)."""

    try:
        info = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return []
    addresses = {entry[4][0] for entry in info}
    return sorted(addresses)


def same_site(a: str, b: str) -> bool:
    """Return ``True`` if the two URLs belong to the same registrable site."""

    pa = urlparse(a)
    pb = urlparse(b)
    return (pa.hostname or "").lower() == (pb.hostname or "").lower() and (pa.scheme or "").lower() == (pb.scheme or "").lower()