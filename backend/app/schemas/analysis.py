"""Pydantic schemas for analysis endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskStatusLiteral = Literal["flagged", "acknowledged", "dismissed"]


class ClauseOut(BaseModel):
    id: str
    clause_type: str
    extracted_text: str
    summary: str | None = None
    page_number: int
    paragraph_index: int | None = None
    confidence_score: float | None = None
    source_chunk_ids: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClauseListResponse(BaseModel):
    items: list[ClauseOut]
    not_found: list[str]
    total: int


class RiskOut(BaseModel):
    id: str
    risk_type: str
    severity: str
    description: str
    recommendation: str | None = None
    page_number: int | None = None
    confidence_score: float | None = None
    status: str
    clause_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RiskListResponse(BaseModel):
    items: list[RiskOut]
    total: int


class RiskUpdateRequest(BaseModel):
    status: RiskStatusLiteral


class EntityOut(BaseModel):
    id: str
    entity_type: str
    value: str
    raw_text: str
    page_number: int
    confidence_score: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EntityGroup(BaseModel):
    entity_type: str
    items: list[EntityOut]


class EntityListResponse(BaseModel):
    groups: list[EntityGroup]
    total: int


class ObligationOut(BaseModel):
    id: str
    obligated_party: str
    description: str
    deadline_date: datetime | None = None
    deadline_type: str
    status: str
    page_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ObligationListResponse(BaseModel):
    items: list[ObligationOut]
    total: int


class PartyOut(BaseModel):
    name: str
    role: str | None = None


class SummaryOut(BaseModel):
    document_id: str
    parties: list[PartyOut]
    purpose: str | None = None
    duration: str | None = None
    termination_conditions: str | None = None
    key_risks: str | None = None
    financial_terms: str | None = None
    governing_law: str | None = None
    effective_date: date | None = None
    expiration_date: date | None = None
    contract_value: float | None = None
    contract_currency: str | None = None


class RiskDeduction(BaseModel):
    risk_id: str
    risk_type: str
    severity: str
    deduction: int


class ScoreOut(BaseModel):
    document_id: str
    contract_score: float | None = Field(default=None, ge=0, le=100)
    ai_confidence_score: float | None = Field(default=None, ge=0, le=1)
    scores_version: int
    breakdown: list[RiskDeduction]
    total_deduction: int
