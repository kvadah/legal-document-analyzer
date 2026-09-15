"""Org-scoped repository for the append-only audit log."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from app.models.models import AuditLog, User
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def list_entries(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Paginated audit entries for this org, newest first, with filters."""
        filters = [self._org_filter()]
        if action:
            filters.append(AuditLog.action == action)
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if date_from:
            filters.append(AuditLog.created_at >= date_from)
        if date_to:
            filters.append(AuditLog.created_at <= date_to)

        total: int = (
            await self.session.execute(
                select(func.count()).select_from(AuditLog).where(*filters)
            )
        ).scalar_one()
        stmt = (
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def prune_before(self, cutoff: datetime) -> int:
        """Delete entries older than *cutoff* (retention job only).

        Returns the number of rows removed. This is the ONLY sanctioned
        delete path for audit rows (11-security-compliance.md §6).
        """
        from sqlalchemy import delete

        result = await self.session.execute(
            delete(AuditLog).where(self._org_filter(), AuditLog.created_at < cutoff)
        )
        return result.rowcount or 0

    async def user_emails(self, user_ids: list[UUID]) -> dict[UUID, str]:
        """Map user ids to emails for display (users of this org only)."""
        if not user_ids:
            return {}
        stmt = select(User.id, User.email).where(
            User.organization_id == self.organization_id, User.id.in_(user_ids)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row.id: row.email for row in rows}
