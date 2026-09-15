"""Analysis API endpoints (09-api-spec.md §3)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.models.models import RiskStatus
from app.schemas.analysis import (
    ClauseListResponse,
    EntityListResponse,
    ObligationListResponse,
    RiskListResponse,
    RiskOut,
    RiskUpdateRequest,
    ScoreOut,
    SummaryOut,
)
from app.services import analysis_service, audit_service

router = APIRouter(prefix="/documents", tags=["analysis"])


@router.get("/{document_id}/summary", response_model=SummaryOut)
async def get_document_summary(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SummaryOut:
    return await analysis_service.get_summary(session, current_user, document_id)


@router.get("/{document_id}/clauses", response_model=ClauseListResponse)
async def get_document_clauses(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClauseListResponse:
    return await analysis_service.list_clauses(session, current_user, document_id)


@router.get("/{document_id}/risks", response_model=RiskListResponse)
async def get_document_risks(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskListResponse:
    return await analysis_service.list_risks(session, current_user, document_id)


@router.patch("/{document_id}/risks/{risk_id}", response_model=RiskOut)
async def update_document_risk(
    document_id: UUID,
    risk_id: UUID,
    body: RiskUpdateRequest,
    request: Request,
    # Triage is a mutation — viewers are read-only (11-security-compliance.md §2).
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskOut:
    """Risk triage (flagged/acknowledged/dismissed) — audited per 11 §6."""
    risk = await analysis_service.update_risk_status(
        session, current_user, document_id, risk_id, RiskStatus(body.status)
    )
    await audit_service.record(
        session,
        organization_id=current_user.org_id,
        user_id=current_user.id,
        action=audit_service.AuditAction.RISK_STATUS_CHANGED,
        resource_type="risk",
        resource_id=risk_id,
        ip_address=request.client.host if request.client else None,
        details={"document_id": str(document_id), "status": body.status},
    )
    await session.commit()
    return risk


@router.get("/{document_id}/entities", response_model=EntityListResponse)
async def get_document_entities(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EntityListResponse:
    return await analysis_service.list_entities(session, current_user, document_id)


@router.get("/{document_id}/obligations", response_model=ObligationListResponse)
async def get_document_obligations(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ObligationListResponse:
    return await analysis_service.list_obligations(session, current_user, document_id)


@router.get("/{document_id}/score", response_model=ScoreOut)
async def get_document_score(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScoreOut:
    return await analysis_service.get_score(session, current_user, document_id)
