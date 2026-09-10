"""Pydantic schemas for authentication endpoints."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""

    org_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Request body for POST /auth/refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body for POST /auth/logout."""

    refresh_token: str


class InviteRequest(BaseModel):
    """Request body for POST /auth/invite (admin only)."""

    email: EmailStr
    role: str = Field(..., pattern="^(reviewer|viewer)$")


class AcceptInviteRequest(BaseModel):
    """Request body for POST /auth/accept-invite."""

    token: str
    password: str = Field(..., min_length=8, max_length=128)


class AuthUserOut(BaseModel):
    """Minimal user info returned alongside tokens."""

    id: str
    email: str
    role: str
    org_id: str
    org_name: str


class AuthResponse(BaseModel):
    """Full auth response returned on login/register."""

    access_token: str
    token_type: str = "bearer"
    user: AuthUserOut


class UserOut(BaseModel):
    """Org member as shown in the admin users list."""

    id: str
    email: str
    role: str
    is_active: bool
    full_name: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int


class UserUpdateRequest(BaseModel):
    """Request body for PATCH /auth/users/{user_id} (admin only)."""

    role: Literal["admin", "reviewer", "viewer"] | None = None
    is_active: bool | None = None
