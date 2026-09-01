"""Auth endpoints — POST /api/v1/auth/*"""
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db.session import get_session
from app.schemas.auth import (
    AcceptInviteRequest,
    AuthResponse,
    InviteRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_KWARGS = dict(
    httponly=True,
    samesite="lax",
    secure=False,   # set to True in production (HTTPS only)
    max_age=7 * 24 * 60 * 60,
    path="/api/v1/auth",
)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(_REFRESH_COOKIE, token, **_COOKIE_KWARGS)


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(_REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Create a new organisation and its first admin user."""
    access_token, refresh_token, auth_resp = await auth_service.register(
        session,
        org_name=body.org_name,
        email=body.email,
        password=body.password,
    )
    _set_refresh_cookie(response, refresh_token)
    return auth_resp


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Authenticate with email/password and receive tokens."""
    access_token, refresh_token, auth_resp = await auth_service.login(
        session,
        email=body.email,
        password=body.password,
    )
    _set_refresh_cookie(response, refresh_token)
    return auth_resp


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    # Accept refresh token from cookie (preferred) or body (fallback)
    cookie_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
    body: RefreshRequest | None = None,
) -> AuthResponse:
    """Rotate the refresh token and return a new access token."""
    token = cookie_token or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Refresh token is required"},
        )
    new_access, new_refresh, user_id = await auth_service.refresh_tokens(session, refresh_token=token)
    _set_refresh_cookie(response, new_refresh)

    # Build a minimal AuthResponse (full user info would require another DB lookup;
    # the frontend should use the access token claims for user info)
    import jwt as _jwt

    from app.core.config import settings as _s
    from app.schemas.auth import AuthUserOut
    claims = _jwt.decode(new_access, _s.jwt_secret_key, algorithms=[_s.jwt_algorithm])
    return AuthResponse(
        access_token=new_access,
        user=AuthUserOut(
            id=claims["sub"],
            email="",           # not stored in JWT — client should re-fetch /me if needed
            role=claims["role"],
            org_id=claims["org_id"],
            org_name="",        # same; client already has this from initial login
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    cookie_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
    body: LogoutRequest | None = None,
) -> None:
    """Invalidate the refresh token and clear the cookie."""
    token = cookie_token or (body.refresh_token if body else None)
    if token:
        await auth_service.logout(refresh_token=token)
    _clear_refresh_cookie(response)


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite(
    body: InviteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[CurrentUser, Depends(require_role("admin"))],
) -> dict:
    """Admin: invite a user to join the current org by email."""
    token = await auth_service.invite_user(
        session,
        admin_user_id=current_user.id,
        admin_org_id=current_user.org_id,
        email=body.email,
        role=body.role,
    )
    return {"message": f"Invite sent to {body.email}", "token": token}


@router.post("/accept-invite", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def accept_invite(
    body: AcceptInviteRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Accept an org invite and create a new account."""
    access_token, refresh_token, auth_resp = await auth_service.accept_invite(
        session,
        token=body.token,
        password=body.password,
    )
    _set_refresh_cookie(response, refresh_token)
    return auth_resp
