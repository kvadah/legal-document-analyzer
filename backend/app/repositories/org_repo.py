"""Organization repository (not org-scoped; orgs are the root of scoping)."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Organization


class OrgRepository:
    """Non-scoped repository for Organizations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_org(self, *, name: str) -> Organization:
        org = Organization(name=name)
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        stmt = select(Organization).where(Organization.id == org_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
