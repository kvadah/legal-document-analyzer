"""Collaboration business logic — comments and annotations (08 §5–6).

Permissions (08 §8): viewers read collaboration objects but cannot create
them (enforced at the router); content edits are author-only; comment
resolution is the review workflow and available to any reviewer/admin;
deletion is author-or-admin. All objects are org-scoped through their parent
document.
"""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models.models import Annotation, Comment, User
from app.repositories.collaboration_repo import CollaborationRepository
from app.repositories.document_repo import DocumentRepository
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


def _not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": f"{resource} not found"},
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "forbidden", "message": message},
    )


def _comment_out(comment: Comment, author: User) -> CommentOut:
    return CommentOut(
        id=str(comment.id),
        document_id=str(comment.document_id),
        user_id=str(comment.user_id),
        author_email=author.email,
        author_name=author.full_name,
        content=comment.content,
        page_number=comment.page_number,
        parent_comment_id=(
            str(comment.parent_comment_id) if comment.parent_comment_id else None
        ),
        resolved=comment.resolved,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def _annotation_out(annotation: Annotation, author: User) -> AnnotationOut:
    return AnnotationOut(
        id=str(annotation.id),
        document_id=str(annotation.document_id),
        user_id=str(annotation.user_id),
        author_email=author.email,
        author_name=author.full_name,
        content=annotation.content,
        highlight_text=annotation.highlight_text,
        color=annotation.color,
        page_number=annotation.page_number,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


async def _verify_document_access(
    session: AsyncSession, current_user: CurrentUser, document_id: UUID
) -> None:
    """404 unless the document exists in the caller's org (also the
    cross-tenant guard — other orgs' documents are indistinguishable from
    nonexistent ones)."""
    repo = DocumentRepository(session, UUID(current_user.org_id))
    await repo.get_by_id(document_id)


# ── Comments ─────────────────────────────────────────────────────────────────


async def list_comments(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
) -> CommentListResponse:
    await _verify_document_access(session, current_user, document_id)
    repo = CollaborationRepository(session, UUID(current_user.org_id))
    rows = await repo.list_comments(document_id)
    comments = [_comment_out(comment, author) for comment, author in rows]
    return CommentListResponse(
        document_id=str(document_id), comments=comments, total=len(comments)
    )


async def create_comment(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
    request: CommentCreateRequest,
) -> CommentOut:
    await _verify_document_access(session, current_user, document_id)
    repo = CollaborationRepository(session, UUID(current_user.org_id))

    parent: Comment | None = None
    if request.parent_comment_id is not None:
        try:
            parent_id = UUID(request.parent_comment_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "validation_error",
                    "message": "Invalid parent comment id",
                },
            ) from None
        parent = await repo.get_comment(parent_id)
        if parent is None:
            raise _not_found("Parent comment")
        if parent.document_id != document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "validation_error",
                    "message": "Parent comment belongs to a different document",
                },
            )

    comment = await repo.save_comment(
        Comment(
            id=uuid.uuid4(),
            document_id=document_id,
            user_id=UUID(current_user.id),
            content=request.content,
            page_number=request.page_number,
            parent_comment_id=parent.id if parent else None,
        )
    )
    author = await repo.get_user(UUID(current_user.id))
    assert author is not None  # author just acted with a valid org token
    await session.commit()
    return _comment_out(comment, author)


async def update_comment(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    comment_id: UUID,
    request: CommentUpdateRequest,
) -> CommentOut:
    repo = CollaborationRepository(session, UUID(current_user.org_id))
    comment = await repo.get_comment(comment_id)
    if comment is None:
        raise _not_found("Comment")

    if request.content is not None and comment.user_id != UUID(current_user.id):
        raise _forbidden("Only the author can edit a comment's content")
    if request.content is not None:
        comment.content = request.content
    if request.resolved is not None:
        comment.resolved = request.resolved

    comment = await repo.save_comment(comment)
    author = await repo.get_user(comment.user_id)
    assert author is not None
    await session.commit()
    return _comment_out(comment, author)


async def delete_comment(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    comment_id: UUID,
) -> None:
    repo = CollaborationRepository(session, UUID(current_user.org_id))
    comment = await repo.get_comment(comment_id)
    if comment is None:
        raise _not_found("Comment")
    if comment.user_id != UUID(current_user.id) and current_user.role != "admin":
        raise _forbidden("Only the author or an admin can delete a comment")

    # Delete replies alongside their parent so no orphan threads remain.
    for child, _author in await repo.list_comments(comment.document_id):
        if child.parent_comment_id == comment.id:
            await repo.delete_comment(child)
    await repo.delete_comment(comment)
    await session.commit()


# ── Annotations ──────────────────────────────────────────────────────────────


async def list_annotations(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
) -> AnnotationListResponse:
    await _verify_document_access(session, current_user, document_id)
    repo = CollaborationRepository(session, UUID(current_user.org_id))
    rows = await repo.list_annotations(document_id)
    annotations = [_annotation_out(annotation, author) for annotation, author in rows]
    return AnnotationListResponse(
        document_id=str(document_id), annotations=annotations, total=len(annotations)
    )


async def create_annotation(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    document_id: UUID,
    request: AnnotationCreateRequest,
) -> AnnotationOut:
    await _verify_document_access(session, current_user, document_id)
    repo = CollaborationRepository(session, UUID(current_user.org_id))

    annotation = await repo.save_annotation(
        Annotation(
            id=uuid.uuid4(),
            document_id=document_id,
            user_id=UUID(current_user.id),
            content=request.content,
            annotation_type="highlight",
            page_number=request.page_number,
            paragraph_index=request.paragraph_index,
            start_offset=request.start_offset,
            end_offset=request.end_offset,
            highlight_text=request.highlight_text,
            color=request.color,
        )
    )
    author = await repo.get_user(UUID(current_user.id))
    assert author is not None
    await session.commit()
    return _annotation_out(annotation, author)


async def update_annotation(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    annotation_id: UUID,
    request: AnnotationUpdateRequest,
) -> AnnotationOut:
    repo = CollaborationRepository(session, UUID(current_user.org_id))
    annotation = await repo.get_annotation(annotation_id)
    if annotation is None:
        raise _not_found("Annotation")

    if annotation.user_id != UUID(current_user.id):
        raise _forbidden("Only the author can edit an annotation")
    if request.content is not None:
        annotation.content = request.content
    if request.color is not None:
        annotation.color = request.color

    annotation = await repo.save_annotation(annotation)
    author = await repo.get_user(annotation.user_id)
    assert author is not None
    await session.commit()
    return _annotation_out(annotation, author)


async def delete_annotation(
    session: AsyncSession,
    *,
    current_user: CurrentUser,
    annotation_id: UUID,
) -> None:
    repo = CollaborationRepository(session, UUID(current_user.org_id))
    annotation = await repo.get_annotation(annotation_id)
    if annotation is None:
        raise _not_found("Annotation")
    if annotation.user_id != UUID(current_user.id) and current_user.role != "admin":
        raise _forbidden("Only the author or an admin can delete an annotation")

    await repo.delete_annotation(annotation)
    await session.commit()
