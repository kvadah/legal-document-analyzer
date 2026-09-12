"""Report repository — org-scoped access to the reports table."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Report


class ReportRepository:
    """Org-scoped access to generated reports."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    async def save(self, report: Report) -> Report:
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def get_by_id(self, report_id: UUID) -> Report | None:
        stmt = select(Report).where(
            Report.id == report_id,
            Report.organization_id == self.organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_reports(self, *, limit: int = 50, offset: int = 0) -> list[Report]:
        stmt = (
            select(Report)
            .where(Report.organization_id == self.organization_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(Report).where(
            Report.organization_id == self.organization_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
