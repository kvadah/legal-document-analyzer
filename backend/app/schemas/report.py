"""Pydantic schemas for portfolio reports (09-api-spec.md §8)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReportStatus = Literal["pending", "processing", "completed", "error"]
ReportType = Literal["portfolio_risk", "obligation_calendar"]
ReportExportFormat = Literal["json", "xlsx", "pdf", "docx"]

REPORT_TYPES: list[str] = ["portfolio_risk", "obligation_calendar"]
EXPORT_FORMATS: list[str] = ["json", "xlsx", "pdf", "docx"]


class ReportCreateRequest(BaseModel):
    report_type: ReportType
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Scope the report to specific documents. Omit for the whole portfolio.",
    )
    export_format: ReportExportFormat = "json"


class ReportCreatedResponse(BaseModel):
    """202 response: report queued as an async job."""

    report_id: str
    status: ReportStatus


class ReportOut(BaseModel):
    report_id: str
    report_type: ReportType
    status: ReportStatus
    export_format: ReportExportFormat
    document_ids: list[str] | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    generated_by: str | None = None


class ReportListResponse(BaseModel):
    reports: list[ReportOut]
    total: int
