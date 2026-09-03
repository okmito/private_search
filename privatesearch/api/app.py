"""FastAPI application exposing the PrivateSearch search API."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from privatesearch import __version__
from privatesearch.api.dependencies import get_holder, get_search_service
from privatesearch.api.schemas import (
    DocumentDetail,
    HealthResponse,
    HybridSearchResponse,
    IndexStats,
    SearchHit,
    SearchResponse,
    SuggestionResponse,
)
from privatesearch.common.config import get_settings
from privatesearch.embeddings.tfidf import TFIDFEmbedding
from privatesearch.retrieval.hybrid import HybridConfig, HybridSearch
from privatesearch.retrieval.retriever import Retriever
from privatesearch.retrieval.snippets import build_snippet
from privatesearch.storage import repository as repo
from privatesearch.storage.engine import session_scope

logger = logging.getLogger("privatesearch.api")


# ----------------------------------------------------------------------
# Middleware.
# ----------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, requests_per_minute: int) -> None:
        super().__init__(app)
        self.limit = max(1, requests_per_minute)
        self.window = 60.0
        self._bucket: dict[str, list[float]] = {}

    async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
        client = request.client.host if request.client else "anon"
        bucket = self._bucket.setdefault(client, [])
        now = time.monotonic()
        bucket[:] = [t for t in bucket if now - t < self.window]
        if len(bucket) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )
        bucket.append(now)
        return await call_next(request)


# ----------------------------------------------------------------------
# Helpers.
# ----------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _suggest_terms(query: str, limit: int = 5) -> list[str]:
    if not query.strip():
        return []
    tokens = _TOKEN_RE.findall(query.lower())
    if not tokens:
        return []
    holder = get_holder()
    service = holder.service
    suffix = tokens[-1]
    prefix = " ".join(tokens[:-1])
    matches: list[str] = []
    for term in service.index.terms():
        if term.startswith(suffix[:3]) and term != suffix:
            candidate = f"{prefix} {term}".strip() if prefix else term
            if candidate not in matches:
                matches.append(candidate)
            if len(matches) >= limit:
                break
    return matches


# ----------------------------------------------------------------------
# Application factory.
# ----------------------------------------------------------------------


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PrivateSearch",
        version=__version__,
        description="Privacy-first search API for PrivateSearch.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RateLimitMiddleware, requests_per_minute=settings.api_rate_limit_per_minute
    )

    _register_routes(app)
    _register_exception_handlers(app)
    return app


# ----------------------------------------------------------------------
# Routes.
# ----------------------------------------------------------------------


def _register_routes(app: FastAPI) -> None:
    @app.get("/api/v1/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        service = get_search_service()
        stats = service.index.stats
        return HealthResponse(
            status="ok",
            version=__version__,
            documents=stats.num_documents,
            terms=stats.num_terms,
        )

    @app.get("/api/v1/stats", response_model=IndexStats, tags=["meta"])
    def stats() -> IndexStats:
        service = get_search_service()
        s = service.index.stats
        return IndexStats(
            documents=s.num_documents,
            terms=s.num_terms,
            avg_document_length=s.avg_document_length,
        )

    @app.get("/api/v1/search", response_model=SearchResponse, tags=["search"])
    def search(
        q: str = Query(..., min_length=1),
        page: int = Query(1, ge=1),
        limit: int = Query(
            get_settings().api_default_page_size,
            ge=1,
            le=get_settings().api_max_page_size,
        ),
    ) -> SearchResponse:
        q = q.strip()
        if not q:
            raise HTTPException(status_code=400, detail="Query must not be blank")
        if len(q) > get_settings().api_max_query_length:
            raise HTTPException(status_code=400, detail="Query too long")
        service = get_search_service()
        retriever = Retriever(
            service.index, k1=get_settings().bm25_k1, b=get_settings().bm25_b
        )
        offset = (page - 1) * limit
        results = retriever.search(q, limit=limit, offset=offset, documents=None)
        total = retriever.count(q)

        hits: list[SearchHit] = []
        for result in results:
            doc_field = service.index.document(result.doc_id)
            body = doc_field.title if doc_field else ""
            snippet = build_snippet(
                body,
                query_terms=list(result.matched_terms),
                tokenizer=retriever.tokenizer,
                max_length=retriever.snippet_max_length,
            )
            explanation: dict[str, float] = {
                "bm25": float(result.score),
                "title_length": float(doc_field.title_length if doc_field else 0),
            }
            hits.append(
                SearchHit(
                    doc_id=result.doc_id,
                    score=result.score,
                    title=result.title,
                    url=result.url,
                    snippet=snippet.text,
                    highlighted=snippet.highlighted,
                    matched_terms=list(result.matched_terms),
                    explanation=explanation,
                )
            )
        return SearchResponse(
            query=q,
            total=total,
            page=page,
            page_size=limit,
            results=hits,
        )

    @app.get("/api/v1/suggestions", response_model=SuggestionResponse, tags=["search"])
    def suggestions(
        q: str = Query(..., min_length=1),
        limit: int = Query(5, ge=1, le=20),
    ) -> SuggestionResponse:
        candidates = _suggest_terms(q, limit=limit)
        return SuggestionResponse(query=q, suggestions=candidates)

    @app.get("/api/v1/search/hybrid", response_model=HybridSearchResponse, tags=["search"])
    def hybrid_search(
        q: str = Query(..., min_length=1),
        page: int = Query(1, ge=1),
        limit: int = Query(
            get_settings().api_default_page_size,
            ge=1,
            le=get_settings().api_max_page_size,
        ),
    ) -> HybridSearchResponse:
        q = q.strip()
        if not q:
            raise HTTPException(status_code=400, detail="Query must not be blank")
        service = get_search_service()
        embedding = TFIDFEmbedding()
        try:
            documents = [
                (doc.doc_id, doc.url, doc.title, doc.body or doc.title)
                for doc in service.pipeline.index.all_documents()
            ]
            hybrid = HybridSearch(
                service.index,
                embedding,
                config=HybridConfig(bm25_weight=1.0, semantic_weight=1.0),
            )
            hybrid.fit(documents)
            offset = (page - 1) * limit
            hits = hybrid.search(q, limit=limit, offset=offset)
        except Exception:  # noqa: BLE001
            logger.exception("Hybrid search failed")
            raise HTTPException(status_code=500, detail="Hybrid search failed")
        payload: list[HybridSearchHit] = []
        for hit in hits:
            doc_field = service.index.document(hit.doc_id)
            body = doc_field.title if doc_field else ""
            snippet = build_snippet(
                body,
                query_terms=list(hit.matched_terms),
                tokenizer=service.index.tokenizer,
                max_length=240,
            )
            payload.append(
                HybridSearchHit(
                    doc_id=hit.doc_id,
                    score=hit.final_score,
                    title=doc_field.title if doc_field else "",
                    url=doc_field.url if doc_field else "",
                    snippet=snippet.text,
                    highlighted=snippet.highlighted,
                    matched_terms=list(hit.matched_terms),
                    explanation=hit.explanation(),
                )
            )
        return HybridSearchResponse(
            query=q,
            total=len(payload),
            page=page,
            page_size=limit,
            method="hybrid(tfidf)",
            results=payload,
        )

    @app.get("/api/v1/documents/{doc_id}", response_model=DocumentDetail, tags=["documents"])
    def get_document(doc_id: int) -> DocumentDetail:
        with session_scope() as session:
            document = repo.get_document_by_doc_id(session, doc_id)
            if document is None:
                raise HTTPException(status_code=404, detail="Document not found")
            return DocumentDetail(
                doc_id=document.doc_id,
                url=document.url,
                canonical_url=document.canonical_url,
                title=document.title,
                description=document.description,
                language=document.language,
                content_hash=document.content_hash,
                body_length=document.body_length,
                title_length=document.title_length,
                last_crawled_at=document.last_crawled_at.isoformat()
                if document.last_crawled_at
                else None,
                body=document.body,
                headings=[],
                links=[link.target_url for link in document.links],
            )

    @app.get("/api/v1/index/rebuild", tags=["admin"])
    def rebuild_index() -> dict[str, int]:
        holder = get_holder()
        documents = holder.rebuild()
        return {"documents": documents}


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    def _http_exception_handler(  # type: ignore[no-untyped-def]
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or None,
        )

    @app.exception_handler(Exception)
    def _generic_exception_handler(  # type: ignore[no-untyped-def]
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


app = create_app()