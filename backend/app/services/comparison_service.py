"""Comparison service — API-facing create/get for document comparison."""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.models import Comparison, DocumentStatus
from app.repositories.comparison_repo import ComparisonRepository
from app.schemas.compare import (
    ClauseDiffEntry,
    CompareRequest,
    ComparisonCounts,
    ComparisonCreatedResponse,
    ComparisonDocumentOut,
    ComparisonOut,
    ParagraphDiffEntry,
)
from app.services import document_service
from app.workers.pool import enqueue_comparison


async def create_comparison(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    request: CompareRequest,
) -> ComparisonCreatedResponse:
    """Validate both documents and queue the comparison job (async, 202)."""
    if request.document_id_a == request.document_id_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "same_document",
                "message": "Cannot compare a document with itself.",
            },
        )

    doc_a = await document_service.get_document(
        session, current_user=current_user, document_id=request.document_id_a
    )
    doc_b = await document_service.get_document(
        session, current_user=current_user, document_id=request.document_id_b
    )
    for doc in (doc_a, doc_b):
        if doc.status != DocumentStatus.ANALYSIS_READY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "analysis_not_ready",
                    "message": (
                        f"Comparison requires clause detection to have run on both "
                        f"documents. '{doc.filename}' has status: {doc.status}."
                    ),
                },
            )

    repo = ComparisonRepository(session, UUID(current_user.org_id))
    comparison = await repo.save(
        Comparison(
            id=uuid4(),
            document_id_a=request.document_id_a,
            document_id_b=request.document_id_b,
            status="pending",
        )
    )
    await session.commit()
    await enqueue_comparison(str(comparison.id))
    return ComparisonCreatedResponse(comparison_id=str(comparison.id), status="pending")


async def get_comparison(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    comparison_id: UUID,
) -> ComparisonOut:
    """Fetch a comparison result (org-scoped)."""
    repo = ComparisonRepository(session, UUID(current_user.org_id))
    comparison = await repo.get_by_id(comparison_id)
    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"Comparison {comparison_id} not found",
            },
        )

    documents = await repo.get_documents(comparison.document_id_a, comparison.document_id_b)
    doc_a = documents.get(comparison.document_id_a)
    doc_b = documents.get(comparison.document_id_b)
    if doc_a is None or doc_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"Comparison {comparison_id} not found",
            },
        )

    result: dict[str, Any] = comparison.result or {}
    clauses = [ClauseDiffEntry(**entry) for entry in result.get("clauses", [])]
    other_changes = [
        ParagraphDiffEntry(**entry) for entry in result.get("other_changes", [])
    ]
    counts = (
        ComparisonCounts(**result["counts"]) if "counts" in result else None
    )
    error = result.get("error") if comparison.status == "error" else None

    return ComparisonOut(
        id=str(comparison.id),
        document_id_a=str(comparison.document_id_a),
        document_id_b=str(comparison.document_id_b),
        document_a=ComparisonDocumentOut(
            id=str(doc_a.id), filename=doc_a.filename, document_type=doc_a.document_type
        ),
        document_b=ComparisonDocumentOut(
            id=str(doc_b.id), filename=doc_b.filename, document_type=doc_b.document_type
        ),
        status=comparison.status,
        error=error,
        clauses=clauses,
        other_changes=other_changes,
        counts=counts,
        created_at=comparison.created_at,
        updated_at=comparison.updated_at,
    )
