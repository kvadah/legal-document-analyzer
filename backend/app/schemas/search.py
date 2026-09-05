"""Pydantic schemas for search and RAG Q&A endpoints (09-api-spec.md §4)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SearchMode = Literal["keyword", "semantic", "hybrid"]


class SearchFilters(BaseModel):
    document_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    document_ids: list[str] | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: SearchMode = "hybrid"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class ResultDocument(BaseModel):
    id: str
    filename: str
    document_type: str
    status: str
    page_count: int | None = None
    contract_score: float | None = None
    created_at: datetime


class SearchSnippet(BaseModel):
    chunk_id: str
    text: str
    page_number: int
    section_heading: str | None = None
    score: float
    source: Literal["keyword", "semantic", "both"]


class SearchResultGroup(BaseModel):
    document: ResultDocument
    snippets: list[SearchSnippet]


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    groups: list[SearchResultGroup]
    total_documents: int
    total_snippets: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


class AskCitation(BaseModel):
    index: int
    chunk_id: str
    page_number: int
    quote: str


class AskCitationsEvent(BaseModel):
    citations: list[AskCitation]


class AskDeltaEvent(BaseModel):
    text: str


class AskDoneEvent(BaseModel):
    conversation_id: str
    found_in_document: bool
    answer: str