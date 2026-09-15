"""Export API endpoints (09-api-spec.md §8)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_session
from app.services import audit_service, export_service

router = APIRouter(prefix="/documents", tags=["export"])


@router.get("/{document_id}/export")
async def export_document_analysis(
    document_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    format: str = Query(default="json", description="pdf | docx | json"),
) -> StreamingResponse:
    """Export a single document's analysis (sync for typical document sizes).

    Document exports are audited per 11-security-compliance.md §6.
    """
    response = await export_service.export_document(
        session,
        current_user=current_user,
        document_id=document_id,
        export_format=format,
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.DOCUMENT_EXPORTED,
        resource_type="document",
        resource_id=document_id,
        ip_address=request.client.host if request.client else None,
        details={"format": format},
    )
    await session.commit()
    return response
