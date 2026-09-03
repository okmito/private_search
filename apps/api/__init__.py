"""ASGI entrypoint for the PrivateSearch API service."""

from privatesearch.api.app import app

__all__ = ["app"]