"""ASGI entrypoint used by ``uvicorn main:app``."""

from privatesearch.api.app import app

__all__ = ["app"]
