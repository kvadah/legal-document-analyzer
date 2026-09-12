"""Document relationship API endpoints (09-api-spec.md §2, 08 §2)."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.schemas.relationship import (
    RelatedDocumentOut,
    RelationshipCreateRequest,
    RelationshipListResponse,
)
from app.services import relationship_service

router = APIRouter(tags=["relationships"])


@router.get(
    "/documents/{document_id}/relationships",
    response_model=RelationshipListResponse,
)
async def list_relationships(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RelationshipListResponse:
    return await relationship_service.list_relationships(
        session, current_user=current_user, document_id=document_id
    )


@router.post(
    "/documents/{document_id}/relationships",
    response_model=RelatedDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    document_id: UUID,
    body: RelationshipCreateRequest,
    # Creating relationships is a reviewer-level permission
    # (08-feature-spec-collaboration.md §8).
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RelatedDocumentOut:
    return await relationship_service.create_relationship(
        session, current_user=current_user, document_id=document_id, request=body
    )


@router.post("/relationships/{relationship_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_relationship(
    relationship_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await relationship_service.confirm_relationship(
        session, current_user=current_user, relationship_id=relationship_id
    )


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    relationship_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_role("reviewer", "admin"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await relationship_service.delete_relationship(
        session, current_user=current_user, relationship_id=relationship_id
    )
