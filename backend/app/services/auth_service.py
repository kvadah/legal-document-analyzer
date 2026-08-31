"""Auth service: registration, login, token lifecycle, invitations."""
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_invite_token,
    generate_refresh_token,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.redis import (
    check_login_rate_limit,
    clear_login_failures,
    delete_invite_token,
    delete_refresh_token,
    get_invite_token,
    increment_login_failures,
    store_invite_token,
    store_refresh_token,
    validate_refresh_token,
)
from app.models.models import User, UserRole
from app.repositories.org_repo import OrgRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import AuthResponse, AuthUserOut


def _build_auth_response(user: User, org_name: str) -> tuple[str, str, AuthResponse]:
    """Issue tokens and build the auth response. Returns (access_token, refresh_token, response)."""
    access_token = create_access_token(
        user_id=str(user.id),
        org_id=str(user.organization_id),
        role=user.role.value,
    )
    refresh_token = generate_refresh_token()
    response = AuthResponse(
        access_token=access_token,
        user=AuthUserOut(
            id=str(user.id),
            email=user.email,
            role=user.role.value,
            org_id=str(user.organization_id),
            org_name=org_name,
        ),
    )
    return access_token, refresh_token, response


async def register(
    session: AsyncSession,
    *,
    org_name: str,
    email: str,
    password: str,
) -> tuple[str, str, AuthResponse]:
    """Create a new org and first admin user atomically.

    Returns ``(access_token, refresh_token, AuthResponse)``.
    Raises HTTP 409 if the email is already registered.
    """
    org_repo = OrgRepository(session)
    # Temp user repo (org id not known yet – use a dummy for the email lookup)
    temp_user_repo = UserRepository(session, organization_id=uuid.UUID(int=0))

    existing = await temp_user_repo.get_by_email(email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "message": "Email already registered"},
        )

    org = await org_repo.create_org(name=org_name)
    user_repo = UserRepository(session, organization_id=org.id)
    user = await user_repo.create_user(
        org_id=org.id,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
    )
    await session.commit()

    access_token, refresh_token, resp = _build_auth_response(user, org.name)
    await store_refresh_token(refresh_token, str(user.id))
    return access_token, refresh_token, resp


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> tuple[str, str, AuthResponse]:
    """Verify credentials and issue tokens.

    Returns ``(access_token, refresh_token, AuthResponse)``.
    Raises HTTP 401 on bad credentials, 429 on rate-limit exceeded.
    """
    if await check_login_rate_limit(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Too many failed login attempts. Try again in 15 minutes."},
            headers={"Retry-After": "900"},
        )

    # Unscoped lookup – we need to find the user before we know their org
    temp_repo = UserRepository(session, organization_id=uuid.UUID(int=0))
    user = await temp_repo.get_by_email(email)

    if user is None or not verify_password(password, user.password_hash):
        await increment_login_failures(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Account is deactivated"},
        )

    await clear_login_failures(email)

    # Fetch org name
    org_repo = OrgRepository(session)
    org = await org_repo.get_by_id(user.organization_id)
    org_name = org.name if org else "Unknown"

    access_token, refresh_token, resp = _build_auth_response(user, org_name)
    await store_refresh_token(refresh_token, str(user.id))
    return access_token, refresh_token, resp


async def refresh_tokens(
    session: AsyncSession,
    *,
    refresh_token: str,
) -> tuple[str, str, str]:
    """Rotate refresh token and issue new access token.

    Returns ``(new_access_token, new_refresh_token, user_id)``.
    Raises HTTP 401 if the token is invalid or expired.
    """
    user_id = await validate_refresh_token(refresh_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid or expired refresh token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    from sqlalchemy import select
    from app.models.models import User as UserModel
    stmt = select(UserModel).where(UserModel.id == uuid.UUID(user_id))
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        await delete_refresh_token(refresh_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "User not found or deactivated"},
        )

    # Token rotation: delete old, issue new
    await delete_refresh_token(refresh_token)
    new_access = create_access_token(
        user_id=str(user.id),
        org_id=str(user.organization_id),
        role=user.role.value,
    )
    new_refresh = generate_refresh_token()
    await store_refresh_token(new_refresh, str(user.id))
    return new_access, new_refresh, str(user.id)


async def logout(*, refresh_token: str) -> None:
    """Invalidate a refresh token."""
    await delete_refresh_token(refresh_token)


async def invite_user(
    session: AsyncSession,
    *,
    admin_user_id: str,
    admin_org_id: str,
    email: str,
    role: str,
) -> str:
    """Store an invite token for a new user and return it.

    In production this would also send an email; for now it just returns the token
    so it can be surfaced via the API response (dev/testing convenience).
    """
    token = generate_invite_token()
    payload: dict[str, Any] = {
        "email": email.lower(),
        "role": role,
        "org_id": admin_org_id,
        "invited_by": admin_user_id,
    }
    await store_invite_token(token, payload)
    return token


async def accept_invite(
    session: AsyncSession,
    *,
    token: str,
    password: str,
) -> tuple[str, str, AuthResponse]:
    """Create a user from a valid invite token and return auth tokens.

    Raises HTTP 400 if the token is invalid/expired.
    """
    payload = await get_invite_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "validation_error", "message": "Invalid or expired invite token"},
        )

    org_id = uuid.UUID(payload["org_id"])
    role_str = payload["role"]
    email = payload["email"]

    # Check for duplicate
    temp_repo = UserRepository(session, organization_id=uuid.UUID(int=0))
    existing = await temp_repo.get_by_email(email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "conflict", "message": "Email already registered"},
        )

    user_repo = UserRepository(session, organization_id=org_id)
    user = await user_repo.create_user(
        org_id=org_id,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole(role_str),
    )
    await session.commit()
    await delete_invite_token(token)

    org_repo = OrgRepository(session)
    org = await org_repo.get_by_id(org_id)
    org_name = org.name if org else "Unknown"

    access_token, refresh_token, resp = _build_auth_response(user, org_name)
    await store_refresh_token(refresh_token, str(user.id))
    return access_token, refresh_token, resp
