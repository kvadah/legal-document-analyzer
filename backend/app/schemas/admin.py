"""Pydantic schemas for the admin API (09-api-spec.md §9)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Usage dashboard ───────────────────────────────────────────────────────────


class UsageDocumentStats(BaseModel):
    total: int
    analyzed: int
    processing: int
    errored: int
    deleted: int


class UsageLLMStageStats(BaseModel):
    stage: str
    calls: int
    input_tokens: int
    output_tokens: int


class UsageLLMStats(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    by_stage: list[UsageLLMStageStats]


class UsageUserStats(BaseModel):
    total: int
    active: int


class UsageResponse(BaseModel):
    """GET /admin/usage payload (09-api-spec.md §9)."""

    documents: UsageDocumentStats
    storage_bytes: int
    llm: UsageLLMStats
    users: UsageUserStats


# ── Org settings ──────────────────────────────────────────────────────────────


class OrgSettingsOut(BaseModel):
    """GET /admin/org payload."""

    id: str
    name: str
    plan: str
    retention_days: int
    audit_retention_days: int
    llm_provider: str | None
    scheduled_deletion_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrgSettingsUpdateRequest(BaseModel):
    """Request body for PATCH /admin/org."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    audit_retention_days: int | None = Field(default=None, ge=30, le=3650)
    llm_provider: Literal["anthropic", "openai", "gemini", "mock"] | None = None


class OrgDeletionRequest(BaseModel):
    """Request body for POST /admin/org/deletion — explicit confirmation required."""

    confirm: bool


# ── Audit logs ────────────────────────────────────────────────────────────────


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None = None
    user_email: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    details: dict | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    limit: int
    offset: int
