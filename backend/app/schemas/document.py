"""Pydantic schemas for document endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    """Document metadata returned by list/get endpoints."""

    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    document_type: str
    status: str
    status_detail: Optional[str] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    file_hash: Optional[str] = None
    possible_duplicate_of: Optional[str] = None
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
    possible_duplicate_of: Optional[str] = None


class UploadResponse(BaseModel):
    documents: list[UploadDocumentResult]


class DocumentStatusEvent(BaseModel):
    document_id: str
    status: str
    status_detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
