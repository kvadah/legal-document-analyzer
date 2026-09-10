"""Pydantic schemas for document comparison (09-api-spec.md §5)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ComparisonStatus = Literal["pending", "processing", "completed", "error"]
ClauseChangeStatus = Literal["added", "removed", "modified", "unchanged"]
ParagraphChangeStatus = Literal["added", "removed", "modified"]
DiffOp = Literal["equal", "replace", "insert", "delete"]


class CompareRequest(BaseModel):
    document_id_a: UUID
    document_id_b: UUID


class ComparisonCreatedResponse(BaseModel):
    """202 response: comparison queued as an async job."""

    comparison_id: str
    status: ComparisonStatus


class WordDiffOp(BaseModel):
    """One word-level diff segment between two texts.

    ``equal`` carries both texts, ``replace`` carries both, ``delete`` only
    ``text_a``, ``insert`` only ``text_b``.
    """

    op: DiffOp
    text_a: str | None = None
    text_b: str | None = None


class ClauseDiffEntry(BaseModel):
    """Aligned clause pair classification (07-feature-spec-comparison-search.md §1)."""

    clause_type: str
    status: ClauseChangeStatus
    text_a: str | None = None
    text_b: str | None = None
    word_diff: list[WordDiffOp] | None = None
    page_a: int | None = None
    page_b: int | None = None
    summary_a: str | None = None
    summary_b: str | None = None
    confidence_a: float | None = None
    confidence_b: float | None = None


class ParagraphDiffEntry(BaseModel):
    """Non-clause ("Other Changes") paragraph-level diff entry."""

    status: ParagraphChangeStatus
    text_a: str | None = None
    text_b: str | None = None
    word_diff: list[WordDiffOp] | None = None
    page_a: int | None = None
    page_b: int | None = None


class ComparisonCounts(BaseModel):
    added: int
    removed: int
    modified: int
    unchanged: int
    other_changes: int


class ComparisonDocumentOut(BaseModel):
    id: str
    filename: str
    document_type: str


class ComparisonOut(BaseModel):
    id: str
    document_id_a: str
    document_id_b: str
    document_a: ComparisonDocumentOut
    document_b: ComparisonDocumentOut
    status: ComparisonStatus
    error: str | None = None
    clauses: list[ClauseDiffEntry] = Field(default_factory=list)
    other_changes: list[ParagraphDiffEntry] = Field(default_factory=list)
    counts: ComparisonCounts | None = None
    created_at: datetime
    updated_at: datetime
