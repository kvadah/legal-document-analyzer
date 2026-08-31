"""Pydantic schemas for user models."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    """Public-facing user representation."""

    id: uuid.UUID
    email: str
    role: str
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """Schema for creating a user."""

    email: EmailStr
    password: str
    role: str = "viewer"
    organization_id: uuid.UUID


class UserUpdate(BaseModel):
    """Schema for updating a user (admin only)."""

    role: str | None = None
    is_active: bool | None = None
