"""Report API endpoints (09-api-spec.md §8)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.schemas.report import ReportCreateRequest, ReportCreatedResponse, ReportListResponse, ReportOut
from app.services import audit_service, report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    body: ReportCreateRequest,
    http_request: Request,
    # Generating reports consumes storage + compute; reviewer-level
    # permission mirrors comparison triggering (11-security-compliance.md §2).
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReportCreatedResponse:
    """Queue a portfolio report generation job (audited per 11 §6)."""
    result = await report_service.create_report(
        session, current_user=current_user, request=body
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.REPORT_GENERATED,
        resource_type="report",
        resource_id=result.report_id,
        ip_address=http_request.client.host if http_request.client else None,
        details={"report_type": body.report_type, "export_format": body.export_format},
    )
    await session.commit()
    return result


@router.get("", response_model=ReportListResponse)
async def list_reports(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ReportListResponse:
    return await report_service.list_reports(
        session, current_user=current_user, limit=limit, offset=offset
    )


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReportOut:
    return await report_service.get_report(
        session, current_user=current_user, report_id=report_id
    )


@router.get("/{report_id}/download")
async def download_report(
    report_id: UUID,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    """Download a completed report's generated file (audited per 11 §6)."""
    response = await report_service.download_report(
        session, current_user=current_user, report_id=report_id
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.REPORT_DOWNLOADED,
        resource_type="report",
        resource_id=report_id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return response
