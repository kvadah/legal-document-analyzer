"""Analysis output repository (clauses, risks, entities, obligations, summary).

Child tables have no organization_id column, so every query joins through
Document to enforce tenant scoping (spec 11-security-compliance.md §3).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Clause,
    Document,
    DocumentSummary,
    Entity,
    Obligation,
    Risk,
    RiskStatus,
)


class AnalysisRepository:
    """Org-scoped access to a document's analysis outputs."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    async def _document_exists(self, document_id: UUID) -> bool:
        stmt = select(Document.id).where(
            Document.id == document_id,
            Document.organization_id == self.organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_clauses(self, document_id: UUID) -> list[Clause]:
        stmt = (
            select(Clause)
            .join(Document, Clause.document_id == Document.id)
            .where(
                Clause.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
            .order_by(Clause.clause_type, Clause.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_risks(self, document_id: UUID) -> list[Risk]:
        stmt = (
            select(Risk)
            .join(Document, Risk.document_id == Document.id)
            .where(
                Risk.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
            .order_by(Risk.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_risk(self, document_id: UUID, risk_id: UUID) -> Risk | None:
        stmt = (
            select(Risk)
            .join(Document, Risk.document_id == Document.id)
            .where(
                Risk.id == risk_id,
                Risk.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_risk_status(self, risk: Risk, status: RiskStatus) -> Risk:
        risk.status = status
        self.session.add(risk)
        await self.session.flush()
        await self.session.refresh(risk)
        return risk

    async def list_entities(self, document_id: UUID) -> list[Entity]:
        stmt = (
            select(Entity)
            .join(Document, Entity.document_id == Document.id)
            .where(
                Entity.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
            .order_by(Entity.entity_type, Entity.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_obligations(self, document_id: UUID) -> list[Obligation]:
        stmt = (
            select(Obligation)
            .join(Document, Obligation.document_id == Document.id)
            .where(
                Obligation.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
            .order_by(Obligation.deadline_date, Obligation.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(self, document_id: UUID) -> DocumentSummary | None:
        stmt = (
            select(DocumentSummary)
            .join(Document, DocumentSummary.document_id == Document.id)
            .where(
                DocumentSummary.document_id == document_id,
                Document.organization_id == self.organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_for_document(self, document_id: UUID) -> None:
        """Remove all analysis rows for a document (idempotent re-runs)."""
        if not await self._document_exists(document_id):
            return
        await self.session.execute(
            delete(Risk).where(Risk.document_id == document_id)
        )
        await self.session.execute(
            delete(Clause).where(Clause.document_id == document_id)
        )
        await self.session.execute(
            delete(Entity).where(Entity.document_id == document_id)
        )
        await self.session.execute(
            delete(Obligation).where(Obligation.document_id == document_id)
        )
        await self.session.execute(
            delete(DocumentSummary).where(DocumentSummary.document_id == document_id)
        )
        await self.session.flush()
