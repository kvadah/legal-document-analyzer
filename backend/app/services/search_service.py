"""Search service — keyword / semantic / hybrid over an org's chunks
(07-feature-spec-comparison-search.md §3).

- Keyword: SQL LIKE matching over chunk text, org-scoped through the documents
  join. (Postgres tsvector upgrade path noted inline — the LIKE form keeps the
  exact same org scoping and runs on SQLite in tests.)
- Semantic: query embedded with the same provider as ingestion, searched
  against the vector store (Qdrant or in-memory) filtered by org, then
  re-hydrated from Postgres with org + metadata filters applied.
- Hybrid: both run, merged with Reciprocal Rank Fusion (no hand-tuned weights).

Results are grouped by document with snippet-level scores so the UI can show
top matching snippets per document and deep-link to the matched page.
"""
from __future__ import annotations

import logging
import re
import shlex
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy import or_ as sqlalchemy_or
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.models.models import Chunk, Document, DocumentStatus
from app.providers.embeddings import get_embedding_provider
from app.schemas.search import (
    ResultDocument,
    SearchRequest,
    SearchResponse,
    SearchResultGroup,
    SearchSnippet,
)
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

# Statuses at which a document's chunks exist and are searchable.
SEARCHABLE_STATUSES = {
    DocumentStatus.INGESTION_READY,
    DocumentStatus.AI_PIPELINE_PROCESSING,
    DocumentStatus.ANALYSIS_READY,
}


def _parse_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "validation_error",
                "message": f"Invalid date filter: {value!r} (expected YYYY-MM-DD)",
            },
        ) from None


def _query_terms(query: str) -> list[str]:
    """Split a query into match terms, keeping quoted phrases intact."""
    try:
        tokens = shlex.split(query)
    except ValueError:
        tokens = query.split()
    return [t for t in (token.strip() for token in tokens) if t]


async def _apply_filters(
    stmt: Select,
    *,
    current_user: CurrentUser,
    filters: Any,
) -> Select:
    stmt = stmt.where(Document.organization_id == UUID(current_user.org_id))
    stmt = stmt.where(Document.status.in_(SEARCHABLE_STATUSES))
    if filters.document_type:
        stmt = stmt.where(Document.document_type == filters.document_type)
    if filters.date_from:
        stmt = stmt.where(Document.created_at >= _parse_date(filters.date_from))
    if filters.date_to:
        stmt = stmt.where(Document.created_at < _parse_date(filters.date_to))
    if filters.document_ids:
        try:
            ids = [UUID(doc_id) for doc_id in filters.document_ids]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "validation_error", "message": "Invalid document id filter"},
            ) from None
        stmt = stmt.where(Document.id.in_(ids))
    return stmt


async def _keyword_search(
    session: AsyncSession, *, current_user: CurrentUser, request: SearchRequest
) -> list[tuple[Chunk, float]]:
    terms = _query_terms(request.query)
    if not terms:
        return []
    # DB-side narrowing (LIKE is the portable form; Postgres tsvector is the
    # production upgrade path — same org scoping either way).
    stmt = select(Chunk).join(Document, Chunk.document_id == Document.id)
    stmt = await _apply_filters(stmt, current_user=current_user, filters=request.filters)
    stmt = stmt.where(
        sqlalchemy_or(*(Chunk.text.ilike(f"%{term}%") for term in terms))
    )
    rows = (await session.execute(stmt)).scalars().all()

    scored: list[tuple[Chunk, float]] = []
    for chunk in rows:
        lower = (chunk.text or "").lower()
        hits = sum(1 for term in terms if term.lower() in lower)
        if hits:
            scored.append((chunk, float(hits) / len(terms)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


async def _semantic_search(
    session: AsyncSession, *, current_user: CurrentUser, request: SearchRequest
) -> list[tuple[Chunk, float]]:
    provider = get_embedding_provider()
    query_vectors = await provider.embed_texts([request.query])
    if not query_vectors:
        return []
    document_ids = None
    if request.filters.document_ids:
        document_ids = list(request.filters.document_ids)
    hits = await get_vector_store().search(
        query_vectors[0],
        organization_id=current_user.org_id,
        document_ids=document_ids,
        limit=settings.semantic_candidate_k,
    )
    if not hits:
        return []

    # Re-hydrate chunk rows from Postgres — keeps org scoping authoritative
    # (never trust vector-store payloads alone) and applies metadata filters.
    chunk_ids = [hit.chunk_id for hit in hits]
    scores = {hit.chunk_id: hit.score for hit in hits}
    stmt = select(Chunk).join(Document, Chunk.document_id == Document.id).where(
        Chunk.id.in_([UUID(chunk_id) for chunk_id in chunk_ids])
    )
    stmt = await _apply_filters(stmt, current_user=current_user, filters=request.filters)
    rows = (await session.execute(stmt)).scalars().all()
    return [(chunk, scores.get(str(chunk.id), 0.0)) for chunk in rows]


def _rrf_merge(
    keyword: list[tuple[Chunk, float]],
    semantic: list[tuple[Chunk, float]],
) -> list[tuple[Chunk, float, str]]:
    """Reciprocal Rank Fusion at chunk level: score = Σ 1/(k + rank)."""
    k = settings.rrf_k
    fused: dict[str, float] = {}
    chunks: dict[str, tuple[Chunk, str]] = {}

    for rank, (chunk, _score) in enumerate(keyword, start=1):
        key = str(chunk.id)
        fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
        chunks.setdefault(key, (chunk, "keyword"))
    for rank, (chunk, _score) in enumerate(semantic, start=1):
        key = str(chunk.id)
        fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
        if key in chunks:
            _chunk, _source = chunks[key]
            chunks[key] = (_chunk, "both")
        else:
            chunks[key] = (chunk, "semantic")

    merged = [
        (chunks[key][0], score, chunks[key][1]) for key, score in fused.items()
    ]
    merged.sort(key=lambda item: item[1], reverse=True)
    return merged


def _document_out(doc: Document) -> ResultDocument:
    return ResultDocument(
        id=str(doc.id),
        filename=doc.filename,
        document_type=doc.document_type.value,
        status=doc.status.value,
        page_count=doc.page_count,
        contract_score=float(doc.contract_score) if doc.contract_score is not None else None,
        created_at=doc.created_at,
    )


async def search(
    session: AsyncSession, *, current_user: CurrentUser, request: SearchRequest
) -> SearchResponse:
    mode = request.mode
    keyword_results: list[tuple[Chunk, float]] = []
    semantic_results: list[tuple[Chunk, float]] = []

    if mode in ("keyword", "hybrid"):
        keyword_results = await _keyword_search(
            session, current_user=current_user, request=request
        )
    if mode in ("semantic", "hybrid"):
        try:
            semantic_results = await _semantic_search(
                session, current_user=current_user, request=request
            )
        except Exception:
            # Semantic search failing (e.g. no vector backend) must not break
            # keyword-only results in hybrid mode.
            logger.exception("search.semantic_failed")
            if mode == "semantic":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "processing_error",
                        "message": "Semantic search is currently unavailable.",
                    },
                )

    if mode == "hybrid":
        merged = _rrf_merge(keyword_results, semantic_results)
    elif mode == "keyword":
        merged = [(chunk, score, "keyword") for chunk, score in keyword_results]
    else:
        merged = [(chunk, score, "semantic") for chunk, score in semantic_results]

    # Chunk-level pagination window
    window = merged[request.offset : request.offset + request.limit]
    if not window:
        return SearchResponse(
            query=request.query,
            mode=mode,
            groups=[],
            total_documents=0,
            total_snippets=0,
        )

    # Load parent documents for the window (org-scoped again for safety)
    doc_ids = {chunk.document_id for chunk, _score, _source in window}
    doc_stmt = await _apply_filters(
        select(Document).where(Document.id.in_(doc_ids)),
        current_user=current_user,
        filters=request.filters,
    )
    docs = (await session.execute(doc_stmt)).scalars().all()
    docs_by_id = {doc.id: doc for doc in docs}

    # Group snippets by document, keeping relevance order
    groups: dict[UUID, list[SearchSnippet]] = {}
    for chunk, score, source in window:
        if chunk.document_id not in docs_by_id:
            continue
        groups.setdefault(chunk.document_id, []).append(
            SearchSnippet(
                chunk_id=str(chunk.id),
                text=chunk.text,
                page_number=chunk.page_number,
                section_heading=chunk.section_heading,
                score=round(score, 6),
                source=source,  # type: ignore[arg-type]
            )
        )

    result_groups = [
        SearchResultGroup(document=_document_out(docs_by_id[doc_id]), snippets=snippets)
        # documents with more/better snippets first
        for doc_id, snippets in sorted(
            groups.items(),
            key=lambda pair: max(s.score for s in pair[1]),
            reverse=True,
        )
    ]
    return SearchResponse(
        query=request.query,
        mode=mode,
        groups=result_groups,
        total_documents=len(result_groups),
        total_snippets=len(merged),
    )
