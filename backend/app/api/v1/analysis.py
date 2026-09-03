"""Analysis API endpoints (09-api-spec.md §3)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
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
from app.services import analysis_service

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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RiskOut:
    return await analysis_service.update_risk_status(
        session, current_user, document_id, risk_id, RiskStatus(body.status)
    )


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
