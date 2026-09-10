"""Comparison repository.

The comparisons table has no organization_id column, so every query joins
through Document (both sides) to enforce tenant scoping
(spec 11-security-compliance.md §3).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Comparison, Document


class ComparisonRepository:
    """Org-scoped access to document comparisons."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    async def save(self, comparison: Comparison) -> Comparison:
        self.session.add(comparison)
        await self.session.flush()
        await self.session.refresh(comparison)
        return comparison

    async def get_by_id(self, comparison_id: UUID) -> Comparison | None:
        doc_a = Document.__table__.alias("doc_a")
        doc_b = Document.__table__.alias("doc_b")
        stmt = (
            select(Comparison)
            .join(doc_a, Comparison.document_id_a == doc_a.c.id)
            .join(doc_b, Comparison.document_id_b == doc_b.c.id)
            .where(
                Comparison.id == comparison_id,
                doc_a.c.organization_id == self.organization_id,
                doc_b.c.organization_id == self.organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_documents(
        self, document_id_a: UUID, document_id_b: UUID
    ) -> dict[UUID, Document]:
        stmt = select(Document).where(
            Document.id.in_([document_id_a, document_id_b]),
            Document.organization_id == self.organization_id,
        )
        result = await self.session.execute(stmt)
        return {doc.id: doc for doc in result.scalars().all()}
