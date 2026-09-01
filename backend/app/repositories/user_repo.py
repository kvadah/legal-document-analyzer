"""User repository with org-scoped access and an unscoped email lookup."""
from uuid import UUID

from sqlalchemy import select

from app.models.models import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    # ── Unscoped lookups (needed before org is known) ─────────────────────────

    async def get_by_email(self, email: str) -> User | None:
        """Find a user by email regardless of org (used at login)."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Writes ────────────────────────────────────────────────────────────────

    async def create_user(
        self,
        *,
        org_id: UUID,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.VIEWER,
    ) -> User:
        """Create and persist a new user."""
        user = User(
            organization_id=org_id,
            email=email.lower(),
            password_hash=hashed_password,
            role=role,
        )
        return await self.save(user)
