"""Collaboration API endpoints — comments and annotations (08 §5–6).

Read access: any org member. Creation/editing: reviewer+admin per the
collaboration permissions matrix (08 §8). Author/admin-only rules beyond
that are enforced in the service layer.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_session
from app.schemas.collaboration import (
    AnnotationCreateRequest,
    AnnotationListResponse,
    AnnotationOut,
    AnnotationUpdateRequest,
    CommentCreateRequest,
    CommentListResponse,
    CommentOut,
    CommentUpdateRequest,
)
from app.services import collaboration_service

router = APIRouter(tags=["collaboration"])


# ── Comments (08 §5) ─────────────────────────────────────────────────────────


@router.get(
    "/documents/{document_id}/comments", response_model=CommentListResponse
)
async def list_comments(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommentListResponse:
    return await collaboration_service.list_comments(
        session, current_user=current_user, document_id=document_id
    )


@router.post(
    "/documents/{document_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    document_id: UUID,
    body: CommentCreateRequest,
    current_user: Annotated[
        CurrentUser, Depends(require_role("reviewer", "admin"))
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommentOut:
    return await collaboration_service.create_comment(
        session, current_user=current_user, document_id=document_id, request=body
    )


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def update_comment(
    comment_id: UUID,
    body: CommentUpdateRequest,
    current_user: Annotated[
        CurrentUser, Depends(require_role("reviewer", "admin"))
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommentOut:
    return await collaboration_service.update_comment(
        session, current_user=current_user, comment_id=comment_id, request=body
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: UUID,
    current_user: Annotated[
        CurrentUser, Depends(require_role("reviewer", "admin"))
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await collaboration_service.delete_comment(
        session, current_user=current_user, comment_id=comment_id
    )


# ── Annotations (08 §6) ──────────────────────────────────────────────────────


@router.get(
    "/documents/{document_id}/annotations", response_model=AnnotationListResponse
)
async def list_annotations(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnnotationListResponse:
    return await collaboration_service.list_annotations(
        session, current_user=current_user, document_id=document_id
    )


@router.post(
    "/documents/{document_id}/annotations",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    document_id: UUID,
    body: AnnotationCreateRequest,
    current_user: Annotated[
        CurrentUser, Depends(require_role("reviewer", "admin"))
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnnotationOut:
    return await collaboration_service.create_annotation(
        session, current_user=current_user, document_id=document_id, request=body
    )


@router.patch("/annotations/{annotation_id}", response_model=AnnotationOut)
async def update_annotation(
    annotation_id: UUID,
    body: AnnotationUpdateRequest,
    current_user: Annotated[
        CurrentUser, Depends(require_role("reviewer", "admin"))
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnnotationOut:
    return await collaboration_service.update_annotation(
        session, current_user=current_user, annotation_id=annotation_id, request=body
    )


@router.delete(
    "/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_annotation(
    annotation_id: UUID,
    current_user: Annotated[
        CurrentUser, Depends(require_role("reviewer", "admin"))
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await collaboration_service.delete_annotation(
        session, current_user=current_user, annotation_id=annotation_id
    )
