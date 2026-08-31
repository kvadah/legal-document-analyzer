"""Pydantic schemas for organization models."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class OrgOut(BaseModel):
    """Public-facing organization representation."""

    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrgCreate(BaseModel):
    """Schema for creating an organization."""

    name: str
