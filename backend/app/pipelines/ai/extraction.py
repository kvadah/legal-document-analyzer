"""Pydantic schemas for structured LLM outputs in the AI pipeline.

These are the tool-call schemas sent to the LLM provider. Every field that
can be un-groundable is nullable so the model can return "not found" instead
of fabricating (spec 05-ai-pipeline.md §3).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RiskSeverityLiteral = Literal["low", "medium", "high", "critical"]
DeadlineTypeLiteral = Literal[
    "effective_date",
    "payment_date",
    "renewal_date",
    "notice_period",
    "expiration_date",
    "other",
]
EntityTypeLiteral = Literal[
    "company",
    "person",
    "money",
    "date",
    "address",
    "law_reference",
]


class PartyInfo(BaseModel):
    name: str
    role: str | None = None


class MetadataExtraction(BaseModel):
    parties: list[PartyInfo] = Field(default_factory=list)
    governing_law: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    contract_value: float | None = None
    contract_currency: str | None = None


class ClauseInstance(BaseModel):
    chunk_id: str
    extracted_text: str = Field(min_length=1)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class ClauseDetectionResult(BaseModel):
    found: bool
    instances: list[ClauseInstance] = Field(default_factory=list)


class EntityInstance(BaseModel):
    entity_type: EntityTypeLiteral
    value: str
    raw_text: str
    chunk_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class EntityListResult(BaseModel):
    entities: list[EntityInstance] = Field(default_factory=list)


class ObligationInstance(BaseModel):
    obligated_party: str
    description: str
    deadline_date: str | None = None
    deadline_type: DeadlineTypeLiteral
    chunk_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class ObligationListResult(BaseModel):
    obligations: list[ObligationInstance] = Field(default_factory=list)


class RiskJudgmentResult(BaseModel):
    flagged: bool
    severity: RiskSeverityLiteral = "medium"
    description: str = ""
    recommendation: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("severity")
    @classmethod
    def _require_severity(cls, v: str) -> str:
        if v not in ("low", "medium", "high", "critical"):
            return "medium"
        return v


class SummaryExtraction(BaseModel):
    purpose: str | None = None
    duration: str | None = None
    termination_summary: str | None = None
    key_risks_summary: str | None = None
    financial_terms_summary: str | None = None
