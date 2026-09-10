"""Comparison API endpoints (09-api-spec.md §5)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.schemas.compare import (
    CompareRequest,
    ComparisonCreatedResponse,
    ComparisonOut,
)
from app.services import comparison_service

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=ComparisonCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_comparison(
    request: CompareRequest,
    # "Trigger comparisons" is a reviewer-level permission
    # (11-security-compliance.md §2).
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ComparisonCreatedResponse:
    return await comparison_service.create_comparison(
        session, current_user=current_user, request=request
    )


@router.get("/{comparison_id}", response_model=ComparisonOut)
async def get_comparison(
    comparison_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ComparisonOut:
    return await comparison_service.get_comparison(
        session, current_user=current_user, comparison_id=comparison_id
    )
