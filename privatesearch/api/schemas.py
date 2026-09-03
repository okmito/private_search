"""Pydantic schemas exposed by the search API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    doc_id: int
    score: float
    title: str
    url: str
    snippet: str
    highlighted: str
    matched_terms: list[str] = Field(default_factory=list)
    explanation: Optional[dict[str, float]] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    page: int
    page_size: int
    results: list[SearchHit]


class DocumentSummary(BaseModel):
    doc_id: int
    url: str
    canonical_url: str
    title: str
    description: str
    language: Optional[str] = None
    content_hash: str
    body_length: int
    title_length: int
    last_crawled_at: Optional[str] = None


class DocumentDetail(DocumentSummary):
    body: str
    headings: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class SuggestionResponse(BaseModel):
    query: str
    suggestions: list[str]


class IndexStats(BaseModel):
    documents: int
    terms: int
    avg_document_length: float


class HealthResponse(BaseModel):
    status: str
    version: str
    documents: int
    terms: int


class HybridSearchHit(BaseModel):
    doc_id: int
    score: float
    title: str
    url: str
    snippet: str
    highlighted: str
    matched_terms: list[str] = Field(default_factory=list)
    explanation: dict[str, float] = Field(default_factory=dict)


class HybridSearchResponse(BaseModel):
    query: str
    total: int
    page: int
    page_size: int
    method: str
    results: list[HybridSearchHit]