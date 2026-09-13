"""Collaboration repository — comments and annotations.

Neither table carries an organization_id column, so every query joins
through Document to enforce tenant scoping — the same pattern as
RelationshipRepository (11-security-compliance.md §3).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Annotation, Comment, Document, User


class CollaborationRepository:
    """Org-scoped access to comments and annotations."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    # ── Comments ──────────────────────────────────────────────────────────────

    async def list_comments(self, document_id: UUID) -> list[tuple[Comment, User]]:
        stmt = (
            select(Comment, User)
            .join(Document, Comment.document_id == Document.id)
            .join(User, Comment.user_id == User.id)
            .where(
                Comment.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
            .order_by(Comment.created_at)
        )
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

    async def get_comment(self, comment_id: UUID) -> Comment | None:
        stmt = (
            select(Comment)
            .join(Document, Comment.document_id == Document.id)
            .where(
                Comment.id == comment_id,
                Document.organization_id == self.organization_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_comment(self, comment: Comment) -> Comment:
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        return comment

    async def delete_comment(self, comment: Comment) -> None:
        await self.session.delete(comment)
        await self.session.flush()

    # ── Annotations ───────────────────────────────────────────────────────────

    async def list_annotations(
        self, document_id: UUID
    ) -> list[tuple[Annotation, User]]:
        stmt = (
            select(Annotation, User)
            .join(Document, Annotation.document_id == Document.id)
            .join(User, Annotation.user_id == User.id)
            .where(
                Annotation.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
            .order_by(Annotation.created_at)
        )
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

    async def get_annotation(self, annotation_id: UUID) -> Annotation | None:
        stmt = (
            select(Annotation)
            .join(Document, Annotation.document_id == Document.id)
            .where(
                Annotation.id == annotation_id,
                Document.organization_id == self.organization_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save_annotation(self, annotation: Annotation) -> Annotation:
        self.session.add(annotation)
        await self.session.flush()
        await self.session.refresh(annotation)
        return annotation

    async def delete_annotation(self, annotation: Annotation) -> None:
        await self.session.delete(annotation)
        await self.session.flush()

    # ── Shared ────────────────────────────────────────────────────────────────

    async def get_user(self, user_id: UUID) -> User | None:
        return (
            await self.session.execute(
                select(User).where(
                    User.id == user_id,
                    User.organization_id == self.organization_id,
                )
            )
        ).scalar_one_or_none()
