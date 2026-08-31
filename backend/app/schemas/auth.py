"""Pydantic schemas for authentication endpoints."""
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
