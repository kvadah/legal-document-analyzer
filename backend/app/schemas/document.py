"""Pydantic schemas for document endpoints."""
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    """Document metadata returned by list/get endpoints."""

    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    document_type: str
    status: str
    status_detail: str | None = None
    page_count: int | None = None
    language: str | None = None
    file_hash: str | None = None
    possible_duplicate_of: str | None = None
    contract_score: float | None = None
    ai_confidence_score: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class UploadDocumentResult(BaseModel):
    document_id: str
    filename: str
    status: str
    possible_duplicate_of: str | None = None


class UploadResponse(BaseModel):
    documents: list[UploadDocumentResult]


class DocumentStatusEvent(BaseModel):
    document_id: str
    status: str
    status_detail: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PageBlock(BaseModel):
    """One contiguous text block on a page (derived from a stored chunk)."""

    chunk_index: int
    text: str
    section_heading: str | None = None


class DocumentPage(BaseModel):
    page_number: int
    blocks: list[PageBlock]


class DocumentTextResponse(BaseModel):
    """Extracted/OCR'd text with page position metadata (09-api-spec.md §2)."""

    document_id: str
    page_count: int
    pages: list[DocumentPage]
