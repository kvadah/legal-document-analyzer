"""Document relationship repository.

The document_relationships table has no organization_id column, so every
query joins through Document (both sides) to enforce tenant scoping — the
same pattern as ComparisonRepository (spec 11-security-compliance.md §3).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Document, DocumentRelationship


class RelationshipRepository:
    """Org-scoped access to document relationships."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    async def save(self, relationship: DocumentRelationship) -> DocumentRelationship:
        self.session.add(relationship)
        await self.session.flush()
        await self.session.refresh(relationship)
        return relationship

    async def get_by_id(self, relationship_id: UUID) -> DocumentRelationship | None:
        doc_a = Document.__table__.alias("doc_a")
        doc_b = Document.__table__.alias("doc_b")
        stmt = (
            select(DocumentRelationship)
            .join(doc_a, DocumentRelationship.document_id_a == doc_a.c.id)
            .join(doc_b, DocumentRelationship.document_id_b == doc_b.c.id)
            .where(
                DocumentRelationship.id == relationship_id,
                doc_a.c.organization_id == self.organization_id,
                doc_b.c.organization_id == self.organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_document(self, document_id: UUID) -> list[DocumentRelationship]:
        other_a = Document.__table__.alias("other_a")
        other_b = Document.__table__.alias("other_b")
        stmt = (
            select(DocumentRelationship)
            .join(other_a, DocumentRelationship.document_id_a == other_a.c.id)
            .join(other_b, DocumentRelationship.document_id_b == other_b.c.id)
            .where(
                or_(
                    DocumentRelationship.document_id_a == document_id,
                    DocumentRelationship.document_id_b == document_id,
                ),
                other_a.c.organization_id == self.organization_id,
                other_b.c.organization_id == self.organization_id,
            )
            .order_by(DocumentRelationship.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_any_between(
        self, document_id_a: UUID, document_id_b: UUID
    ) -> list[DocumentRelationship]:
        """Any relationship (either direction, any type) between two docs."""
        stmt = select(DocumentRelationship).where(
            or_(
                (DocumentRelationship.document_id_a == document_id_a)
                & (DocumentRelationship.document_id_b == document_id_b),
                (DocumentRelationship.document_id_a == document_id_b)
                & (DocumentRelationship.document_id_b == document_id_a),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, relationship: DocumentRelationship) -> None:
        await self.session.execute(
            delete(DocumentRelationship).where(
                DocumentRelationship.id == relationship.id
            )
        )
