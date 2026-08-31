"""Base repository providing automatic org-scoped data access."""
from typing import Any, Generic, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    """Generic async repository with automatic organization_id scoping.

    Every query method automatically filters by ``organization_id`` so
    individual endpoint implementations cannot accidentally leak cross-tenant
    data (prevents IDOR-style access bugs).
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _org_filter(self) -> Any:
        return self.model.organization_id == self.organization_id  # type: ignore[attr-defined]

    def _not_found(self, resource_id: Any) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"{self.model.__name__} {resource_id} not found",
            },
        )

    # ── CRUD ─────────────────────────────────────────────────────────────────

    async def get_by_id(self, resource_id: UUID) -> ModelT:
        """Fetch a record by ID, scoped to this org.

        Raises HTTP 404 if not found *or* belongs to a different org
        (prevents information-disclosure via timing/error differences).
        """
        stmt = (
            select(self.model)
            .where(self.model.id == resource_id)  # type: ignore[attr-defined]
            .where(self._org_filter())
        )
        result = await self.session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise self._not_found(resource_id)
        return obj

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        extra_filters: list[Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        """Return a paginated list of records for this org.

        Returns ``(items, total)`` where *total* is the unfiltered count.
        """
        from sqlalchemy import func

        filters = [self._org_filter()]
        if extra_filters:
            filters.extend(extra_filters)

        count_stmt = select(func.count()).select_from(self.model).where(*filters)
        total: int = (await self.session.execute(count_stmt)).scalar_one()

        stmt = select(self.model).where(*filters).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def save(self, obj: ModelT) -> ModelT:
        """Persist a new or modified ORM object."""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, resource_id: UUID) -> None:
        """Hard-delete a record (use soft-delete at the service layer instead)."""
        obj = await self.get_by_id(resource_id)
        await self.session.delete(obj)
        await self.session.flush()
