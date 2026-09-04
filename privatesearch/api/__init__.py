"""FastAPI search application."""

from privatesearch.api.app import app, create_app
from privatesearch.api.dependencies import get_search_service

__all__ = ["app", "create_app", "get_search_service"]
